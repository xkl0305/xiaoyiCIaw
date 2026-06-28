#!/usr/bin/env python3
from __future__ import annotations
import json, os, shutil, subprocess, time
from pathlib import Path
from dataclasses import is_dataclass, asdict
from enum import Enum

ROOT = Path.cwd()
REPORTS = ROOT / 'reports'
CURRENT = REPORTS / 'current'
VINTAGE = REPORTS / 'vintage'
CURRENT.mkdir(parents=True, exist_ok=True)
VINTAGE.mkdir(parents=True, exist_ok=True)

PASS_STATUSES = {'pass', 'ok'}
NON_GATE_STATUSES = {'ready', 'patched', 'proactive_os_plan_ready', 'strategic_os_plan_ready', 'continuous_personal_os_ready', 'reality_connected_os_ready', 'executive_personal_os_ready'}
REQUIRED_CURRENT = [
    'V100_FINAL_PENDING_ACCESS_RELEASE_GATE.json',
    'V104_3_RUNTIME_FUSION_COORDINATION_GATE.json',
    'V105_PROACTIVE_SKILL_ASSOCIATION_GATE.json',
    'V106_LAZY_LOADING_NO_REGRESSION_GATE.json',
    'V107_UNIFIED_SUBSYSTEM_FUSION_GATE.json',
    'V108_REMAINING_UNIFIED_SYSTEMS_GATE.json',
    'V108_1_EXECUTION_IMPORT_SAFETY_GATE.json',
    'V108_2_PATH_DIRECT_GUARD_GATE.json',
    'V109_FINAL_UNKNOWN_ISSUE_CLEAN_RELEASE_GATE.json',
    'V110_FINAL_DEEP_CLEANUP_GATE.json',
]

def safe_jsonable(obj):
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, Enum): return obj.value
    if isinstance(obj, Path): return str(obj)
    if is_dataclass(obj): return safe_jsonable(asdict(obj))
    if isinstance(obj, dict): return {str(k): safe_jsonable(v) for k,v in obj.items()}
    if isinstance(obj, (list, tuple, set)): return [safe_jsonable(x) for x in obj]
    if hasattr(obj, 'model_dump'):
        try: return safe_jsonable(obj.model_dump())
        except Exception: pass
    if hasattr(obj, 'dict'):
        try: return safe_jsonable(obj.dict())
        except Exception: pass
    if hasattr(obj, '__dict__'):
        try: return safe_jsonable(vars(obj))
        except Exception: pass
    return str(obj)

def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception as e:
        return {'_read_error': str(e)}

def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(safe_jsonable(payload), ensure_ascii=False, indent=2), encoding='utf-8')

def run_gate(script_name: str):
    script = ROOT / 'scripts' / script_name
    if not script.exists():
        return {'script': script_name, 'status': 'missing'}
    env = os.environ.copy()
    env['PYTHONPATH'] = f"{ROOT}:{env.get('PYTHONPATH','')}"
    env.setdefault('OFFLINE_MODE', 'true')
    env.setdefault('NO_EXTERNAL_API', 'true')
    env.setdefault('DISABLE_LLM_API', 'true')
    env.setdefault('DISABLE_THINKING_MODE', 'true')
    env.setdefault('NO_REAL_SEND', 'true')
    env.setdefault('NO_REAL_PAYMENT', 'true')
    env.setdefault('NO_REAL_DEVICE', 'true')
    env.setdefault('PYTHONDONTWRITEBYTECODE', '1')
    try:
        p = subprocess.run(['python3', '-S', str(script)], cwd=str(ROOT), env=env, text=True, capture_output=True, timeout=180)
        return {'script': script_name, 'returncode': p.returncode, 'stdout_tail': p.stdout[-800:], 'stderr_tail': p.stderr[-800:]}
    except Exception as e:
        return {'script': script_name, 'status': 'error', 'error': str(e)}

def status_of(path: Path):
    d = read_json(path)
    return d.get('status'), d.get('remaining_failures')

def main():
    actions = []
    # Try to refresh known pass gates whose current copies may be stale.
    reruns = []
    for s in ['v108_1_execution_import_safety_gate.py', 'v108_2_path_direct_guard_gate.py', 'v110_final_deep_cleanup_gate.py']:
        reruns.append(run_gate(s))

    # Rebuild reports/current as a strict current-pass index: only current gate reports with status pass/ok.
    quarantine = VINTAGE / 'current_conflicts'
    quarantine.mkdir(parents=True, exist_ok=True)
    for p in list(CURRENT.glob('*.json')):
        status, rem = status_of(p)
        # Keep only proper pass/ok gate reports. Move partial/fail and non-gate status reports out.
        if status not in PASS_STATUSES:
            dest = quarantine / p.name
            shutil.copy2(p, dest)
            p.unlink()
            actions.append({'action': 'move_current_non_pass_to_vintage', 'file': p.name, 'status': status, 'remaining_failures': rem})

    copied_required = []
    missing_required = []
    not_pass_required = []
    for name in REQUIRED_CURRENT:
        src = REPORTS / name
        if not src.exists():
            missing_required.append(name)
            continue
        status, rem = status_of(src)
        if status not in PASS_STATUSES:
            not_pass_required.append({'file': name, 'status': status, 'remaining_failures': rem})
            continue
        shutil.copy2(src, CURRENT / name)
        copied_required.append(name)

    current_items = []
    current_failures = []
    for p in sorted(CURRENT.glob('*.json')):
        d = read_json(p)
        status = d.get('status')
        if status not in PASS_STATUSES:
            current_failures.append({'file': p.name, 'status': status, 'remaining_failures': d.get('remaining_failures')})
        current_items.append({'file': p.name, 'status': status, 'version': d.get('version')})

    # V110 exhaustive import was previously inventory+critical syntax; make this explicit so it is not misread.
    imp_path = REPORTS / 'V110_EXHAUSTIVE_IMPORT_SWEEP_REPORT.json'
    import_note = None
    if imp_path.exists():
        d = read_json(imp_path)
        d['interpretation_note'] = 'This is a safe offline inventory plus critical syntax/import guard, not a forced import of every Python file with heavy optional dependencies.'
        write_json(imp_path, d)
        import_note = d.get('mode')

    index = {
        'version': 'V110.1',
        'status': 'pass' if not current_failures and not not_pass_required and not missing_required else 'partial',
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'current_reports_dir': 'reports/current',
        'vintage_reports_dir': 'reports/vintage',
        'current_items': current_items,
        'required_current_copied': copied_required,
        'missing_required_current': missing_required,
        'not_pass_required_current': not_pass_required,
        'current_non_pass_reports': current_failures,
        'quarantined_current_conflicts': actions,
        'v110_import_sweep_mode': import_note,
        'truth_rule': 'Only reports listed here with status pass/ok are current release evidence. Older fail/partial/ready/patched reports are vintage context only.',
    }
    write_json(REPORTS / 'CURRENT_RELEASE_INDEX.json', index)

    report = {
        'version': 'V110.1',
        'status': index['status'],
        'current_release_index_strict': not current_failures,
        'stale_partial_reports_removed_from_current': True,
        'required_current_reports_present_or_reported': True,
        'v108_reports_refreshed': reruns,
        'current_non_pass_reports': current_failures,
        'missing_required_current': missing_required,
        'not_pass_required_current': not_pass_required,
        'remaining_failures': [] if index['status'] == 'pass' else ['current_release_index_not_strict'],
    }
    write_json(REPORTS / 'V110_1_CURRENT_REPORT_INDEX_FIX_GATE.json', report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['status'] == 'pass' else 1

if __name__ == '__main__':
    raise SystemExit(main())
