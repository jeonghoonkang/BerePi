"""Keep a foreground local Nominatim process tied to Photo Browser's lifetime."""
import json
import os
import select
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from urllib.request import ProxyHandler, build_opener

URL_ENV = 'PHOTO_BROWSER_REVERSE_GEOCODER_URL'
DEFAULT_URL = 'http://127.0.0.1:8080/reverse'


def _signal_group(pid, sig):
    try:
        os.killpg(pid, sig)
    except ProcessLookupError:
        return False
    return True


def _stop_group(service):
    if _signal_group(service.pid, signal.SIGTERM):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            service.poll()
            if not _signal_group(service.pid, 0):
                break
            time.sleep(.05)
        else:
            _signal_group(service.pid, signal.SIGKILL)
    service.wait()


def _watch(argv):
    # The write end is held only by Photo Browser. Even SIGKILL closes it.
    if select.select([sys.stdin], [], [], 0)[0]:
        return 0
    service = subprocess.Popen(argv, stdin=subprocess.DEVNULL, start_new_session=True)
    try:
        while service.poll() is None:
            if select.select([sys.stdin], [], [], .2)[0]:
                return 0
        return service.returncode or 1  # A foreground server should not exit on its own.
    finally:
        _stop_group(service)


def _status_url(endpoint):
    url = urlsplit(endpoint)
    if (url.scheme != 'http' or url.hostname not in {'localhost', '127.0.0.1', '::1'}
            or url.username or url.password or url.query or url.fragment
            or not url.path.endswith('/reverse')):
        raise ValueError('함께 실행할 Nominatim 주소는 로컬 HTTP /reverse 주소여야 합니다.')
    return url, urlunsplit(url._replace(path=url.path[:-len('reverse')] + 'status', query='format=json'))


def _healthy(status_url, timeout):
    opener = build_opener(ProxyHandler({}))
    try:
        with opener.open(status_url, timeout=timeout) as response:
            result = json.loads(response.read(16384))
        return isinstance(result, dict) and type(result.get('status')) is int and result['status'] == 0
    except (OSError, ValueError):
        return False


def _validate_command(argv):
    executable = shutil.which(os.path.expanduser(argv[0]))
    if not executable and argv[0] == 'nominatim':
        local_server = Path(__file__).with_name('nominatim') / 'server.py'
        if local_server.is_file():
            argv = [sys.executable, str(local_server), *argv[1:]]
            executable = sys.executable
    if not executable:
        raise ValueError(f'Nominatim 실행 파일을 찾을 수 없거나 실행 권한이 없습니다: {argv[0]}')
    argv = [executable, *argv[1:]]
    for index, argument in enumerate(argv[1:], 1):
        if argument == '--project-dir':
            if index + 1 >= len(argv):
                raise ValueError('--project-dir에 Nominatim 프로젝트 경로를 지정하세요.')
            project = argv[index + 1]
        elif argument.startswith('--project-dir='):
            project = argument.split('=', 1)[1]
        else:
            continue
        if not project or not Path(project).is_dir():
            raise ValueError(f'Nominatim 프로젝트 디렉토리가 없습니다: {project}')
    return argv


def _wait_ready(watcher, status_url, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if watcher.poll() is not None:
            raise RuntimeError('Nominatim 실행 명령이 먼저 종료되었습니다. 실행 명령과 서버 로그를 확인하세요.')
        if _healthy(status_url, min(.5, max(.01, deadline - time.monotonic()))) and watcher.poll() is None:
            return
        time.sleep(.1)
    raise RuntimeError(f'Nominatim이 {timeout:g}초 안에 준비되지 않았습니다. 실행 명령과 지도 DB를 확인하세요.')


@contextmanager
def managed_nominatim(command, timeout=30):
    if not command:
        yield
        return
    if os.name != 'posix':
        raise ValueError('Nominatim 동시 실행은 Linux/macOS에서 지원합니다.')
    argv = shlex.split(command)
    if not argv:
        raise ValueError('Nominatim 실행 명령을 입력하세요.')
    previous = os.environ.get(URL_ENV)
    endpoint = previous or DEFAULT_URL
    url, status_url = _status_url(endpoint)
    occupied = False
    try:
        with socket.create_connection((url.hostname, url.port or 80), timeout=.2):
            occupied = True
    except OSError:
        pass
    if occupied:
        if not _healthy(status_url, .5):
            raise ValueError('Nominatim 포트가 이미 사용 중이지만 상태 API가 정상이 아닙니다. 포트·지도 DB·기존 프로세스를 확인하세요.')
        os.environ[URL_ENV] = endpoint
        print(f'Nominatim 점검: 기존 서버 정상 · 재사용: {endpoint} (종료 관리 제외)', flush=True)
        try:
            yield
        finally:
            if previous is None:
                os.environ.pop(URL_ENV, None)
            else:
                os.environ[URL_ENV] = previous
        return
    argv = _validate_command(argv)
    print(f'Nominatim 점검: 실행 파일 확인 완료 · 새 서버 시작: {argv[0]}', flush=True)
    watcher = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), *argv],
                               stdin=subprocess.PIPE, start_new_session=True)
    try:
        _wait_ready(watcher, status_url, timeout)
        os.environ[URL_ENV] = endpoint
        print(f'Nominatim 위치 조회 준비 완료: {endpoint}', flush=True)
        yield
    finally:
        if previous is None:
            os.environ.pop(URL_ENV, None)
        else:
            os.environ[URL_ENV] = previous
        watcher.stdin.close()
        watcher.wait(timeout=8)


if __name__ == '__main__':
    sys.exit(_watch(sys.argv[1:]))
