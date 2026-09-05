"""Additive project routing, included in the checkout snapshot."""
import json
from pathlib import Path, PurePosixPath

SPECIALISTS = {"ui_expert", "test_quality"}


def additions(repo: Path, changed: list[str]) -> dict[str, list[str]]:
    policy = repo / '.agents' / 'review-policy.json'
    if not policy.exists() and not policy.is_symlink():
        return {}
    if policy.is_symlink() or not policy.resolve().is_relative_to(repo.resolve()):
        raise ValueError('Review policy must be a regular file inside the checkout')
    data = json.loads(policy.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or set(data) - {'version', 'require', 'paths'} or type(data.get('version')) is not int or data.get('version') != 1:
        raise ValueError('Review policy requires version 1 and only require/paths fields')
    out = {}

    def validate(keys):
        if not isinstance(keys, list) or any(not isinstance(k, str) or k not in SPECIALISTS for k in keys):
            raise ValueError('Policy can only add ui_expert/test_quality reviewers')

    def add(keys, reason):
        validate(keys)
        for key in set(keys):
            out.setdefault(key, []).append(reason)

    add(data.get('require', []), 'project policy')
    paths = data.get('paths', {})
    if not isinstance(paths, dict):
        raise ValueError('Policy paths must map relative directory/file paths to reviewers')
    for prefix, keys in paths.items():
        if not isinstance(prefix, str) or not prefix or '\\' in prefix or PurePosixPath(prefix).is_absolute() or '..' in prefix.split('/') or ':' in prefix:
            raise ValueError('Policy paths must be checkout-relative without traversal')
        # Validate even inactive rules so a typo cannot silently suppress routing.
        validate(keys)
        normalized = prefix.rstrip('/')
        if any(p == normalized or p.startswith(normalized + '/') for p in changed):
            add(keys, 'project path policy: ' + prefix)
    return out
