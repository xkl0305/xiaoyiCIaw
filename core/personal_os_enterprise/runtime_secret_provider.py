from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


class MissingRuntimeSecretError(RuntimeError):
    pass


def project_root(root: Optional[str | Path] = None) -> Path:
    if root is not None:
        return Path(root).resolve()
    return Path(__file__).resolve().parents[2]


def _env_candidates(name: str, namespace: str) -> list[str]:
    def norm(v: str) -> str:
        return ''.join(ch if ch.isalnum() else '_' for ch in str(v or '')).upper()
    ns = norm(namespace or 'default')
    nm = norm(name or 'default')
    candidates = [
        f'PERSONAL_OS_{ns}_{nm}_SECRET',
        f'{ns}_{nm}_SECRET',
        f'PERSONAL_OS_{ns}_KEY',
        f'{ns}_KEY',
    ]
    if namespace == 'side_effect_proof' and name == 'default':
        candidates.extend(['PERSONAL_OS_SIDE_EFFECT_PROOF_DEFAULT_SECRET', 'SIDE_EFFECT_PROOF_KEY', 'PERSONAL_OS_SIDE_EFFECT_PROOF_KEY'])
    if namespace in {'mainchain_proof', 'persona_visual_mainchain'}:
        candidates.extend(['MAINCHAIN_PROOF_KEY', 'PERSONA_VISUAL_MAINCHAIN_SECRET'])
    return list(dict.fromkeys(candidates))


class RuntimeSecretProvider:
    """Environment-only runtime secret provider.

    V111.52.6 hardening: secrets are never auto-generated into the worktree.
    Missing secrets fail closed so proof issuing/validation cannot silently fall
    back to a package-local secret.
    """

    def __init__(self, root: Optional[str | Path] = None):
        self.root = project_root(root)

    def require(self, name: str, namespace: str = 'side_effect_proof') -> str:
        for key in _env_candidates(name, namespace):
            value = os.environ.get(key, '').strip()
            if value:
                return value
        raise MissingRuntimeSecretError(
            f"missing_runtime_secret: namespace={namespace} name={name} candidates={','.join(_env_candidates(name, namespace))}"
        )

    def get_or_create(self, name: str, namespace: str = 'side_effect_proof') -> str:
        # Backwards-compatible method name; intentionally does not create files.
        return self.require(name=name, namespace=namespace)


def require_secret(name: str, namespace: str = 'side_effect_proof', root: Optional[str | Path] = None) -> str:
    return RuntimeSecretProvider(root=root).require(name=name, namespace=namespace)


def get_or_create_secret(name: str, namespace: str = 'side_effect_proof', root: Optional[str | Path] = None) -> str:
    return require_secret(name=name, namespace=namespace, root=root)
