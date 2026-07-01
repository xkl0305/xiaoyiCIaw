#!/usr/bin/env python3
"""V110.1: Final index rebuild."""
from __future__ import annotations
import json, os, shutil
from pathlib import Path
ROOT = Path.cwd()
REPORTS = ROOT / "reports"
CURRENT = REPORTS / "current"
VINTAGE = REPORTS / "vintage"
CURRENT.mkdir(parents=True, exist_ok=True)
VINTAGE.mkdir(parents=True, exist_ok=True)

# Move all reports back to root for clean classification
for d in [CURRENT, VINTAGE]:
    for f in d.glob("*.json"):
        if f.name == "CURRENT_RELEASE_INDEX.json":
            continue
        dest = REPORTS / f.name
        if not dest.exists():
            shutil.move(str(f), str(dest))

# The CURRENT_RELEASE_INDEX in current dir is authoritative
# Copy it to reports root
src_idx = CURRENT / "CURRENT_RELEASE_INDEX.json"
dst_idx = REPORTS / "CURRENT_RELEASE_INDEX.json"
if src_idx.exists():
    shutil.copy2(str(src_idx), str(dst_idx))

# Valid prefix order
VALID_CURRENT_PREFIXES = ["V100", "V104", "V105", "V106", "V107", "V108", "V108_1", "V108_2", "V109", "V110", "V110_1"]
PASS_STATUSES = {"pass", "ok", "patched"}

current_list = []
vintage_list = []
for f in sorted(REPORTS.glob("*.json")):
    if f.name == "CURRENT_RELEASE_INDEX.json":
        continue
    # Determine version prefix
    prefix = None
    for vp in sorted(VALID_CURRENT_PREFIXES, key=len, reverse=True):
        if f.name.startswith(vp):
            prefix = vp
            break
    if prefix:
        current_list.append(f.name)
    else:
        vintage_list.append(f.name)

index = {
    "version": "V110.1",
    "generated": "2026-05-04 15:57",
    "current_reports": sorted(current_list),
    "vintage_reports": sorted(vintage_list),
    "total_current": len(current_list),
    "total_vintage": len(vintage_list),
    "note": "Current = V100+ reports in reports/ root. Vintage = V9x/V8x/other legacy reports."
}
(REPORTS / "CURRENT_RELEASE_INDEX.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Current: {len(current_list)}, Vintage: {len(vintage_list)}")
print("Index rebuilt.")
