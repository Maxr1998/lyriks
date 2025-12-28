from abc import ABC, abstractmethod

from lyriks.lyrics import Lyrics
from lyriks.mb_client import Release, Artist


class Song(ABC):
    """
    Represents a song in a provider-specific context.
    """
    pass


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
    def fetch_song_by_id(self, song_id: int | str) -> Song | None:
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
    def has_artist_url(self, artist: Artist) -> bool:
        """
        Check if the artist has a URL relationship for the service used by this provider.
        :return: True if we're unable to check or if this artist has a URL, False otherwise.
        """
        pass
