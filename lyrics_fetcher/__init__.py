import glob
from os import path
from sys import argv

from .lyrics_fetcher import LyricsFetcher


def main():
    if len(argv) != 2:
        print('No path provided')
        exit(1)
    collection_path = argv[1]

    fetcher = LyricsFetcher()

    files = glob.iglob(path.join(collection_path, '**/*.*'), recursive=True)
    for file in files:
        if path.isdir(file):
            continue
        if not file.lower().endswith('.flac') and not file.lower().endswith('.mp3'):
            continue
        fetcher.fetch_lyrics(file)
