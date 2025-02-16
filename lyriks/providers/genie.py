import json
from dataclasses import dataclass
from json.decoder import JSONDecodeError
from urllib.parse import unquote

import requests

from lyriks.lyrics import Lyrics
from lyriks.mb_client import Release, get_releases_by_release_group, Artist
from lyriks.providers import Provider

GENIE_ALBUM_API_URL = 'https://app.genie.co.kr/song/j_AlbumSongList.json?axnm={album_id:d}'
GENIE_LYRICS_API_URL = 'https://dn.genie.co.kr/app/purchase/get_msl.asp?songid={song_id:d}&callback=GenieCallback'
GENIE_STREAM_INFO_API_URL = 'https://stm.genie.co.kr/player/j_StmInfo.json?xgnm={song_id:d}'

CURL_USER_AGENT = 'curl/8.7.1'  # for whatever reason, this works, but the python-requests UA doesn't


@dataclass
class GenieSong:
    id: int
    track: int
    name: str


class Genie(Provider):
    """
    Provider for Genie Music.
    """

    def fetch_lyrics(self, track_release: Release, recording_mbid: str) -> Lyrics | None:
        # Resolve Genie album
        genie_songs = self.get_genie_songs(track_release)
        if not genie_songs:
            return None

        # Get Genie song for track
        genie_song = genie_songs.get(recording_mbid)
        if not genie_song:
            return None

        # Fetch lyrics
        return self.fetch_single_song(genie_song.id)

    def fetch_single_song(self, song_id: int) -> Lyrics | None:
        # Fetch stream info with general song info and static lyrics
        try:
            stream_info = requests.get(
                GENIE_STREAM_INFO_API_URL.format(song_id=song_id),
                headers={'User-Agent': CURL_USER_AGENT},
            ).json()
        except JSONDecodeError:
            return None

        try:
            song_title = unquote(stream_info['DataSet']['DATA'][0]['SONG_NAME'])
        except KeyError:
            return None

        # Try to fetch synced lyrics
        lyrics_response = requests.get(
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

            return Lyrics.synced(song_id, song_title, lyrics_dict)
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

            return Lyrics.static(song_id, song_title, lines)

    def has_artist_url(self, artist: Artist) -> bool:
        if artist.has_genie_url:
            return True

        if artist.id not in self.missing_artists:
            print(f'No Genie URL found for artist {artist.name} [{artist.id}]')
            self.missing_artists[artist.id] = artist

        return False

    def get_genie_songs(self, track_release: Release) -> dict[str, GenieSong] | None:
        """
        Get Genie songs for a track release, matched to recordings.

        :return: A dictionary mapping recording MBIDs to Genie songs, or None if there was an error.
        """
        if track_release.id in self.cache:
            return self.cache[track_release.id]

        genie_release, album_id = self.get_genie_release(track_release)
        if not genie_release or not album_id:
            self.cache[track_release.id] = None
            return None

        genie_song_ids = self.fetch_genie_album_song_ids(album_id)
        if not genie_song_ids:
            self.cache[track_release.id] = None
            return None

        # Ensure track count matches
        if len(genie_song_ids) != genie_release.get_track_count():
            print(f'Track count mismatch for release {track_release.title} [{track_release.id}]')
            self.cache[track_release.id] = None
            return None

        # Match recordings to Genie songs
        genie_songs = {}

        # Iterate over all tracks in the release
        for medium in genie_release.media:
            for track in medium['tracks']:
                recording_mbid: str = track['recording']['id']
                try:
                    # Match song by track number if possible
                    track_number = int(track['number'])
                    song = next(song for song in genie_song_ids if song.track == track_number)
                except (ValueError, StopIteration):
                    # Fall back to track position
                    track_index = track['position'] - 1
                    if track_index >= len(genie_song_ids):
                        continue
                    song = genie_song_ids[track_index]

                genie_songs[recording_mbid] = song

        self.cache[track_release.id] = genie_songs

        return genie_songs

    def get_genie_release(self, track_release: Release) -> tuple[Release | None, int | None]:
        # Try to get the album ID from the release itself first
        album_id = track_release.get_genie_album_id()
        if album_id is not None:
            return track_release, album_id

        # If that fails, check all releases from the release group
        rg_releases = get_releases_by_release_group(track_release.rg_mbid)
        if not rg_releases:
            return None, None

        # Sort releases by track count delta
        track_release_track_count = track_release.get_track_count()
        rg_releases = sorted(rg_releases, key=lambda r: abs(r.get_track_count() - track_release_track_count))

        # Return the first release group release with a Genie URL
        for rg_release in rg_releases:
            album_id = rg_release.get_genie_album_id()
            if album_id is not None:
                return rg_release, album_id

        print(f'No Genie URL found for release {track_release.title} [{track_release.id}]')
        self.missing_releases[track_release.id] = track_release

        return None, None

    @staticmethod
    def fetch_genie_album_song_ids(album_id: int) -> list[GenieSong] | None:
        response = requests.get(GENIE_ALBUM_API_URL.format(album_id=album_id),
                                headers={'User-Agent': CURL_USER_AGENT})
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

            result.append(GenieSong(id=song_id, track=track_num, name=unquote(song_name)))

        result = sorted(result, key=lambda x: x.track)

        return result
