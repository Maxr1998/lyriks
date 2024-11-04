import html
import os
from os import PathLike
from os import path
from pathlib import Path
from sys import stderr

import mutagen
from mutagen.easymp4 import EasyMP4Tags

from .genie_client import fetch_genie_album_song_ids, GenieSong, fetch_lyrics
from .mb_client import Artist, Release, get_artist, get_release_by_track, get_releases_by_release_group

TITLE_TAG = 'title'
ALBUM_TAG = 'album'
TRACKNUMBER_TAG = 'tracknumber'
ALBUMARTIST_TAG = 'albumartist'
MB_RGID_TAG = 'musicbrainz_releasegroupid'
MB_RTID_TAG = 'musicbrainz_releasetrackid'
MB_RAID_TAG = 'musicbrainz_albumartistid'

VARIOUS_ARTISTS_MBID = '89ad4ac3-39f7-470e-963a-56509c546377'

EasyMP4Tags.RegisterFreeformKey(MB_RGID_TAG, 'MusicBrainz Release Group Id')
EasyMP4Tags.RegisterFreeformKey(MB_RTID_TAG, 'MusicBrainz Release Track Id')


def main(
        check_artist: bool,
        dry_run: bool,
        upgrade: bool,
        force: bool,
        skip_instrumentals: bool,
        report_path: Path | None,
        collection_path: Path,
):
    # Validate collection path
    if not collection_path.is_dir():
        print(f'Error: directory \'{collection_path}\' does not exist', file=stderr)
        exit(2)

    # Normalize and validate report path
    if report_path:
        report_path = report_path.expanduser().absolute()
        if report_path.is_dir():
            report_path = report_path / 'report.html'
        if not report_path.parent.exists():
            print(f'Error: directory \'{report_path.parent}\' does not exist', file=stderr)
            exit(2)

    fetcher = LyricsFetcher(check_artist, dry_run, upgrade, force, skip_instrumentals)

    for root_dir, dirs, files in os.walk(collection_path, topdown=True):
        if path.exists(path.join(root_dir, '.nolyrics')):
            dirs.clear()
            continue

        for file in files:
            extension = path.splitext(file)[1].lower()
            if extension in ('.flac', '.m4a', '.mp3'):
                fetcher.fetch_lyrics(root_dir, file)

    if report_path:
        try:
            fetcher.write_report(report_path)
        except OSError:
            print(f'Error: could not write report to \'{report_path}\'', file=stderr)
            exit(2)


def fetch_single_song(song_id: int, output_path: str):
    lyrics = fetch_lyrics(song_id)
    if lyrics is None:
        print('Failed to fetch lyrics.')
        return

    extension = 'lrc' if lyrics.is_timed else 'txt'
    output_path = output_path or f'{lyrics.song_title}.{extension}'
    lyrics.write_to_file(output_path)

    print(f'Lyrics saved to {output_path}')


class LyricsFetcher:
    def __init__(self,
                 check_artist: bool = False,
                 dry_run: bool = False,
                 upgrade: bool = False,
                 force: bool = False,
                 skip_inst: bool = False):
        self.check_artist = check_artist
        self.dry_run = dry_run
        self.upgrade = upgrade
        self.force = force
        self.skip_inst = skip_inst
        self.artist_cache: dict[str, Artist] = {}
        self.release_cache: dict[str, Release] = {}
        self.genie_cache: dict[str, dict[str, GenieSong] | None] = {}
        self.missing_artists: dict[str, Artist] = {}
        self.missing_releases: dict[str, Release] = {}

    def fetch_lyrics(self, dirname: str, filename: str) -> None:
        filepath = path.join(dirname, filename)
        basename = filename.rsplit('.', 1)[0]

        # Skip instrumental tracks if enabled and applicable
        if self.skip_inst and ('instrumental' in basename.lower() or 'inst.' in basename.lower()):
            return

        # Skip if .nolyrics file exists
        nolyrics_file = path.join(dirname, f'{basename}.nolyrics')
        if path.exists(nolyrics_file):
            return

        timed_lyrics_file = path.join(dirname, f'{basename}.lrc')
        static_lyrics_file = path.join(dirname, f'{basename}.txt')
        has_timed_lyrics = path.exists(timed_lyrics_file)
        has_static_lyrics = path.exists(static_lyrics_file)

        # Skip if lyrics already exist
        if (has_timed_lyrics or (has_static_lyrics and not self.upgrade)) and not self.force:
            return

        file = mutagen.File(filepath, easy=True)
        if not file:
            return

        tags = file.tags
        if (TITLE_TAG not in tags or ALBUM_TAG not in tags or TRACKNUMBER_TAG not in tags or
                MB_RGID_TAG not in tags or MB_RTID_TAG not in tags):
            return

        title = tags[TITLE_TAG][0] or 'Unknown title'
        album = tags[ALBUM_TAG][0] or 'Unknown album'
        rg_mbid = tags[MB_RGID_TAG][0]
        track_mbid = tags[MB_RTID_TAG][0]

        # Handle empty MBIDs
        if not rg_mbid or not track_mbid:
            return

        # Check artist for Genie URL
        if self.check_artist and not self.has_artist_genie_url(tags):
            return

        # Resolve release for the track
        track_release = self.get_release(track_mbid, album)
        if not track_release:
            return

        # Resolve track
        for medium in track_release.get_track_map():
            track = medium.get(track_mbid)
            if track:
                break
        else:
            return

        # Resolve Genie album
        genie_songs = self.get_genie_songs(track_release, rg_mbid)
        if not genie_songs:
            return

        # Get Genie song for track
        recording_mbid = track['recording']['id']
        genie_song = genie_songs.get(recording_mbid)
        if not genie_song:
            return

        print(f'Fetching lyrics for {title}', end='')

        # Fetch lyrics
        lyrics = fetch_lyrics(genie_song.id)
        if not lyrics:
            print(' - no lyrics found')
            return

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
            elif self.upgrade and has_static_lyrics:
                print(' - no timed lyrics available to upgrade to')
            else:
                print(f' - writing to {static_lyrics_file}')
                lyrics.write_to_file(static_lyrics_file)

    def has_artist_genie_url(self, tags):
        """
        Check if the artist has a Genie URL.
        :return: True if we're unable to check or if this artist has a Genie URL, False otherwise.
        """
        if MB_RAID_TAG not in tags or ALBUMARTIST_TAG not in tags:
            return True

        albumartist_mbid = tags[MB_RAID_TAG][0]
        if not albumartist_mbid:  # handle empty MBID
            return True

        # Skip various artists
        if albumartist_mbid == VARIOUS_ARTISTS_MBID:
            return True

        albumartist = tags[ALBUMARTIST_TAG][0] or 'Unknown artist'
        artist = self.get_artist(albumartist_mbid, albumartist)
        if not artist or artist.has_genie_url:
            return True

        if artist.id not in self.missing_artists:
            print(f'No Genie URL found for artist {artist.name} [{artist.id}]')
            self.missing_artists[artist.id] = artist

        return False

    def get_artist(self, artist_mbid: str, artist_name: str) -> Artist | None:
        if artist_mbid in self.artist_cache:
            return self.artist_cache[artist_mbid]

        print(f'Fetching artist info for {artist_name}', end='')

        artist = get_artist(artist_mbid)
        if not artist:
            print(' - no artist found')
            return None

        self.artist_cache[artist_mbid] = artist

        print()  # terminate line

        return artist

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

    def get_genie_songs(self, track_release: Release, rg_mbid: str) -> dict[str, GenieSong] | None:
        """
        Get Genie songs for a track release, matched to recordings.

        :return: A dictionary mapping recording MBIDs to Genie songs, or None if there was an error.
        """
        if track_release.id in self.genie_cache:
            return self.genie_cache[track_release.id]

        genie_release, album_id = self.get_genie_release(track_release, rg_mbid)
        if not genie_release or not album_id:
            self.genie_cache[track_release.id] = None
            return None

        genie_song_ids = fetch_genie_album_song_ids(album_id)
        if not genie_song_ids:
            self.genie_cache[track_release.id] = None
            return None

        # Ensure track count matches
        if len(genie_song_ids) != genie_release.get_track_count():
            print(f'Track count mismatch for release {track_release.title} [{track_release.id}]')
            self.genie_cache[track_release.id] = None
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

        self.genie_cache[track_release.id] = genie_songs

        return genie_songs

    def get_genie_release(self, track_release: Release, rg_mbid: str) -> tuple[Release | None, int | None]:
        # Try to get the album ID from the release itself first
        album_id = track_release.get_genie_album_id()
        if album_id is not None:
            return track_release, album_id

        # If that fails, check all releases from the release group
        rg_releases = get_releases_by_release_group(rg_mbid)
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

    # noinspection DuplicatedCode
    def write_report(self, file: str | PathLike[str]):
        with open(file, 'w') as f:
            f.write('<!DOCTYPE html>\n')
            f.write('<html>\n')
            f.write('<head><title>lyriks report</title></head>\n')
            f.write('<body>\n')
            f.write('<h1>lyriks report</h1>\n')
            f.write(f'<h2>Artists missing Genie URLs ({len(self.missing_artists)})</h2>\n')
            if self.missing_artists:
                f.write('<ul>\n')
                for artist in self.missing_artists.values():
                    url = f'https://musicbrainz.org/artist/{artist.id}'
                    f.write(f'<li><a href="{url}">{html.escape(artist.name)}</a></li>\n')
                f.write('</ul>\n')
            else:
                f.write('<p>None.</p>\n')
            f.write(f'<h2>Releases missing Genie URLs ({len(self.missing_releases)})</h2>\n')
            if self.missing_releases:
                f.write('<ul>\n')
                for release in self.missing_releases.values():
                    url = f'https://musicbrainz.org/release/{release.id}'
                    f.write(f'<li><a href="{url}">{html.escape(release.title)}</a></li>\n')
                f.write('</ul>\n')
            else:
                f.write('<p>None.</p>\n')
            f.write('</body>\n')
            f.write('</html>')
