from json import JSONDecodeError

import requests

from lyriks import Provider
from lyriks.lyrics import Lyrics
from lyriks.mb_client import Release, Artist

VIBE_LYRICS_API_URL = 'https://apis.naver.com/vibeWeb/musicapiweb/vibe/v4/lyric/{song_id:d}'
VIBE_ALBUM_TRACKS_API_URL = 'https://apis.naver.com/vibeWeb/musicapiweb/album/{album_id:d}/tracks?start=1&display=1000'


class Vibe(Provider):
    def fetch_lyrics(self, track_release: Release, recording_mbid: str) -> Lyrics | None:

        pass

    def fetch_single_song(self, song_id):
        try:
            lyrics_response = requests.get(
                VIBE_LYRICS_API_URL.format(song_id=song_id),
                headers={'Accept': 'application/json'},
            ).json()
        except JSONDecodeError:
            return None

        lyrics_data = lyrics_response['response']['result']['lyric']

        if lyrics_data['hasSyncLyric']:
            sync_lyrics = lyrics_data['syncLyric']
            start_times = sync_lyrics['startTimeIndex']
            lines = sync_lyrics['contents'][0]['text']

            try:
                joined_lyrics = list(zip(start_times, lines, strict=True))
            except ValueError:
                return None

            # Convert timestamps and cleanup lines
            lyrics_dict: dict[int, str] = {int(timestamp * 1000): line.strip() for timestamp, line in joined_lyrics}

            return Lyrics.synced(song_id, 'TODO', lyrics_dict)
        elif lyrics_data['hasNormalLyric']:
            lines = lyrics_data['normalLyric']['text'].split('\n')

            return Lyrics.static(song_id, 'TODO', lines)

        return None

    def has_artist_url(self, artist: Artist) -> bool:
        return False

    @staticmethod
    def fetch_album_song_ids(album_id):
        try:
            response_json = requests.get(
                VIBE_ALBUM_TRACKS_API_URL.format(album_id=album_id),
                headers={'Accept': 'application/json'},
            ).json()
        except JSONDecodeError:
            return None

        tracks = response_json['response']['result']['tracks']

        print(list(map(lambda x: x['trackId'], tracks)))
