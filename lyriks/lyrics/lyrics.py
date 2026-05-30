import os
from dataclasses import dataclass, field

from lyriks.const import PROGNAME
from .util import format_lrc_timestamp

LRC_KEY_ORDER = {'ti': 0, 'ar': 1, 'al': 2, 'by': 3, 're': 4, 'source': 5, 'offset': 6}


def opener(path: str, flags: int) -> int:
    return os.open(path, flags, 0o644)


@dataclass
class Lyrics:
    song_id: int
    song_title: str
    lines: list[str]
    is_synced: bool
    source: str
    extra_metadata: dict[str, str] = field(default_factory=dict)

    def write_to_file(self, path: str | None = None) -> str:
        path = path or f'{self.song_title}.{"lrc" if self.is_synced else "txt"}'
        with open(path, 'w', encoding='utf-8', opener=opener) as f:
            if self.is_synced:
                # Write metadata
                metadata = self.extra_metadata | {
                    'ti': self.song_title,
                    're': PROGNAME,
                    'source': self.source,
                }
                metadata_sorted = sorted(metadata.items(), key=lambda kv: LRC_KEY_ORDER.get(kv[0], 99))
                f.writelines(f'[{key}: {value}]\n' for key, value in metadata_sorted)
                f.write('\n')
            f.writelines(self.lines)
        return path

    @classmethod
    def from_dict(
        cls,
        song_id: int,
        song_title: str,
        lyrics_dict: dict[int, str],
        source: str,
        extra_metadata: dict[str, str] | None = None,
    ) -> 'Lyrics':
        """
        Constructs a synced lyrics object from a dict of timestamps/lines.
        """
        return cls(
            song_id=song_id,
            song_title=song_title,
            lines=_convert_to_lrc(lyrics_dict),
            is_synced=True,
            source=source,
            extra_metadata=extra_metadata or {},
        )


def _convert_to_lrc(lyrics_dict: dict[int, str]) -> list[str]:
    """
    Takes a dict of millis/lines and converts it to the lrc format.
    """
    sorted_lines = sorted(lyrics_dict.items())
    formatted_lines = [f'[{format_lrc_timestamp(timestamp)}]{line}\n' for timestamp, line in sorted_lines]
    return formatted_lines
