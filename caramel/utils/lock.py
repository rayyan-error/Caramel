"""
Single-Instance Process Lock using POSIX fcntl.
Prevents duplicate background daemon instances from competing for the microphone.
"""

import fcntl
import os
from pathlib import Path
from typing import Optional


class SingleInstanceLock:
    """Acquires a non-blocking advisory file lock for the lifetime of the process."""
    def __init__(self, lockfile_path: Optional[str] = None):
        self.lockfile_path = lockfile_path or os.path.expanduser("~/.cache/caramel.lock")
        self._fd: Optional[int] = None

    def acquire(self) -> bool:
        """Attempt to acquire the lock. Returns True if acquired, False if already running."""
        if self._fd is not None:
            return True
        fd: Optional[int] = None
        try:
            parent_dir = os.path.dirname(os.path.abspath(self.lockfile_path))
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            fd = os.open(self.lockfile_path, os.O_CREAT | os.O_RDWR, 0o600)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # Write current PID into lock file
            os.ftruncate(fd, 0)
            os.write(fd, f"{os.getpid()}\n".encode("utf-8"))
            self._fd = fd
            return True
        except (IOError, OSError):
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
            return False

    def release(self) -> None:
        """Release the file lock."""
        if self._fd is not None:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
                os.close(self._fd)
            except Exception:
                pass
            self._fd = None
