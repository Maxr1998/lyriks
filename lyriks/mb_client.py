import re
import time
from json.decoder import JSONDecodeError
from typing import AnyStr

import httpx

from .const import VERSION

API_URL = 'https://musicbrainz.org/ws/2'
USER_AGENT = f'lyriks/{VERSION} ( max@maxr1998.de )'
_ARTIST_INC = 'url-rels'
_RELEASE_INC = 'artist-credits+release-groups+recordings+media+url-rels'

last_request_time = 0


def handle_rate_limit():
    global last_request_time
    time_since = time.time() - last_request_time
    if time_since < 1:
        time.sleep(1 - time_since)
    last_request_time = time.time()


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


def get_artist(artist_mbid: str) -> Artist | None:
    handle_rate_limit()

    artist_url = f'{API_URL}/artist/{artist_mbid}?inc={_ARTIST_INC}'
    response = httpx.get(artist_url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'})
    try:
        response_json = response.json()
    except JSONDecodeError:
        print(f'Error: could not fetch artist data for {artist_mbid}')
        return None

    if 'error' in response_json:
        print(f'Error: {response_json["error"]}')
        return None

    return Artist(response_json)


def get_releases(browse_url: str) -> list[Release]:
    handle_rate_limit()

    response = httpx.get(browse_url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'})
    try:
        response_json = response.json()
    except JSONDecodeError:
        return []

    return [Release(release) for release in response_json.get("releases", [])]


def get_release_by_track(track_mbid: str) -> Release | None:
    return next(iter(get_releases(f'{API_URL}/release?track={track_mbid}&status=official&inc={_RELEASE_INC}')), None)


def get_releases_by_release_group(rg_mbid: str) -> list[Release]:
    return get_releases(f'{API_URL}/release?release-group={rg_mbid}&status=official&inc={_RELEASE_INC}')
