#!/usr/bin/env python

import lyriks
from lyriks.providers.vibe import Vibe

if __name__ == '__main__':
    #lyriks.cli()
    Vibe().fetch_album_song_ids(9334427)
    lyriks.fetch_single_song(Vibe(), 42036917, output_path='test.lrc')
