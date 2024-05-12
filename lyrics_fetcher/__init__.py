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
        fetcher.fetch_lyrics(file)