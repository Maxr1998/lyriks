from abc import ABC, abstractmethod
from typing import Generic, Protocol
from typing import TypeVar

from httpx import AsyncClient as HttpClient

from lyriks.cli.console import console
from lyriks.lyrics import Lyrics
from lyriks.mb_client import Mbid, Artist, Release
from .api.song import Song
from .util import pick_release_from_release_group

T = TypeVar('T', str, int)
S = TypeVar('S', bound=Song)


class Provider(Generic[T, S], ABC):
    """
    Generic abstract base class for lyrics providers.
    Supports fetching lyrics as part of the sync process,
    or once for a single song, identified by its provider-specific ID.

    The provider is responsible for caching releases to avoid redundant API calls.
    Artists and releases that don't have a URL relationship can be recorded for later reporting.
    """

    provider_domain: str
    """The primary domain of the provider"""

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not getattr(cls, 'provider_domain', None):
            raise NotImplementedError(f'{cls.__name__}: provider_domain must be set')

    def __init__(self, http_client: HttpClient):
        self.http_client = http_client
        self.cache: dict[str, dict[Mbid, S] | None] = {}
        self.missing_artists: dict[str, Artist] = {}
        self.missing_releases: dict[str, Release] = {}

    @abstractmethod
    def extract_album_id(self, release: Release) -> T | None:
        """
        Try to extract the provider-specific album ID from a release,
        or None if no URL for this provider is attached to the release.
        """
        pass

    @abstractmethod
    async def fetch_album_songs(self, album_id: T) -> list[S] | None:
        """
        Fetch a list of provider-specific song entities for a given album ID.
        """
        pass

    @abstractmethod
    async def fetch_song_by_id(self, song_id: int) -> S | None:
        """
        Fetch a provider-specific song entity by its ID.
        """
        pass

    @abstractmethod
    async def fetch_song_lyrics(self, song: S) -> Lyrics | None:
        """
        Fetch lyrics for a given song entity.
        """
        pass

    def has_artist_url(self, artist: Artist) -> bool:
        """
        Check if the artist has a URL relationship for the service used by this provider.
        :return: True if we're unable to check or if this artist has a URL, False otherwise.
        """

        domain = self.provider_domain
        if any(domain in url for url in artist.urls):
            return True

        if artist.id not in self.missing_artists:
            console.print(f'No {domain} URL found for artist {artist.rich_string}', style='warning')
            self.missing_artists[artist.id] = artist

        return False

    async def fetch_recording_lyrics(self, track_release: Release, recording_mbid: Mbid) -> Lyrics | None:
        """
        Fetch lyrics for a track, identified by its recording MBID and the release it appears on.
        """
        # Resolve album
        songs = await self.get_mapped_provider_songs(track_release)
        if not songs:
            return None

        # Get song for recording
        song = songs.get(recording_mbid)
        if not song:
            return None

        # Fetch lyrics
        return await self.fetch_song_lyrics(song)

    async def get_mapped_provider_songs(self, track_release: Release) -> dict[Mbid, S] | None:
        """
        Get songs for a track release, matched to its recordings.

        :param track_release: The release to fetch and map songs for.
        :return: A dictionary mapping recording MBIDs to provider-specific songs, or None if there was an error.
        """
        if track_release.id in self.cache:
            return self.cache[track_release.id]

        result = await pick_release_from_release_group(self.http_client, track_release, self.extract_album_id)
        if not result:
            console.print(f'No URL found for release {track_release.rich_string}', style='warning')
            self.cache[track_release.id] = None
            self.missing_releases[track_release.id] = track_release
            return None
        matched_release, album_id = result

        provider_songs = await self.fetch_album_songs(album_id)
        if not provider_songs:
            self.cache[track_release.id] = None
            return None

        # Ensure track count matches
        if len(provider_songs) != matched_release.get_track_count():
            console.print(f'Track count mismatch for release {matched_release.rich_string}', style='warning')
            self.cache[track_release.id] = None
            return None

        # Match recordings to songs
        mapped_songs = {}

        # Iterate over all tracks in the release
        for medium in matched_release.media:
            for track in medium['tracks']:
                recording_mbid: Mbid = track['recording']['id']
                try:
                    # Match song by track number if possible
                    track_number = int(track['number'])
                    song = next((song for song in provider_songs if song.album_index == track_number), None)
                except ValueError:
                    song = None

                if song is None:
                    # Fall back to track position
                    track_index = track['position'] - 1
                    if track_index >= len(provider_songs):
                        continue
                    song = provider_songs[track_index]

                mapped_songs[recording_mbid] = song

        self.cache[track_release.id] = mapped_songs

        return mapped_songs


class ProviderFactory(Protocol):
    """
    A factory protocol for creating Provider instances.
    Has to match the Provider constructor signature.
    """

    def __call__(self, http_client: HttpClient) -> Provider: ...
