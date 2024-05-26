import html
import os
from os import PathLike
from os import path

import mutagen

from .genie_client import fetch_genie_album_song_ids, GenieSong, fetch_lyrics
from .mb_client import Artist, Release, get_artist, get_release_by_track, get_releases_by_release_group

TITLE_TAG = 'title'
ALBUM_TAG = 'album'
TRACKNUMBER_TAG = 'tracknumber'
ALBUMARTIST_TAG = 'albumartist'
MB_RGID_TAG = 'musicbrainz_releasegroupid'
MB_RTID_TAG = 'musicbrainz_releasetrackid'
MB_RAID_TAG = 'musicbrainz_albumartistid'


class LyricsFetcher:
    def __init__(self, check_artist: bool = False, dry_run: bool = False, force: bool = False):
        self.check_artist = check_artist
        self.dry_run = dry_run
        self.force = force
        self.artist_cache: dict[str, Artist] = {}
        self.release_cache: dict[str, Release] = {}
        self.genie_cache = {}
        self.missing_artists: set[str] = set()
        self.missing_releases: set[str] = set()

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

        title = tags[TITLE_TAG][0] or 'Unknown title'
        album = tags[ALBUM_TAG][0] or 'Unknown album'
        track_number = int(tags[TRACKNUMBER_TAG][0].split('/')[0])
        rg_mbid = tags[MB_RGID_TAG][0]
        track_mbid = tags[MB_RTID_TAG][0]

        # Handle empty MBIDs
        if not rg_mbid or not track_mbid:
            return False

        # Check artist for Genie URL
        if self.check_artist and not self.has_artist_genie_url(tags):
            return False

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
            print(' - no lyrics found')
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

        albumartist = tags[ALBUMARTIST_TAG][0] or 'Unknown artist'
        artist = self.get_artist(albumartist_mbid, albumartist)
        if not artist or artist.has_genie_url:
            return True

        if artist.id not in self.missing_artists:
            print(f'No Genie URL found for artist {artist.name} [{artist.id}]')
            self.missing_artists.add(artist.id)

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
        self.missing_releases.add(release.id)

        return None

    def write_report(self, file: str | PathLike[str]):
        with open(file, 'w') as f:
            f.write('<!DOCTYPE html>\n')
            f.write('<html>\n')
            f.write('<head><title>lyriks report</title></head>\n')
            f.write('<body>\n')
            f.write('<h1>lyriks report</h1>\n')
            f.write('<h2>Artists missing Genie URLs</h2>\n')
            f.write('<ul>\n')
            for artist_mbid in self.missing_artists:
                url = f'https://musicbrainz.org/artist/{artist_mbid}'
                artist = self.artist_cache[artist_mbid]
                artist_name = artist.name if artist else 'Unknown artist'
                f.write(f'<li><a href="{url}">{html.escape(artist_name)}</a></li>\n')
            f.write('</ul>\n')
            f.write('<h2>Releases missing Genie URLs</h2>\n')
            f.write('<ul>\n')
            for release_mbid in self.missing_releases:
                url = f'https://musicbrainz.org/release/{release_mbid}'
                release = self.release_cache[release_mbid]
                release_name = release.title if release else 'Unknown release'
                f.write(f'<li><a href="{url}">{html.escape(release_name)}</a></li>\n')
            f.write('</ul>\n')
            f.write('</body>\n')
            f.write('</html>')
