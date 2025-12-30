from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, TypeVar

from lyriks.lyrics import Lyrics
from lyriks.mb_client import Release, Artist
from .util import pick_release_from_release_group


@dataclass
class Song(ABC):
    """
    Represents a song in a provider-specific context.
    """

    id: int
    album_index: int
    title: str


T = TypeVar('T')
S = TypeVar('S', bound=Song)


class Provider(ABC):
    """
    Abstract base class for lyrics providers.
    Supports fetching lyrics as part of the sync process,
    or once for a single song, identified by its provider-specific ID.

    The provider is responsible for caching releases to avoid redundant API calls.
    Artists and releases that don't have a URL relationship can be recorded for later reporting.
    """

    def __init__(self):
        self.cache: dict[str, dict[str, object] | None] = {}
        self.missing_artists: dict[str, Artist] = {}
        self.missing_releases: dict[str, Release] = {}

    @abstractmethod
    def fetch_recording_lyrics(self, track_release: Release, recording_mbid: str) -> Lyrics | None:
        """
        Fetch lyrics for a track, identified by its recording MBID and the release it appears on.

        Typically, this resolves the provider-specific song entity and then
        delegates to fetch_provider_song_lyrics to fetch the lyrics.
        """
        pass

    @abstractmethod
    def fetch_song_by_id(self, song_id: int) -> Song | None:
        """
        Fetch a provider-specific song entity by its ID.
        """
        pass

    @abstractmethod
    def fetch_provider_song_lyrics(self, song: Song) -> Lyrics | None:
        """
        Fetch lyrics for a given song entity. Its content may be provider-specific.
        """
        pass

    @abstractmethod
    def provider_domain(self) -> str:
        """
        Get the primary domain of the provider.
        """
        pass

    def has_artist_url(self, artist: Artist) -> bool:
        """
        Check if the artist has a URL relationship for the service used by this provider.
        :return: True if we're unable to check or if this artist has a URL, False otherwise.
        """

        domain = self.provider_domain()
        if any(domain in url for url in artist.urls):
            return True

        if artist.id not in self.missing_artists:
            print(f'\rNo {domain} URL found for artist {artist.name} [{artist.id}]')
            self.missing_artists[artist.id] = artist

        return False

    def get_mapped_provider_songs(
        self, track_release: Release, selector: Callable[[Release], T | None], fetcher: Callable[[T], list[S] | None]
    ) -> dict[str, S] | None:
        """
        Get songs for a track release, matched to its recordings.

        :param track_release: The release to fetch and map songs for.
        :param selector: A lambda function extracting a provider-specific identifier from a release if available.
        :param fetcher: A function that takes the provider-specific identifier and returns a list of songs.
        :return: A dictionary mapping recording MBIDs to provider-specific songs, or None if there was an error.
        """
        if track_release.id in self.cache:
            return self.cache[track_release.id]

        result = pick_release_from_release_group(track_release, selector)
        if not result:
            print(f'\rNo URL found for release {track_release.title} [{track_release.id}]')
            self.cache[track_release.id] = None
            self.missing_releases[track_release.id] = track_release
            return None
        matched_release, album_id = result

        provider_songs = fetcher(album_id)
        if not provider_songs:
            self.cache[track_release.id] = None
            return None

        # Ensure track count matches
        if len(provider_songs) != matched_release.get_track_count():
            print(f'\rTrack count mismatch for release {track_release.title} [{track_release.id}]')
            self.cache[track_release.id] = None
            return None

        # Match recordings to songs
        mapped_songs = {}

        # Iterate over all tracks in the release
        for medium in matched_release.media:
            for track in medium['tracks']:
                recording_mbid: str = track['recording']['id']
                try:
                    # Match song by track number if possible
                    track_number = int(track['number'])
                    song = next(song for song in provider_songs if song.album_index == track_number)
                except (ValueError, StopIteration):
                    # Fall back to track position
                    track_index = track['position'] - 1
                    if track_index >= len(provider_songs):
                        continue
                    song = provider_songs[track_index]

                mapped_songs[recording_mbid] = song

        self.cache[track_release.id] = mapped_songs

        return mapped_songs
