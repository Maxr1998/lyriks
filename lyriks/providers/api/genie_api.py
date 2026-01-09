import json
from dataclasses import dataclass
from json.decoder import JSONDecodeError
from urllib.parse import unquote

from httpx import AsyncClient as HttpClient
from httpx import RequestError
from stamina import retry

from lyriks.lyrics import Lyrics
from .song import Song

GENIE_ALBUM_API_URL = 'https://app.genie.co.kr/song/j_AlbumSongList.json?axnm={album_id:d}'
GENIE_LYRICS_API_URL = 'https://dn.genie.co.kr/app/purchase/get_msl.asp?songid={song_id:d}&callback=GenieCallback'
GENIE_STREAM_INFO_API_URL = 'https://stm.genie.co.kr/player/j_StmInfo.json?xgnm={song_id:d}'

CURL_USER_AGENT = 'curl/8.7.1'  # for whatever reason, this works, but the python-requests UA doesn't


@dataclass
class GenieSong(Song):
    pass


@retry(on=RequestError, attempts=3)
async def get_album_songs(http_client: HttpClient, album_id: int) -> list[GenieSong] | None:
    try:
        response = (
            await http_client.get(
                GENIE_ALBUM_API_URL.format(album_id=album_id),
                headers={'User-Agent': CURL_USER_AGENT},
            )
        ).json()
    except JSONDecodeError:
        return None

    try:
        songs = list(response['DATA1']['DATA'])
    except KeyError:
        return None

    # Reject albums with multiple CDs
    if any(song.get('ALBUM_CD_NO') != '1' for song in songs):
        return None

    # Extract songs
    result = []

    for song in songs:
        song_id = song.get('SONG_ID')
        track_num = song.get('ALBUM_TRACK_NO')
        song_name = song.get('SONG_NAME')

        if song_id is None or track_num is None or song_name is None:
            return None

        try:
            song_id = int(song_id)
            track_num = int(track_num)
        except ValueError:
            return None

        result.append(GenieSong(id=song_id, album_index=track_num, title=unquote(song_name)))

    result = sorted(result, key=lambda x: x.album_index)

    return result


@retry(on=RequestError, attempts=3)
async def get_stream_info(http_client: HttpClient, song_id: int) -> dict | None:
    try:
        response = (
            await http_client.get(
                GENIE_STREAM_INFO_API_URL.format(song_id=song_id),
                headers={'User-Agent': CURL_USER_AGENT},
            )
        ).json()
    except JSONDecodeError:
        return None

    try:
        stream_info = response['DataSet']['DATA'][0]
    except KeyError:
        return None

    return stream_info


async def get_song_info(http_client: HttpClient, song_id: int) -> GenieSong | None:
    stream_info = await get_stream_info(http_client, song_id)
    if stream_info is None:
        return None

    try:
        album_id = int(stream_info['ALBUM_ID'])
    except (KeyError, ValueError):
        return None

    genie_songs = await get_album_songs(http_client, album_id)
    if not genie_songs:
        return None

    return next((s for s in genie_songs if s.id == song_id), None)


@retry(on=RequestError, attempts=3)
async def get_song_lyrics(http_client: HttpClient, song: GenieSong) -> Lyrics | None:
    # Try to fetch synced lyrics
    try:
        response = (
            await http_client.get(
                GENIE_LYRICS_API_URL.format(song_id=song.id),
                headers={'User-Agent': CURL_USER_AGENT},
            )
        ).text
    except RequestError:
        return None

    if response is not None and response.startswith('GenieCallback('):
        # We (probably) got synced lyrics
        response = response.removeprefix('GenieCallback(').removesuffix(');')
        try:
            raw_lyrics = json.loads(response)
        except JSONDecodeError:
            return None

        # Convert timestamps and cleanup lines
        lyrics_dict: dict[int, str] = {int(timestamp): line.strip() for timestamp, line in raw_lyrics.items()}

        return Lyrics.from_dict(song.id, song.title, lyrics_dict)
    else:
        # Fall back to static lyrics from stream info
        stream_info = await get_stream_info(http_client, song.id)
        if not stream_info:
            return None

        try:
            raw_lyrics = stream_info['LYRICS']
        except KeyError:
            return None

        # Reject empty lyrics
        if not raw_lyrics:
            return None

        lines = unquote(raw_lyrics).split('<br>')

        # Reject instrumental tracks
        if '이 곡은 연주곡 입니다.' in lines:
            return None

        return Lyrics(song_id=song.id, song_title=song.title, lines=lines, is_synced=False)
