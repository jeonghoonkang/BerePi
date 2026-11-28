"""ANSI stdout header with a separate scrolling region for ordinary output."""
import contextlib
import os
import shutil
import sys
import threading
import unicodedata


def clipped(text, width):
    output, cells = [], 0
    for char in str(text):
        if unicodedata.category(char) in {'Cc', 'Cf'}:
            char = repr(char)[1:-1]
        for value in char:
            size = 0 if unicodedata.combining(value) else 2 if unicodedata.east_asian_width(value) in {'W', 'F'} else 1
            if cells + size > width:
                return ''.join(output)
            output.append(value); cells += size
    return ''.join(output)


class OutputRegion:
    def __init__(self, screen):
        self.screen = screen

    def write(self, text):
        with self.screen.lock:
            return self.screen.stream.write(text)

    def flush(self):
        with self.screen.lock:
            return self.screen.stream.flush()

    def __getattr__(self, name):
        return getattr(self.screen.stream, name)


class PruneTerminal:
    HEADER_ROWS = 9

    def __init__(self, mode='auto'):
        self.mode = mode
        self.stream = sys.stdout
        self.lock = threading.RLock()
        self.enabled = False
        self.redirects = contextlib.ExitStack()
        self.dimensions = None
        self.windows_console = None

    def _enable_ansi(self):
        if os.name != 'nt':
            return True
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.windll.kernel32
        kernel.GetStdHandle.argtypes = [wintypes.DWORD]
        kernel.GetStdHandle.restype = wintypes.HANDLE
        kernel.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        handle, flags = kernel.GetStdHandle(-11), wintypes.DWORD()
        if not kernel.GetConsoleMode(handle, ctypes.byref(flags)):
            return False
        self.windows_console = (kernel, handle, flags.value)
        return bool(kernel.SetConsoleMode(handle, flags.value | 0x0004))

    def __enter__(self):
        stdout_tty = getattr(self.stream, 'isatty', lambda: False)()
        stderr_tty = getattr(sys.stderr, 'isatty', lambda: False)()
        self.enabled = (self.mode != 'plain' and stdout_tty and os.environ.get('TERM') != 'dumb'
                        and (self.mode == 'pretty' or stderr_tty))
        if self.enabled:
            self.enabled = self._enable_ansi()
        if self.enabled:
            size = shutil.get_terminal_size((80, 24))
            self.enabled = size.lines > self.HEADER_ROWS + 3 and size.columns >= 30
        if self.enabled:
            self._configure(size)
            proxy = OutputRegion(self)
            self.redirects.enter_context(contextlib.redirect_stdout(proxy))
            if stderr_tty:
                self.redirects.enter_context(contextlib.redirect_stderr(proxy))
        return self

    def _configure(self, size):
        self.dimensions = size
        self.stream.write(f'\033[r\033[2J\033[H\033[{self.HEADER_ROWS + 1};{size.lines}r\033[{self.HEADER_ROWS + 1};1H')
        self.stream.flush()

    def render(self, state):
        if not self.enabled:
            return False
        with self.lock:
            size = shutil.get_terminal_size((80, 24))
            if size.lines <= self.HEADER_ROWS + 3 or size.columns < 30:
                self.stream.write('\0337\033[r\0338')
                self.enabled = False
                return False
            if size != self.dimensions:
                self._configure(size)
            total = '?' if state['total'] is None else f"{state['total']:,}"
            percent = '미확정' if state['progress_percent'] is None else f"{state['progress_percent']:.2f}%"
            eta = state['estimated_finish_at'] or f"계산 대기 ({state['estimate_status']})"
            remaining = state['estimated_remaining_seconds']
            if remaining is not None:
                eta += f' · 남은 {remaining / 60:.2f}분'
            memory = state.get('memory', {})
            def mib(value): return '?' if value is None else f'{value / (1024 * 1024):,.1f}'
            ram = (f"RAM 사용(RSS): {mib(memory.get('rss_bytes'))} MiB"
                   f" · 가용: {mib(memory.get('available_bytes'))} MiB")
            cache = (f"캐시: {mib(memory.get('cache_used_bytes'))}/{mib(memory.get('cache_budget_bytes'))} MiB"
                     f" · {memory.get('adjustment', '예산 계산 준비 중')}")
            lines = [f"DB prune · {state['operation']} · {state['status']}",
                     f"로그 파일: {state['log_file']}",
                     ram, cache, f"시작: {state['started_at']}",
                     f"현재: {state['current_time']} · 경과 {state['elapsed_minutes']:.2f}분",
                     f"단계: {state['phase']} · 처리 {state['processed']:,}/{total} ({percent})",
                     f"경로: {state['path']}", f'종료 예상: {eta}']
            self.stream.write('\0337')
            for row, line in enumerate(lines, 1):
                self.stream.write(f'\033[{row};1H\033[2K{clipped(line, size.columns - 1)}')
            self.stream.write('\0338')
            self.stream.flush()
        return True

    def __exit__(self, kind, value, traceback):
        with self.lock:
            try:
                if self.dimensions is not None:
                    self.stream.write('\0337\033[r\0338')
                    self.stream.flush()
            finally:
                self.enabled = False
                self.redirects.close()
                if self.windows_console:
                    kernel, handle, flags = self.windows_console
                    kernel.SetConsoleMode(handle, flags)
