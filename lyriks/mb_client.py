import re
import time
from json.decoder import JSONDecodeError
from typing import AnyStr

import trio
from httpx import AsyncClient as HttpClient
from httpx import RequestError
from rich.markup import escape
from stamina import retry
from trio import Lock

from .cli.console import console
from .const import VERSION

MB_URL = 'https://musicbrainz.org'
API_URL = f'{MB_URL}/ws/2'
USER_AGENT = f'lyriks/{VERSION} ( max@maxr1998.de )'
_ARTIST_INC = 'url-rels'
_RELEASE_INC = 'artist-credits+release-groups+recordings+media+url-rels'


class Artist:
    def __init__(self, data: dict):
        self.data = data
        self.id: str = data['id']
        self.name: str = data['name']
        self.urls: set = {
            relation['url']['resource']
            for relation in data.get('relations', [])
            if relation.get('target-type') == 'url'
        }

    @property
    def url(self):
        return f'{MB_URL}/artist/{self.id}'

    @property
    def rich_string(self) -> str:
        return f'[underline][link={self.url}]{escape(self.name)}[/link][/underline]'


class Release:
    def __init__(self, data: dict):
        self.data = data
        self.id: str = data['id']
        self.title: str = data['title']
        self.artist_credit: dict = data['artist-credit']
        self.rg_mbid: str = data['release-group']['id']
        self.media: list = self.data['media']

    def get_track_count(self) -> int:
        return sum(medium['track-count'] for medium in self.media)

    def get_track_map(self) -> list[dict[str, dict]]:
        return [{track['id']: track for track in medium['tracks']} for medium in self.media]

    @property
    def url(self):
        return f'{MB_URL}/release/{self.id}'

    @property
    def rich_string(self) -> str:
        return f'[underline][link={self.url}]{escape(self.title)}[/link][/underline]'

    def extract_url_str(self, pattern: AnyStr) -> str | None:
        """
        Extracts an ID from the release's URL relations using the provided RegEx pattern.
        The pattern must contain exactly one capturing group for the ID.
        """
        pattern_obj = re.compile(pattern)
        if pattern_obj.groups != 1:
            raise ValueError("Pattern must contain exactly one capturing group: %r" % pattern)

        relations = self.data['relations']
        for relation in relations:
            if relation.get('target-type') != 'url' or relation.get('ended'):
                continue
            url = relation['url']['resource']
            match = pattern_obj.fullmatch(url)
            if match:
                return match.group(1)
        return None

    def extract_url_id(self, pattern: AnyStr) -> int | None:
        """
        Extracts an integer ID from the release's URL relations using the provided RegEx pattern.
        The pattern must contain exactly one capturing group for the ID.
        """
        id_str = self.extract_url_str(pattern)
        if id_str is None:
            return None

        try:
            return int(id_str)
        except ValueError:
            return None


class RequestRateLimiter:
    def __init__(self, delay: float):
        self.delay: float = delay
        self.lock: Lock = Lock()
        self.last_request_time: float = 0

    async def __aenter__(self):
        await self.lock.acquire()
        time_since = time.time() - self.last_request_time
        if time_since <= self.delay:
            await trio.sleep(self.delay - time_since)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.last_request_time = time.time()
        self.lock.release()


rate_limiter = RequestRateLimiter(delay=1.0)


@retry(on=RequestError, attempts=3)
async def get_artist(http_client: HttpClient, artist_mbid: str) -> Artist | None:
    async with rate_limiter:
        artist_url = f'{API_URL}/artist/{artist_mbid}?inc={_ARTIST_INC}'
        try:
            response = (
                await http_client.get(
                    artist_url,
                    headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'},
                )
            ).json()
        except JSONDecodeError:
            return None

    if 'error' in response:
        console.print(f'[bold red]Error: {escape(repr(response["error"]))}')
        return None

    return Artist(response)


@retry(on=RequestError, attempts=3)
async def get_releases(http_client: HttpClient, browse_url: str) -> list[Release]:
    async with rate_limiter:
        try:
            response = (
                await http_client.get(
                    browse_url,
                    headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'},
                )
            ).json()
        except JSONDecodeError:
            return []

    return [Release(release) for release in response.get("releases", [])]


async def get_release_by_track(http_client: HttpClient, track_mbid: str) -> Release | None:
    releases = await get_releases(
        http_client, f'{API_URL}/release?track={track_mbid}&status=official&inc={_RELEASE_INC}'
    )
    return next(iter(releases), None)


async def get_releases_by_release_group(http_client: HttpClient, rg_mbid: str) -> list[Release]:
    return await get_releases(
        http_client, f'{API_URL}/release?release-group={rg_mbid}&status=official&inc={_RELEASE_INC}'
    )
