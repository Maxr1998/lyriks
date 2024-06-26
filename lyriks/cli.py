import argparse
from pathlib import Path

PROGNAME = 'lyriks'
VERSION = '0.3.2'


def parse_arguments():
    parser = argparse.ArgumentParser(prog=PROGNAME, description='A command line tool that fetches lyrics from Genie.')
    path_help = f"""
                The path to the music collection.
                {PROGNAME} will recursively search for music files in this directory.
                """
    parser.add_argument('collection_path', type=Path, metavar='path', help=path_help)
    parser.add_argument('-a', '--check-artist',
                        action='store_true',
                        help='ensure artist has a Genie URL when processing albums')
    parser.add_argument('-n', '--dry-run', action='store_true', help='fetch lyrics without writing them to files')
    parser.add_argument('-f', '--force',
                        action='store_true',
                        help='force fetching lyrics for all tracks, even if they already have them'
                             ' - THIS WILL OVERWRITE EXISTING LYRICS FILES!')
    parser.add_argument('-I', '--skip-instrumentals',
                        action='store_true',
                        help='skip instrumental tracks')
    parser.add_argument('-R', '--report',
                        type=Path, nargs='?', metavar='path', const='report.html',
                        help='write a HTML report of releases missing album URLs to a file at [path]'
                             ' (default: report.html in the current directory)')
    parser.add_argument('-v', '--version', action='version', version='%(prog)s ' + VERSION)

    return parser.parse_args()
