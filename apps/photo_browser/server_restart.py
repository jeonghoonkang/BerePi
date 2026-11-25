"""Owned development-server lifecycle; restart only the captured Python command."""
import os
from pathlib import Path
import sys
import threading

from library import uid


class ServerRestart:
    def __init__(self):
        self.instance_id = uid()
        self.lock = threading.Lock()
        self.pending = False
        self.enabled = False
        self.error = None
        self.shutdown = None
        self.command = None

    def capture(self, argv=None):
        # orig_argv retains interpreter options such as -X, -u and -m.
        original = getattr(sys, 'orig_argv', [sys.executable, *sys.argv])
        self.command = [sys.executable, *original[1:]] if argv is None else [sys.executable, str(Path(__file__).with_name('app.py')), *argv]
        self.cwd = os.getcwd()
        self.environment = dict(os.environ)

    def state(self):
        with self.lock:
            return {'instance_id': self.instance_id, 'pid': os.getpid(), 'supported': self.enabled,
                    'pending': self.pending, 'error': self.error,
                    'reason': '' if self.enabled else 'python app.py로 직접 실행한 서버에서 재시작할 수 있습니다. 외부 WSGI 서버는 서비스 관리자를 사용하세요.'}

    def request(self):
        with self.lock:
            if not self.enabled or not self.command or self.shutdown is None:
                raise ValueError('현재 실행 방식에서는 웹 재시작을 지원하지 않습니다.')
            if self.pending:
                raise ValueError('이미 서버 재시작을 요청했습니다.')
            self.pending, self.error = True, None
        def stop_server():
            try:
                self.shutdown()
            except Exception as exc:
                with self.lock:
                    self.pending, self.error = False, str(exc)
        # Let the restart response reach the client before stopping accepts.
        timer = threading.Timer(0.25, stop_server)
        timer.daemon = True
        timer.start()
        return self.state()

    def serve(self, app, host, port, ssl_context=None):
        from werkzeug.serving import make_server
        from db_locks import exclusive_file_lock
        with exclusive_file_lock(app.extensions['photo_library'].db / '.server.lock'), \
                make_server(host, port, app, threaded=True, ssl_context=ssl_context) as server:
            # Drain in-flight requests, including uploads, before replacing Python.
            server.daemon_threads = False
            self.shutdown = server.shutdown
            with self.lock:
                self.enabled = True
            print(f'웹서버 시작: {"https" if ssl_context else "http"}://{host}:{server.server_port}', flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                with self.lock:
                    self.enabled = False

    def replace_process(self):
        if not self.pending or not self.command:
            return
        os.chdir(self.cwd)
        os.execve(self.command[0], self.command, self.environment)
