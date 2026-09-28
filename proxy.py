import logging
import time
from urllib.parse import urlencode, urljoin

import requests
from flask import Flask, Response, abort

from helpers import DEBUG, log


class PROXY:
    def __init__(
        self,
        jambox,
        channels,
        port,
        threaded,
        cookie,
        debug,
    ):
        self.jambox = jambox
        self.token = ''
        self.user = ''
        self.channels = channels
        self.cookie = cookie
        self.session = requests.Session()

        self.app = Flask('Jambox Go decoder')

        logging.getLogger('werkzeug').setLevel(
            logging.INFO if debug else logging.WARNING
        )

        self.app.route('/<int:channel_id>')(self.channel)

        self.app.run(
            host='0.0.0.0',
            port=int(port),
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

    def get_channel_playlist(self, channel_id):
        channel_name, channel_url = self.channels[channel_id]
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

    def channel(self, channel_id):
        if channel_id < 0 or channel_id >= len(self.channels):
            abort(404)

        manifest, status = self.get_channel_playlist(channel_id)

        if manifest is None:
            return Response(
                'Unable to retrieve channel playlist',
                status=status,
                mimetype='text/plain',
            )

        return Response(
            manifest,
            mimetype='application/vnd.apple.mpegurl',
        )
