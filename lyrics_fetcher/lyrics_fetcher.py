from os import path

import mutagen

from .genie_client import fetch_genie_album_song_ids, GenieSong, fetch_lyrics
from .mb_client import get_release_by_track, get_releases_by_release_group, Release

TITLE_TAG = 'title'
TRACKNUMBER_TAG = 'tracknumber'
MB_RGID_TAG = 'musicbrainz_releasegroupid'
MB_RTID_TAG = 'musicbrainz_releasetrackid'


class LyricsFetcher:
    def __init__(self):
        self.release_cache = {}
        self.genie_cache = {}

    def fetch_lyrics(self, filename) -> bool:
        basename = filename.rsplit('.', 1)[0]
        timed_lyrics_file = f'{basename}.lrc'
        static_lyrics_file = f'{basename}.txt'

        if path.exists(timed_lyrics_file) or path.exists(static_lyrics_file):
            # Skip if lyrics already exist
            return True

        file = mutagen.File(filename, easy=True)
        if not file:
            return False

        tags = file.tags
        if (TITLE_TAG not in tags or TRACKNUMBER_TAG not in tags or
                MB_RGID_TAG not in tags or MB_RTID_TAG not in tags):
            return False

        print(f'Processing {filename}')

        title = tags[TITLE_TAG][0]
        track_number = int(tags[TRACKNUMBER_TAG][0].split('/')[0])
        rg_mbid = tags[MB_RGID_TAG][0]
        track_mbid = tags[MB_RTID_TAG][0]

        # Resolve release for the track
        track_release = self.get_release(track_mbid)
        if not track_release:
            return False

        # Resolve Genie album
        songs = self.get_genie_album(track_release, rg_mbid)
        if not songs or track_release.get_track_count() != len(songs):
            return False

        # Fetch lyrics
        song = songs[track_number - 1]
        lyrics = fetch_lyrics(song.song_id)
        if not lyrics:
            return False

        print(f'Found lyrics for {title} / {song.name} [{song.song_id}], ', end='')

        # Write lyrics to file
        if lyrics.is_timed:
            print(f'writing to {timed_lyrics_file}')
            lyrics.write_to_file(timed_lyrics_file)
        else:
            print(f'writing to {static_lyrics_file}')
            lyrics.write_to_file(static_lyrics_file)

        return True

    def get_release(self, track_mbid):
        if track_mbid in self.release_cache:
            return self.release_cache[track_mbid]

        release = get_release_by_track(track_mbid)
        if not release:
            return None

        for media in release.data['media']:
            for track in media['tracks']:
                self.release_cache[track['id']] = release

        return release

    def get_genie_album(self, release: Release, rg_mbid) -> list[GenieSong] | None:
        if release.id in self.genie_cache:
            return self.genie_cache[release.id]

        album_id = self.get_genie_album_id(release, rg_mbid)
        if not album_id:
            self.genie_cache[release.id] = None
            return None

        songs = fetch_genie_album_song_ids(album_id)
        if not songs:
            self.genie_cache[release.id] = None
            return None

        self.genie_cache[release.id] = songs

        return songs

    @staticmethod
    def get_genie_album_id(release: Release, rg_mbid):
        # Try to get the album ID from the release itself first
        album_id = release.get_genie_album_id()
        if album_id is not None:
            return album_id

        # If that fails, check all releases from the release group
        rg_releases = get_releases_by_release_group(rg_mbid)
        if not rg_releases:
            return None

        for rg_release in rg_releases:
            if rg_release.get_track_count() != release.get_track_count():
                continue
            album_id = release.get_genie_album_id()
            if album_id is not None:
                return album_id

        return None
