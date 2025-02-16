from abc import ABC, abstractmethod
from typing import Callable

from lyriks.lyrics import Lyrics
from lyriks.mb_client import Release, Artist, get_releases_by_release_group


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
    def fetch_lyrics(self, track_release: Release, recording_mbid: str) -> Lyrics | None:
        """
        Fetch lyrics for a single song, given by its recording MBID and the actual release it appears on.
        """
        pass

    @abstractmethod
    def fetch_single_song(self, track_id):
        """
        Fetch lyrics for a specific song. The track_id uniquely identifies the song, its format is provider-specific.
        """
        pass

    @abstractmethod
    def has_artist_url(self, artist: Artist) -> bool:
        """
        Check if the artist has a URL relationship for the service used by this provider.
        :return: True if we're unable to check or if this artist has a URL, False otherwise.
        """
        pass

    def pick_release_from_release_group(self, release: Release, selector: Callable[[Release], int | None]):
        """
        TODO: write docs, rename method and remove "album ID" references
        """
        # Try to get the album ID from the release itself first
        selection = selector(release)
        if selection is not None:
            return release, selection

        # If that fails, check all releases from the release group
        rg_releases = get_releases_by_release_group(release.rg_mbid)
        if not rg_releases:
            return None, None

        # Sort releases by track count delta
        track_release_track_count = release.get_track_count()
        rg_releases = sorted(rg_releases, key=lambda r: abs(r.get_track_count() - track_release_track_count))

        # Return the first release group release with a Genie URL
        for rg_release in rg_releases:
            selection = selector(rg_release)
            if selection is not None:
                return rg_release, selection

        print(f'No URL found for release {release.title} [{release.id}]')
        self.missing_releases[release.id] = release

        return None, None
