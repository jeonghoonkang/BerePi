"""Docker-only Nominatim lifecycle with parent-death monitoring and persistent DBs."""
import hashlib
import json
import os
import re
import select
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timedelta
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
_OBSERVER = ContextVar('nominatim_observer', default=None)


def _emit(*args, **kwargs):
    print(*args, **kwargs)
    observer = _OBSERVER.get()
    if observer is not None:
        observer(' '.join(str(arg) for arg in args))


@contextmanager
def observe_nominatim(observer):
    token = _OBSERVER.set(observer)
    try:
        yield
    finally:
        _OBSERVER.reset(token)


class NominatimStopped(Exception):
    pass


def _relay_watcher(stream, observer):
    with observe_nominatim(observer):
        for line in stream:
            _emit(line.rstrip(), flush=True)
    stream.close()


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
    _emit(f'Nominatim Docker 이미지 다운로드: {image}', flush=True)
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


def _report_database(docker, config, running=False):
    if not running and not config.get('volume_existed'):
        _emit('지도 DB: 없음 · 지도 다운로드 및 DB 최초 구축이 필요합니다.', flush=True)
        return
    # A volume alone does not prove that the initial import completed.
    probe = ('if [ -f /var/lib/postgresql/16/main/PG_VERSION ] && '
             '[ -f /var/lib/postgresql/16/main/import-finished ]; '
             'then exit 0; else exit 3; fi')
    if running:
        result = docker.run('exec', config['name'], '/bin/sh', '-c', probe, check=False)
    else:
        result = docker.run('run', '--rm', '--network=none', '--read-only',
                            '--mount', f'type=volume,source={config["volume"]},target=/var/lib/postgresql/16/main,readonly',
                            '--entrypoint', '/bin/sh', config['image'], '-c', probe, check=False)
    if result.returncode == 0:
        _emit('지도 DB: 기존 DB 및 가져오기 완료 표시 확인 · 재다운로드 없이 시작 가능'
              ' (실제 사용 가능 여부는 상태 API로 최종 확인)', flush=True)
    elif result.returncode == 3:
        _emit('지도 DB: 볼륨은 있으나 구축 완료가 확인되지 않습니다.'
              ' · 다운로드 및 DB 구축이 필요할 수 있습니다.', flush=True)
    else:
        raise RuntimeError('지도 DB 사전 점검 실패: ' + (result.stderr or 'Docker 로그를 확인하세요.').strip())


class DownloadProgress:
    """Translate the image's curl meter without estimating DB import duration."""
    def __init__(self):
        self.downloading = False
        self.last_notice = -float('inf')

    def consume(self, line):
        if 'Downloading OSM extract from' in line and not line.startswith('+'):
            self.downloading = True
            _emit('Nominatim 지도 다운로드 시작 · 진행률/용량/속도/남은 시간/완료 예상 계산 대기', flush=True)
        if self.downloading:
            fields = line.split()
            if len(fields) == 12 and all(fields[i].isdigit() for i in (0, 2, 4)):
                percent = int(fields[2])
                now = time.monotonic()
                if now - self.last_notice >= 2 or percent == 100:
                    self.last_notice = now
                    remaining = fields[10]
                    finish = '계산 중'
                    if re.fullmatch(r'\d+:\d{2}:\d{2}', remaining):
                        hours, minutes, seconds = map(int, remaining.split(':'))
                        finish = (datetime.now().astimezone() + timedelta(
                            hours=hours, minutes=minutes, seconds=seconds)).strftime('%Y-%m-%d %H:%M:%S %Z')
                    _emit(f'Nominatim 지도 다운로드 · {percent}% · {fields[3]} / {fields[1]}'
                          f' · 속도 {fields[11]}/s · 경과 {fields[9]} · 남은 시간 {remaining}'
                          f' · 다운로드 완료 예상 {finish}', flush=True)
                return
            if 'nominatim import --osm-file' in line or 'Reading OSM extract from' in line:
                self.downloading = False
                _emit('Nominatim 지도 DB 구축 중 · 전체 완료 예상: 계산 불가 (다운로드 이후 DB 가져오기·색인 필요)', flush=True)
        _emit(line, flush=True)


def _follow_logs(stream):
    progress = DownloadProgress()
    pending = b''
    try:
        while True:
            chunk = os.read(stream.fileno(), 4096)
            if not chunk:
                break
            parts = re.split(b'[\r\n]', pending + chunk)
            pending = parts.pop()
            for part in parts:
                if part:
                    progress.consume(part.decode('utf-8', errors='replace'))
            # Bound memory even when a custom image emits an unterminated line.
            if len(pending) > 65536:
                progress.consume(pending.decode('utf-8', errors='replace'))
                pending = b''
        if pending:
            progress.consume(pending.decode('utf-8', errors='replace'))
    finally:
        stream.close()


def _watch(config):
    docker = Docker(config['docker'])
    logs = None
    try:
        if not _pull(docker, config['image']) or not _alive():
            return 0
        _report_database(docker, config)
        if not _alive():
            return 0
        _emit('사전 점검이 완료되어 실행 준비가 되었습니다. Nominatim 실행을 시작합니다.', flush=True)
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
        logs = subprocess.Popen([docker.executable, 'logs', '--follow', config['name']],
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        threading.Thread(target=_follow_logs, args=(logs.stdout,), daemon=True).start()
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


def _wait_ready(status_url, timeout, watcher=None, stop_event=None):
    started = time.monotonic()
    deadline = started + timeout
    next_notice = 0
    while time.monotonic() < deadline:
        if stop_event is not None and stop_event.is_set():
            raise NominatimStopped()
        if watcher is not None and watcher.poll() is not None:
            raise RuntimeError('Nominatim Docker 실행이 종료되었습니다. 위 Docker 로그를 확인하세요.')
        if _healthy(status_url) and (watcher is None or watcher.poll() is None):
            _emit(f'Nominatim 준비 완료 · 소요 {time.monotonic() - started:.0f}초 · '
                  f'완료 시각 {datetime.now().astimezone():%Y-%m-%d %H:%M:%S %Z}', flush=True)
            return
        if time.monotonic() >= next_notice:
            _emit(f'Nominatim Docker 준비 대기 · 경과 {time.monotonic() - started:.0f}초'
                  ' · 전체 완료 예상: 계산 불가 (이미지 다운로드·지도 DB 구축 포함)', flush=True)
            next_notice = time.monotonic() + 30
        time.sleep(.5)
    raise RuntimeError('Nominatim 준비 시간이 초과되었습니다. --nominatim-ready-timeout과 Docker 로그를 확인하세요.')


@contextmanager
def nominatim_shutdown_signals(enabled):
    """Unwind the lifecycle on shutdown and wait for Docker cleanup before exit."""
    if not enabled:
        yield
        return
    previous = {}

    def shutdown(signum, frame):
        # A repeated stop request must not interrupt the watchdog wait.
        for stop_signal in previous:
            signal.signal(stop_signal, signal.SIG_IGN)
        raise SystemExit(128 + signum)

    try:
        for stop_signal in (signal.SIGINT, signal.SIGTERM):
            previous[stop_signal] = signal.signal(stop_signal, shutdown)
        yield
    finally:
        for stop_signal, handler in previous.items():
            signal.signal(stop_signal, handler)


@contextmanager
def managed_nominatim_docker(enabled, image=DEFAULT_IMAGE, pbf_url=DEFAULT_PBF,
                             volume=DEFAULT_VOLUME, port=8080, timeout=7200, stop_event=None):
    if not enabled:
        yield
        return
    if os.name != 'posix':
        raise ValueError('Docker 종료 감시는 Linux/macOS에서 지원합니다.')
    config = settings(image, pbf_url, volume, port)
    if timeout <= 0:
        raise ValueError('Nominatim 대기 시간은 0보다 커야 합니다.')
    _emit('\nNominatim Docker 시작 전 종합 점검', flush=True)
    executable = shutil.which('docker')
    if not executable:
        _emit('Docker 설치: 확인되지 않음 · 실행 불가', flush=True)
        raise ValueError('Docker 실행 파일이 없습니다. Docker Engine 또는 Docker Desktop을 먼저 설치하세요.')
    _emit(f'Docker 설치: 확인 · {executable}', flush=True)
    config['docker'] = executable
    docker = Docker(executable)
    try:
        docker.run('info')
    except RuntimeError:
        _emit('Docker 데몬: 연결 실패 · Docker 실행 상태와 접근 권한을 확인하세요.', flush=True)
        raise
    _emit('Docker 데몬: 연결 가능', flush=True)
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
    config['volume_existed'] = volume_record is not None
    _emit(f'지도 DB 볼륨: {volume} · ' + ('기존 볼륨 확인 · 설정 일치' if volume_record else '없음 · 새로 생성'), flush=True)
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
            _emit(f'조회 포트: 127.0.0.1:{port} · 사용 가능', flush=True)
            cached = docker.run('image', 'inspect', image, check=False).returncode == 0
            _emit(f'Docker 이미지: {image} · ' + ('설치됨' if cached else '없음 · 다운로드 예정'), flush=True)
            watcher = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), json.dumps(config)],
                                       stdin=subprocess.PIPE, start_new_session=True,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            threading.Thread(target=_relay_watcher, args=(watcher.stdout, _OBSERVER.get()), daemon=True).start()
        else:
            _report_database(docker, config, running=True)
            _emit('사전 점검이 완료되어 실행 준비가 되었습니다. 실행 중인 Nominatim을 재사용합니다.', flush=True)
        _emit(f'Nominatim Docker: {config["name"]} · 볼륨: {volume}' + (' (기존 컨테이너 재사용)' if reused else ''), flush=True)
        _wait_ready(endpoint.replace('/reverse', '/status?format=json'), timeout, watcher, stop_event)
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
        _emit(f'Nominatim Docker 오류: {exc}', file=sys.stderr, flush=True)
        sys.exit(1)
