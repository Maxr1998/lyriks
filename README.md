# lyriks [![License][license-badge]][license-link] [![PyPI version][version-badge]][version-link] ![PyPI downloads][pypi-downloads]

A command line tool that fetches lyrics from various streaming providers.

### Installation

You can install lyriks from PyPI using `uv` or `pip`:

```bash
# uv
uv tool install lyriks

# pip
pip install lyriks
```

To install it from source instead, clone the repository and build the wheel before installing it:

```bash
uv build

# uv
uv tool install dist/lyriks-*-py3-none-any.whl

# pip
pip install dist/lyriks-*-py3-none-any.whl
```

You can also run the script directly from within the repository:

```bash
./lyriks.py /path/to/music/folder
```

Make sure to first install the required dependencies from `pyproject.toml` (i.e. `uv sync`).

### Usage

Run the script with the path to the folder containing your music as an argument.
This can be your whole collection, a single artist, or a single album.

```bash
lyriks /path/to/music/folder
```

By default, lyrics are fetched from [Genie](https://www.genie.co.kr/),
but you can switch to other providers with the `--provider`/`-P` flag.

Currently supported providers are:

- [Genie](https://www.genie.co.kr/)
- [Bugs!](https://music.bugs.co.kr/)
- [Naver Vibe](https://vibe.naver.com/)
- [QQ Music](https://y.qq.com/)

The script will search for audio files (`.flac` or `.mp3`) in the given folder, and attempt to fetch the lyrics.
Note that it will only be able to do that for files that are properly tagged with MusicBrainz MBIDs
(specifically [`musicbrainz_releasegroupid`][rgid] and [`musicbrainz_trackid`][tid]).
It then uses them to resolve the provider ID from the release or release group on MusicBrainz.
Thus, at least one release in the release group must have an album URL relationship for the selected provider.

If successful, the lyrics will be downloaded and stored next to the audio files with the appropriate extension
(`.lrc` or `.txt`, depending on whether they're synced or not).

For more information on usage, check the help message:

```bash
lyriks --help
```

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
