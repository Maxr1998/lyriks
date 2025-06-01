import os
from dataclasses import dataclass


def opener(path: str, flags: int) -> int:
    return os.open(path, flags, 0o644)


@dataclass
class Lyrics:
    song_id: int
    song_title: str
    lines: list[str]
    is_synced: bool

    def write_to_file(self, path: str):
        with open(path, 'w', encoding='utf-8', opener=opener) as f:
            f.writelines(self.lines)

    @staticmethod
    def synced(song_id, song_title: str, lyrics_dict: dict[int, str]) -> 'Lyrics':
        """
        Constructs a synced lyrics object from a dict of timestamps/lines.
        """
        return Lyrics(song_id, song_title, _convert_to_lrc(lyrics_dict), is_synced=True)

    @staticmethod
    def static(song_id, song_title: str, lyrics: list[str]) -> 'Lyrics':
        return Lyrics(song_id, song_title, [line + '\n' for line in lyrics], is_synced=False)


def _convert_to_lrc(lyrics_dict: dict[int, str]) -> list[str]:
    """
    Takes a dict of millis/lines and converts it to the lrc format.
    """
    sorted_lines = sorted(lyrics_dict.items())
    formatted_lines = [f'{_millis_to_lrc_timestamp(timestamp)}{line}\n' for timestamp, line in sorted_lines]
    return formatted_lines


def _millis_to_lrc_timestamp(timestamp: int) -> str:
    minutes = timestamp // 60000
    seconds = (timestamp % 60000) // 1000
    centis = (timestamp % 1000) // 10
    return f'[{minutes:02d}:{seconds:02d}.{centis:02d}]'
