from typing import Callable, TypeVar

from httpx import Client as HttpClient

from lyriks.mb_client import Release, get_releases_by_release_group

T = TypeVar('T')


def pick_release_from_release_group(
    http_client: HttpClient,
    release: Release,
    selector: Callable[[Release], T | None],
) -> tuple[Release, T] | None:
    """
    Pick a release from the release's release group that matches the given selector.

    Attempts to match the release itself first, then checks all releases in the release group,
    sorted by an increasing track count delta from the original release.
    This ensures the most similar release is chosen.
    """

    # Try to match the release itself first
    selection = selector(release)
    if selection is not None:
        return release, selection

    # If that fails, check all releases from the release group
    rg_releases = get_releases_by_release_group(http_client, release.rg_mbid)
    if not rg_releases:
        return None

    # Sort releases by track count delta
    track_release_track_count = release.get_track_count()
    rg_releases = sorted(rg_releases, key=lambda r: abs(r.get_track_count() - track_release_track_count))

    # Return the first matching release
    for rg_release in rg_releases:
        selection = selector(rg_release)
        if selection is not None:
            return rg_release, selection

    return None
