# lyriks

A command line tool that fetches lyrics from [Genie](https://www.genie.co.kr/).

### Installation

Build the wheel and install it with pip:

```bash
python -m build --wheel
pip install dist/lyriks-0.3.2-py3-none-any.whl
```

Alternatively, you can directly run the script from the repository:

```bash
`./lyriks.py /path/to/music/folder`
```

Make sure to first install the required dependencies from `pyproject.toml`.

### Usage

Simply run the script with the path to the folder containing your music as an argument.
This can be your whole collection, a single artist, or a single album.

```bash
lyriks /path/to/music/folder
```

The script will search for audio files (`.flac` or `.mp3`) in the given folder, and attempt to fetch the lyrics.
Note that it will only be able to do that for files that are properly tagged with MusicBrainz MBIDs
(specifically [`musicbrainz_releasegroupid`][rgid] and [`musicbrainz_trackid`][tid]).
It then uses them to resolve the Genie album ID from the release or release group on MusicBrainz.
Thus, at least one release in the release group must have a URL relationship to the album on Genie.

If successful, the lyrics will be downloaded and stored next to the audio files with the appropriate extension
(`.lrc` or `.txt`, depending on whether they're synced or not).

[rgid]: https://picard-docs.musicbrainz.org/en/appendices/tag_mapping.html#musicbrainz-release-group-id

[tid]: https://picard-docs.musicbrainz.org/en/appendices/tag_mapping.html#id24
