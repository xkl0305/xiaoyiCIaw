#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
COMPATIBLE_PREFIXES = ('V111.52.11', 'V111.52.12')
def load(path): return json.loads((ROOT/path).read_text(encoding='utf-8'))
def main():
    version = load('xiaoyi_persona_visual/version.json').get('version','')
    manifest = load('release_manifest.json')
    model_hash = load('profiles/model_hash_manifest.json')
    checks = {
        'version_compatible_52_11_or_newer': version.startswith(COMPATIBLE_PREFIXES),
        'release_manifest_active_version_compatible': str(manifest.get('version','')).startswith(COMPATIBLE_PREFIXES),
        'model_hash_manifest_active_version_compatible': str(model_hash.get('version','')).startswith(COMPATIBLE_PREFIXES),
        'strict_local_profile_preserved': load('openclaw.json').get('DEFAULT_RUNTIME_PROFILE') == 'strict_local_enterprise',
    }
    from infrastructure.packaging.source_runtime_boundary import package_clean_check
    clean = package_clean_check(ROOT)
    checks['package_clean_check_full'] = clean.get('clean') is True
    out = {'overall':'passed' if all(checks.values()) else 'failed','checks':checks,'compatibility_target':'V111.52.11.1+','active_version':version,'package_clean_summary':clean}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if all(checks.values()) else 1
if __name__ == '__main__':
    raise SystemExit(main())
