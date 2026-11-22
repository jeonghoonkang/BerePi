"""One-level, paginated original/managed directory navigation with confined media."""
from pathlib import Path

from flask import jsonify, request, send_file

from library import EXTENSIONS, VIDEO_EXTENSIONS


class DirectoryTree:
    def __init__(self, library):
        self.library = library

    def roots(self):
        config = self.library.config()
        return {'sources': [{'name': source['source_id'], 'source_id': source['source_id'],
                             'path': source['root'], 'scope': 'source'} for source in config['sources']
                            if source.get('protocol', 'file') == 'file'],
                'managed': [{'name': '라이브러리 관리 폴더', 'path': config['managed_root'], 'scope': 'managed'}]}

    def checked(self, scope, source_id, value=None):
        config = self.library.config()
        if scope == 'managed':
            root = self.library.local(config['managed_root'])
        elif scope == 'source':
            source = next((entry for entry in config['sources'] if entry['source_id'] == source_id
                           and entry.get('protocol', 'file') == 'file'), None)
            if source is None:
                raise ValueError('등록된 로컬 소스가 아닙니다.')
            root = self.library.local(source['root'])
        else:
            raise ValueError('원본 또는 라이브러리 범위를 선택하세요.')
        raw = Path(value) if value else root
        path = self.library.local(raw)
        if not raw.is_absolute() or not raw.is_relative_to(root) or not path.is_relative_to(root):
            raise ValueError('선택한 디렉토리 범위 밖입니다.')
        current = root
        for part in raw.relative_to(root).parts:
            current = current / part
            if part.startswith('.') or current.is_symlink():
                raise ValueError('숨김 경로 또는 링크는 탐색하지 않습니다.')
        if path.is_relative_to(self.library.db) or (scope == 'source' and
                path.is_relative_to(Path(config['managed_root']).resolve())):
            raise ValueError('DB 또는 관리 디렉토리는 원본 범위로 탐색할 수 없습니다.')
        return root, path

    def page(self, scope, source_id=None, path=None, offset=0, kind='directories'):
        if type(offset) is not int or offset < 0 or kind not in {'directories', 'media'}:
            raise ValueError('올바른 페이지와 항목 종류를 지정하세요.')
        root, folder = self.checked(scope, source_id, path)
        if not folder.is_dir():
            raise ValueError('디렉토리가 없거나 연결할 수 없습니다.')
        excluded = [self.library.db]
        if scope == 'source':
            excluded.append(Path(self.library.config()['managed_root']).resolve())
        entries, skipped = [], 0
        for child in folder.iterdir():
            try:
                if child.name.startswith('.') or child.is_symlink() or any(child.is_relative_to(p) for p in excluded):
                    continue
                if kind == 'directories' and child.is_dir():
                    entries.append(child)
                elif kind == 'media' and child.suffix.lower() in EXTENSIONS and child.is_file():
                    entries.append(child)
            except OSError:
                skipped += 1
        entries.sort(key=lambda child: (child.name.casefold(), child.name))
        items = []
        for child in entries[offset:offset + 100]:
            item = {'name': child.name, 'path': str(child)}
            if kind == 'media':
                try:
                    item.update(size_bytes=child.stat().st_size, video=child.suffix.lower() in VIDEO_EXTENSIONS)
                except OSError:
                    skipped += 1
                    continue
            items.append(item)
        return {'root': str(root), 'path': str(folder), 'items': items, 'total': len(entries), 'skipped': skipped,
                'next_offset': offset + 100 if offset + 100 < len(entries) else None}


def register_tree(app, library):
    tree = DirectoryTree(library)

    @app.get('/api/directory-tree/roots')
    def directory_tree_roots():
        return jsonify(tree.roots())

    @app.get('/api/directory-tree')
    def directory_tree_page():
        return jsonify(tree.page(request.args.get('scope'), request.args.get('source_id'), request.args.get('path'),
                                 int(request.args.get('offset', 0)), request.args.get('kind', 'directories')))

    @app.get('/api/directory-tree/media')
    def directory_tree_media():
        _, path = tree.checked(request.args.get('scope'), request.args.get('source_id'), request.args.get('path'))
        if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
            raise ValueError('지원하는 미디어 파일이 아닙니다.')
        from downloads import download_name
        return send_file(path, conditional=True, as_attachment=request.args.get('download') == '1',
                         download_name=download_name(path.name))
