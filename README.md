# LyricsFetcher

A command line tool that fetches lyrics from [Genie](http://www.genie.co.kr/).

### Installation

Build the wheel and install it with pip:

```bash
python -m build --wheel
pip install dist/lyrics_fetcher-0.0.1-py3-none-any.whl
```

Alternatively, you can directly run the script from the repository:

```bash
`./fetch-lyrics /path/to/music/folder`
```

Make sure to first install the required dependencies from `pyproject.toml`.

### Usage

Simply run the script with the path to the folder containing your music as an argument:

```bash
fetch-lyrics /path/to/music/folder
```

The script will search for audio files (`.flac` or `.mp3`) in the folder and fetch the lyrics for each song.
The lyrics will be saved in a `.lrc` or `.txt` file with the same name as the audio file.
