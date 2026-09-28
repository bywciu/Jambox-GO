import datetime
import json
import socket
import time
from pathlib import Path

import const


DEBUG = 'debug'
INFO = 'info'
ERROR = 'error'

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / 'data'

files = [
    DATA_DIR / 'config.json',
    DATA_DIR / 'credentials.json',
    DATA_DIR / 'cookie.json',
]
channels_file = DATA_DIR / 'channels.list'
playlist_file = DATA_DIR / 'tv.m3u'

CONFIG = {
    'host': '127.0.0.1',
    'port': 8080,
    'debug': False,
    'quality': 'high',
    'threaded': True,
    'hls': True,
}

CREDENTIALS = {
    'username': '',
    'password': '',
}

debug = False


def set_debug(value):
    global debug
    debug = bool(value)


def log(level, message):
    now = datetime.datetime.now()
    if level in (ERROR, INFO) or debug:
        print(now.strftime('%Y-%m-%d %H:%M:%S'), '|   ', message)


def load_json(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return json.load(file)


def save_json(file_path, value):
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, 'w', encoding='utf-8') as file:
        json.dump(value, file, indent=4, ensure_ascii=False)
        file.write('\n')


def check_files():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    created = False

    if not files[0].exists():
        save_json(files[0], CONFIG)
        created = True

    if not files[1].exists():
        save_json(files[1], CREDENTIALS)
        created = True

    if not files[2].exists():
        save_json(files[2], {})
        created = True

    if created:
        return False, False

    credentials = load_json(files[1])

    if not credentials.get('username') or not credentials.get('password'):
        return True, False

    return True, True


def export_channels(api, hls):
    uuid_f = '5234b234-647a-47b9-8441-b21ed321140'
    channel_list = []
    channel_not_found = []
    asset = api.get_asset().json()

    if hls:
        for channel in asset:
            try:
                channel_list.append([
                    channel['name'],
                    channel['url']['hlsAac'],
                ])
                log(
                    INFO,
                    const.CHANNEL_FOUND.format(
                        channel['name'],
                        channel['url']['hlsAac'],
                    ),
                )
            except (KeyError, TypeError):
                channel_not_found.append(channel.get('name', '<unknown>'))
    else:
        for counter, channel in enumerate(asset, start=1):
            try:
                name = channel['name']
                uuid = channel['alternate_id']['vectra_uuid']
                live = api.get_channel(uuid).json()['url'].split('?')[0]
                log(INFO, const.CHANNEL_FOUND.format(name, live))
                channel_list.append([name, live])
                time.sleep(0.3)

                if uuid == uuid_f and counter > 40:
                    break
            except (KeyError, TypeError, ValueError):
                channel_not_found.append(channel.get('name', '<unknown>'))

    for channel in channel_not_found:
        log(DEBUG, const.CHANNEL_NOT_FOUND.format(channel))

    save_json(channels_file, channel_list)


def check_channels():
    return not channels_file.exists()


def export_list(host_ip, port):
    m3u = ['#EXTM3U\n']
    channels = load_json(channels_file)

    for index, channel in enumerate(channels):
        m3u.append('#EXTINF:-1,{}\n'.format(channel[0]))
        m3u.append('http://{}:{}/{}\n'.format(host_ip, port, index))

    with open(playlist_file, 'w', encoding='utf-8') as file:
        file.writelines(m3u)


def check_list():
    return not playlist_file.exists()
