import html
import os
from os import PathLike
from os import path
from pathlib import Path

import mutagen
from httpx import AsyncClient as HttpClient
from mutagen.easymp4 import EasyMP4Tags
from stamina import instrumentation

from .cli.console import console
from .logging import LoggingOnRetryHook
from .mb_client import Artist, Release, get_artist, get_release_by_track
from .providers import ProviderFactory

TITLE_TAG = 'title'
ALBUM_TAG = 'album'
TRACKNUMBER_TAG = 'tracknumber'
ALBUMARTIST_TAG = 'albumartist'
MB_RGID_TAG = 'musicbrainz_releasegroupid'
MB_RTID_TAG = 'musicbrainz_releasetrackid'
MB_AAID_TAG = 'musicbrainz_albumartistid'

VARIOUS_ARTISTS_MBID = '89ad4ac3-39f7-470e-963a-56509c546377'

instrumentation.set_on_retry_hooks([LoggingOnRetryHook])

EasyMP4Tags.RegisterFreeformKey(MB_RGID_TAG, 'MusicBrainz Release Group Id')
EasyMP4Tags.RegisterFreeformKey(MB_RTID_TAG, 'MusicBrainz Release Track Id')


async def main(
    provider_factory: ProviderFactory,
    check_artist: bool,
    dry_run: bool,
    upgrade: bool,
    force: bool,
    skip_instrumentals: bool,
    report_path: Path | None,
    collection_path: Path,
):
    # Normalize and validate report path
    if report_path:
        report_path = report_path.expanduser().absolute()
        if report_path.is_dir():
            report_path = report_path / 'report.html'
        if not report_path.parent.exists():
            console.print(f'Error: directory \'{report_path.parent}\' does not exist', style='error')
            exit(2)

    async with LyricsFetcher(provider_factory, check_artist, dry_run, upgrade, force, skip_instrumentals) as fetcher:
        for root_dir, dirs, files in os.walk(collection_path, topdown=True):
            if path.exists(path.join(root_dir, '.nolyrics')):
                dirs.clear()
                continue

            for file in files:
                extension = path.splitext(file)[1].lower()
                if extension in ('.flac', '.m4a', '.mp3'):
                    try:
                        await fetcher.fetch_lyrics(root_dir, file)
                    except Exception as e:
                        console.print(f'Error: could fetch lyrics for \'{file}\': {e!r}', style='error')

        if report_path:
            try:
                fetcher.write_report(report_path)
            except OSError:
                console.print(f'Error: could not write report to \'{report_path}\'', style='error')
                exit(2)


async def fetch_single_song(provider_factory: ProviderFactory, song_id: int, output_path: str):
    with console.status('Fetching lyrics…'):
        async with HttpClient() as http_client:
            provider = provider_factory(http_client)
            song = await provider.fetch_song_by_id(song_id)
            if song is None:
                console.print('Song not found.')
                return
            lyrics = await provider.fetch_provider_song_lyrics(song)
            if lyrics is None:
                console.print('Failed to fetch lyrics.')
                return

    extension = 'lrc' if lyrics.is_synced else 'txt'
    output_path = output_path or f'{lyrics.song_title}.{extension}'
    lyrics.write_to_file(output_path)

    console.print(f'Lyrics saved to {output_path}')


class LyricsFetcher:
    def __init__(
        self,
        provider_factory: ProviderFactory,
        check_artist: bool = False,
        dry_run: bool = False,
        upgrade: bool = False,
        force: bool = False,
        skip_inst: bool = False,
    ):
        self.provider_factory = provider_factory
        self.check_artist = check_artist
        self.dry_run = dry_run
        self.upgrade = upgrade
        self.force = force
        self.skip_inst = skip_inst
        self.status = console.status('idle')
        self.artist_cache: dict[str, Artist] = {}
        self.release_cache: dict[str, Release] = {}

    async def __aenter__(self) -> 'LyricsFetcher':
        self.http_client = HttpClient()
        self.provider = self.provider_factory(self.http_client)
        self.status.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.status.stop()
        await self.http_client.aclose()

    async def fetch_lyrics(self, dirname: str, filename: str) -> None:
        filepath = path.join(dirname, filename)
        basename = filename.rsplit('.', 1)[0]

        # Skip instrumental tracks if enabled and applicable
        if self.skip_inst and ('instrumental' in basename.lower() or 'inst.' in basename.lower()):
            return

        # Skip if .nolyrics file exists
        nolyrics_file = path.join(dirname, f'{basename}.nolyrics')
        if path.exists(nolyrics_file):
            return

        synced_lyrics_file = path.join(dirname, f'{basename}.lrc')
        static_lyrics_file = path.join(dirname, f'{basename}.txt')
        has_synced_lyrics = path.exists(synced_lyrics_file)
        has_static_lyrics = path.exists(static_lyrics_file)

        # Skip if lyrics already exist
        if (has_synced_lyrics or (has_static_lyrics and not self.upgrade)) and not self.force:
            return

        file = mutagen.File(filepath, easy=True)
        if not file:
            return

        tags = file.tags
        if (
            TITLE_TAG not in tags
            or ALBUM_TAG not in tags
            or TRACKNUMBER_TAG not in tags
            or MB_RGID_TAG not in tags
            or MB_RTID_TAG not in tags
        ):
            return

        title = tags[TITLE_TAG][0] or 'Unknown title'
        album = tags[ALBUM_TAG][0] or 'Unknown album'
        rg_mbid = tags[MB_RGID_TAG][0]
        track_mbid = tags[MB_RTID_TAG][0]

        # Handle empty MBIDs
        if not rg_mbid or not track_mbid:
            return

        # Check artist URL
        if self.check_artist and not await self.has_artist_url(tags):
            return

        # Resolve release for the track
        track_release = await self.get_release(track_mbid, album)
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
        self.status.update(f'Fetching lyrics for {title}')
        recording_mbid = track['recording']['id']
        lyrics = await self.provider.fetch_recording_lyrics(track_release, recording_mbid)
        if not lyrics:
            console.print(f'No lyrics found for {title}')
            return

        if self.dry_run:
            console.print(f'Fetched lyrics for {title} \\[dry run]')
        else:
            # Write lyrics to file
            if lyrics.is_synced:
                lyrics.write_to_file(synced_lyrics_file)
                console.print(f'Wrote synced lyrics for {title} to \'{synced_lyrics_file}\'')

                # Remove static lyrics file if necessary
                if has_static_lyrics:
                    os.unlink(static_lyrics_file)
            elif has_synced_lyrics:
                console.print(f'Not writing static lyrics for {title} as synced lyrics already exist')
            elif self.upgrade and has_static_lyrics:
                console.print(f'No upgraded lyrics available for {title}')
            else:
                lyrics.write_to_file(static_lyrics_file)
                console.print(f'Wrote static lyrics for {title} to \'{static_lyrics_file}\'')

    async def has_artist_url(self, tags) -> bool:
        """
        Check if the artist has a URL for the current provider.
        :return: True if we're unable to check or if this artist has a URL, False otherwise.
        """
        if MB_AAID_TAG not in tags or ALBUMARTIST_TAG not in tags:
            return True

        albumartist_mbid = tags[MB_AAID_TAG][0]
        if not albumartist_mbid:  # handle empty MBID
            return True

        # Skip various artists
        if albumartist_mbid == VARIOUS_ARTISTS_MBID:
            return True

        albumartist = tags[ALBUMARTIST_TAG][0] or 'Unknown artist'
        artist = await self.get_artist(albumartist_mbid, albumartist)
        if not artist or self.provider.has_artist_url(artist):
            return True

        return False

    async def get_artist(self, artist_mbid: str, artist_name: str) -> Artist | None:
        if artist_mbid in self.artist_cache:
            return self.artist_cache[artist_mbid]

        self.status.update(f'Fetching artist info for {artist_name}')

        artist = await get_artist(self.http_client, artist_mbid)
        if not artist:
            console.print(f'Artist {artist_name} not found', style='warning')
            return None

        self.artist_cache[artist_mbid] = artist

        return artist

    async def get_release(self, track_mbid: str, album_name: str) -> Release | None:
        if track_mbid in self.release_cache:
            return self.release_cache[track_mbid]

        self.status.update(f'Fetching release info for {album_name}')

        release = await get_release_by_track(self.http_client, track_mbid)
        if not release:
            console.print(f'No release found for {album_name}', style='warning')
            return None

        for media in release.data['media']:
            for track in media['tracks']:
                self.release_cache[track['id']] = release

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
