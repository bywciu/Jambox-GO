import html
import json
import logging
import re
import threading
import time
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlencode, urljoin
import requests
from Crypto.Cipher import AES
from flask import Flask, Response, abort, stream_with_context
from helpers import DEBUG, log

class PROXY:
    EPG_CHUNK_SECONDS = 90 * 60
    EPG_CACHE_SECONDS = 600

    def __init__(
        self,
        jambox,
        channels,
        host,
        public_host,
        port,
        tuners,
        threaded,
        cookie,
        debug,
    ):
        self.jambox = jambox
        self.token = ''
        self.user = ''
        self.channels = sorted(
            channels,
            key=self._channel_sort_key,
        )
        self.public_host = public_host
        self.port = int(port)
        self.tuners = int(tuners)
        self.cookie = cookie
        self.session = requests.Session()
        self.epg_cache = None
        self.epg_cache_at = 0
        self.epg_lock = threading.Lock()

        self.app = Flask('JAMBOX go! proxy')

        logging.getLogger('werkzeug').setLevel(
            logging.INFO if debug else logging.WARNING
        )

        self.app.route('/<int:channel_id>')(self.channel)
        self.app.route('/stream/<int:channel_id>')(self.channel)
        self.app.route('/auto/v<int:vchannel>')(self.auto_channel)
        self.app.route('/playlist.m3u')(self.playlist)
        self.app.route('/discover.json')(self.discover)
        self.app.route('/lineup.json')(self.lineup)
        self.app.route('/lineup_status.json')(self.lineup_status)
        self.app.route('/device.xml')(self.device_xml)
        self.app.route('/xmltv.xml')(self.xmltv)

        self.app.run(
            host=host,
            port=self.port,
            threaded=bool(threaded),
        )

    def _refresh_token(self):
        response = self.jambox.get_token()
        query = response.decode('utf-8').split('"')[3]

        self.token = query.replace('\\', '')
        self.user = self.cookie.get('id', '').strip('\\')

        log(
            DEBUG,
            'New token: {} user: {}'.format(
                self.token[:10] + '************',
                self.user[:10] + '************',
            ),
        )

    def req(self, url):
        response = self.session.get(url, timeout=15)

        if response.status_code == 404:
            for retry in range(200):
                time.sleep(0.005)
                response = self.session.get(url, timeout=15)
                if response.status_code == 200:
                    log(DEBUG, '404 retries {}'.format(retry))
                    break

        if response.status_code == 403:
            self._refresh_token()

        return response

    def _channel_name(self, channel):
        return channel['name']

    def _channel_url(self, channel):
        return channel['url']

    def _channel_sgtid(self, channel):
        return channel['sgtid']

    @staticmethod
    def _channel_sort_key(channel):
        try:
            return (0, int(channel.get('number')))
        except (AttributeError, TypeError, ValueError):
            return (1, 0)

    def _channel_number(self, channel, index):
        try:
            return int(channel.get('number'))
        except (AttributeError, TypeError, ValueError):
            return index + 1

    def _channel_epg_id(self, channel, index=None):
        epg_mapping_id = channel.get('epg_mapping_id')
        if epg_mapping_id is not None and str(epg_mapping_id).strip():
            return str(epg_mapping_id)

        return 'jambox-{}'.format(self._channel_sgtid(channel))

    def get_channel_playlist(self, channel_id):
        channel = self.channels[channel_id]
        channel_name = self._channel_name(channel)
        channel_url = self._channel_url(channel)
        log(DEBUG, 'CHANNEL: {}'.format(channel_name))

        playlist_url = channel_url.replace(
            'playlist.m3u8',
            'high/playlist.m3u8',
            1,
        )
        url = '{}?{}'.format(
            playlist_url,
            urlencode({
                'token': self.token,
                'hash': self.user,
            }),
        )

        log(DEBUG, 'Request url: {}'.format(playlist_url))
        response = self.req(url)

        if response.status_code == 403:
            url = '{}?{}'.format(
                playlist_url,
                urlencode({
                    'token': self.token,
                    'hash': self.user,
                }),
            )
            response = self.req(url)

        if response.status_code != 200:
            return None, response.status_code

        lines = response.text.splitlines()

        for index, line in enumerate(lines):
            if line.startswith('#EXT-X-KEY:') and 'URI="' in line:
                prefix, uri = line.split('URI="', 1)
                uri, suffix = uri.split('"', 1)

                lines[index] = '{}URI="{}"{}'.format(
                    prefix,
                    urljoin(response.url, uri),
                    suffix,
                )

        return '\n'.join(lines) + '\n', 200

    def _base_url(self):
        return 'http://{}:{}'.format(self.public_host, self.port)

    def playlist(self):
        lines = ['#EXTM3U']

        for index, channel in enumerate(self.channels):
            name = self._channel_name(channel)
            epg_id = self._channel_epg_id(channel, index)
            lines.append(
                '#EXTINF:-1 tvg-id="{}" tvg-name="{}" tvg-chno="{}",{}'.format(
                    self._xml_escape(epg_id),
                    self._xml_escape(name),
                    self._channel_number(channel, index),
                    name,
                )
            )
            lines.append('{}/{}'.format(self._base_url(), index))

        return Response(
            '\n'.join(lines) + '\n',
            mimetype='audio/x-mpegurl',
        )

    def discover(self):
        base_url = self._base_url()

        return Response(
            json.dumps({
                'FriendlyName': 'Jambox-GO',
                'Manufacturer': 'Jambox-GO',
                'ModelNumber': 'JAMBOX-GO',
                'FirmwareName': 'Jambox-GO',
                'FirmwareVersion': '1.0',
                'DeviceID': '103B33B0',
                'DeviceAuth': 'none',
                'TunerCount': self.tuners,
                'UpgradeAvailable': 0,
                'BaseURL': base_url,
                'LineupURL': '{}/lineup.json'.format(base_url),
            }),
            mimetype='application/json',
        )

    def lineup(self):
        lineup = [
            {
                'GuideNumber': str(self._channel_number(channel, index)),
                'GuideName': self._channel_name(channel),
                'URL': '{}/auto/v{}'.format(self._base_url(), index + 1),
            }
            for index, channel in enumerate(self.channels)
        ]

        return Response(
            json.dumps(lineup, ensure_ascii=False),
            mimetype='application/json',
        )

    def auto_channel(self, vchannel):
        if vchannel < 1 or vchannel > len(self.channels):
            abort(404)

        return self.channel(vchannel - 1)

    def lineup_status(self):
        return Response(
            json.dumps({
                'ScanInProgress': 0,
                'ScanPossible': 1,
                'Source': 'Jambox-GO',
                'SourceList': ['Jambox-GO'],
            }),
            mimetype='application/json',
        )

    def device_xml(self):
        base_url = self._base_url()
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<root xmlns="urn:schemas-upnp-org:device-1-0">'
            '<specVersion><major>1</major><minor>0</minor></specVersion>'
            '<device>'
            '<deviceType>urn:schemas-upnp-org:device:MediaServer:1</deviceType>'
            '<friendlyName>JAMBOX go!</friendlyName>'
            '<manufacturer>bywciu</manufacturer>'
            '<modelName>JAMBOX-GO</modelName>'
            '<modelNumber>JAMBOX-GO</modelNumber>'
            '<serialNumber>JAMBOXGO0001</serialNumber>'
            '<UDN>uuid:JAMBOXGO0001</UDN>'
            '<presentationURL>{}</presentationURL>'
            '</device>'
            '</root>'
        ).format(base_url)

        return Response(xml, mimetype='application/xml')

    @staticmethod
    def _first_epg_chunk(timestamp=None):
        if timestamp is None:
            timestamp = int(time.time())

        return timestamp - (timestamp % PROXY.EPG_CHUNK_SECONDS)

    def _load_epg(self):
        now = time.time()

        if self.epg_cache is not None and now - self.epg_cache_at < self.EPG_CACHE_SECONDS:
            return self.epg_cache

        with self.epg_lock:
            now = time.time()
            if self.epg_cache is not None and now - self.epg_cache_at < self.EPG_CACHE_SECONDS:
                return self.epg_cache

            asset_ids = [
                self._channel_sgtid(channel)
                for channel in self.channels
                if self._channel_sgtid(channel) is not None
            ]

            if not asset_ids:
                return {}

            chunk = self._first_epg_chunk()
            programs = {str(asset_id): [] for asset_id in asset_ids}
            boundary = None
            seen_chunks = set()

            while chunk not in seen_chunks:
                seen_chunks.add(chunk)
                response = self.jambox.get_epg_chunk(chunk, asset_ids)
                response.raise_for_status()
                data = response.json()

                boundary = data.get('boundary')

                for asset_id, entries in (data.get('chunk') or {}).items():
                    if asset_id not in programs:
                        continue
                    programs[asset_id].extend(entries or [])

                next_chunk = data.get('end')
                if not isinstance(next_chunk, int) or next_chunk <= chunk:
                    break

                chunk = next_chunk

                if boundary is not None and chunk >= boundary:
                    break

            self.epg_cache = programs
            self.epg_cache_at = time.time()
            log(DEBUG, 'EPG loaded for {} channels'.format(len(programs)))
            return programs

    @staticmethod
    def _strip_html(value):
        if not value:
            return ''
        value = re.sub(r'<br\s*/?>', '\n', value, flags=re.IGNORECASE)
        value = re.sub(r'<[^>]+>', '', value)
        return html.unescape(value).strip()

    @staticmethod
    def _xml_escape(value):
        return html.escape(str(value), quote=True)

    @staticmethod
    def _xmltv_time(timestamp):
        return datetime.fromtimestamp(timestamp, timezone.utc).strftime('%Y%m%d%H%M%S +0000')

    def xmltv(self):
        programs = self._load_epg()
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<tv generator-info-name="Jambox-GO">',
        ]

        for index, channel in enumerate(self.channels):
            channel_id = self._channel_epg_id(channel, index)
            name = self._channel_name(channel)
            lines.extend([
                '  <channel id="{}">'.format(self._xml_escape(channel_id)),
                '    <display-name>{}</display-name>'.format(self._xml_escape(name)),
                '    <lcn>{}</lcn>'.format(self._channel_number(channel, index)),
                '  </channel>',
            ])

        for index, channel in enumerate(self.channels):
            sgtid = str(self._channel_sgtid(channel))
            channel_id = self._channel_epg_id(channel, index)

            normalized_entries = []
            for entry in programs.get(sgtid, []):
                try:
                    start = int(entry.get('start'))
                    end = int(entry.get('end'))
                except (TypeError, ValueError):
                    continue

                name = entry.get('name')
                if end <= start or not name:
                    continue

                normalized_entry = dict(entry)
                normalized_entry['start'] = start
                normalized_entry['end'] = end
                normalized_entries.append(normalized_entry)

            entries = sorted(
                normalized_entries,
                key=lambda entry: entry['start'],
            )

            seen = set()
            for entry in entries:
                start = entry['start']
                end = entry['end']
                name = entry.get('name')

                key = (start, end, name)
                if key in seen:
                    continue
                seen.add(key)

                lines.append(
                    '  <programme channel="{}" start="{}" stop="{}">'.format(
                        self._xml_escape(channel_id),
                        self._xmltv_time(start),
                        self._xmltv_time(end),
                    )
                )
                lines.append('    <title>{}</title>'.format(self._xml_escape(name)))

                description = self._strip_html(entry.get('description'))
                if description:
                    lines.append('    <desc>{}</desc>'.format(self._xml_escape(description)))

                lines.append('  </programme>')

        lines.append('</tv>')

        return Response(
            '\n'.join(lines) + '\n',
            mimetype='application/xml',
        )

    @staticmethod
    def _hls_attribute(line, name):
        match = re.search(r'{}=([^,]+)'.format(re.escape(name)), line)
        if not match:
            return None
        value = match.group(1).strip()
        if value.startswith('"') and value.endswith('"'):
            return value[1:-1]
        return value

    @staticmethod
    def _hls_iv(value, sequence):
        if value:
            value = value.strip()
            if value.lower().startswith('0x'):
                value = value[2:]
            value = value.zfill(32)
            return bytes.fromhex(value)
        return int(sequence).to_bytes(16, 'big')

    def _hls_segments(self, channel_id):
        seen = set()
        key_cache = {}
        media_sequence = 0

        while True:
            manifest, status = self.get_channel_playlist(channel_id)
            if manifest is None:
                log(DEBUG, 'HLS manifest failed for channel {}: {}'.format(channel_id, status))
                time.sleep(1)
                continue

            lines = manifest.splitlines()
            key_uri = None
            key_iv = None
            sequence = media_sequence
            segment_urls = []

            for line in lines:
                line = line.strip()
                if line.startswith('#EXT-X-MEDIA-SEQUENCE:'):
                    try:
                        sequence = int(line.split(':', 1)[1])
                    except ValueError:
                        sequence = media_sequence
                elif line.startswith('#EXT-X-KEY:'):
                    method = self._hls_attribute(line, 'METHOD')
                    if method == 'AES-128':
                        key_uri = self._hls_attribute(line, 'URI')
                        key_iv = self._hls_attribute(line, 'IV')
                elif line and not line.startswith('#'):
                    segment_urls.append((sequence, line, key_uri, key_iv))
                    sequence += 1

            if not segment_urls:
                time.sleep(0.5)
                continue

            for segment_sequence, segment_url, segment_key_uri, segment_iv in segment_urls:
                if segment_url in seen:
                    continue

                try:
                    response = self.session.get(segment_url, timeout=15)
                    response.raise_for_status()
                    data = response.content

                    if segment_key_uri:
                        if segment_key_uri not in key_cache:
                            key_response = self.session.get(segment_key_uri, timeout=15)
                            key_response.raise_for_status()
                            key_cache[segment_key_uri] = key_response.content

                        key = key_cache[segment_key_uri]
                        if len(key) != 16:
                            raise ValueError('Invalid AES-128 key length')

                        iv = self._hls_iv(segment_iv, segment_sequence)
                        data = AES.new(key, AES.MODE_CBC, iv).decrypt(data)
                        padding = data[-1] if data else 0
                        if 0 < padding <= 16 and data.endswith(bytes([padding]) * padding):
                            data = data[:-padding]

                    seen.add(segment_url)
                    yield data
                except requests.RequestException as exc:
                    log(DEBUG, 'HLS segment failed: {}'.format(exc))
                except (ValueError, TypeError) as exc:
                    log(DEBUG, 'HLS segment decode failed: {}'.format(exc))

            media_sequence = max(sequence, media_sequence)
            if len(seen) > 200:
                seen = set(list(seen)[-100:])
            time.sleep(0.2)

    def channel(self, channel_id):
        if channel_id < 0 or channel_id >= len(self.channels):
            abort(404)

        return Response(
            stream_with_context(self._hls_segments(channel_id)),
            mimetype='video/mpeg',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'close',
            },
        )
