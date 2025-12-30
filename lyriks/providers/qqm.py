from lyriks.lyrics import Lyrics
from lyriks.mb_client import Release
from . import Provider
from .api import qqm_api
from .api.qqm_api import QQMSong
from .registry import register_provider


@register_provider('qq', 'qqm', 'qqmusic')
class QQMusic(Provider):
    """
    Provider for QQ Music.
    """

    def fetch_recording_lyrics(self, track_release: Release, recording_mbid: str) -> Lyrics | None:
        # Resolve album
        qqm_songs = self.get_mapped_provider_songs(
            track_release,
            lambda r: r.get_qqm_album_mid(),
            qqm_api.get_album_songs,
        )
        if not qqm_songs:
            return None

        # Get song for recording
        qqm_song = qqm_songs.get(recording_mbid)
        if not qqm_song:
            return None

        # Fetch lyrics
        return self.fetch_provider_song_lyrics(qqm_song)

    def fetch_song_by_id(self, song_id: int) -> QQMSong | None:
        return qqm_api.get_song_info(song_id)

    def fetch_provider_song_lyrics(self, song: QQMSong) -> Lyrics | None:
        return qqm_api.get_song_lyrics(song)

    def provider_domain(self) -> str:
        return 'y.qq.com'
