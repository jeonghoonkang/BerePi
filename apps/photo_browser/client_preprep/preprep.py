#!/usr/bin/env python3
"""Standalone Python 3.10+ client; only the standard library is required."""
import argparse
import base64
from contextlib import closing
from collections import Counter
from datetime import datetime, timezone
import getpass
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import urllib.request
from urllib.parse import urlsplit

EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.mp4', '.mov', '.avi'}


def signature(path):
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino


def scan(roots, database):
    roots = sorted({Path(root).expanduser().resolve(strict=True) for root in roots})
    if any(not root.is_dir() for root in roots):
        raise ValueError('All sources must be directories')
    database = Path(database).expanduser().resolve()
    database.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.preprep-', dir=database.parent)
    os.close(fd)
    db = sqlite3.connect(temporary)
    errors = 0
    try:
        db.execute('CREATE TABLE files (path TEXT PRIMARY KEY, size_bytes INTEGER, mtime_ns INTEGER, '
                   'sha256 TEXT, status TEXT, match_count INTEGER, error TEXT)')
        db.execute('CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)')
        def failed(error):
            raise error
        for root in roots:
            for base, directories, names in os.walk(root, followlinks=False, onerror=failed):
                directories[:] = sorted(d for d in directories if not (Path(base) / d).is_symlink())
                for name in sorted(names):
                    path = Path(base) / name
                    if path.is_symlink() or name.startswith('._') or path.suffix.lower() not in EXTENSIONS:
                        continue
                    if db.execute('SELECT 1 FROM files WHERE path=?', (str(path),)).fetchone():
                        continue
                    size = modified = sha = None
                    error = None
                    try:
                        before = signature(path)
                        digest = hashlib.sha256()
                        with path.open('rb') as stream:
                            for block in iter(lambda: stream.read(1024 * 1024), b''):
                                digest.update(block)
                        if signature(path) != before:
                            raise OSError('File changed during hashing; scan again')
                        size, modified = before[:2]
                        sha = digest.hexdigest()
                    except OSError as exc:
                        error = str(exc)
                        errors += 1
                    db.execute('INSERT INTO files VALUES (?,?,?,?,?,?,?)',
                               (str(path), size, modified, sha, 'error' if error else 'unchecked', None, error))
        db.execute('CREATE INDEX fingerprints ON files (sha256, size_bytes)')
        db.execute('INSERT INTO metadata VALUES (?,?)', ('scanned_at', datetime.now(timezone.utc).isoformat()))
        db.commit()
        db.close()
        os.replace(temporary, database)
    finally:
        db.close()
        Path(temporary).unlink(missing_ok=True)
    return errors


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Redirect refused; use the final server URL')


def requester(server, password, allow_http=False):
    parsed = urlsplit(server)
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Use a server HTTP(S) URL without credentials, query or fragment')
    if parsed.scheme != 'https' and not allow_http:
        raise ValueError('Use HTTPS, or explicitly pass --allow-http on a trusted network')
    opener = urllib.request.build_opener(NoRedirect())
    authorization = base64.b64encode(('client-preprep:' + password).encode()).decode()
    def send(files):
        req = urllib.request.Request(server.rstrip('/') + '/api/client-preprep/check',
            data=json.dumps({'files': files}).encode(), headers={
                'Content-Type': 'application/json', 'X-Photo-Browser': '1',
                'Authorization': 'Basic ' + authorization})
        with opener.open(req, timeout=120) as response:
            return json.load(response)
    return send


def connect(database):
    return sqlite3.connect(Path(database).expanduser().resolve().as_uri() + '?mode=rw', uri=True)


def check(database, server, send):
    with closing(connect(database)) as db, db:
        # Invalidate old conclusions even if this server is unavailable.
        db.execute("UPDATE files SET status='unchecked', match_count=NULL WHERE sha256 IS NOT NULL")
        db.execute("DELETE FROM metadata WHERE key IN ('server', 'checked_at')")
        db.commit()
        for path, size, modified in db.execute('SELECT path,size_bytes,mtime_ns FROM files WHERE sha256 IS NOT NULL').fetchall():
            try:
                if signature(Path(path))[:2] != (size, modified):
                    raise OSError('File changed; scan again')
            except OSError:
                db.execute("UPDATE files SET status='stale' WHERE path=?", (path,))
        db.commit()
        keys = db.execute("SELECT DISTINCT sha256,size_bytes FROM files WHERE status='unchecked'").fetchall()
        for start in range(0, len(keys), 500):
            batch = keys[start:start + 500]
            response = send([{'sha256': sha, 'size_bytes': size} for sha, size in batch])
            if (not isinstance(response, dict) or response.get('schema_version') != 1
                    or response.get('basis') != 'active_database_records'
                    or not isinstance(response.get('results'), list) or len(response['results']) != len(batch)):
                raise ValueError('Invalid server comparison response')
            for expected, result in zip(batch, response['results']):
                if (not isinstance(result, dict) or (result.get('sha256'), result.get('size_bytes')) != expected
                        or type(result.get('match_count')) is not int or result['match_count'] < 0):
                    raise ValueError('Invalid server comparison result')
                count = result['match_count']
                db.execute("UPDATE files SET status=?,match_count=? WHERE sha256=? AND size_bytes=? AND status='unchecked'",
                           ('exists' if count else 'not_in_server_db', count, *expected))
        db.executemany('INSERT OR REPLACE INTO metadata VALUES (?,?)',
                       [('server', server), ('checked_at', datetime.now(timezone.utc).isoformat())])


def report(database):
    with closing(connect(database)) as db, db:
        db.row_factory = sqlite3.Row
        files = [dict(row) for row in db.execute('SELECT * FROM files ORDER BY path')]
        counts = Counter((f['sha256'], f['size_bytes']) for f in files if f['sha256'])
        selected = set()
        for item in files:
            key = item['sha256'], item['size_bytes']
            item['local_copy_count'] = counts[key] if item['sha256'] else 0
            item['upload_candidate'] = item['status'] == 'not_in_server_db' and key not in selected
            if item['upload_candidate']:
                selected.add(key)
        return {'metadata': dict(db.execute('SELECT key,value FROM metadata')),
                'summary': dict(Counter(f['status'] for f in files)), 'files': files}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    scan_parser = commands.add_parser('scan')
    scan_parser.add_argument('sources', nargs='+')
    check_parser = commands.add_parser('check')
    check_parser.add_argument('--server', required=True)
    check_parser.add_argument('--allow-http', action='store_true')
    for command in (scan_parser, check_parser, commands.add_parser('report')):
        command.add_argument('--db', default='inventory.sqlite3')
    args = parser.parse_args()
    try:
        if args.command == 'scan':
            errors = scan(args.sources, args.db)
            print(json.dumps(report(args.db)['summary'], ensure_ascii=False))
            return 1 if errors else 0
        if args.command == 'check':
            password = os.environ.get('PHOTO_BROWSER_PASSWORD') or getpass.getpass('Server password: ')
            check(args.db, args.server, requester(args.server, password, args.allow_http))
        print(json.dumps(report(args.db), ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        parser.exit(1, f'{type(exc).__name__}: {exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
