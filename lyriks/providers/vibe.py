import re

from lyriks.lyrics import Lyrics
from lyriks.mb_client import Release
from .api import vibe_api
from .api.vibe_api import VibeSong
from .provider import Provider
from .registry import register_provider


@register_provider('vibe')
class Vibe(Provider[int, VibeSong]):
    """
    Provider for Naver Vibe.
    """

    provider_domain = 'vibe.naver.com'
    album_pattern = re.compile(r'https://vibe.naver.com/album/(\d+)')

    def extract_album_id(self, release: Release) -> int | None:
        return release.extract_url_id(self.album_pattern)

    async def fetch_album_songs(self, album_id: int) -> list[VibeSong] | None:
        return await vibe_api.get_album_songs(self.http_client, album_id)

    async def fetch_song_by_id(self, song_id: int) -> VibeSong | None:
        return await vibe_api.get_song_info(self.http_client, song_id)

    async def fetch_song_lyrics(self, song: VibeSong) -> Lyrics | None:
        return await vibe_api.get_song_lyrics(self.http_client, song)
