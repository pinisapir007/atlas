import json
import os
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Protocol

if os.name == "nt":
    import msvcrt
else:
    import fcntl


_LOCKS_GUARD = threading.Lock()
_PATH_LOCKS: dict[Path, threading.RLock] = {}


def _lock_for(path: Path) -> threading.RLock:
    """Return the shared in-process lock for one JSON document path."""
    key = Path(path).expanduser().absolute()
    with _LOCKS_GUARD:
        lock = _PATH_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _PATH_LOCKS[key] = lock
        return lock


@contextmanager
def _interprocess_lock(path: Path):
    """Exclusive lock shared by separate ATLAS processes."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(f".{path.name}.lock")

    with open(lock_path, "a+b") as lock_file:
        if os.name == "nt":
            lock_file.seek(0, os.SEEK_END)
            if lock_file.tell() == 0:
                lock_file.write(b"\0")
                lock_file.flush()

            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def read_json(path: Path, default: dict) -> dict:
    """Read a JSON document from `path`, or return `default` if it doesn't
    exist yet. Shared by every JSON-file-backed store in atlas.core/brain so
    the read side of the pattern is defined once."""
    if not path.exists():
        return default
    return json.loads(path.read_text())


def _write_json_atomic_unlocked(path: Path, data: dict) -> None:
    """Write atomically while the caller already owns required locks."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp:
            json.dump(data, tmp, indent=2)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_name = tmp.name

        Path(tmp_name).replace(path)
    finally:
        if tmp_name is not None:
            tmp_path = Path(tmp_name)
            if tmp_path.exists():
                tmp_path.unlink()


def write_json_atomic(path: Path, data: dict) -> None:
    """Atomically replace one JSON document with thread/process protection."""
    path = Path(path)

    with _lock_for(path):
        with _interprocess_lock(path):
            _write_json_atomic_unlocked(path, data)


def update_json_atomic(path: Path, default: dict, mutator) -> dict:
    """Atomically perform one read-modify-write transaction.

    The same thread and inter-process locks protect the entire transaction,
    not just the final replace, preventing lost updates between concurrent
    ATLAS writers.
    """
    path = Path(path)

    with _lock_for(path):
        with _interprocess_lock(path):
            if path.exists():
                data = read_json(path, default)
            else:
                # Give every new document its own independent default,
                # including nested dict/list structures.
                data = json.loads(json.dumps(default))

            result = mutator(data)
            if result is not None:
                data = result

            _write_json_atomic_unlocked(path, data)
            return data


class Store(Protocol):
    def get(self, asset_id: str) -> dict: ...
    def set(self, asset_id: str, state: dict) -> None: ...


class JSONStore:
    """Default Store backend: one JSON file holding {asset_id: state}."""

    def __init__(self, path: Path = Path(".atlas/state.json")):
        self._path = Path(path)

    def get(self, asset_id: str) -> dict:
        return self._read().get(asset_id, {})

    def set(self, asset_id: str, state: dict) -> None:
        with _lock_for(self._path):
            with _interprocess_lock(self._path):
                data = self._read()
                data[asset_id] = state
                _write_json_atomic_unlocked(self._path, data)

    def _read(self) -> dict:
        return read_json(self._path, {})
