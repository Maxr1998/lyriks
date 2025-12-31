from dataclasses import dataclass, field
from json import JSONDecodeError

from httpx import Client as HttpClient
from httpx import RequestError
from stamina import retry

from lyriks.lyrics import Lyrics
from .song import Song

VIBE_LYRICS_API_URL = 'https://apis.naver.com/vibeWeb/musicapiweb/vibe/v4/lyric/{song_id:d}'
VIBE_ALBUM_TRACKS_API_URL = 'https://apis.naver.com/vibeWeb/musicapiweb/album/{album_id:d}/tracks?start=1&display=1000'
VIBE_TRACK_API_URL = 'https://apis.naver.com/vibeWeb/musicapiweb/track/{song_id:d}'


@dataclass
class VibeSong(Song):
    artists: list[str] = field(default_factory=list)

    @classmethod
    def from_track_info(cls, track_info: dict) -> 'VibeSong':
        try:
            track_id = track_info['trackId']
            album_index = track_info['trackNumber']
            title = track_info['trackTitle']
            artists = [artist['artistName'] for artist in track_info['artists']]
        except KeyError:
            raise ValueError('Invalid track info data')

        return cls(id=track_id, album_index=album_index, title=title, artists=artists)


@retry(on=RequestError, attempts=3)
def get_album_songs(http_client: HttpClient, album_id: int) -> list[VibeSong]:
    try:
        response = http_client.get(
            VIBE_ALBUM_TRACKS_API_URL.format(album_id=album_id),
            headers={'Accept': 'application/json'},
        ).json()
    except JSONDecodeError:
        return []

    try:
        tracks = response['response']['result']['tracks']
    except KeyError:
        return []

    try:
        return [VibeSong.from_track_info(track_info) for track_info in tracks]
    except ValueError:
        return []


@retry(on=RequestError, attempts=3)
def get_song_info(http_client: HttpClient, song_id: int) -> VibeSong | None:
    try:
        response = http_client.get(
            VIBE_TRACK_API_URL.format(song_id=song_id),
            headers={'Accept': 'application/json'},
        ).json()
    except JSONDecodeError:
        return None

    try:
        track_info = response['response']['result']['track']
    except KeyError:
        return None

    try:
        return VibeSong.from_track_info(track_info)
    except ValueError:
        return None


@retry(on=RequestError, attempts=3)
def get_song_lyrics(http_client: HttpClient, song: VibeSong) -> Lyrics | None:
    try:
        lyrics_response = http_client.get(
            VIBE_LYRICS_API_URL.format(song_id=song.id),
            headers={'Accept': 'application/json'},
        ).json()
    except JSONDecodeError:
        return None

    try:
        lyrics_data = lyrics_response['response']['result']['lyric']
    except KeyError:
        return None

    if lyrics_data.get('hasSyncLyric'):
        try:
            sync_lyrics = lyrics_data['syncLyric']
            start_times = sync_lyrics['startTimeIndex']
            lines = sync_lyrics['contents'][0]['text']
        except IndexError | KeyError:
            return None

        try:
            joined_lyrics = list(zip(start_times, lines, strict=True))
        except ValueError:
            return None

        # Convert timestamps and cleanup lines
        lyrics_dict: dict[int, str] = {int(timestamp * 1000): line.strip() for timestamp, line in joined_lyrics}

        return Lyrics.from_dict(song.id, song.title, lyrics_dict)
    elif lyrics_data.get('hasNormalLyric'):
        try:
            lines = lyrics_data['normalLyric']['text'].split('\n')
        except KeyError:
            return None

        return Lyrics(song_id=song.id, song_title=song.title, lines=lines, is_synced=False)

    return None
