#!/usr/bin/env python3
"""Install a local reverse-geocoding database on Ubuntu 22.04/24.04."""
import argparse
import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

KOREA_OSM = 'https://download.geofabrik.de/asia/south-korea-latest.osm.pbf'
VERSION = '5.3.3'
PACKAGES = ('python3-venv', 'python3-dev', 'build-essential', 'pkg-config', 'libicu-dev',
            'libpq-dev', 'postgresql', 'postgresql-postgis', 'postgresql-postgis-scripts',
            'osm2pgsql', 'curl', 'ca-certificates')


def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError('0보다 큰 정수를 입력하세요.')
    return number


def parser():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument('--project-dir', default=str(Path.home() / '.local/share/photo-browser/nominatim-project'))
    args.add_argument('--venv', help='전용 Python 가상환경 (기본: 프로젝트 옆 nominatim-venv)')
    args.add_argument('--db-name', default='photo_browser_nominatim')
    source = args.add_mutually_exclusive_group()
    source.add_argument('--osm-url', help='다운로드할 HTTPS .osm.pbf 주소 (기본 한국 Geofabrik 추출본)')
    source.add_argument('--osm-file', help='이미 다운로드한 로컬 .osm.pbf 파일')
    args.add_argument('--osm-sha256', help='선택: 다운로드/로컬 지도 파일 SHA-256 검증값')
    args.add_argument('--version', default=VERSION, help=f'Nominatim 5.3.x 패키지 버전 (기본 {VERSION})')
    args.add_argument('--threads', type=positive_int, default=min(4, os.cpu_count() or 1))
    args.add_argument('--osm2pgsql-cache', type=positive_int, default=256, help='가져오기 캐시 MiB (기본 256)')
    args.add_argument('--min-free-gb', type=positive_int, default=10, help='프로젝트·PostgreSQL 저장소의 최소 여유 GiB (기본 10, 용량 보장값 아님)')
    args.add_argument('--dry-run', action='store_true', help='명령·경로만 표시, 설치·다운로드·DB 변경 없음')
    return args


def atomic_text(path, text):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix=path.name + '.', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class Setup:
    def __init__(self, args, user):
        self.args, self.user = args, user
        self.project = Path(args.project_dir).expanduser().resolve()
        self.venv = Path(args.venv).expanduser().resolve() if args.venv else self.project.parent / 'nominatim-venv'
        self.tool = self.venv / 'bin/nominatim'
        self.python = self.venv / 'bin/python'
        self.state_file = self.project / 'setup.json'
        self.env_file = self.project / '.env'
        self.state = json.loads(self.state_file.read_text()) if self.state_file.exists() else None
        if self.state is not None and not isinstance(self.state, dict):
            raise ValueError('setup.json 구축 기록의 형식이 올바르지 않습니다.')
        self.osm_file = Path(args.osm_file).expanduser().resolve() if args.osm_file else self.project / 'downloads/map.osm.pbf'
        self.identity = {'db': args.db_name, 'role': user, 'version': args.version,
                         'source': str(self.osm_file) if args.osm_file else args.osm_url or KOREA_OSM,
                         'sha256': args.osm_sha256, 'venv': str(self.venv)}
        self.environment = {key: value for key, value in os.environ.items() if not key.startswith(('NOMINATIM_', 'PG'))}
        self.environment['PYTHONNOUSERSITE'] = '1'

    def run(self, command, capture=False):
        command = [str(part) for part in command]
        print('+ ' + shlex.join(command), flush=True)
        if self.args.dry_run:
            return ''
        result = subprocess.run(command, check=True, text=True, stdout=subprocess.PIPE if capture else None,
                                env=self.environment)
        return result.stdout.strip() if capture else ''

    def sql(self, statement):
        return self.run(['sudo', '-u', 'postgres', 'psql', '--host=/var/run/postgresql',
                         '--dbname=postgres', '--no-psqlrc', '-At', '-v', 'ON_ERROR_STOP=1', '-c', statement], capture=True)

    def validate(self):
        if not re.fullmatch(r'[a-z][a-z0-9_]{0,62}', self.args.db_name):
            raise ValueError('--db-name은 영문 소문자로 시작하고 소문자·숫자·밑줄만 사용하세요.')
        if not re.fullmatch(r'[a-z_][a-z0-9_-]{0,62}', self.user):
            raise ValueError('현재 Linux 사용자 이름을 PostgreSQL 역할로 사용할 수 없습니다.')
        if not re.fullmatch(r'5\.3\.\d+', self.args.version):
            raise ValueError('이 스크립트는 Nominatim 5.3.x 버전을 지원합니다.')
        if self.args.osm_sha256 and not re.fullmatch(r'[0-9a-fA-F]{64}', self.args.osm_sha256):
            raise ValueError('--osm-sha256에는 64자리 SHA-256 값을 입력하세요.')
        if self.args.osm_file:
            if not self.osm_file.is_file() or self.osm_file.stat().st_size == 0:
                raise ValueError('로컬 지도 파일이 없거나 비어 있습니다.')
        else:
            url = urlsplit(self.identity['source'])
            if url.scheme != 'https' or not url.hostname or url.username or url.password or url.fragment:
                raise ValueError('--osm-url은 인증정보 없는 HTTPS 주소여야 합니다.')
        if self.state and self.state.get('identity') != self.identity:
            raise ValueError('기존 구축 설정과 다릅니다. 다른 프로젝트·DB 이름을 지정하세요.')
        expected_env = self.config_text()
        if self.env_file.exists() and (not self.state or self.env_file.read_text() != expected_env):
            raise ValueError('기존 .env를 덮어쓰지 않습니다. 새 프로젝트 경로를 지정하세요.')
        if self.venv == self.project or self.project.is_relative_to(self.venv) or self.venv.is_relative_to(self.project):
            raise ValueError('프로젝트와 가상환경은 서로 분리된 경로로 지정하세요.')

    def config_text(self):
        return (f'NOMINATIM_DATABASE_DSN="pgsql:dbname={self.args.db_name};user={self.user};host=/var/run/postgresql"\n'
                f'NOMINATIM_DATABASE_WEBUSER={self.user}\nNOMINATIM_IMPORT_STYLE=admin\n')

    def check_space(self, path):
        while not path.exists():
            path = path.parent
        if shutil.disk_usage(path).free < self.args.min_free_gb * 1024 ** 3:
            raise ValueError(f'저장 공간이 부족합니다: {path} (최소 {self.args.min_free_gb} GiB)')

    def save_state(self, status):
        atomic_text(self.state_file, json.dumps({'identity': self.identity, 'status': status}, ensure_ascii=False, indent=2) + '\n')

    def execute(self):
        self.validate()
        if not self.args.dry_run:
            self.check_space(self.project)
            # Prevent two installers racing over the same project.
            self.project.mkdir(parents=True, exist_ok=True)
        print(f'프로젝트: {self.project}\n전용 가상환경: {self.venv}\nPostgreSQL DB: {self.args.db_name}', flush=True)
        self.run(['sudo', 'apt-get', 'update'])
        self.run(['sudo', 'apt-get', 'install', '-y', *PACKAGES])
        self.run(['sudo', 'systemctl', 'start', 'postgresql'])
        exists = self.sql(f"SELECT 1 FROM pg_database WHERE datname = '{self.args.db_name}'") == '1'
        if self.args.dry_run:
            exists = bool(self.state and self.state.get('status') == 'complete')
        if exists and (not self.state or self.state.get('status') != 'complete'):
            raise ValueError('같은 이름의 DB가 이미 있습니다. 미완료 DB도 자동 삭제·덮어쓰기하지 않습니다. 새 DB·프로젝트를 지정하세요.')
        if not exists and self.state and self.state.get('status') == 'complete':
            raise ValueError('완료 기록의 DB가 없습니다. 새 프로젝트·DB로 다시 구축하세요.')
        role = self.sql(f"SELECT rolsuper FROM pg_roles WHERE rolname = '{self.user}'")
        if not role:
            self.run(['sudo', '-u', 'postgres', 'createuser', '--host=/var/run/postgresql', '--superuser', self.user])
        elif role != 't' and not exists:
            raise ValueError('지도 가져오기에 PostgreSQL superuser 역할이 필요합니다. 기존 역할은 자동 변경하지 않습니다.')
        if not self.args.dry_run:
            pg_data = Path(self.sql('SHOW data_directory'))
            # PostgreSQL paths may be inaccessible as the login user; ask PostgreSQL's account.
            available = int(self.run(['sudo', '-u', 'postgres', 'python3', '-c',
                                     'import shutil,sys; print(shutil.disk_usage(sys.argv[1]).free)', str(pg_data)], capture=True))
            if available < self.args.min_free_gb * 1024 ** 3:
                raise ValueError('PostgreSQL 저장소의 디스크 여유가 부족합니다.')
        if not (self.venv / 'pyvenv.cfg').exists():
            if self.venv.exists():
                raise ValueError('기존 가상환경 경로가 Python 가상환경이 아닙니다.')
            self.run(['python3', '-m', 'venv', self.venv])
        self.run([self.python, '-m', 'pip', 'install', f'nominatim-db=={self.args.version}',
                  f'nominatim-api=={self.args.version}', 'psycopg[binary]', 'falcon>=3.1,<5', 'uvicorn>=0.30,<1'])
        if not exists:
            if not self.args.dry_run:
                self.save_state('in_progress')
                if not self.env_file.exists():
                    atomic_text(self.env_file, self.config_text())
                    self.env_file.chmod(0o600)
            if not self.args.osm_file and not self.osm_file.exists():
                temporary = self.osm_file.with_suffix('.pbf.part')
                if not self.args.dry_run:
                    temporary.parent.mkdir(parents=True, exist_ok=True)
                self.run(['curl', '--fail', '--location', '--retry', '3', '--proto', '=https',
                          '--proto-redir', '=https', '--output', temporary, self.identity['source']])
                if not self.args.dry_run:
                    if temporary.stat().st_size == 0:
                        raise ValueError('다운로드한 지도 파일이 비어 있습니다.')
                    temporary.replace(self.osm_file)
            if self.args.osm_sha256 and not self.args.dry_run:
                checksum = hashlib.sha256()
                with self.osm_file.open('rb') as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b''):
                        checksum.update(block)
                if checksum.hexdigest() != self.args.osm_sha256.lower():
                    raise ValueError('지도 파일의 SHA-256이 일치하지 않습니다.')
            self.run([self.tool, 'import', '--project-dir', self.project, '--osm-file', self.osm_file,
                      '--reverse-only', '--threads', self.args.threads, '--osm2pgsql-cache', self.args.osm2pgsql_cache])
        else:
            print('완료된 기존 구축 DB를 검사합니다. 지도를 다시 가져오지 않습니다.', flush=True)
        self.run([self.tool, 'admin', '--project-dir', self.project, '--check-database'])
        server = Path(__file__).with_name('server.py').resolve()
        command = [self.python, server, 'serve', '--project-dir', self.project, '--server', '127.0.0.1:8080']
        if not self.args.dry_run:
            self.save_state('complete')
            launcher = self.project / 'start-nominatim.sh'
            atomic_text(launcher, '#!/bin/sh\nexec ' + shlex.join([str(part) for part in command]) + '\n')
            launcher.chmod(0o700)
        print(('실행 계획 완료 (변경 없음)' if self.args.dry_run else '구축 완료') + '\nPhoto Browser 실행 옵션:\n  --nominatim-command ' + shlex.quote(shlex.join([str(part) for part in command])), flush=True)


def main(argv=None):
    cli = parser()
    args = cli.parse_args(argv)
    try:
        if not args.dry_run:
            if platform.system() != 'Linux':
                raise ValueError('실제 자동 구축은 Ubuntu 22.04/24.04에서 지원합니다. --dry-run은 다른 OS에서도 가능합니다.')
            release = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
            if release.get('ID', '').strip('"') != 'ubuntu' or release.get('VERSION_ID', '').strip('"') not in {'22.04', '24.04'}:
                raise ValueError('Ubuntu 22.04/24.04에서 실행하세요.')
            if os.getuid() == 0:
                raise ValueError('전체 스크립트를 sudo/root로 실행하지 마세요. 일반 사용자로 실행하면 필요한 단계에 sudo를 사용합니다.')
            if os.sysconf('SC_PHYS_PAGES') * os.sysconf('SC_PAGE_SIZE') < 2 * 1024 ** 3:
                raise ValueError('지도 가져오기는 최소 2 GiB RAM이 필요합니다.')
        if os.name == 'posix':
            import pwd
            user = pwd.getpwuid(os.getuid()).pw_name
        else:
            import getpass
            user = getpass.getuser()
        setup = Setup(args, user)
        if args.dry_run:
            setup.execute()
        else:
            import fcntl
            setup.validate()
            setup.project.mkdir(parents=True, exist_ok=True)
            with (setup.project / '.setup.lock').open('a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                # Reload after taking the lock; another invocation may have completed.
                Setup(args, user).execute()
        return 0
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f'구축 중단: {exc}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('구축을 중지했습니다. 부분 DB는 자동 삭제하지 않습니다.', file=sys.stderr)
        return 130


if __name__ == '__main__':
    sys.exit(main())
