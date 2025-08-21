import argparse
import json


def download_file_list(config_path: str = "nocommit_url2.ini") -> None:
    """Read WebDAV credentials from a JSON config and download file_list.json."""
    from webdav3.client import Client

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
        import requests

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
    except ImportError:
        print('requests library is required for download')


def check_ctime(local_path: str = './file_list.json') -> None:
    """Print oldest and newest ctime values from file_list.json."""
    try:
        from rich.console import Console
        from rich.syntax import Syntax
    except ImportError:
        print('rich library is required for check')
        return

    console = Console()
    try:
        with open(local_path, 'r', encoding='utf-8') as f:
            text = f.read()
    except FileNotFoundError:
        console.print(f"[red]{local_path} not found[/red]")
        return

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        console.print(f"[red]JSON syntax error: {e}[/red]")
        syntax = Syntax(text, "json", theme="monokai", line_numbers=True, highlight_lines={e.lineno})
        console.print(syntax)
        return

    items = data.values() if isinstance(data, dict) else data
    ctimes = []
    for item in items:
        if isinstance(item, dict) and 'ctime' in item:
            ctimes.append(item['ctime'])

    if not ctimes:
        console.print('[yellow]No ctime fields found[/yellow]')
        return

    console.print(f"Oldest ctime: {min(ctimes)}")
    console.print(f"Newest ctime: {max(ctimes)}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Download or check file_list.json')
    parser.add_argument('--check', action='store_true', help='show ctime range instead of downloading')
    parser.add_argument('--config', default='nocommit_url2.ini', help='path to JSON config file')
    args = parser.parse_args()

    if args.check:
        check_ctime()
    else:
        download_file_list(config_path=args.config)
