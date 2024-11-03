from pathlib import Path

import click

from .const import PROGNAME, VERSION
from .default_group import DefaultGroup
from .lyrics_fetcher import main


@click.group(
    cls=DefaultGroup,
    default_command='sync',
    no_args_is_help=True,
    invoke_without_command=True,
    context_settings=dict(
        ignore_unknown_options=True,
        max_content_width=160,
    ),
)
def cli():
    pass


@cli.command()
@click.option(
    '-a', '--check-artist', is_flag=True,
    help='ensure artist has a Genie URL when processing albums',
)
@click.option(
    '-n', '--dry-run', is_flag=True,
    help='fetch lyrics without writing them to files',
)
@click.option(
    '-u', '--upgrade', is_flag=True,
    help='upgrade existing static lyrics to timed lyrics if possible',
)
@click.option(
    '-f', '--force', is_flag=True,
    help='force fetching lyrics for all tracks, even if they already have them'
         ' - THIS WILL OVERWRITE EXISTING LYRICS FILES!',
)
@click.option(
    '-I', '--skip-instrumentals', is_flag=True,
    help='skip instrumental tracks',
)
@click.option(
    '-R', '--report', 'report_path', is_flag=False, flag_value='report.html', type=click.Path(),
    help='write a HTML report of releases missing album URLs to a file at PATH'
         ' (default: report.html in the current directory)',
)
@click.argument('collection_path', type=click.Path(exists=True))
@click.version_option(
    VERSION, '-v', '--version',
    prog_name=PROGNAME,
    message='%(prog)s %(version)s',
    help='show the version and exit',
)
@click.help_option(
    '-h', '--help',
    help='show this message and exit',
)
def sync(
        check_artist: bool,
        dry_run: bool,
        upgrade: bool,
        force: bool,
        skip_instrumentals: bool,
        report_path: str,
        collection_path: str,
):
    """
    A command line tool that fetches lyrics from Genie.
    """
    report_path = Path(report_path) if report_path else None
    collection_path = Path(collection_path)
    main(check_artist, dry_run, upgrade, force, skip_instrumentals, report_path, collection_path)
