import re

from lyriks.lyrics import Lyrics
from lyriks.mb_client import Release
from .api import bugs_api
from .api.bugs_api import BugsSong
from .provider import Provider
from .registry import register_provider


@register_provider('bugs')
class Bugs(Provider[int, BugsSong]):
    """
    Provider for Bugs!
    """

    provider_domain = 'music.bugs.co.kr'
    album_pattern = re.compile(r'https://music.bugs.co.kr/album/(\d+).*')

    def extract_album_id(self, release: Release) -> int | None:
        return release.extract_url_id(self.album_pattern)

    async def fetch_album_songs(self, album_id: int) -> list[BugsSong] | None:
        return await bugs_api.get_album_songs(self.http_client, album_id)

    async def fetch_song_by_id(self, song_id: int) -> BugsSong | None:
        return await bugs_api.get_song_info(self.http_client, song_id)

    async def fetch_song_lyrics(self, song: BugsSong) -> Lyrics | None:
        return await bugs_api.get_song_lyrics(self.http_client, song)
