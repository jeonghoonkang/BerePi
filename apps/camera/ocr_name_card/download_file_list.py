import json
from webdav3.client import Client


def download_file_list(config_path: str = "nocommit_url2.ini") -> None:
    """Read WebDAV credentials from a JSON config and download file_list.json."""
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    nc_cfg = config.get('nextcloud', {})
    options = {
        'webdav_hostname': nc_cfg.get('webdav_hostname'),
        'webdav_login': nc_cfg.get('username'),
        'webdav_password': nc_cfg.get('password'),
    }

    client = Client(options)
    client.verify = True

    remote_dir = '/Photos/biz_card'
    for name in client.list(remote_dir):
        print(name)

    remote_path = f'{remote_dir}/file_list.json'

    local_path = './file_list.json'

    client.download_sync(remote_path=remote_path, local_path=local_path)


if __name__ == '__main__':
    download_file_list()
