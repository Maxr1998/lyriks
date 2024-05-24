import argparse

PROGNAME = 'lyriks'


def parse_arguments():
    parser = argparse.ArgumentParser(prog=PROGNAME, description='A command line tool that fetches lyrics from Genie.')
    path_help = f"""
                The path to the music collection.
                {PROGNAME} will recursively search for music files in this directory.
                """
    parser.add_argument('path', type=str, help=path_help)

    return parser.parse_args()
