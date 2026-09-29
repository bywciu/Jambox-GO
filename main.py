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

    channels = helpers.load_json(helpers.channels_file)

    def channel_sort_key(item):
        index, channel = item
        try:
            number = int(channel.get('number'))
        except (AttributeError, TypeError, ValueError):
            return (1, index)
        return (0, number, index)

    channels = [
        channel
        for _, channel in sorted(
            enumerate(channels),
            key=channel_sort_key,
        )
    ]

    PROXY(
        jambox=jambox,
        channels=channels,
        host='0.0.0.0',
        public_host=config['host'],
        port=config['port'],
        tuners=config.get('tuners', 4),
        threaded=config['threaded'],
        cookie=helpers.load_json(helpers.files[2]),
        debug=config['debug'],
    )


if __name__ == '__main__':
    main()
