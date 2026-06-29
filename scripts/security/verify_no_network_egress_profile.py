from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def main() -> int:
    data=json.loads((ROOT/'openclaw.json').read_text(encoding='utf-8'))
    checks={
        'ALLOW_NETWORK_false': data.get('ALLOW_NETWORK') is False,
        'NO_EXTERNAL_API_true': data.get('NO_EXTERNAL_API') is True,
        'OFFLINE_MODE_true': data.get('OFFLINE_MODE') is True,
        'ONLINE_MODE_false': data.get('ONLINE_MODE') is False,
        'ZERO_EXTERNAL_MODE_true': data.get('ZERO_EXTERNAL_MODE') is True,
        'NO_REAL_PAYMENT_true': data.get('NO_REAL_PAYMENT') is True,
        'NO_REAL_SEND_true': data.get('NO_REAL_SEND') is True,
        'external_access_disallowed': data.get('externalAccessPolicy',{}).get('allowExternalApi') is False,
        'persona_external_provider_disabled': data.get('personaVisual',{}).get('externalProviderAllowed') is False,
    }
    overall=all(checks.values())
    print({'overall':'passed' if overall else 'failed','checks':checks})
    return 0 if overall else 1

if __name__ == '__main__':
    raise SystemExit(main())
