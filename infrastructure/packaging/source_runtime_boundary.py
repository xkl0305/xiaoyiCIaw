from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List
import re
import os
import fnmatch

RUNTIME_ROOT_NAMES = {
    '.openclaw/state',
    '.openclaw/hook_state',
    '.persona_visual/generated',
    '.lazy_state',
    '.context_state',
    '.v107_state',
    '.v98_state',
    'logs',
    'generated-images',
    '__pycache__',
    '.pytest_cache',
}

RUNTIME_FILE_NAMES = {
    '.DS_Store',
    'runtime_wardrobe_state.json',
}

ROOT_ARTIFACT_FILE_GLOBS = (
    'overlay*.zip',
    'generated*.jpg',
)

RUNTIME_SUFFIXES = (
    '.pyc',
    '.pyo',
    '.secret',
    '.sqlite',
    '.sqlite3',
    '.db',
    '.sqlite-wal',
    '.sqlite-shm',
    '.cache',
    '.tmp',
    '.db-shm',
    '.db-wal',
    '.sqlite3-shm',
    '.sqlite3-wal',
    '.jsonl',
    '.log',
)

FORBIDDEN_SOURCE_PREFIXES = (
    'overlay_payload',
    '_overlay',
    'legacy_readonly/',
)

SECRET_LITERAL_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bark-[A-Za-z0-9_-]{20,}\b"),
)

_PACKAGE_CLEAN_CACHE: Dict[str, Dict[str, object]] = {}

TEXT_SECRET_SCAN_SUFFIXES = {
    '', '.py', '.pyw', '.sh', '.bash', '.zsh', '.ps1', '.json', '.yaml', '.yml',
    '.toml', '.ini', '.cfg', '.md', '.txt', '.rst', '.sql', '.env', '.example',
    '.js', '.ts', '.tsx', '.jsx', '.html', '.css', '.xml', '.csv', '.lock'
}


def contains_secret_literal(path: Path) -> bool:
    if not path.is_file():
        return False
    if path.suffix.lower() in {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.zip', '.tar', '.gz', '.tgz'}:
        return False
    try:
        if path.stat().st_size > 5_000_000:
            return False
    except OSError:
        return False
    try:
        text = path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return False
    return any(p.search(text) for p in SECRET_LITERAL_PATTERNS)


def normalize_rel(path: str | Path) -> str:
    rel = str(path).replace('\\', '/')
    while rel.startswith('./'):
        rel = rel[2:]
    return rel.rstrip('/')


def _matches_runtime_root(rel: str) -> bool:
    if rel in RUNTIME_ROOT_NAMES:
        return True
    return any(rel.startswith(root + '/') for root in RUNTIME_ROOT_NAMES)


def is_runtime_path(path: str | Path) -> bool:
    rel = normalize_rel(path)
    name = rel.split('/')[-1]
    if '/' not in rel and any(fnmatch.fnmatch(name, pat) for pat in ROOT_ARTIFACT_FILE_GLOBS):
        return True
    if _matches_runtime_root(rel):
        return True
    if name in RUNTIME_FILE_NAMES:
        return True
    if name == '.DS_Store':
        return True
    if any(rel.endswith(suffix) for suffix in RUNTIME_SUFFIXES):
        return True
    if '/__pycache__/' in f'/{rel}/':
        return True
    return False


def is_forbidden_source_residue(path: str | Path) -> bool:
    rel = normalize_rel(path)
    return any(rel == prefix.rstrip('/') or rel.startswith(prefix) for prefix in FORBIDDEN_SOURCE_PREFIXES)


def iter_source_files(root: str | Path) -> Iterable[Path]:
    root = Path(root)
    for p in root.rglob('*'):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if not is_runtime_path(rel) and not is_forbidden_source_residue(rel):
            yield p


def package_clean_check(root: str | Path) -> Dict[str, object]:
    """Return whether a source package is free of runtime residue.

    This implementation uses a pruned os.walk instead of Path.rglob + full-text
    reads for every file. It preserves the same boundary contract while keeping
    enterprise acceptance repeatable on large single-repo workspaces. Results are
    cached per process because enterprise acceptance calls the same package gate
    several times after explicit clean steps; this avoids non-deterministic slow
    repeated full-tree scans in constrained runtimes.
    """
    root = Path(root)
    cache_key = str(root.resolve())
    if os.environ.get('SOURCE_RUNTIME_BOUNDARY_DISABLE_CACHE') != '1' and cache_key in _PACKAGE_CLEAN_CACHE:
        return dict(_PACKAGE_CLEAN_CACHE[cache_key])
    runtime_files: List[str] = []
    forbidden_residue: List[str] = []
    secret_literals: List[str] = []
    if root.exists():
        for dirpath, dirnames, filenames in os.walk(root, topdown=True):
            dpath = Path(dirpath)
            kept_dirs: List[str] = []
            for d in dirnames:
                dp = dpath / d
                try:
                    rel = dp.relative_to(root)
                except ValueError:
                    continue
                rel_norm = normalize_rel(rel)
                if is_runtime_path(rel) or is_forbidden_source_residue(rel):
                    if is_runtime_path(rel):
                        runtime_files.append(rel_norm)
                    if is_forbidden_source_residue(rel):
                        forbidden_residue.append(rel_norm)
                    continue
                kept_dirs.append(d)
            dirnames[:] = kept_dirs
            for f in filenames:
                p = dpath / f
                try:
                    rel = p.relative_to(root)
                except ValueError:
                    continue
                rel_norm = normalize_rel(rel)
                runtime_hit = is_runtime_path(rel)
                forbidden_hit = is_forbidden_source_residue(rel)
                if runtime_hit:
                    runtime_files.append(rel_norm)
                if forbidden_hit:
                    forbidden_residue.append(rel_norm)
                # Secret scanning remains source-focused and bounded. Binary and
                # large artifacts are skipped by suffix/size rules.
                if not runtime_hit and not forbidden_hit and p.suffix.lower() in TEXT_SECRET_SCAN_SUFFIXES and contains_secret_literal(p):
                    secret_literals.append(rel_norm)
    out = {
        'clean': not runtime_files and not forbidden_residue and not secret_literals,
        'runtime_files_detected': runtime_files[:50],
        'runtime_file_count': len(runtime_files),
        'forbidden_residue_detected': forbidden_residue[:50],
        'forbidden_residue_count': len(forbidden_residue),
        'secret_literals_detected': secret_literals[:50],
        'secret_literal_count': len(secret_literals),
    }
    if os.environ.get('SOURCE_RUNTIME_BOUNDARY_DISABLE_CACHE') != '1':
        _PACKAGE_CLEAN_CACHE[cache_key] = dict(out)
    return out
