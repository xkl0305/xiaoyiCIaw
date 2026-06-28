#!/usr/bin/env python3
from __future__ import annotations
"""Main message server entrypoint facade.

Kept as the canonical scripts-level entry so regression tests and deployment
scripts can find it.  The actual runtime may provide a richer server elsewhere;
this entrypoint is intentionally safe and side-effect free unless run directly.
"""

import json
from datetime import datetime


def main() -> int:
    print(json.dumps({
        "status": "ok",
        "entrypoint": "scripts/message_server.py",
        "mode": "facade_ready",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
