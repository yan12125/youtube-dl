# encoding: utf-8
from __future__ import unicode_literals

import base64
import re
import time

from .common import InfoExtractor
from ..compat import compat_urlparse
from ..utils import (
    float_or_none,
    remove_end,
    struct_pack,
    ExtractorError,
)
from Crypto.Cipher import Blowfish


class RTVECipher(object):
    bs = Blowfish.block_size
    key = b'yeL&daD3'
    cipher = Blowfish.new(key, Blowfish.MODE_ECB)

    @classmethod
    def encrypt(cls, plaintexts, clean_url=False):
        plainbytes = plaintexts.encode('utf-8')
        plen = cls.bs - len(plainbytes) % cls.bs
        padding = [plen] * plen
        padding = struct_pack('b' * plen, *padding)
        cipherbytes = cls.cipher.encrypt(plainbytes + padding)
        ret = base64.b64encode(cipherbytes).decode('utf-8')
        if clean_url:
            ret = ret.replace('/', '_').replace('+', '-')
        return ret

    @classmethod
    def decrypt(cls, ciphertexts):
        cipherbytes = base64.b64decode(ciphertexts.encode('utf-8'))
        original = cls.cipher.decrypt(cipherbytes).decode('utf-8')
        return original[:-ord(original[-1])]


class RTVEBaseIE(InfoExtractor):
    def _real_extract(self, url):
        mobj = re.match(self._VALID_URL, url)
        video_id = mobj.group('id')
        info = self._download_json(
            'http://www.rtve.es/api/videos/%s/config/alacarta_videos.json' % video_id,
            video_id)['page']['items'][0]

        ztnr_res = self._download_xml(
            'http://ztnr.rtve.es/ztnr/res/' + RTVECipher.encrypt(video_id + '_banebdyede_video_es', clean_url=True),
            video_id, transform_source=lambda s: RTVECipher.decrypt(s).replace('&', '&amp;'))

        response_code = ztnr_res.find('./preset/response').attrib['code']
        if response_code != 'ok':
            raise ExtractorError(response_code, expected=True)

        for url_element in ztnr_res.findall('./preset/response/url'):
            video_url = url_element.text

            if video_url.endswith('.f4m'):
                break

            auth_url = video_url.replace(
                'resources/', 'auth/resources/'
            ).replace('.net.rtve', '.multimedia.cdn.rtve')
            try:
                video_path = self._download_webpage(
                    auth_url, video_id, 'Getting video url')
                # Use mvod1.akcdn instead of flash.akamaihd.multimedia.cdn to get
                # the right Content-Length header and the mp4 format
                video_url = compat_urlparse.urljoin(
                    'http://mvod1.akcdn.rtve.es/', video_path)
                break
            except ExtractorError:
                continue

        subtitles = None
        if info.get('sbtFile') is not None:
            subtitles = self.extract_subtitles(video_id, info['sbtFile'])

        return {
            'id': video_id,
            'title': info['title'],
            'url': video_url,
            'thumbnail': info.get('image'),
            'page_url': url,
            'subtitles': subtitles,
            'duration': float_or_none(info.get('duration'), scale=1000),
        }

    def _get_subtitles(self, video_id, sub_file):
        subs = self._download_json(
            sub_file + '.json', video_id,
            'Downloading subtitles info')['page']['items']
        return dict(
            (s['lang'], [{'ext': 'vtt', 'url': s['src']}])
            for s in subs)


class RTVEALaCartaIE(RTVEBaseIE):
    IE_NAME = 'rtve.es:alacarta'
    IE_DESC = 'RTVE a la carta'
    _VALID_URL = r'http://www\.rtve\.es/(m/)?alacarta/videos/[^/]+/[^/]+/(?P<id>\d+)'

    _TESTS = [{
        'url': 'http://www.rtve.es/alacarta/videos/balonmano/o-swiss-cup-masculina-final-espana-suecia/2491869/',
        'md5': '9c8cfbc423548372ebad6d6b4680459c',
        'info_dict': {
            'id': '2491869',
            'ext': 'mp4',
            'title': 'Balonmano - Swiss Cup masculina. Final: España-Suecia',
            'duration': 5024.566,
        },
    }, {
        'url': 'http://www.rtve.es/alacarta/videos/ciudad-k/ciudad-20100927-2131/888631/',
        'md5': '01db3d5de2e3c0e1518454753c428922',
        'info_dict': {
            'id': '888631',
            'ext': 'flv',
            'title': 'Ciudad K - Capítulo 3',
            'duration': 1561.68,
        }
    }, {
        'note': 'Live stream',
        'url': 'http://www.rtve.es/alacarta/videos/television/24h-live/1694255/',
        'info_dict': {
            'id': '1694255',
            'ext': 'flv',
            'title': 'TODO',
        },
        'skip': 'The f4m manifest can\'t be used yet',
    }, {
        'url': 'http://www.rtve.es/m/alacarta/videos/cuentame-como-paso/cuentame-como-paso-t16-ultimo-minuto-nuestra-vida-capitulo-276/2969138/?media=tve',
        'only_matching': True,
    }]


class RTVEInfantilIE(RTVEBaseIE):
    IE_NAME = 'rtve.es:infantil'
    IE_DESC = 'RTVE infantil'
    _VALID_URL = r'https?://(?:www\.)?rtve\.es/infantil/serie/(?P<show>[^/]*)/video/(?P<short_title>[^/]*)/(?P<id>[0-9]+)/'


class RTVELiveIE(InfoExtractor):
    IE_NAME = 'rtve.es:live'
    IE_DESC = 'RTVE.es live streams'
    _VALID_URL = r'http://www\.rtve\.es/(?:deportes/directo|directo|noticias|television)/(?P<id>[a-zA-Z0-9-]+)'

    _TESTS = [{
        'url': 'http://www.rtve.es/noticias/directo-la-1/',
        'info_dict': {
            'id': 'directo-la-1',
            'ext': 'flv',
            'title': 're:^Estoy viendo La 1 en directo en RTVE.es [0-9]{4}-[0-9]{2}-[0-9]{2}Z[0-9]{6}$',
        },
        'params': {
            'skip_download': 'live stream',
        }
    }, {
        'url': 'http://www.rtve.es/directo/la-2/',
        'only_matching': True,
    }]

    def _real_extract(self, url):
        mobj = re.match(self._VALID_URL, url)
        start_time = time.gmtime()
        video_id = mobj.group('id')

        webpage = self._download_webpage(url, video_id)
        player_url = self._search_regex(
            r'<param name="movie" value="([^"]+)"/>', webpage, 'player URL')
        title = remove_end(self._og_search_title(webpage), ' en directo')
        title += ' ' + time.strftime('%Y-%m-%dZ%H%M%S', start_time)

        internal_video_id = self._search_regex(
            r'assetID=(\d+)[^\&]+\&', webpage, 'internal video ID')

        ztnr_res = self._download_xml(
            'http://ztnr.rtve.es/ztnr/res/' + RTVECipher.encrypt(internal_video_id + '_banebdyede_video_es', clean_url=True),
            video_id, transform_source=lambda s: RTVECipher.decrypt(s).replace('&', '&amp;'))
        video_url = ztnr_res.find('./preset/response/url').text

        return {
            'id': video_id,
            'ext': 'flv',
            'title': title,
            'url': video_url,
            'app': 'live?ovpfv=2.1.2',
            'player_url': player_url,
            'rtmp_live': True,
        }
