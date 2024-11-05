# lyriks [![License][license-badge]][license-link] [![PyPI version][version-badge]][version-link] ![PyPI downloads][pypi-downloads]

A command line tool that fetches lyrics from [Genie](https://www.genie.co.kr/).

### Installation

You can easily install lyriks from PyPI by using `pip`:

```bash
pip install lyriks
```

To install it from source instead, clone the repository and build the wheel before installing it with pip:

```bash
python -m build --wheel
pip install dist/lyriks-0.4.0-py3-none-any.whl
```

You can also run the script directly from within the repository:

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

### Exclude files and folders

You can recursively ignore folders by adding a (empty) `.nolyrics` file inside the folder you want to exclude.
This can be useful for Western artists, where Genie is unlikely to have lyrics, or for instrumental releases.

Likewise, you can ignore specific songs by creating a file with the same name as the audio file
but the extension changed to `.nolyrics`.
For example, a track named `01 Song.flac` can be excluded by creating a file named `01 Song.nolyrics`.

Excluded files won't be queried at all, which can noticeably speed up the synchronisation process for large collections.

[license-badge]: https://img.shields.io/github/license/Maxr1998/lyriks

[license-link]: LICENSE

[version-badge]: https://img.shields.io/pypi/v/lyriks

[version-link]: https://pypi.org/project/lyriks/

[pypi-downloads]: https://img.shields.io/pypi/dm/lyriks

[rgid]: https://picard-docs.musicbrainz.org/en/appendices/tag_mapping.html#musicbrainz-release-group-id

[tid]: https://picard-docs.musicbrainz.org/en/appendices/tag_mapping.html#id24
