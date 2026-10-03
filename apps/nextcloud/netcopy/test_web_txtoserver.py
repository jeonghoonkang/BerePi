"""Offline lifecycle and HTTP tests: python3 -m unittest discover -s . -p 'test_web*.py'."""
import json
import io
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import web_txtoserver as web


def settings():
    return {name: dict(webdav_hostname=f'https://{name}.example.com', webdav_root='/dav/user',
                       root='Photos', username='user', password='secret', port='443')
            for name in ('source', 'destination')}


def wait(manager):
    manager.worker.join(5)
    assert not manager.worker.is_alive()


class LifecycleTests(unittest.TestCase):
    def test_port_and_speed_configuration(self):
        data = settings()
        data['source']['port'] = '22080'
        data['destination']['port'] = '4001'
        data['speed_limit_mbps'] = '1.5'
        config = web.parse_config(data)
        with tempfile.TemporaryDirectory() as directory:
            manager = web.Manager(Path(directory)/'state.json')
            manager.config = config
            source, dest = manager.clients()
            self.assertEqual(source.webdav.hostname, 'https://source.example.com:22080')
            self.assertEqual(dest.webdav.hostname, 'https://destination.example.com:4001')
            self.assertEqual(source.speed_limit, 1.5 * 1024 * 1024)
            manager.history.add(config)
            self.assertEqual(manager.history.snapshot()[0]['speed_limit_mbps'], '1.5')
        for value in ('-1', 'nan', 'inf', 'invalid'):
            data['speed_limit_mbps'] = value
            with self.assertRaises(ValueError): web.parse_config(data)

    def test_limiter_delays_by_bytes(self):
        with patch.object(web.transfer.time, 'monotonic', return_value=0), \
             patch.object(web.transfer.time, 'sleep') as sleep:
            reader = web.transfer.LimitedReader(io.BytesIO(b'x' * 20), 100)
            self.assertEqual(reader.read(20), b'x' * 10)
            sleep.assert_called_with(0.1)
            self.assertEqual(reader.read(20), b'x' * 10)
            sleep.assert_called_with(0.2)

    def test_limited_http_transfer(self):
        stored = {}
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_PUT(self):
                stored[self.path] = self.rfile.read(int(self.headers['Content-Length']))
                self.send_response(201); self.end_headers()
            def do_GET(self):
                content = stored[self.path]
                self.send_response(200)
                self.send_header('Content-Length', str(len(content)))
                self.end_headers(); self.wfile.write(content)
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            data = settings()
            data['source'].update(webdav_hostname='http://127.0.0.1', port=str(server.server_port), webdav_root='/dav/')
            config = web.parse_config(data)
            client = web.transfer.build_client(config['source'], True, 10000)
            with tempfile.TemporaryDirectory() as directory:
                source, dest = Path(directory)/'source', Path(directory)/'dest'
                source.write_bytes(b'0123456789' * 250)
                client.upload_sync(remote_path='folder/a b.txt', local_path=str(source))
                client.download_sync(remote_path='folder/a b.txt', local_path=str(dest))
                self.assertEqual(source.read_bytes(), dest.read_bytes())
                self.assertIn('/dav/folder/a%20b.txt', stored)
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def test_pause_restart_and_retry(self):
        entries = [dict(path=f'Photos/{n}.jpg', size=10, etag=str(n)) for n in range(3)]
        destinations = {}
        calls = []
        entered, release = threading.Event(), threading.Event()
        class Client:
            def check(self, path): return True
            def list(self, *args, **kwargs): return []
        source, dest = Client(), Client()
        def tree(client, root):
            return entries if client is source else list(destinations.values())
        def upload(sc, dc, sp, dp):
            calls.append(sp)
            if len(calls) == 1:
                entered.set()
                self.assertTrue(release.wait(5))
            destinations[dp] = dict(path=dp, size=10, etag='destination-etag')
            return 10
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(web.Manager, 'clients', return_value=(source, dest)), \
             patch.object(web.transfer, 'list_tree', side_effect=tree), \
             patch.object(web.transfer, 'upload_and_verify_file', side_effect=upload):
            path = Path(directory)/'state.json'
            manager = web.Manager(path)
            manager.check(settings()); wait(manager)
            self.assertEqual(manager.status, 'ready')
            manager.start(); self.assertTrue(entered.wait(5))
            manager.request_pause(); release.set(); wait(manager)
            self.assertEqual(manager.status, 'paused')
            self.assertEqual(manager.snapshot()['completed_files'], 1)
            self.assertNotIn('secret', path.read_text())
            restored = web.Manager(path)
            restored.check(settings()); wait(restored)
            self.assertEqual(restored.snapshot()['completed_files'], 1)
            restored.start(); wait(restored)
            self.assertEqual(restored.status, 'completed')
            self.assertEqual(calls, [e['path'] for e in entries])
            self.assertEqual(restored.snapshot()['percent'], 100)
            # A deleted destination must invalidate that file's checkpoint.
            del destinations['Photos/0.jpg']
            restored.check(settings()); wait(restored)
            self.assertEqual(restored.snapshot()['completed_files'], 2)
            with patch.object(web.transfer, 'upload_and_verify_file', side_effect=RuntimeError('secret')):
                restored.start(); wait(restored)
            self.assertEqual(restored.status, 'error')
            self.assertNotIn('secret', '\n'.join(restored.logs))
            restored.start(); wait(restored)
            self.assertEqual(restored.status, 'completed')

    def test_missing_destination_created_only_on_run(self):
        class Client:
            def __init__(self):
                self.dirs = {''}
                self.files = {}
                self.created = []
            def check(self, path): return path in self.dirs
            def list(self, path, **kwargs):
                if path not in self.dirs: raise RuntimeError('Missing directory')
                return []
            def mkdir(self, path):
                self.assert_parent(path)
                self.dirs.add(path)
                self.created.append(path)
            def assert_parent(self, path):
                if web.posixpath.dirname(path) not in self.dirs:
                    raise RuntimeError('Missing parent')
            def download_sync(self, remote_path, local_path):
                Path(local_path).write_bytes(self.files[remote_path])
            def upload_sync(self, remote_path, local_path):
                self.assert_parent(remote_path)
                self.files[remote_path] = Path(local_path).read_bytes()
        for empty in (False, True):
            with self.subTest(empty=empty), tempfile.TemporaryDirectory() as directory:
                source, dest = Client(), Client()
                source.files['Photos/year/photo.jpg'] = b'photo contents'
                entries = [] if empty else [dict(path='Photos/year/photo.jpg', size=14, etag='source')]
                data = settings()
                data['destination']['root'] = 'Backup/Photos'
                with patch.object(web.Manager, 'clients', return_value=(source, dest)), \
                     patch.object(web.transfer, 'list_tree', return_value=entries):
                    manager = web.Manager(Path(directory)/'state.json')
                    manager.check(data); wait(manager)
                    self.assertEqual(manager.status, 'ready')
                    self.assertEqual(dest.created, [])
                    manager.start(); wait(manager)
                    self.assertEqual(manager.status, 'completed')
                    self.assertEqual(dest.created[:2], ['Backup', 'Backup/Photos'])
                    if not empty:
                        self.assertIn('Backup/Photos/year', dest.dirs)
                        self.assertEqual(dest.files['Backup/Photos/year/photo.jpg'], b'photo contents')

    def test_history_limit_redaction_and_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'history.json'
            history = web.ConfigHistory(path)
            for number in range(105):
                data = settings()
                data['source']['root'] = f'Photos/{number}'
                data['source']['password'] = f'source-secret-{number}'
                data['destination']['password'] = f'dest-secret-{number}'
                data['verify_ssl'] = False
                history.add(web.parse_config(data))
            text = path.read_text()
            self.assertNotIn('source-secret', text)
            self.assertNotIn('dest-secret', text)
            restored = web.ConfigHistory(path).snapshot()
            self.assertEqual(len(restored), 100)
            self.assertEqual(restored[0]['source']['root'], 'Photos/104')
            self.assertEqual(restored[-1]['source']['root'], 'Photos/5')
            self.assertEqual(restored[0]['source']['password'], '********')
            self.assertFalse(restored[0]['verify_ssl'])
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            restored[0]['source']['root'] = 'changed'
            self.assertEqual(history.snapshot()[0]['source']['root'], 'Photos/104')

    def test_failed_preview_cannot_start(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(web.Manager, 'clients', side_effect=RuntimeError()):
            manager = web.Manager(Path(directory)/'state.json')
            manager.check(settings()); wait(manager)
            self.assertEqual(manager.status, 'error')
            with self.assertRaises(ValueError): manager.start()

    def test_http(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = web.Manager(Path(directory)/'state.json')
            server = ThreadingHTTPServer(('127.0.0.1', 0), web.handler_for(manager, {'verify_ssl': True}, 'token'))
            host = f'127.0.0.1:{server.server_port}'
            server.allowed_hosts = {host}
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            try:
                base = 'http://' + host
                with urlopen(base) as response:
                    self.assertIn('SHA-256', response.read().decode())
                with urlopen(base+'/api/status') as response:
                    self.assertEqual(json.load(response)['status'], 'idle')
                manager.history.add(web.parse_config(settings()))
                with urlopen(base+'/api/history') as response:
                    history = json.load(response)
                    self.assertEqual(history[0]['source']['password'], '********')
                    self.assertNotIn('secret', json.dumps(history))
                with self.assertRaises(HTTPError) as error:
                    urlopen(Request(base+'/api/start', data=b'{}', method='POST'))
                self.assertEqual(error.exception.code, 403)
                with self.assertRaises(HTTPError) as error:
                    urlopen(Request(base+'/api/start', data=b'{}', method='POST', headers={'X-CSRF-Token':'token'}))
                self.assertEqual(error.exception.code, 400)
                with self.assertRaises(HTTPError) as error:
                    urlopen(Request(base, headers={'Host':'evil.example'}))
                self.assertEqual(error.exception.code, 403)
            finally:
                server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__': unittest.main()
