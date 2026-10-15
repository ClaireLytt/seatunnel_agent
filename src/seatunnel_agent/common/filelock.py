"""Cross-process file lock for read-modify-write of small JSON stores.

``threading.Lock`` only serializes writers inside one process; the CLI
(``cron serve``) and the hub UI can write the same store file from two
processes. This guards the write path with a sibling ``<file>.lock``:

- Windows: ``msvcrt.locking`` on the lock file (non-blocking, with a
  spin + timeout so a stuck holder surfaces as a clear error).
- POSIX: ``fcntl.flock`` (same non-blocking spin).

Reads stay lock-free and tolerant by design (atomic writes mean a reader
never sees a half-written file).
"""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

DEFAULT_TIMEOUT = 10.0
_POLL_SECONDS = 0.05


class FileLockTimeout(TimeoutError):
    """Raised when the cross-process lock cannot be acquired in time."""


if sys.platform == "win32":
    import msvcrt

    def _try_lock(fd: int) -> bool:
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False

    def _unlock(fd: int) -> None:
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        except OSError:
            pass  # closing the fd below releases the lock anyway
else:
    import fcntl

    def _try_lock(fd: int) -> bool:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False

    def _unlock(fd: int) -> None:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass  # closing the fd below releases the lock anyway


@contextmanager
def file_lock(target: str | Path,
              timeout: float = DEFAULT_TIMEOUT) -> Iterator[None]:
    """Exclusive cross-process lock guarding writes to ``target``.

    Locks the sibling file ``<target>.lock`` (never the data file itself,
    so atomic-replace writes keep working). Raises :class:`FileLockTimeout`
    when the lock is still held by another process after ``timeout``
    seconds.
    """
    lock_path = Path(str(target) + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT)
    try:
        deadline = time.monotonic() + timeout
        while not _try_lock(fd):
            if time.monotonic() >= deadline:
                raise FileLockTimeout(
                    f"could not acquire file lock {lock_path} "
                    f"within {timeout:g}s (held by another process?)"
                )
            time.sleep(_POLL_SECONDS)
        try:
            yield
        finally:
            _unlock(fd)
    finally:
        os.close(fd)
