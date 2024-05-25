import glob
from os import path
from pathlib import Path
from sys import stderr

from .cli import parse_arguments
from .lyrics_fetcher import LyricsFetcher


def main():
    args = parse_arguments()

    collection_path = args.path
    report_path: Path = args.report

    # Normalize and validate report path
    if report_path:
        report_path = report_path.expanduser().absolute()
        if report_path.is_dir():
            report_path = report_path / 'report.html'
        if not report_path.parent.exists():
            print(f'Error: directory \'{report_path.parent}\' does not exist', file=stderr)
            exit(2)

    fetcher = LyricsFetcher(args.dry_run, args.force)

    files = glob.iglob(path.join(collection_path, '**/*.*'), recursive=True)
    for file in files:
        if path.isdir(file):
            continue
        if not file.lower().endswith('.flac') and not file.lower().endswith('.mp3'):
            continue
        fetcher.fetch_lyrics(file)

    if report_path:
        try:
            fetcher.write_report(report_path)
        except OSError:
            print(f'Error: could not write report to \'{report_path}\'', file=stderr)
            exit(2)
