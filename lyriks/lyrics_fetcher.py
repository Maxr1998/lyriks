import html
import os
from os import PathLike
from os import path
from pathlib import Path
from sys import stderr

import mutagen
from mutagen.easymp4 import EasyMP4Tags

from .mb_client import Artist, Release, get_artist, get_release_by_track
from .providers import Provider

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
        provider: Provider,
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

    fetcher = LyricsFetcher(provider, check_artist, dry_run, upgrade, force, skip_instrumentals)

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


def fetch_single_song(provider: Provider, song_id: int, output_path: str):
    lyrics = provider.fetch_single_song(song_id)
    if lyrics is None:
        print('Failed to fetch lyrics.')
        return

    extension = 'lrc' if lyrics.is_timed else 'txt'
    output_path = output_path or f'{lyrics.song_title}.{extension}'
    lyrics.write_to_file(output_path)

    print(f'Lyrics saved to {output_path}')


class LyricsFetcher:
    def __init__(self,
                 provider: Provider,
                 check_artist: bool = False,
                 dry_run: bool = False,
                 upgrade: bool = False,
                 force: bool = False,
                 skip_inst: bool = False):
        self.provider = provider
        self.check_artist = check_artist
        self.dry_run = dry_run
        self.upgrade = upgrade
        self.force = force
        self.skip_inst = skip_inst
        self.artist_cache: dict[str, Artist] = {}
        self.release_cache: dict[str, Release] = {}

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

        # Check artist URL
        if self.check_artist and not self.has_artist_url(self.provider, tags):
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

        # Fetch lyrics
        print(f'Fetching lyrics for {title}', end='')
        recording_mbid = track['recording']['id']
        lyrics = self.provider.fetch_lyrics(track_release, recording_mbid)
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

    def has_artist_url(self, provider: Provider, tags) -> bool:
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
        if not artist or provider.has_artist_url(artist):
            return True

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

    # noinspection DuplicatedCode
    def write_report(self, file: str | PathLike[str]):
        with open(file, 'w') as f:
            f.write('<!DOCTYPE html>\n')
            f.write('<html>\n')
            f.write('<head><title>lyriks report</title></head>\n')
            f.write('<body>\n')
            f.write('<h1>lyriks report</h1>\n')
            f.write(f'<h2>Artists missing URLs ({len(self.provider.missing_artists)})</h2>\n')
            if self.provider.missing_artists:
                f.write('<ul>\n')
                for artist in self.provider.missing_artists.values():
                    url = f'https://musicbrainz.org/artist/{artist.id}'
                    f.write(f'<li><a href="{url}">{html.escape(artist.name)}</a></li>\n')
                f.write('</ul>\n')
            else:
                f.write('<p>None.</p>\n')
            f.write(f'<h2>Releases missing URLs ({len(self.provider.missing_releases)})</h2>\n')
            if self.provider.missing_releases:
                f.write('<ul>\n')
                for release in self.provider.missing_releases.values():
                    url = f'https://musicbrainz.org/release/{release.id}'
                    f.write(f'<li><a href="{url}">{html.escape(release.title)}</a></li>\n')
                f.write('</ul>\n')
            else:
                f.write('<p>None.</p>\n')
            f.write('</body>\n')
            f.write('</html>')
