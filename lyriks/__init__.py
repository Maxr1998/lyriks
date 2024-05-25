import glob
from os import path

from .cli import parse_arguments
from .lyrics_fetcher import LyricsFetcher


def main():
    args = parse_arguments()

    collection_path = args.path

    fetcher = LyricsFetcher(args.dry_run, args.force)

    files = glob.iglob(path.join(collection_path, '**/*.*'), recursive=True)
    for file in files:
        if path.isdir(file):
            continue
        if not file.lower().endswith('.flac') and not file.lower().endswith('.mp3'):
            continue
        fetcher.fetch_lyrics(file)
