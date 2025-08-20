import json
import requests
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
    entries = client.list(remote_dir)
    for name in entries:
        print(name)

    remote_path = f'{remote_dir}/file_list.json'
    local_path = './file_list.json'

    if not isinstance(remote_path, str):
        print(f"remote_path must be str, got {type(remote_path).__name__}")
        return


    if 'file_list.json' not in entries:
        print(f"{remote_path} not found on server")
        return

    try:
        client.download_sync(remote_path=remote_path, local_path=local_path)
    except KeyError:
        url = f"{options['webdav_hostname'].rstrip('/')}{remote_path}"
        with requests.get(
            url,
            auth=(options['webdav_login'], options['webdav_password']),
            stream=True,
            verify=client.verify,
        ) as r:
            r.raise_for_status()
            with open(local_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)


if __name__ == '__main__':
    download_file_list()
