import base64
import hashlib
import hmac
import math
import random
import string
import time
import requests
import helpers

class API:
    def __init__(self, credentials, cookie):
        self.cookie = cookie
        self.credentials = credentials
        self.device = 'other'
        self.api_url = 'https://api.sgtsa.pl/'

        if not self.cookie:
            self.login()

        self._load_cookie()

    def _load_cookie(self):
        self.cookie = helpers.load_json(helpers.files[2])
        self.id = self.cookie.get('id')
        self.seed = self.cookie.get('seed')
        devices = self.cookie.get('devices') or []
        self.impersonate = devices[0].get('id') if devices else None

    def get_auth_headers(self, data):
        return {
            'host': 'api.sgtsa.pl',
            'Accept': '*/*',
            'X-Auth': data[1],
            'X-Nonce': data[0],
            'sec-ch-ua': 'Google Chrome";v="107", "Chromium";v="107", "Not=A?Brand";v="24"',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36',
            'X-Device-Id': self.id,
            'X-Device-Type': self.device,
            'X-Impersonate': self.impersonate,
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'cross-site',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': 'Windows',
        }

    def random_string(self, length):
        return ''.join(
            random.choice(string.ascii_lowercase + string.digits)
            for _ in range(length)
        )

    def get_time_30(self):
        return str(math.floor(time.time() / 30) * 30)

    def auth(self, endpoint):
        nonce = self.random_string(36)[2:13] + self.random_string(36)[2:13]
        date = self.get_time_30()

        signature = hmac.new(
            self.seed.encode(),
            (nonce + endpoint + date).encode(),
            hashlib.sha256,
        ).hexdigest()

        return nonce, base64.b64encode(signature.encode('utf-8'))

    def login(self):
        endpoint = 'v1/auth/login'
        url = self.api_url + endpoint
        headers = {
            'host': 'api.sgtsa.pl',
            'X-Time': self.get_time_30(),
        }

        response = requests.post(
            url,
            headers=headers,
            json=self.credentials,
            timeout=15,
        )
        helpers.log(
            helpers.DEBUG,
            'Login status: {}'.format(response.status_code),
        )
        response.raise_for_status()

        cookie = response.json()
        helpers.save_json(helpers.files[2], cookie)
        self.cookie = cookie

    def get_token(self):
        endpoint = 'v1/ott/token'
        url = self.api_url + endpoint
        headers = self.get_auth_headers(self.auth(endpoint))
        response = requests.get(url=url, headers=headers, timeout=15)
        helpers.log(
            helpers.DEBUG,
            'Token status: {}'.format(response.status_code),
        )
        return response.content

    def set_channel(self, endpoint_id):
        endpoint = 'v1/ott/dash/{}'.format(endpoint_id)
        url = self.api_url + endpoint
        headers = self.get_auth_headers(self.auth(endpoint))
        response = requests.get(url=url, headers=headers, timeout=15)
        helpers.log(
            helpers.DEBUG,
            'Set channel status: {}'.format(response.status_code),
        )

    def get_license(self, endpoint_id, data):
        endpoint = 'v1/ott/dash/{}/widevine/'.format(endpoint_id)
        url = self.api_url + endpoint
        headers = self.get_auth_headers(self.auth(endpoint))
        response = requests.post(
            url,
            headers=headers,
            data=data,
            timeout=15,
        )
        helpers.log(
            helpers.DEBUG,
            'License status: {}'.format(response.status_code),
        )
        return response

    def get_asset(self):
        endpoint = 'v1/asset'
        url = self.api_url + endpoint
        headers = self.get_auth_headers(self.auth(endpoint))
        return requests.get(url, headers=headers, timeout=15)

    def get_channel(self, endpoint_id):
        endpoint = 'v1/ott/dash/{}'.format(endpoint_id)
        url = self.api_url + endpoint
        headers = self.get_auth_headers(self.auth(endpoint))
        return requests.get(url, headers=headers, timeout=15)

    def get_epg_chunk(self, chunk, asset_ids):
        assets = ','.join(str(asset_id) for asset_id in asset_ids)
        endpoint = 'v1/epg/chunk/{}/assets/{}'.format(chunk, assets)
        url = self.api_url + endpoint
        headers = self.get_auth_headers(self.auth(endpoint))
        response = requests.get(url, headers=headers, timeout=15)
        helpers.log(
            helpers.DEBUG,
            'EPG chunk {} status: {}'.format(chunk, response.status_code),
        )
        return response
