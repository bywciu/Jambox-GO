import datetime
import json
import time
from pathlib import Path
import requests
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

CHANNEL_LOGO_URL = 'https://static.sgtsa.pl/channels/logos/{}.png'

CONFIG = {
    'host': '127.0.0.1',
    'port': 8080,
    'debug': False,
    'quality': 'high',
    'threaded': True,
    'hls': True,
    'tuners': 4,
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

def get_channel_logo(sgtid):
    url = CHANNEL_LOGO_URL.format(sgtid)

    try:
        response = requests.head(
            url,
            timeout=5,
            allow_redirects=True,
        )

        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', '').lower()
            if content_type.startswith('image/'):
                return url
    except requests.RequestException:
        pass

    return None

def export_channels(api, hls):
    uuid_f = '5234b234-647a-47b9-8441-b21ed321140'
    channel_list = []
    channel_not_found = []
    asset = api.get_asset().json()

    for counter, channel in enumerate(asset, start=1):
        try:
            name = channel['name']
            sgtid = channel['sgtid']
            number = channel.get('number')
            try:
                number = int(number)
            except (TypeError, ValueError):
                number = counter
            epg_mapping_id = channel.get('epg_mapping_id')
            logo = get_channel_logo(sgtid)

            if hls:
                live = channel['url']['hlsAac']
            else:
                uuid = channel['alternate_id']['vectra_uuid']
                live = api.get_channel(uuid).json()['url'].split('?')[0]
                time.sleep(0.3)

                if uuid == uuid_f and counter > 40:
                    break

            channel_list.append({
                'name': name,
                'url': live,
                'sgtid': sgtid,
                'epg_mapping_id': epg_mapping_id,
                'number': number,
                'logo': logo,
            })
            log(
                INFO,
                const.CHANNEL_FOUND.format(name, live),
            )
        except (KeyError, TypeError, ValueError):
            channel_not_found.append(channel.get('name', '<unknown>'))

    for channel in channel_not_found:
        log(DEBUG, const.CHANNEL_NOT_FOUND.format(channel))

    save_json(channels_file, channel_list)

def check_channels():
    if not channels_file.exists():
        return True

    try:
        channels = load_json(channels_file)
    except (OSError, ValueError, TypeError):
        return True

    if not isinstance(channels, list) or not channels:
        return True

    return any(
        not isinstance(channel, dict)
        or not channel.get('name')
        or not channel.get('url')
        or channel.get('sgtid') is None
        for channel in channels
    )
