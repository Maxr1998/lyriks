import json
import random
import re
import zlib
from dataclasses import dataclass, field
from datetime import datetime
from json import JSONDecodeError

import lxml.etree as xml
import pyqqmusicdes
from httpx import Client as HttpClient
from httpx import RequestError
from lxml.etree import XMLParser
from stamina import retry

from lyriks.lib.zzc_sign import zzc_sign
from lyriks.lyrics import Lyrics
from lyriks.lyrics.util import format_lrc_timestamp
from .song import Song

xml.set_default_parser(XMLParser(no_network=True, recover=True, remove_blank_text=True))

QQM_API_URL = "https://u.y.qq.com/cgi-bin/musicu.fcg"
QQM_COMM = {
    'cv': 4747474,
    'ct': 24,
    'format': 'json',
    'inCharset': 'utf-8',
    'outCharset': 'utf-8',
    'notice': 0,
    'platform': 'yqq.json',
    'needNewCode': 1,
    'uin': ''.join(random.sample('1234567890', 10)),
    'g_tk_new_20200303': 1077614320,
    'g_tk': 1077614320,
}
QQM_LYRICS_API_URL = "https://c.y.qq.com/qqmusic/fcgi-bin/lyric_download.fcg"
QQM_DES_KEY = b'!@#)(*$%123ZXC!@!@#)(NHL'

CHROME_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)

LYRIC_CONTENT_TAG = 'LyricContent'
LYRIC_CONTENT_REGEX = re.compile(r'LyricContent="([\s\S]*?)"\s*/>')


@dataclass
class QQMSong(Song):
    mid: str
    artists: list[str] = field(default_factory=list)

    @classmethod
    def from_song_info(cls, song_info: dict) -> 'QQMSong':
        try:
            song_id = song_info['id']
            song_mid = song_info['mid']
            album_index = song_info['index_album']
            title = song_info['title']
            artists = [artist['name'] for artist in song_info['singer']]
        except KeyError:
            raise ValueError("Invalid song info data")

        return cls(id=song_id, mid=song_mid, album_index=album_index, title=title, artists=artists)


@retry(on=RequestError, attempts=3)
def _qqm_request(http_client: HttpClient, modules: list[dict]) -> list[dict]:
    request = dict([('comm', QQM_COMM)] + [(f'req_{i + 1}', module) for i, module in enumerate(modules)])
    body = json.dumps(request)
    signature = zzc_sign(body)

    try:
        response = http_client.post(
            QQM_API_URL,
            params={
                "_": int(datetime.now().timestamp() * 1000),
                "sign": signature,
            },
            headers={
                "Accept": "application/json",
                "Accept-Language": "en-DE,en;q=1",
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://y.qq.com",
                "Referer": "https://y.qq.com/",
                "User-Agent": CHROME_USER_AGENT,
            },
            content=body,
        ).json()
    except JSONDecodeError:
        return []

    try:
        response_modules = [response[f'req_{i + 1}'] for i in range(len(modules))]
    except KeyError:
        return []

    return response_modules


def get_album_songs(http_client: HttpClient, album_mid: str) -> list[QQMSong]:
    response = _qqm_request(
        http_client,
        [
            {
                'module': 'music.musichallAlbum.AlbumSongList',
                'method': 'GetAlbumSongList',
                'param': {'albumMid': album_mid, 'albumID': 0, 'begin': 0, 'num': 100, 'order': 2},
            }
        ],
    )

    if not response:
        return []

    try:
        song_infos = [song['songInfo'] for song in response[0]['data']['songList']]
    except IndexError | KeyError:
        return []

    try:
        return [QQMSong.from_song_info(song_info) for song_info in song_infos]
    except ValueError:
        return []


def get_song_info(http_client: HttpClient, song_id: int) -> QQMSong | None:
    response = _qqm_request(
        http_client,
        [
            {
                "module": "music.trackInfo.UniformRuleCtrl",
                "method": "CgiGetTrackInfo",
                "param": {"ids": [song_id], "types": [0]},
            }
        ],
    )

    if not response:
        return None

    try:
        song_info = response[0]['data']['tracks'][0]
    except IndexError | KeyError:
        return None

    return QQMSong.from_song_info(song_info)


@retry(on=RequestError, attempts=3)
def get_song_lyrics(http_client: HttpClient, song: QQMSong) -> Lyrics | None:
    request = {
        "version": "15",
        "miniversion": "82",
        "lrctype": "4",
        "musicid": song.id,
    }

    response = http_client.post(
        QQM_LYRICS_API_URL,
        headers={
            "Accept": "application/xml",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "https://c.y.qq.com/",
            "User-Agent": CHROME_USER_AGENT,
        },
        data=request,
    ).text

    if response is None:
        return None

    # Remove surrounding comment tags
    response_text = response.replace("<!--", "").replace("-->", "")

    # Parse main XML response
    root = xml.fromstring(response_text)
    lyric_node = root.find(".//lyric")
    if lyric_node is None:
        return None

    content_node = lyric_node.find('content')
    if content_node is None:
        return None

    content_text = _decrypt_content_node(content_node)
    if content_text is None:
        return None

    # The XML is malformed (unescaped quotes inside attribute) and contains newlines.
    # Thus, as standard XML parsers would fail, we use a regex to extract the content.
    match = LYRIC_CONTENT_REGEX.search(content_text)
    if not match:
        return None

    lyric_content = match.group(1)
    lines = lyric_content.splitlines()
    lines = _convert_qrc_to_lrc(lines)

    return Lyrics(song_id=song.id, song_title=song.title, lines=lines, is_synced=True)


def _decrypt_content_node(content_node) -> str | None:
    content = content_node.text
    if content is None:
        return None

    content = content.strip()
    if len(content) == 0:
        return None

    buf = bytes.fromhex(content)

    res = pyqqmusicdes.decrypt_des(buf, QQM_DES_KEY)
    if res != 0:
        return None

    try:
        buf = zlib.decompress(buf)
    except zlib.error:
        return None

    try:
        content_text = buf.decode('utf-8')
    except UnicodeDecodeError:
        return None

    return content_text


def _convert_qrc_to_lrc(lines: list[str]) -> list[str] | None:
    """
    Converts lines from QRC format to LRC format.
    """
    lrc_lines = []
    metadata_regex = re.compile(r'\[[a-z]+:[^]]*]')
    line_timestamp_regex = re.compile(r'\[(\d+),(\d+)]')
    words_regex = re.compile(r'(.*?)\((\d+),(\d+)\)')

    for line in lines:
        if not line.startswith('['):
            # Ignore lines without a start tag
            continue

        if metadata_regex.match(line):
            # Copy metadata lines as-is
            lrc_lines.append(f'{line}\n')
            continue

        line_timestamp_match = line_timestamp_regex.match(line)
        if not line_timestamp_match:
            # Abort on malformed lines
            return None

        line_start = int(line_timestamp_match.group(1))
        lrc_line_timestamp = f'[{format_lrc_timestamp(line_start)}]'

        line_content_start = line_timestamp_match.end()
        line_content = line[line_content_start:]

        timed_words = words_regex.findall(line_content)
        lrc_line = ''
        for word, start_str, duration_str in timed_words:
            start = int(start_str)
            end = start + int(duration_str)
            lrc_line += f'<{format_lrc_timestamp(start)}>{word}<{format_lrc_timestamp(end)}>'

        lrc_lines.append(f'{lrc_line_timestamp}{lrc_line}\n')

    return lrc_lines
