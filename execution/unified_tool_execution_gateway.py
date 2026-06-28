from __future__ import annotations
import json
try:
    from infrastructure.offline_runtime_guard import activate, assert_safe_action; activate()
except Exception:
    def assert_safe_action(action, context=None): return {'allowed':False,'mode':'blocked','reason':'guard_unavailable'}
def execute_tool(tool_name, args=None, context=None):
    decision=assert_safe_action(str(tool_name)+' '+str(args or {}), context)
    if not decision.get('allowed'): return {'status':'blocked','tool':tool_name,'decision':decision,'side_effects':False}
    return {'status':'ok','mode':'dry_run','tool':tool_name,'args':args or {},'side_effects':False}

def check_tool_call(tool_name=None, command=None, args=None, context=None):
    """
    Legacy compatibility wrapper for old V108 gate.
    Routes through the current unified tool execution gateway.
    Dangerous outbound/real-side-effect calls are blocked.
    Harmless dry-runs return ok/mock.

    Supports two call patterns:
      check_tool_call('git push origin main')      # old V108 gate
      check_tool_call(tool_name='payment', args={}) # symbolic
    """
    import os as _os
    import json as _json
    no_ext = _os.environ.get('NO_EXTERNAL_API','').lower() == 'true'
    no_send = _os.environ.get('NO_REAL_SEND','').lower() == 'true'
    no_pay = _os.environ.get('NO_REAL_PAYMENT','').lower() == 'true'
    no_dev = _os.environ.get('NO_REAL_DEVICE','').lower() == 'true'

    ctx = context or {}
    # If command is provided as first positional arg (old gate pattern):
    # check_tool_call('git push origin main')
    cmd_text = ''
    if command:
        cmd_text = str(command)
    elif tool_name and not args:
        # First positional arg could be a command string or a tool name
        cmd_text = str(tool_name)

    name_str = str(tool_name) if tool_name and (args is not None or command) else ''
    args_str = json.dumps(args or {}) if args else ''
    full = (cmd_text + ' ' + name_str + ' ' + args_str).lower()
    dangerous = ['git push', 'curl ', 'wget ', 'ssh ', 'scp ', 'rsync ', 'gh ',
                 'webhook', 'send_email', 'send_message', 'make_call',
                 'payment', 'pay', 'transfer', 'device_control', 'delete',
                 'destructive', 'sign']

    if any(x in full for x in dangerous):
        return {'status': 'blocked', 'tool': name_str or cmd_text or '',
                'command': cmd_text or name_str or '',
                'reason': 'dangerous_or_outbound_action_blocked',
                'side_effects': False, 'execution_mode': 'blocked'}

    if name_str or cmd_text:
        return {'status': 'ok', 'tool': name_str or cmd_text or '',
                'command': cmd_text or name_str or '',
                'mode': 'mock_or_draft', 'side_effects': False}

    return {'status': 'ok', 'mode': 'mock_or_draft', 'side_effects': False}
