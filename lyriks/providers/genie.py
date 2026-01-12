import re

from lyriks.lyrics import Lyrics
from lyriks.mb_client import Release
from .api import genie_api
from .api.genie_api import GenieSong
from .provider import Provider
from .registry import register_provider


@register_provider('genie')
class Genie(Provider[int, GenieSong]):
    """
    Provider for Genie Music.
    """

    provider_domain = 'genie.co.kr'
    album_pattern = re.compile(r'https://(?:www.)?genie.co.kr/detail/albumInfo\?axnm=(\d+).*')

    def extract_album_id(self, release: Release) -> int | None:
        return release.extract_url_id(self.album_pattern)

    async def fetch_album_songs(self, album_id: int) -> list[GenieSong] | None:
        return await genie_api.get_album_songs(self.http_client, album_id)

    async def fetch_song_by_id(self, song_id: int) -> GenieSong | None:
        return await genie_api.get_song_info(self.http_client, song_id)

    async def fetch_song_lyrics(self, song: GenieSong) -> Lyrics | None:
        return await genie_api.get_song_lyrics(self.http_client, song)
