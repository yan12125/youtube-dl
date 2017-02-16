from __future__ import unicode_literals

# Usage:
# $ python find_url.py "https://www.youtube.com/watch?v=BaW_jenozKc&t=1s&end=9"
# test_Youtube

from os.path import abspath, dirname
import sys

sys.path.insert(0, dirname(dirname(dirname(abspath(__file__)))))

import youtube_dl.extractor
from youtube_dl.compat import compat_str

target_url = sys.argv[1]

for ie in youtube_dl.extractor.gen_extractors():
    for idx, tc in enumerate(ie.get_testcases(False)):
        if tc['url'] == target_url:
            print('_'.join(filter(None, [
                'test', ie.ie_key(), compat_str(idx) if idx > 0 else None])))
