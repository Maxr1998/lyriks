from lyriks.lyrics import Lyrics
from lyriks.mb_client import Release, Artist
from . import Provider, Song
from .api import genie_api
from .api.genie_api import GenieSong
from .util import pick_release_from_release_group


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
        stream_info = genie_api.get_stream_info(song_id)
        if stream_info is None:
            return None

        try:
            album_id = int(stream_info['DataSet']['DATA'][0]['ALBUM_ID'])
        except KeyError:
            return None

        genie_songs = genie_api.get_album_songs(album_id)
        if not genie_songs:
            return None

        return next((s for s in genie_songs if s.id == song_id), None)

    def fetch_provider_song_lyrics(self, song: GenieSong) -> Lyrics | None:
        return genie_api.get_song_lyrics(song)

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

        genie_songs = genie_api.get_album_songs(album_id)
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
