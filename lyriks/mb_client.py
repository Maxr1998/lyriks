import re
import time

import requests
from requests import JSONDecodeError

API_URL = 'https://musicbrainz.org/ws/2'
USER_AGENT = 'lyriks/0.1.0 ( max@maxr1998.de )'

last_request_time = 0


class Release:
    def __init__(self, data: dict):
        self.data = data
        self.id = data['id']
        self.title = data['title']

    def get_track_count(self) -> int:
        return sum([media['track-count'] for media in self.data['media']])

    def get_genie_album_id(self) -> int | None:
        relations = self.data['relations']
        for relation in relations:
            if relation.get('target-type') != 'url':
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


def get_releases(browse_url: str) -> list[Release]:
    global last_request_time
    time_since = time.time() - last_request_time
    if time_since < 1:
        time.sleep(1 - time_since)
    response = requests.get(browse_url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'})
    last_request_time = time.time()

    try:
        response_json = response.json()
    except JSONDecodeError:
        return []

    return [Release(release) for release in response_json.get("releases", [])]


def get_release_by_track(track_mbid: str) -> Release | None:
    return next(iter(get_releases(f'{API_URL}/release?track={track_mbid}&status=official&inc=media+url-rels')), None)


def get_releases_by_release_group(rg_mbid: str) -> list[Release]:
    return get_releases(f'{API_URL}/release?release-group={rg_mbid}&status=official&inc=media+url-rels')
