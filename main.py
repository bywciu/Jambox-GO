import json

import helpers
import const
from api import API
from proxy import PROXY


def main():
    files_ready, credentials_ready = helpers.check_files()

    if not files_ready or not credentials_ready:
        helpers.log(helpers.ERROR, const.CONFIG_FILES_ERR)
        return

    config = helpers.load_json(helpers.files[0])
    credentials = helpers.load_json(helpers.files[1])
    cookie = helpers.load_json(helpers.files[2])

    helpers.set_debug(config.get('debug', False))

    jambox = API(credentials, cookie)

    if helpers.check_channels():
        helpers.export_channels(jambox, config.get('hls', True))

    if helpers.check_list():
        helpers.export_list(config['host'], config['port'])

    channels = helpers.load_json(helpers.channels_file)

    PROXY(
        jambox=jambox,
        channels=channels,
        port=config['port'],
        threaded=config['threaded'],
        cookie=helpers.load_json(helpers.files[2]),
        debug=config['debug'],
    )


if __name__ == '__main__':
    main()
