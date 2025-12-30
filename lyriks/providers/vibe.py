from lyriks import Provider
from lyriks.lyrics import Lyrics
from lyriks.mb_client import Release
from .api import vibe_api
from .api.vibe_api import VibeSong
from .registry import register_provider


@register_provider('vibe')
class Vibe(Provider):
    """
    Provider for Naver Vibe.
    """

    def fetch_recording_lyrics(self, track_release: Release, recording_mbid: str) -> Lyrics | None:
        # Resolve album
        vibe_songs = self.get_mapped_provider_songs(
            track_release,
            lambda r: r.extract_url_id(r'https://vibe.naver.com/album/(\d+)'),
            vibe_api.get_album_songs,
        )
        if not vibe_songs:
            return None

        # Get song for recording
        vibe_song = vibe_songs.get(recording_mbid)
        if not vibe_song:
            return None

        # Fetch lyrics
        return self.fetch_provider_song_lyrics(vibe_song)

    def fetch_song_by_id(self, song_id: int) -> VibeSong | None:
        return vibe_api.get_song_info(song_id)

    def fetch_provider_song_lyrics(self, song: VibeSong) -> Lyrics | None:
        return vibe_api.get_song_lyrics(song)

    @property
    def provider_domain(self) -> str:
        return 'vibe.naver.com'
