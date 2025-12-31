from lyriks.lyrics import Lyrics
from lyriks.mb_client import Release
from .api import genie_api
from .api.genie_api import GenieSong
from .provider import Provider
from .registry import register_provider


@register_provider('genie')
class Genie(Provider):
    """
    Provider for Genie Music.
    """

    def fetch_recording_lyrics(self, track_release: Release, recording_mbid: str) -> Lyrics | None:
        # Resolve Genie album
        genie_songs = self.get_mapped_provider_songs(
            track_release,
            lambda r: r.extract_url_id(r'https://(?:www.)?genie.co.kr/detail/albumInfo\?axnm=(\d+).*'),
            genie_api.get_album_songs,
        )
        if not genie_songs:
            return None

        # Get Genie song for recording
        genie_song = genie_songs.get(recording_mbid)
        if not genie_song:
            return None

        # Fetch lyrics
        return self.fetch_provider_song_lyrics(genie_song)

    def fetch_song_by_id(self, song_id: int) -> GenieSong | None:
        stream_info = genie_api.get_stream_info(song_id)
        if stream_info is None:
            return None

        try:
            album_id = int(stream_info['ALBUM_ID'])
        except KeyError | ValueError:
            return None

        genie_songs = genie_api.get_album_songs(album_id)
        if not genie_songs:
            return None

        return next((s for s in genie_songs if s.id == song_id), None)

    def fetch_provider_song_lyrics(self, song: GenieSong) -> Lyrics | None:
        return genie_api.get_song_lyrics(song)

    @property
    def provider_domain(self) -> str:
        return 'genie.co.kr'
