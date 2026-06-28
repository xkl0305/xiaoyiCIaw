from __future__ import annotations
import json, os, subprocess, time
from pathlib import Path
from typing import Dict, Any, Optional
from .action_guard import guard_action
from .capability_router import route_request
from .local_providers import run_local_ocr, run_local_vlm
from .observability_event_bus import emit_event
from .trace_context import new_trace, span
VERSION = 'V111.52.12_FULL_LOCAL_STACK_EMBODIED_OPS_FINAL'
def capture_screenshot(*, root=None, output_path: str = '', command: str = '') -> Dict[str, Any]:
    out = output_path or str(Path(root or '.').resolve()/'.runtime'/'screenshots'/f'screen_{int(time.time()*1000)}.png')
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    cmd = command or os.environ.get('LOCAL_SCREENSHOT_COMMAND','')
    if not cmd:
        return {'status': 'blocked', 'blocked': True, 'blocked_reason': 'screenshot_adapter_not_configured', 'output_path': out, 'network_egress_attempted': False}
    try:
        proc = subprocess.run(cmd.format(output_path=out).split(), text=True, capture_output=True, timeout=20, check=False)
        ok = proc.returncode == 0 and Path(out).exists()
        return {'status': 'captured' if ok else 'blocked', 'blocked': not ok, 'blocked_reason': '' if ok else 'screenshot_command_failed', 'output_path': out, 'stderr': proc.stderr[-1000:]}
    except Exception as e:
        return {'status': 'blocked', 'blocked': True, 'blocked_reason': f'screenshot_exception:{type(e).__name__}', 'error': str(e), 'output_path': out}
def read_window_tree(*, root=None, command: str = '') -> Dict[str, Any]:
    cmd = command or os.environ.get('LOCAL_WINDOW_TREE_COMMAND','')
    if not cmd:
        return {'status': 'blocked', 'blocked': True, 'blocked_reason': 'window_tree_adapter_not_configured', 'windows': []}
    try:
        proc = subprocess.run(cmd.split(), text=True, capture_output=True, timeout=20, check=False)
        return {'status': 'read' if proc.returncode == 0 else 'blocked', 'blocked': proc.returncode != 0, 'windows': json.loads(proc.stdout) if proc.stdout.strip().startswith('[') else [{'raw': proc.stdout}]}
    except Exception as e:
        return {'status': 'blocked', 'blocked': True, 'blocked_reason': f'window_tree_exception:{type(e).__name__}', 'error': str(e), 'windows': []}
def observe_screen(goal: str, *, root=None, screenshot_path: str = '') -> Dict[str, Any]:
    tr = new_trace(entrypoint='embodied_screen_agent')
    with span('observe_screen', trace=tr, root=root, goal=goal):
        shot = {'status': 'provided', 'blocked': False, 'output_path': screenshot_path} if screenshot_path else capture_screenshot(root=root)
        if shot.get('blocked'):
            return {'status': 'blocked', 'blocked_reason': shot.get('blocked_reason'), 'screenshot': shot, 'trace_id': tr.trace_id}
        img = shot.get('output_path')
        ocr = run_local_ocr(img, root=root); vlm = run_local_vlm(img, f'请理解屏幕界面并提取目标相关控件：{goal}', root=root); windows = read_window_tree(root=root)
        emit_event('screen_observed', {'goal': goal, 'trace_id': tr.trace_id, 'ocr_status': ocr.get('status'), 'vlm_status': vlm.get('status')}, root=root)
        return {'status': 'observed', 'screenshot': shot, 'ocr': ocr, 'vlm': vlm, 'windows': windows, 'trace_id': tr.trace_id, 'network_egress_attempted': False}
def plan_gui_action(goal: str, observation: Dict[str, Any]) -> Dict[str, Any]:
    c = []
    if any(k in goal for k in ['点击','打开','选择']): c.append({'type':'click','target':goal,'requires_coordinate_resolution':True})
    if any(k in goal for k in ['输入','填写','发送']): c.append({'type':'type_text','target':goal,'requires_focused_input':True})
    return {'status': 'planned', 'dry_run_only': True, 'goal': goal, 'candidates': c, 'requires_action_guard': True, 'requires_post_action_verify': True, 'confidence': 0.35 if c else 0.0, 'reason': 'coordinate_execution_adapter_not_enabled' if c else 'no_action_candidate'}
def execute_gui_action(plan: Dict[str, Any], *, root=None, proof: Optional[Dict[str, Any]] = None, explicit_approval: bool = False) -> Dict[str, Any]:
    guard = guard_action(action_type='device_action', payload=plan, proof=proof, explicit_approval=explicit_approval, root=root)
    if guard.get('blocked'):
        return {'status': 'blocked', 'blocked_reason': guard.get('blocked_reason'), 'guard': guard, 'executed': False}
    return {'status': 'blocked', 'blocked_reason': 'gui_action_adapter_not_configured', 'guard': guard, 'executed': False}
def embodied_dry_run(goal: str, *, root=None, screenshot_path: str = '') -> Dict[str, Any]:
    observation = observe_screen(goal, root=root, screenshot_path=screenshot_path)
    return {'status': 'dry_run', 'route': route_request(goal, root=root, require_ready=False), 'observation': observation, 'plan': plan_gui_action(goal, observation), 'version': VERSION}
