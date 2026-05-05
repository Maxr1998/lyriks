import time
from dataclasses import dataclass, field
from json import JSONDecodeError

from httpx import AsyncClient as HttpClient
from httpx import RequestError
from stamina import retry

from lyriks.lyrics import Lyrics
from lyriks.providers.api.song import Song

BUGS_API_URL = "https://mapi.bugs.co.kr/music/5/multi/invoke/map"
BUGS_ACCESS_TOKEN_URL = "https://secure.bugs.co.kr/api/5/appToken"
BUGS_APP_CLIENT_SECRET = "d33b!z7xeu"


@dataclass
class BugsApiAccessToken:
    """
    Access token for the Bugs API, including its expiration time.
    """

    access_token: str
    expires_at: int  # Unix timestamp in seconds


@dataclass
class BugsSong(Song):
    artists: list[str] = field(default_factory=list)
    lyrics: Lyrics | None = None

    @classmethod
    def from_track_info(cls, track: dict) -> 'BugsSong':
        try:
            track_id = track['track_id']
            album_index = track['track_no']
            title = track['track_title']
            artists = [artist['artist_nm'] for artist in track['artists']]
            lyrics = _parse_lyrics(track.get('lyrics') or {}, track_id, title)  # type: ignore[arg-type]
        except KeyError:
            raise ValueError('Invalid track info data')

        return cls(id=track_id, album_index=album_index, title=title, artists=artists, lyrics=lyrics)


_cached_token: BugsApiAccessToken | None = None


async def get_api_token(http_client: HttpClient) -> BugsApiAccessToken:
    try:
        response = (
            await http_client.post(
                BUGS_ACCESS_TOKEN_URL,
                params={
                    'client_id': 'bugsapp_credentials_android',
                    'client_secret': BUGS_APP_CLIENT_SECRET,
                    'grant_type': 'client_credentials',
                },
            )
        ).json()
    except JSONDecodeError:
        raise RuntimeError('Failed to fetch access token')

    try:
        result = response['result']
        access_token = result['access_token']
        expires_in = result['expires_in']
    except KeyError:
        raise RuntimeError('Failed to fetch access token')

    return BugsApiAccessToken(
        access_token=access_token,
        expires_at=int(time.time()) + expires_in,
    )


async def _get_cached_token(http_client: HttpClient) -> str:
    global _cached_token
    if _cached_token is None or _cached_token.expires_at <= int(time.time()):
        _cached_token = await get_api_token(http_client)
    return _cached_token.access_token


@retry(on=RequestError, attempts=3)
async def _bugs_request(http_client: HttpClient, requests: list[dict]) -> list[dict]:
    token = await _get_cached_token(http_client)

    try:
        response = (
            await http_client.post(
                BUGS_API_URL,
                headers={
                    'Content-Type': 'application/json; charset=UTF-8',
                    'Authorization': f'Bearer {token}',
                },
                json=requests,
            )
        ).json()
    except JSONDecodeError:
        return []

    return response.get('list', [])


async def get_album_songs(http_client: HttpClient, album_id: int) -> list[BugsSong]:
    response = await _bugs_request(
        http_client,
        [{'id': 'album_track', 'args': {'album_id': album_id, 'result_type': 'LIST'}}],
    )

    if not response:
        return []

    try:
        tracks = response[0]['album_track']['list']
    except (IndexError, KeyError):
        return []

    try:
        return [BugsSong.from_track_info(track) for track in tracks]
    except ValueError:
        return []


async def get_song_info(http_client: HttpClient, song_id: int) -> BugsSong | None:
    response = await _bugs_request(
        http_client,
        [{'id': 'track', 'args': {'track_id': song_id, 'result_type': 'DETAIL'}}],
    )

    if not response:
        return None

    try:
        track_info = response[0]['track']['result']
    except (IndexError, KeyError):
        return None

    return BugsSong.from_track_info(track_info)


async def get_song_lyrics(http_client: HttpClient, song: BugsSong) -> Lyrics | None:
    # Return cached lyrics if available
    if song.lyrics:
        return song.lyrics

    # Fetch lyrics independently
    response = await _bugs_request(
        http_client,
        [{'id': 'track_lyrics', 'args': {'track_id': song.id}}],
    )

    if not response:
        return None

    try:
        lyrics_data = response[0]['track_lyrics']['result']
    except (IndexError, KeyError):
        return None

    if not lyrics_data:
        return None

    return _parse_lyrics(lyrics_data, song.id, song.title)


def _parse_lyrics(lyrics_data: dict[str, str], song_id: int, song_title: str) -> Lyrics | None:
    if timed := lyrics_data.get('time'):
        if lyrics := _parse_synced_lyrics(timed, song_id, song_title):
            return lyrics
    if normal := lyrics_data.get('normal'):
        return _parse_normal_lyrics(normal, song_id, song_title)
    return None


def _parse_synced_lyrics(raw: str, song_id: int, song_title: str) -> Lyrics | None:
    try:
        lyrics_dict = {}
        for raw_line in raw.split('＃'):
            timestamp_str, line = raw_line.split('|', 1)
            timestamp = int(float(timestamp_str) * 1000)
            lyrics_dict[timestamp] = line
    except ValueError:
        return None
    return Lyrics.from_dict(song_id, song_title, lyrics_dict)


def _parse_normal_lyrics(raw: str, song_id: int, song_title: str) -> Lyrics:
    lines = [f'{line}\n' for line in raw.splitlines()]
    return Lyrics(song_id=song_id, song_title=song_title, lines=lines, is_synced=False)
