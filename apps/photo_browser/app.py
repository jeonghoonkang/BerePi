"""Local media browser and JSON media library; run with python app.py."""
import argparse
import os
from datetime import datetime
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_file

EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.mp4'}


def positive_limit(value):
    try:
        limit = int(value)
    except (ValueError, TypeError):
        raise argparse.ArgumentTypeError('스캔 한도는 1 이상의 정수여야 합니다.')
    if limit < 1:
        raise argparse.ArgumentTypeError('스캔 한도는 1 이상의 정수여야 합니다.')
    return limit


def create_app(root=None, start=None, db=None, limit=20000):
    limit = positive_limit(limit)
    app = Flask(__name__)
    boundary = Path(root or os.environ.get('PHOTO_BROWSER_ROOT', '/')).expanduser().resolve()
    initial = Path(start or os.environ.get('PHOTO_BROWSER_START', str(Path.home()))).expanduser().resolve()
    if not initial.is_relative_to(boundary):
        initial = boundary

    from library_api import register_library
    register_library(app, boundary, db or os.environ.get('PHOTO_BROWSER_DB', str(Path(__file__).parent / 'db')))
    app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024
    app.config['PHOTO_BROWSER_START'] = str(initial)
    from server_network import ServerNetwork
    server_network = ServerNetwork()
    app.extensions['server_network'] = server_network

    @app.get('/api/server-network')
    def network_info():
        return jsonify(server_network.get())

    def checked(value):
        path = Path(value).expanduser().resolve()
        if not path.is_relative_to(boundary):
            abort(403, description=f'허용된 루트 디렉토리 밖입니다.\n허용된 루트 디렉토리: {boundary}')
        if not path.exists():
            abort(404, description='경로가 없습니다.')
        return path

    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(400)
    def error(exc):
        return jsonify(error=exc.description), exc.code

    @app.get('/')
    @app.get('/jobs')
    def index():
        return render_template('index.html', initial=str(initial), boundary=str(boundary),
                               db_path=str(app.extensions['photo_library'].db), scan_limit=limit, jobs_page=request.path == '/jobs')

    @app.get('/api/browse')
    def browse():
        folder = checked(request.args.get('path', str(initial)))
        if not folder.is_dir():
            abort(400, description='디렉토리를 입력하세요.')
        recursive = request.args.get('recursive') == '1'
        directories, media, skipped = [], [], 0
        truncated = False
        try:
            children = sorted(folder.iterdir(), key=lambda p: p.name.casefold())
        except OSError:
            abort(403, description='디렉토리를 읽을 권한이 없습니다.')
        for child in children:
            try:
                if child.is_dir() and child.resolve().is_relative_to(boundary):
                    directories.append(dict(name=child.name, path=str(child.resolve())))
            except OSError:
                skipped += 1
        def walk_error(_):
            nonlocal skipped
            skipped += 1
        if recursive:
            candidates = (Path(base) / name for base, _, names in os.walk(folder, onerror=walk_error, followlinks=False) for name in names)
        else:
            candidates = iter(children)
        # Bound response memory for very large collections.
        for child in candidates:
            if child.name.startswith('._') or child.suffix.lower() not in EXTENSIONS:
                continue
            try:
                resolved = child.resolve()
                if not resolved.is_relative_to(boundary) or not resolved.is_file():
                    continue
                info = resolved.stat()
                media.append(dict(name=child.name, path=str(resolved), date=datetime.fromtimestamp(info.st_mtime).strftime('%Y-%m-%d'), modified=info.st_mtime, size=info.st_size, video=child.suffix.lower() == '.mp4'))
                if len(media) >= limit:
                    truncated = True
                    break
            except OSError:
                skipped += 1
        media.sort(key=lambda item: (-item['modified'], item['path']))
        return jsonify(path=str(folder), parent=str(folder.parent) if folder != boundary else None, directories=directories, media=media, skipped=skipped, truncated=truncated, limit=limit)

    @app.get('/media')
    def media():
        path = checked(request.args.get('path', ''))
        if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
            abort(404, description='지원하는 미디어 파일이 아닙니다.')
        try:
            return send_file(path, conditional=True)
        except PermissionError:
            abort(403, description='파일을 읽을 권한이 없습니다.')

    return app


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=7081)
    parser.add_argument('--root', help='접근 가능한 최상위 폴더 (기본 /)')
    parser.add_argument('--directory', help='처음 표시할 폴더 (기본 홈)')
    parser.add_argument('--db', help='JSON DB 디렉토리')
    parser.add_argument('--limit', type=positive_limit, default=20000, help='기존 폴더 탐색에서 요청당 스캔할 최대 미디어 수 (기본 20000)')
    args = parser.parse_args()
    app = create_app(args.root, args.directory, args.db, limit=args.limit)
    library = app.extensions['photo_library']
    config = library.config()
    print('\n사진 브라우저 경로 설정', flush=True)
    print(f'허용된 루트 디렉토리: {library.boundary}', flush=True)
    print(f"시작 디렉토리: {app.config['PHOTO_BROWSER_START']}", flush=True)
    print(f'JSON DB 디렉토리: {library.db}', flush=True)
    print(f"관리 디렉토리: {config['managed_root']}", flush=True)
    for source in config.get('sources', []):
        print(f"소스 [{source['source_id']}]: {source['root']}", flush=True)
    if not config.get('sources'):
        print('소스: 등록된 소스 없음', flush=True)
    print(f'기존 폴더 탐색 스캔 한도: {args.limit:,}개\n', flush=True)
    app.run(host=args.host, port=args.port, threaded=True)
