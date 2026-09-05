"""Shared evidence identity and atomic storage, without external dependencies."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import uuid

from _snapshot import capture

SCHEMA_VERSION = 3
ENGINE_ROOT = Path(__file__).resolve().parent


def context(repo: Path | None = None) -> dict:
    if repo is None:
        from _repo_files import REPO
        repo = REPO
    snap = capture(repo)
    engine = hashlib.sha256()
    for source in sorted(ENGINE_ROOT.glob("*.py")):
        engine.update(source.name.encode())
        engine.update(source.read_bytes())
    return {k: snap[k] for k in ('snapshot_id', 'git_sha', 'repo_id')} | {
        'schema_version': SCHEMA_VERSION,
        'engine_digest': engine.hexdigest(),
        'task_id': os.environ.get('HARNESS_TASK_ID', '').strip() or 'default',
    }


def matches(record: dict, current: dict) -> bool:
    return all(record.get(k) == current.get(k) for k in
               ('schema_version', 'snapshot_id', 'git_sha', 'repo_id', 'task_id', 'engine_digest'))


def atomic_json(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=True, sort_keys=True, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        Path(temp).unlink(missing_ok=True)
    return path


@contextmanager
def locked(path: Path, timeout: float = 5.0):
    path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    # OS-owned advisory locks are released even if the holder crashes.
    # Keep the lock inode: unlinking it permits two different holders.
    with path.open("a+b") as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        while True:
            try:
                stream.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() - started >= timeout:
                    raise TimeoutError(f"Lock unavailable: {path}")
                time.sleep(0.02)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def task_key() -> str:
    return hashlib.sha256((os.environ.get('HARNESS_TASK_ID', '').strip() or 'default').encode()).hexdigest()[:20]


def new_run() -> dict:
    return context() | {'run_id': uuid.uuid4().hex, 'started_at': time.time()}
