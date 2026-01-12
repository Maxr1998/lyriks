import re

from lyriks.lyrics import Lyrics
from lyriks.mb_client import Release
from .api import qqm_api
from .api.qqm_api import QQMSong
from .provider import Provider
from .registry import register_provider


@register_provider('qq', 'qqm', 'qqmusic')
class QQMusic(Provider[str, QQMSong]):
    """
    Provider for QQ Music.
    """

    provider_domain = 'y.qq.com'
    album_pattern = re.compile(r'https://y.qq.com/n/ryqq(?:_v2)?/albumDetail/(\w+)')

    def extract_album_id(self, release: Release) -> str | None:
        return release.extract_url_str(self.album_pattern)

    async def fetch_album_songs(self, album_id: str) -> list[QQMSong] | None:
        return await qqm_api.get_album_songs(self.http_client, album_id)

    async def fetch_song_by_id(self, song_id: int) -> QQMSong | None:
        return await qqm_api.get_song_info(self.http_client, song_id)

    async def fetch_song_lyrics(self, song: QQMSong) -> Lyrics | None:
        return await qqm_api.get_song_lyrics(self.http_client, song)
