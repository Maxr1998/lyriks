import re
import time

import requests
from requests import JSONDecodeError

from .const import VERSION

API_URL = 'https://musicbrainz.org/ws/2'
USER_AGENT = f'lyriks/{VERSION} ( max@maxr1998.de )'
_ARTIST_INC = 'url-rels'
_RELEASE_INC = 'artist-credits+recordings+media+url-rels'

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
            relation['url']['resource'] for relation in data.get('relations', [])
            if relation.get('target-type') == 'url'
        }
        self.has_genie_url: bool = any('genie.co.kr' in url for url in self.urls)


class Release:
    def __init__(self, data: dict):
        self.data = data
        self.id: str = data['id']
        self.title: str = data['title']
        self.artist_credit: dict = data['artist-credit']
        self.media: list = self.data['media']

    def get_track_count(self) -> int:
        return sum(medium['track-count'] for medium in self.media)

    def get_track_map(self) -> list[dict[str, dict]]:
        return [{track['id']: track for track in medium['tracks']} for medium in self.media]

    def get_genie_album_id(self) -> int | None:
        relations = self.data['relations']
        for relation in relations:
            if relation.get('target-type') != 'url' or relation.get('ended'):
                continue
            url = relation['url']['resource']
            match = re.fullmatch(r'https://(?:www.)?genie.co.kr/detail/albumInfo\?axnm=(\d+).*', url)
            if match:
                album_id = match.group(1)
                try:
                    return int(album_id)
                except ValueError:
                    print(f"Invalid album ID: {album_id}")
                    return None
        return None


def get_artist(artist_mbid: str) -> Artist | None:
    handle_rate_limit()

    artist_url = f'{API_URL}/artist/{artist_mbid}?inc={_ARTIST_INC}'
    response = requests.get(artist_url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'})
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

    response = requests.get(browse_url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'})
    try:
        response_json = response.json()
    except JSONDecodeError:
        return []

    return [Release(release) for release in response_json.get("releases", [])]


def get_release_by_track(track_mbid: str) -> Release | None:
    return next(iter(get_releases(f'{API_URL}/release?track={track_mbid}&status=official&inc={_RELEASE_INC}')), None)


def get_releases_by_release_group(rg_mbid: str) -> list[Release]:
    return get_releases(f'{API_URL}/release?release-group={rg_mbid}&status=official&inc={_RELEASE_INC}')
