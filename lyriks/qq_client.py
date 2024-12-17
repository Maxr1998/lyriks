import base64
import binascii
import json
from dataclasses import dataclass
from datetime import datetime
from json import JSONDecodeError

import requests

from lyriks.lyrics import Lyrics
from lyriks.zzc_sign import zzc_sign

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
    'uin': '1152921505320317704',
    'g_tk_new_20200303': 1077614320,
    'g_tk': 1077614320
}

CHROME_USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) "
                     "AppleWebKit/537.36 (KHTML, like Gecko) "
                     "Chrome/130.0.0.0 "
                     "Safari/537.36")


@dataclass
class QQMSong:
    id: int
    mid: str
    track: int
    name: str


def make_qqm_requests(modules: list[dict]) -> list[dict]:
    request = dict(
        [('comm', QQM_COMM)] +
        [(f'req_{i + 1}', module) for i, module in enumerate(modules)]
    )
    body = json.dumps(request)
    signature = zzc_sign(body)

    response = requests.post(
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
        data=body,
    )

    try:
        response_json = response.json()
    except JSONDecodeError:
        return []

    try:
        return [response_json[f'req_{i + 1}'] for i in range(len(modules))]
    except KeyError:
        return []


def fetch_qqm_album_songs(album_mid: str) -> list[QQMSong]:
    response = make_qqm_requests([{
        'module': 'music.musichallAlbum.AlbumSongList',
        'method': 'GetAlbumSongList',
        'param': {'albumMid': album_mid, 'albumID': 0, 'begin': 0, 'num': 100, 'order': 2},
    }])

    if not response:
        return []

    songs = response[0]['data']['songList']

    result = []

    for song in songs:
        song_info = song['songInfo']
        song_id = song_info['id']
        song_mid = song_info['mid']
        track_num = song_info['index_album']
        title = song_info['title']
        result.append(QQMSong(id=song_id, mid=song_mid, track=track_num, name=title))

    return result


def fetch_lyrics(song: QQMSong) -> Lyrics | None:
    response = make_qqm_requests([{
        'module': 'music.musichallSong.PlayLyricInfo',
        'method': 'GetPlayLyricInfo',
        'param': {'songMID': song.mid},
    }])

    if not response:
        return None

    try:
        lyrics_encoded = response[0]['data']['lyric']
    except KeyError:
        return None

    try:
        lyrics = base64.standard_b64decode(lyrics_encoded).decode('utf-8')
    except binascii.Error:
        return None
    except UnicodeDecodeError:
        return None

    return Lyrics(song.id, song.name, lyrics.splitlines(keepends=True), is_timed=True)
