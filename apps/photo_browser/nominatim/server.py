"""Foreground Nominatim ASGI service for Photo Browser's process supervisor."""
import argparse
from importlib import import_module
from pathlib import Path
from urllib.parse import urlsplit


def server_address(value):
    try:
        url = urlsplit('http://' + value)
        port = url.port
        if (not url.hostname or port is None or not 1 <= port <= 65535
                or url.username or url.password or url.path or url.query or url.fragment):
            raise ValueError
        return url.hostname, port
    except ValueError:
        raise argparse.ArgumentTypeError('서버 주소는 HOST:PORT 형식이어야 합니다. 예: 127.0.0.1:8080')


def load_runtime():
    # Import only when starting, so --help also works before optional packages are installed.
    engine = import_module('nominatim_api.server.falcon.server')
    uvicorn = import_module('uvicorn')
    return engine.get_application, uvicorn.run


def main(argv=None):
    parser = argparse.ArgumentParser(prog='nominatim', description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    serve = commands.add_parser('serve', help='자체 Nominatim 지도 DB를 사용하는 HTTP 조회 서버 실행')
    serve.add_argument('--project-dir', required=True, help='지도 DB 연결 설정이 있는 Nominatim 프로젝트 디렉토리')
    serve.add_argument('--server', type=server_address, default=('127.0.0.1', 8080), help='대기 주소 (기본 127.0.0.1:8080)')
    args = parser.parse_args(argv)
    project = Path(args.project_dir).expanduser().resolve()
    if not project.is_dir():
        parser.error(f'Nominatim 프로젝트 디렉토리가 없습니다: {project}')
    try:
        create_application, run_server = load_runtime()
    except ImportError as exc:
        parser.error(f'Nominatim 실행 패키지가 준비되지 않았습니다 ({exc}). '
                     f'사용할 Python 환경에 설치하세요: python3 -m pip install -r {Path(__file__).with_name("requirements.txt")}')
    try:
        application = create_application(project)
    except Exception as exc:
        parser.error(f'Nominatim 프로젝트 초기화 실패: {exc}. 지도 DB와 프로젝트 설정을 확인하세요.')
    host, port = args.server
    print(f'Nominatim 프로젝트: {project}', flush=True)
    print(f'Nominatim 대기 주소: {host}:{port}', flush=True)
    # Stay in the supervisor's process group. No daemon, reload process or detached worker.
    run_server(application, host=host, port=port, workers=1, reload=False,
               log_level='info', timeout_graceful_shutdown=3)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
