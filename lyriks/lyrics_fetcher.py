import os
from os import PathLike
from os import path

import mutagen

from .genie_client import fetch_genie_album_song_ids, GenieSong, fetch_lyrics
from .mb_client import get_release_by_track, get_releases_by_release_group, Release

TITLE_TAG = 'title'
ALBUM_TAG = 'album'
TRACKNUMBER_TAG = 'tracknumber'
MB_RGID_TAG = 'musicbrainz_releasegroupid'
MB_RTID_TAG = 'musicbrainz_releasetrackid'


class LyricsFetcher:
    def __init__(self, dry_run: bool = False, force: bool = False):
        self.dry_run = dry_run
        self.force = force
        self.release_cache = {}
        self.genie_cache = {}
        self.missing_releases = set()

    def fetch_lyrics(self, filename: str) -> bool:
        basename = filename.rsplit('.', 1)[0]
        timed_lyrics_file = f'{basename}.lrc'
        static_lyrics_file = f'{basename}.txt'

        has_timed_lyrics = path.exists(timed_lyrics_file)
        has_static_lyrics = path.exists(static_lyrics_file)

        if (has_timed_lyrics or has_static_lyrics) and not self.force:
            # Skip if lyrics already exist
            return True

        file = mutagen.File(filename, easy=True)
        if not file:
            return False

        tags = file.tags
        if (TITLE_TAG not in tags or ALBUM_TAG not in tags or TRACKNUMBER_TAG not in tags or
                MB_RGID_TAG not in tags or MB_RTID_TAG not in tags):
            return False

        title = tags[TITLE_TAG][0]
        album = tags[ALBUM_TAG][0]
        track_number = int(tags[TRACKNUMBER_TAG][0].split('/')[0])
        rg_mbid = tags[MB_RGID_TAG][0]
        track_mbid = tags[MB_RTID_TAG][0]

        # Resolve release for the track
        track_release = self.get_release(track_mbid, album)
        if not track_release:
            return False

        # Resolve Genie album
        songs = self.get_genie_album(track_release, rg_mbid)
        if not songs or track_release.get_track_count() != len(songs):
            return False

        print(f'Fetching lyrics for {title}', end='')

        # Fetch lyrics
        song = songs[track_number - 1]
        lyrics = fetch_lyrics(song.song_id)
        if not lyrics:
            print(f' - no lyrics found')
            return False

        if self.dry_run:
            print(' - done [dry run]')
        else:
            # Write lyrics to file
            if lyrics.is_timed:
                print(f' - writing to {timed_lyrics_file}')
                lyrics.write_to_file(timed_lyrics_file)

                # Remove static lyrics file if necessary
                if has_static_lyrics:
                    os.unlink(static_lyrics_file)
            elif has_timed_lyrics:
                print(' - not writing static lyrics, timed lyrics already exist')
            else:
                print(f' - writing to {static_lyrics_file}')
                lyrics.write_to_file(static_lyrics_file)

        return True

    def get_release(self, track_mbid: str, album_name: str) -> Release | None:
        if track_mbid in self.release_cache:
            return self.release_cache[track_mbid]

        print(f'Fetching release info for {album_name}', end='')

        release = get_release_by_track(track_mbid)
        if not release:
            print(' - no release found')
            return None

        for media in release.data['media']:
            for track in media['tracks']:
                self.release_cache[track['id']] = release

        print()  # terminate line

        return release

    def get_genie_album(self, release: Release, rg_mbid: str) -> list[GenieSong] | None:
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

    def get_genie_album_id(self, release: Release, rg_mbid: str) -> int | None:
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
            album_id = rg_release.get_genie_album_id()
            if album_id is not None:
                return album_id

        print(f'No Genie URL found for release {release.title} [{release.id}]')
        self.missing_releases.add(release)

        return None

    def write_report(self, file: str | PathLike[str]):
        with open(file, 'w') as f:
            f.write('<html><head><title>lyriks report</title></head>')
            f.write('<body>')
            f.write('<h1>Releases missing Genie URLs</h1>')
            f.write('<ul>')
            for release in self.missing_releases:
                url = f'https://musicbrainz.org/release/{release.id}'
                f.write(f'<li><a href="{url}">{release.title}</a></li>')
            f.write('</ul>')
            f.write('</body>')
            f.write('</html>')
