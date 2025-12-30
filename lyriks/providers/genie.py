import json
from dataclasses import dataclass
from json.decoder import JSONDecodeError
from urllib.parse import unquote

import httpx

from lyriks.lyrics import Lyrics
from lyriks.mb_client import Release, Artist
from lyriks.providers import Provider, Song
from lyriks.providers.util import pick_release_from_release_group

GENIE_ALBUM_API_URL = 'https://app.genie.co.kr/song/j_AlbumSongList.json?axnm={album_id:d}'
GENIE_LYRICS_API_URL = 'https://dn.genie.co.kr/app/purchase/get_msl.asp?songid={song_id:d}&callback=GenieCallback'
GENIE_STREAM_INFO_API_URL = 'https://stm.genie.co.kr/player/j_StmInfo.json?xgnm={song_id:d}'

CURL_USER_AGENT = 'curl/8.7.1'  # for whatever reason, this works, but the python-requests UA doesn't


@dataclass
class GenieSong(Song):
    pass


class Genie(Provider):
    """
    Provider for Genie Music.
    """

    def fetch_recording_lyrics(self, track_release: Release, recording_mbid: str) -> Lyrics | None:
        # Resolve Genie album
        genie_songs = self.get_genie_songs(track_release)
        if not genie_songs:
            return None

        # Get Genie song for recording
        genie_song = genie_songs.get(recording_mbid)
        if not genie_song:
            return None

        # Fetch lyrics
        return self.fetch_provider_song_lyrics(genie_song)

    def fetch_song_by_id(self, song_id: int) -> Song | None:
        stream_info = self.fetch_genie_stream_info(song_id)
        if stream_info is None:
            return None

        try:
            album_id = int(stream_info['DataSet']['DATA'][0]['ALBUM_ID'])
        except KeyError:
            return None

        genie_songs = self.fetch_genie_album_songs(album_id)
        if not genie_songs:
            return None

        return next((s for s in genie_songs if s.id == song_id), None)

    def fetch_provider_song_lyrics(self, song: GenieSong) -> Lyrics | None:
        # Fetch stream info with general song info and static lyrics
        song_id = song.id
        stream_info = self.fetch_genie_stream_info(song_id)
        if not stream_info:
            return None

        # Try to fetch synced lyrics
        lyrics_response = httpx.get(
            GENIE_LYRICS_API_URL.format(song_id=song_id),
            headers={'User-Agent': CURL_USER_AGENT},
        ).text

        if lyrics_response.startswith('GenieCallback('):
            # We (probably) got synced lyrics
            lyrics_response = lyrics_response.removeprefix('GenieCallback(').removesuffix(');')
            try:
                raw_lyrics = json.loads(lyrics_response)
            except JSONDecodeError:
                return None

            # Convert timestamps and cleanup lines
            lyrics_dict: dict[int, str] = {int(timestamp): line.strip() for timestamp, line in raw_lyrics.items()}

            return Lyrics.from_dict(song_id, song.title, lyrics_dict)
        else:
            # Fall back to static lyrics
            try:
                raw_lyrics = stream_info['DataSet']['DATA'][0]['LYRICS']
            except KeyError:
                return None

            # Reject empty lyrics
            if not raw_lyrics:
                return None

            lines = unquote(raw_lyrics).split('<br>')

            # Reject instrumental tracks
            if '이 곡은 연주곡 입니다.' in lines:
                return None

            return Lyrics(song_id=song_id, song_title=song.title, lines=lines, is_synced=False)

    def has_artist_url(self, artist: Artist) -> bool:
        if artist.has_genie_url:
            return True

        if artist.id not in self.missing_artists:
            print(f'\rNo Genie URL found for artist {artist.name} [{artist.id}]')
            self.missing_artists[artist.id] = artist

        return False

    def get_genie_songs(self, track_release: Release) -> dict[str, GenieSong] | None:
        """
        Get Genie songs for a track release, matched to recordings.

        :return: A dictionary mapping recording MBIDs to Genie songs, or None if there was an error.
        """
        if track_release.id in self.cache:
            return self.cache[track_release.id]

        result = pick_release_from_release_group(track_release, lambda r: r.get_genie_album_id())
        if not result:
            print(f'\rNo Genie URL found for release {track_release.title} [{track_release.id}]')
            self.cache[track_release.id] = None
            self.missing_releases[track_release.id] = track_release
            return None
        matched_release, album_id = result

        genie_songs = self.fetch_genie_album_songs(album_id)
        if not genie_songs:
            self.cache[track_release.id] = None
            return None

        # Ensure track count matches
        if len(genie_songs) != matched_release.get_track_count():
            print(f'\rTrack count mismatch for release {track_release.title} [{track_release.id}]')
            self.cache[track_release.id] = None
            return None

        # Match recordings to Genie songs
        mapped_songs = {}

        # Iterate over all tracks in the release
        for medium in matched_release.media:
            for track in medium['tracks']:
                recording_mbid: str = track['recording']['id']
                try:
                    # Match song by track number if possible
                    track_number = int(track['number'])
                    song = next(song for song in genie_songs if song.album_index == track_number)
                except (ValueError, StopIteration):
                    # Fall back to track position
                    track_index = track['position'] - 1
                    if track_index >= len(genie_songs):
                        continue
                    song = genie_songs[track_index]

                mapped_songs[recording_mbid] = song

        self.cache[track_release.id] = mapped_songs

        return mapped_songs

    @staticmethod
    def fetch_genie_album_songs(album_id: int) -> list[GenieSong] | None:
        response = httpx.get(GENIE_ALBUM_API_URL.format(album_id=album_id), headers={'User-Agent': CURL_USER_AGENT})
        try:
            response_json = response.json()
        except JSONDecodeError:
            return None

        try:
            songs = list(response_json['DATA1']['DATA'])
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

    @staticmethod
    def fetch_genie_stream_info(song_id: int) -> dict | None:
        try:
            return httpx.get(
                GENIE_STREAM_INFO_API_URL.format(song_id=song_id),
                headers={'User-Agent': CURL_USER_AGENT},
            ).json()
        except JSONDecodeError:
            return None
