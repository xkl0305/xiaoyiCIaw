#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from infrastructure.packaging.source_runtime_boundary import package_clean_check

    clean = package_clean_check(ROOT)
    findings = []
    for p in clean.get('runtime_files_detected', []):
        findings.append({'path': p, 'reason': 'runtime_path_packaged'})
    for p in clean.get('forbidden_residue_detected', []):
        findings.append({'path': p, 'reason': 'forbidden_source_residue'})
    for p in clean.get('secret_literals_detected', []):
        findings.append({'path': p, 'reason': 'secret_literal'})

    out = {
        'overall': 'passed' if clean.get('clean') is True else 'failed',
        'finding_count': len(findings),
        'findings': findings[:50],
        'package_clean': clean,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if clean.get('clean') is True else 1


if __name__ == '__main__':
    raise SystemExit(main())
