#!/usr/bin/env python3
"""Manage the independent Nominatim Compose service; Python standard library only."""

import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
from urllib.error import URLError
from urllib.request import urlopen


DIRECTORY = Path(__file__).resolve().parent


def initialize(directory):
    template = (directory / '.env.example').read_text(encoding='utf-8')
    contents = template.replace('NOMINATIM_PASSWORD=\n',
                                'NOMINATIM_PASSWORD=' + secrets.token_hex(32) + '\n')
    # Exclusive creation also protects an existing configuration from concurrent init.
    descriptor = os.open(str(directory / '.env'), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
        stream.write(contents)
    print('설정 생성: ' + str(directory / '.env'))


def compose_command(directory):
    if not (directory / '.env').is_file():
        raise ValueError('설정 파일이 없습니다. 먼저 docker_service.py init을 실행하세요.')
    if shutil.which('docker') is None:
        raise ValueError('Docker와 Docker Compose v2를 먼저 설치하고 Docker를 실행하세요.')
    return ['docker', 'compose', '--project-directory', str(directory),
            '--env-file', str(directory / '.env'), '-f', str(directory / 'compose.yaml')]


def check_service(command):
    # Compose resolves .env quoting, interpolation and environment overrides for us.
    # Capture config because it contains the database password; never print it.
    result = subprocess.run(command + ['config', '--format', 'json'],
                            check=True, capture_output=True, text=True)
    service = json.loads(result.stdout)['services']['nominatim']
    port = next(p for p in service['ports'] if int(p['target']) == 8080)
    host = port.get('host_ip', '127.0.0.1')
    if host in ('0.0.0.0', '::'):
        host = '127.0.0.1' if host == '0.0.0.0' else '::1'
    if ':' in host:
        host = '[' + host + ']'
    endpoint = 'http://{}:{}/status?format=json'.format(host, port['published'])
    with urlopen(endpoint, timeout=10) as response:
        payload = json.load(response)
    if not isinstance(payload, dict) or payload.get('status') != 0:
        raise ValueError('아직 지도 DB를 사용할 수 없습니다. logs에서 가져오기 상태를 확인하세요.')
    print('지도 DB 준비 완료: ' + endpoint)


def main(argv=None, directory=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('init', 'up', 'stop', 'down', 'restart',
                                           'status', 'logs', 'check'))
    args = parser.parse_args(argv)
    directory = Path(directory or DIRECTORY).resolve()
    try:
        if args.action == 'init':
            initialize(directory)
            return 0
        command = compose_command(directory)
        if args.action == 'check':
            check_service(command)
            return 0
        actions = {
            'up': ['up', '-d'], 'stop': ['stop'], 'down': ['down'],
            'restart': ['restart'], 'status': ['ps', '--all'],
            'logs': ['logs', '--follow', '--tail', '100', 'nominatim'],
        }
        # Suppress configuration output since it includes credentials.
        subprocess.run(command + ['config', '--quiet'], check=True)
        subprocess.run(command + actions[args.action], check=True)
        if args.action == 'up':
            print('백그라운드 실행 요청 완료. 최초 지도 가져오기 후 check로 준비 상태를 확인하세요.')
        return 0
    except FileExistsError:
        print('기존 .env를 보존했습니다. 설정 변경은 해당 파일을 직접 편집하세요.', file=sys.stderr)
    except subprocess.CalledProcessError as exc:
        # Captured Compose config can contain credentials in stdout/stderr.
        print('Docker Compose 실행 실패 (종료 코드 {}). Docker 상태와 .env 설정을 확인하세요.'
              .format(exc.returncode), file=sys.stderr)
    except (OSError, ValueError, KeyError, TypeError, StopIteration, URLError):
        print('실행 실패: Docker 설치·실행 상태, .env와 지도 가져오기 로그를 확인하세요. '
              '초기 설정: python3 docker_service.py init', file=sys.stderr)
    except KeyboardInterrupt:
        return 130
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
