"""Docker-only Nominatim lifecycle with parent-death monitoring and persistent DBs."""
import hashlib
import json
import os
import re
import select
import shutil
import socket
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, build_opener

DEFAULT_IMAGE = 'mediagis/nominatim:5.3'
DEFAULT_PBF = 'https://download.geofabrik.de/asia/south-korea-latest.osm.pbf'
DEFAULT_VOLUME = 'photo-browser-nominatim-5-3'
URL_ENV = 'PHOTO_BROWSER_REVERSE_GEOCODER_URL'
MANAGED = 'org.berepi.photo-browser.nominatim'
CONFIG = MANAGED + '.config'
OWNER = MANAGED + '.owner'
PORT = MANAGED + '.port'


def positive_int(value):
    number = int(value)
    if number <= 0:
        raise ValueError('0보다 큰 정수를 지정하세요.')
    return number


def _healthy(url, timeout=.5):
    try:
        with build_opener(ProxyHandler({})).open(url, timeout=timeout) as response:
            data = json.loads(response.read(16384))
        return isinstance(data, dict) and type(data.get('status')) is int and data['status'] == 0
    except (OSError, ValueError):
        return False


class Docker:
    def __init__(self, executable):
        self.executable = executable

    def run(self, *args, capture=True, check=True, timeout=30):
        try:
            result = subprocess.run([self.executable, *args], check=False, text=True, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE if capture else None,
                                    stderr=subprocess.PIPE if capture else None, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f'Docker {args[0]} 응답 시간이 초과되었습니다.') from exc
        if check and result.returncode:
            raise RuntimeError(f'Docker {args[0]} 실패: {(result.stderr or "Docker 로그를 확인하세요.").strip()}')
        return result

    def inspect(self, kind, name):
        # List first: distinguish missing objects from daemon/permission failures.
        if kind == 'volume':
            listed = self.run('volume', 'ls', '--format', '{{.Name}}').stdout.splitlines()
        else:
            listed = self.run('container', 'ls', '-a', '--format', '{{.Names}}').stdout.splitlines()
        if name not in listed:
            return None
        return json.loads(self.run(kind, 'inspect', name).stdout)[0]


def settings(image, pbf_url, volume, port):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]+', volume):
        raise ValueError('Nominatim 볼륨은 Docker named volume 이름으로 지정하세요.')
    if not image or image.startswith('-') or any(c.isspace() for c in image):
        raise ValueError('올바른 Docker 이미지 이름을 지정하세요.')
    url = urlsplit(pbf_url)
    if url.scheme != 'https' or not url.hostname or url.username or url.password or url.fragment:
        raise ValueError('지도 다운로드 주소는 인증정보 없는 HTTPS URL이어야 합니다.')
    if not 1 <= port <= 65535:
        raise ValueError('Nominatim 포트는 1~65535 범위여야 합니다.')
    fingerprint = hashlib.sha256(json.dumps([image, pbf_url, 'admin', 'reverse-only', 'pg16']).encode()).hexdigest()
    name = 'photo-browser-nominatim-' + hashlib.sha256(volume.encode()).hexdigest()[:12]
    return {'image': image, 'pbf_url': pbf_url, 'volume': volume, 'port': port,
            'name': name, 'fingerprint': fingerprint, 'owner': uuid.uuid4().hex}


def _matches(record, config):
    labels = (record.get('Config', {}).get('Labels') if 'Config' in record else record.get('Labels')) or {}
    return labels.get(MANAGED) == '1' and labels.get(CONFIG) == config['fingerprint']


def _alive():
    return not select.select([sys.stdin], [], [], 0)[0]


def _pull(docker, image):
    if docker.run('image', 'inspect', image, check=False).returncode == 0:
        return True
    print(f'Nominatim Docker 이미지 다운로드: {image}', flush=True)
    process = subprocess.Popen([docker.executable, 'pull', image], stdin=subprocess.DEVNULL)
    try:
        while process.poll() is None:
            if not _alive():
                return False
            time.sleep(.2)
        if process.returncode:
            raise RuntimeError('Nominatim 이미지 다운로드에 실패했습니다.')
        return _alive()
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def _remove_owned(docker, config):
    record = docker.inspect('container', config['name'])
    if not record or ((record.get('Config') or {}).get('Labels') or {}).get(OWNER) != config['owner']:
        return
    # Target the immutable ID after verifying ownership. Never remove volumes.
    container_id = record['Id']
    if record['State']['Running']:
        docker.run('stop', '--time', '10', container_id, check=False, timeout=20)
    docker.run('rm', '--force', container_id)


def _watch(config):
    docker = Docker(config['docker'])
    logs = None
    try:
        if not _pull(docker, config['image']) or not _alive():
            return 0
        docker.run('create', '--name', config['name'], '--restart=no', '--shm-size=1g',
                   '--label', MANAGED + '=1', '--label', CONFIG + '=' + config['fingerprint'],
                   '--label', OWNER + '=' + config['owner'],
                   '--label', PORT + '=' + str(config['port']),
                   '--publish', f'127.0.0.1:{config["port"]}:8080',
                   '--mount', f'type=volume,source={config["volume"]},target=/var/lib/postgresql/16/main',
                   '--env', 'PBF_URL=' + config['pbf_url'], '--env', 'IMPORT_STYLE=admin',
                   '--env', 'REVERSE_ONLY=true', '--env', 'UPDATE_MODE=none',
                   '--env', 'THREADS=2', '--env', 'GUNICORN_WORKERS=2',
                   '--env', 'POSTGRES_SHARED_BUFFERS=256MB', '--env', 'POSTGRES_MAINTENANCE_WORK_MEM=512MB',
                   '--env', 'POSTGRES_AUTOVACUUM_WORK_MEM=256MB', '--env', 'POSTGRES_EFFECTIVE_CACHE_SIZE=1GB',
                   config['image'])
        if not _alive():
            return 0
        docker.run('start', config['name'])
        logs = subprocess.Popen([docker.executable, 'logs', '--follow', config['name']], stdin=subprocess.DEVNULL)
        while _alive():
            record = docker.inspect('container', config['name'])
            if not record or not record['State']['Running']:
                raise RuntimeError('Nominatim 컨테이너가 종료되었습니다. Docker 로그를 확인하세요.')
            time.sleep(.25)
        return 0
    finally:
        if logs is not None and logs.poll() is None:
            logs.terminate()
            try:
                logs.wait(timeout=2)
            except subprocess.TimeoutExpired:
                logs.kill()
                logs.wait()
        _remove_owned(docker, config)


def _wait_ready(status_url, timeout, watcher=None):
    deadline = time.monotonic() + timeout
    next_notice = 0
    while time.monotonic() < deadline:
        if watcher is not None and watcher.poll() is not None:
            raise RuntimeError('Nominatim Docker 실행이 종료되었습니다. 위 Docker 로그를 확인하세요.')
        if _healthy(status_url) and (watcher is None or watcher.poll() is None):
            return
        if time.monotonic() >= next_notice:
            print('Nominatim Docker 준비 대기 중… 첫 실행은 지도 가져오기가 끝나야 합니다.', flush=True)
            next_notice = time.monotonic() + 30
        time.sleep(.5)
    raise RuntimeError('Nominatim 준비 시간이 초과되었습니다. --nominatim-ready-timeout과 Docker 로그를 확인하세요.')


@contextmanager
def managed_nominatim_docker(enabled, image=DEFAULT_IMAGE, pbf_url=DEFAULT_PBF,
                             volume=DEFAULT_VOLUME, port=8080, timeout=7200):
    if not enabled:
        yield
        return
    if os.name != 'posix':
        raise ValueError('Docker 종료 감시는 Linux/macOS에서 지원합니다.')
    config = settings(image, pbf_url, volume, port)
    if timeout <= 0:
        raise ValueError('Nominatim 대기 시간은 0보다 커야 합니다.')
    executable = shutil.which('docker')
    if not executable:
        raise ValueError('Docker 실행 파일이 없습니다. Docker Engine 또는 Docker Desktop을 먼저 설치하세요.')
    config['docker'] = executable
    docker = Docker(executable)
    docker.run('info')
    endpoint = f'http://127.0.0.1:{port}/reverse'
    previous = os.environ.get(URL_ENV)
    if previous and previous != endpoint:
        raise ValueError(f'{URL_ENV}을 해제하거나 Docker 주소 {endpoint}와 일치시키세요.')
    record = docker.inspect('container', config['name'])
    mounted = docker.run('container', 'ls', '--filter', f'volume={volume}', '--format', '{{.Names}}').stdout.splitlines()
    if any(name != config['name'] for name in mounted):
        raise ValueError('같은 지도 볼륨을 다른 컨테이너가 사용 중입니다. 새 --nominatim-volume을 지정하세요.')
    reused = False
    if record:
        if not _matches(record, config):
            raise ValueError('같은 이름의 다른 컨테이너가 있습니다. 다른 --nominatim-volume을 지정하세요.')
        if record['State']['Running']:
            if ((record.get('Config') or {}).get('Labels') or {}).get(PORT) != str(port):
                raise ValueError('기존 Nominatim 컨테이너의 포트와 --nominatim-port가 다릅니다.')
            reused = True
        elif record['State'].get('Status') in {'exited', 'dead'}:
            docker.run('rm', record['Id'])
        else:
            raise ValueError('같은 볼륨의 컨테이너가 생성 중이거나 비정상 상태입니다. Docker 상태를 확인하세요.')
    volume_record = docker.inspect('volume', volume)
    if volume_record and not _matches(volume_record, config):
        raise ValueError('기존 볼륨의 지도 URL·이미지 설정이 다르거나 관리 볼륨이 아닙니다. 새 볼륨을 지정하세요.')
    if not volume_record:
        docker.run('volume', 'create', '--label', MANAGED + '=1', '--label', CONFIG + '=' + config['fingerprint'], volume)
    watcher = None
    try:
        if not reused:
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=.2):
                    raise ValueError('Nominatim Docker 포트를 다른 프로세스가 사용 중입니다.')
            except OSError:
                pass
            watcher = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), json.dumps(config)],
                                       stdin=subprocess.PIPE, start_new_session=True)
        print(f'Nominatim Docker: {config["name"]} · 볼륨: {volume}' + (' (기존 컨테이너 재사용)' if reused else ''), flush=True)
        _wait_ready(endpoint.replace('/reverse', '/status?format=json'), timeout, watcher)
        os.environ[URL_ENV] = endpoint
        yield
    finally:
        if previous is None:
            os.environ.pop(URL_ENV, None)
        else:
            os.environ[URL_ENV] = previous
        if watcher is not None:
            watcher.stdin.close()
            # Docker create/start can finish in-flight before the watchdog cleans up.
            try:
                watcher.wait(timeout=90)
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError('Docker 종료가 지연되고 있습니다. 컨테이너 상태와 Docker 데몬을 확인하세요.') from exc


if __name__ == '__main__':
    try:
        sys.exit(_watch(json.loads(sys.argv[1])))
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        print(f'Nominatim Docker 오류: {exc}', file=sys.stderr, flush=True)
        sys.exit(1)
