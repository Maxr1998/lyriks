import os
import re
from os import path
from pathlib import Path
from sys import stderr


def fix_timed_lyrics(collection_path: Path):
    # Validate collection path
    if not collection_path.is_dir():
        print(f'Error: directory \'{collection_path}\' does not exist', file=stderr)
        exit(2)

    timestamp_pattern = re.compile(r'^\[(\d+):(\d{2}):(\d{2})]', flags=re.MULTILINE)

    for root_dir, dirs, files in os.walk(collection_path, topdown=True):
        if path.exists(path.join(root_dir, '.nolyrics')):
            dirs.clear()
            continue

        for file in files:
            extension = path.splitext(file)[1].lower()
            if extension == '.lrc':
                fix_timed_lyrics_file(root_dir, file, timestamp_pattern)


def fix_timed_lyrics_file(dirname: str, filename: str, timestamp_pattern: re.Pattern):
    filepath = path.join(dirname, filename)

    with open(filepath, 'r', encoding='utf-8') as f:
        file_content = f.read()

    new_content = timestamp_pattern.sub(r'[\1:\2.\3]', file_content)
    if new_content == file_content:
        return

    print(f'Fixing timed lyrics format for "{filename}"')
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
