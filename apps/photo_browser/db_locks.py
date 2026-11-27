"""Cross-process locks shared by offline maintenance and the owned web server."""
from contextlib import contextmanager
import os
from pathlib import Path


class LockBusyError(ValueError):
    """The file exists and another process owns its lock."""


@contextmanager
def exclusive_file_lock(path):
    path = Path(path)
    if path.is_symlink() or (path.exists() and getattr(path.lstat(), 'st_file_attributes', 0) & 0x400):
        raise ValueError(f'잠금 경로가 링크·정션입니다: {path}')
    handle = path.open('a+b')
    acquired = False
    try:
        try:
            if os.name == 'nt':
                import msvcrt
                if handle.seek(0, 2) == 0:
                    handle.write(b'0'); handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError as exc:
            raise LockBusyError('웹서버 또는 다른 작업이 실행 중입니다. 작업을 중지·저장하고 서버를 종료하세요.') from exc
        yield
    finally:
        if acquired:
            if os.name == 'nt':
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()
