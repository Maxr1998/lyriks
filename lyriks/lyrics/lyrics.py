import os
from dataclasses import dataclass

from lyriks.const import PROGNAME
from .util import format_lrc_timestamp


def opener(path: str, flags: int) -> int:
    return os.open(path, flags, 0o644)


@dataclass
class Lyrics:
    song_id: int
    song_title: str
    lines: list[str]
    is_synced: bool
    source: str

    def write_to_file(self, path: str | None = None) -> str:
        path = path or f'{self.song_title}.{"lrc" if self.is_synced else "txt"}'
        with open(path, 'w', encoding='utf-8', opener=opener) as f:
            if self.is_synced:
                metadata = [
                    f'[ti: {self.song_title}]\n',
                    f'[re: {PROGNAME}]\n',
                    f'[source: {self.source}]\n',
                    '\n',
                ]
                f.writelines(metadata)
            f.writelines(self.lines)
        return path

    @classmethod
    def from_dict(cls, song_id: int, song_title: str, lyrics_dict: dict[int, str], source: str) -> 'Lyrics':
        """
        Constructs a synced lyrics object from a dict of timestamps/lines.
        """
        return cls(
            song_id=song_id,
            song_title=song_title,
            lines=_convert_to_lrc(lyrics_dict),
            is_synced=True,
            source=source,
        )


def _convert_to_lrc(lyrics_dict: dict[int, str]) -> list[str]:
    """
    Takes a dict of millis/lines and converts it to the lrc format.
    """
    sorted_lines = sorted(lyrics_dict.items())
    formatted_lines = [f'[{format_lrc_timestamp(timestamp)}]{line}\n' for timestamp, line in sorted_lines]
    return formatted_lines
