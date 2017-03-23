# coding: utf-8
from __future__ import unicode_literals

import contextlib
import random
import socket
import uuid

from .common import InfoExtractor
from ..compat import (
    compat_chr,
    compat_ord,
    compat_urllib_parse_urlencode,
)
from ..utils import (
    ExtractorError,
    intlist_to_bytes,
    urlencode_postdata,
    xpath_element,
    xpath_text,
)


class QQIE(InfoExtractor):
    _VALID_URL = r'https?://v\.qq\.com/x/page/(?P<id>[0-9a-z]+)\.html'

    # TODO: finish tests
    _TEST = {
        'url': 'https://v.qq.com/x/page/y01647bfni0.html',
    }

    PLATFORM = 10902
    PLAYER_VERSION = '3.2.33.397'
    SWF_URL = 'https://imgcache.qq.com/tencentvideo_v1/playerv3/TencentPlayer.swf?max_age=86400&v=20170106'

    def _sandbox_api(self, api_type, video_id, params):
        req = {
            'type': api_type,
        }
        req.update(params)
        return self._download_json(
            # XXX: Is an external server acceptable?
            'http://sandbox.xinfan.org/cgi-bin/txsp/ckey54',
            video_id, query=req)['result']

    def _real_extract(self, url):
        video_id = self._match_id(url)

        webpage = self._download_webpage(url, video_id)

        video_info = self._parse_json(self._search_regex(
            r'var\s+VIDEO_INFO\s*=\s*({.+?});', webpage, 'video info'), video_id)
        title = video_info['title']

        player_guid = uuid.uuid4().hex.upper()
        encoded_token = self._sandbox_api(
            'token', video_id, {
                'guid': player_guid,
                'platform': self.PLATFORM,
                'player_version': self.PLAYER_VERSION,
            })

        with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            sock.connect(('rlog.video.qq.com', 8080))
            to_be_sent = []
            for i in range(0, len(encoded_token), 2):
                c = encoded_token[i:i + 2]
                to_be_sent.append(int(c, 16))
            sock.send(intlist_to_bytes(to_be_sent))
            data = sock.recv(200)
        l = compat_ord(data[0]) | compat_ord(data[1]) << 8
        if l + 2 != len(data):
            raise ExtractorError('Failed to fetch real token')
        rtoken = ''
        loc5 = [96, 71, 147, 86]
        for i in range(l):
            c = compat_ord(data[i + 2]) ^ loc5[i % 4]
            rtoken += compat_chr(c)

        time_info = self._download_xml(
            'https://vv.video.qq.com/checktime?ran=%.16f' % random.random(),
            video_id)

        ckey = self._sandbox_api('ckey', video_id, {
            'rtoken': rtoken,
            'platform': self.PLATFORM,
            'version': '5.4',
            'player_version': self.PLAYER_VERSION,
            'vid': video_id,
            'timestamp': int(xpath_text(time_info, './t')),
            'rand': xpath_text(time_info, './rand'),
            'sd': 'bceg',
            'guid': player_guid,
        })

        # XXX: are all parameters necessary?
        vinfo = self._download_xml(
            'https://vv.video.qq.com/getvinfo', video_id,
            headers={
                'Referer': self.SWF_URL,
                'Content-type': 'application/x-www-form-urlencoded',
            }, data=urlencode_postdata({
                'vid': video_id,
                'linkver': 2,
                'otype': 'xml',
                'defnpayver': 1,
                'platform': self.PLATFORM,
                'newplatform': self.PLATFORM,
                'charge': 0,
                'ran': '%.16f' % random.random(),
                'speed': random.randint(5000, 9000),
                'defaultfmt': 'shd',
                'pid': uuid.uuid4().hex.upper(),
                'appver': self.PLAYER_VERSION,
                'fhdswitch': 0,
                'guid': player_guid,
                'ehost': url,
                'dtype': 3,
                'fp2p': 1,
                'cKey': ckey,
                'utype': 0,
                'encryptVer': '5.4',
                'ip': '',
                'defn': 'shd',
                'sphls': 1,
                'refer': '',
                'drm': 8,
                'sphttps': 1,
            }))

        vi = xpath_element(vinfo, './vl/vi')
        entries = []
        for idx, ci in enumerate(vi.findall('./cl/ci')):
            formats = []
            for fi in vinfo.findall('./fl/fi'):
                format_note = xpath_text(fi, './cname')
                vclip_info = self._download_xml(
                    'https://vv.video.qq.com/getvclip', video_id,
                    headers={
                        'Referer': self.SWF_URL,
                        'Content-type': 'application/x-www-form-urlencoded',
                    }, data=urlencode_postdata({
                        'cKey': ckey,
                        'appver': self.PLAYER_VERSION,
                        'fmt': xpath_text(fi, './name'),
                        'format': int(xpath_text(fi, './id')),
                        'linkver': 2,
                        'encryptVer': '5.4',
                        'lnk': xpath_text(vi, './lnk'),
                        'idx': int(xpath_text(ci, './idx')),
                        'platform': self.PLATFORM,
                        'guid': player_guid,
                        'vid': video_id,
                    }), note='Download video clip info for segment %d of format %s' % (
                        idx + 1, format_note))

                video_url = '%s%s?%s' % (
                    xpath_text(vi, './ul/ui/url'),
                    xpath_text(vclip_info, './vi/fn'),
                    compat_urllib_parse_urlencode({
                        'sdtfrom': 'v1000',
                        'type': 'mp4',
                        'vkey': xpath_text(vclip_info, './vi/key'),
                        'platform': self.PLATFORM,
                        'br': int(xpath_text(vclip_info, './vi/br')),
                        'fmt': xpath_text(vclip_info, './vi/fmt'),
                        'sp': int(xpath_text(vclip_info, './vi/fs')),
                        'guid': player_guid,
                        'level': 0,
                    }))
                formats.append({
                    'url': video_url,
                    'format_note': format_note,
                })
            # TODO: _sort_formats
            entries.append({
                'id': '%s_%d' % (video_id, idx + 1),
                'title': title,
                'formats': formats,
            })

        return {
            '_type': 'multi_video',
            'id': video_id,
            'title': title,
            'entries': entries,
        }


# TODO: support playlists like https://v.qq.com/x/cover/8vo388mz3gz3ehq.html
