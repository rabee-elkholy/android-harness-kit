"""Content-addressed checkout inputs. Hashes establish freshness, not trust."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess

EXCLUDED_PARTS = {'.git', '.gradle', 'build', '__pycache__', '.pytest_cache',
                  '.harness-backup', '.harness-backups', '.harness-setup', 'node_modules'}
RUNTIME_PREFIXES = ('agents/state/', 'agents/cache/', '.agents/state/', '.agents/cache/')


def git_bytes(repo: Path, *args: str) -> bytes:
    proc = subprocess.run(['git', *args], cwd=repo, capture_output=True, check=False)
    if proc.returncode:
        raise RuntimeError('Cannot inspect Git inputs: ' + proc.stderr.decode('utf-8', 'replace')[:300])
    return proc.stdout


def changed_entries(repo: Path, include_untracked: bool = True) -> list[dict]:
    raw = git_bytes(repo, 'status', '--porcelain=v1', '-z', '--untracked-files=all')
    chunks = iter(raw.split(b'\0'))
    entries = []
    for chunk in chunks:
        if not chunk:
            continue
        status = chunk[:2].decode('ascii')
        name = os.fsdecode(chunk[3:])
        old = os.fsdecode(next(chunks)) if 'R' in status or 'C' in status else None
        if status in ('UU', 'AA', 'DD', 'AU', 'UA', 'DU', 'UD'):
            raise RuntimeError('Resolve merge conflict before verification: ' + name)
        if status == '??' and not include_untracked:
            continue
        entry = {'path': name, 'status': status}
        if old is not None:
            entry['old_path'] = old
        entries.append(entry)
    return entries


def included(name: str) -> bool:
    return not (set(Path(name).parts) & EXCLUDED_PARTS or name.startswith(RUNTIME_PREFIXES))


def file_digest(path: Path, repo: Path) -> str:
    """Do not follow symlinks or silently omit unreadable inputs/deletions."""
    if not path.parent.resolve().is_relative_to(repo.resolve()):
        raise RuntimeError("Input parent escapes checkout: " + str(path))
    try:
        info = path.lstat()
    except FileNotFoundError:
        return 'DELETED'
    if stat.S_ISLNK(info.st_mode):
        target = os.readlink(path)
        resolved = path.resolve()
        if not resolved.is_relative_to(repo.resolve()):
            raise RuntimeError('Input symlink escapes checkout: ' + str(path))
        return 'symlink:' + hashlib.sha256(os.fsencode(target)).hexdigest()
    if not stat.S_ISREG(info.st_mode):
        raise RuntimeError('Unsupported input (including submodules): ' + str(path))
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def capture(repo: Path) -> dict:
    repo = repo.resolve()
    head = git_bytes(repo, 'rev-parse', '--verify', 'HEAD').decode('ascii').strip()
    entries = changed_entries(repo)
    raw = git_bytes(repo, 'ls-files', '--cached', '--others', '--exclude-standard', '-z')
    names = {os.fsdecode(n) for n in raw.split(b'\0') if n}
    # Installed policy/engine is normally ignored by Git but affects every decision.
    installed = repo / '.agents'
    if installed.is_symlink():
        raise RuntimeError("Installed engine must not be a symlink")
    if installed.is_dir():
        names.update(p.relative_to(repo).as_posix() for p in installed.rglob('*') if p.is_file() or p.is_symlink())
    files = {name: file_digest(repo / name, repo) for name in sorted(names) if included(name)}
    # Index modes capture executable/symlink changes as well as source bytes.
    modes = git_bytes(repo, 'ls-files', '--stage', '-z').decode('utf-8', 'surrogateescape')
    index_modes = []
    for item in modes.split('\0'):
        if '\t' in item:
            metadata, name = item.split('\t', 1)
            if included(name):
                index_modes.append([name, metadata.split()[0]])
    worktree_modes = {name: bool((repo / name).lstat().st_mode & 0o111) for name in files if (repo / name).exists()} if os.name != 'nt' else {}
    payload = {'head': head, 'files': files, 'modes': sorted(index_modes), 'worktree_modes': worktree_modes,
               'changes': [e for e in entries if included(e['path'])]}
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(',', ':')).encode()
    return {'snapshot_id': hashlib.sha256(encoded).hexdigest(), 'git_sha': head,
            'repo_id': hashlib.sha256(os.fsencode(str(repo))).hexdigest(), 'files': files,
            'changes': payload['changes']}
