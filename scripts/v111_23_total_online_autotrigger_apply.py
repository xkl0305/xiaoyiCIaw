#!/usr/bin/env python3
from __future__ import annotations
import json, time
from pathlib import Path
from typing import Any
ROOT = Path(__file__).resolve().parents[1]
def write_json(p: Path, data: Any):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
def main() -> int:
    p = ROOT/'openclaw.json'
    data = {}
    if p.exists():
        try: data = json.loads(p.read_text(encoding='utf-8'))
        except Exception: data = {}
    data.update({'NO_EXTERNAL_API': False, 'OFFLINE_MODE': False, 'ONLINE_MODE': True, 'CONNECTED_RUNTIME_ALWAYS_ON': True, 'runtimeMode': 'online_connected'})
    pv = data.setdefault('personaVisual', {})
    pv.update({'enabled': True, 'autoGenerate': True, 'generationConsentMode': 'auto_with_budget', 'userStandingConsent': True, 'requiresPerImageOnlineApproval': False, 'onlineProviderAllowed': True, 'dailyAutoGenerateLimit': 100, 'cooldownTurns': 0, 'sceneTriggerMode': 'semantic_scene_fuzzy_turn_observer', 'triggerSourcePolicy': 'assistant_lobster_output_first', 'fuzzyMatchingEnabled': True, 'nearSynonymMatchingEnabled': True, 'seedAvatarPath': 'assets/persona/seed_avatar.jpg', 'identitySource': 'seed_avatar_image_only', 'seedReferenceWeight': 100})
    cr = data.setdefault('connectedRuntime', {})
    cr.update({'enabled': True, 'alwaysConnected': True, 'defaultMode': 'always_online', 'noPerActionOnlineAuthorization': True, 'xiaoyiCapabilitiesAlwaysConnected': True, 'endSideCapabilitiesAlwaysConnected': True, 'deviceBridgeAlwaysConnected': True, 'allowExternalProvidersWithStandingConsent': True, 'offlineModeRemoved': True})
    write_json(p, data)
    report = {'version':'V111.23','status':'applied','applied_at':time.strftime('%Y-%m-%dT%H:%M:%S'),'purpose':'online_lobster_output_autotrigger_fuzzy_persona_visual','openclaw_online': {'NO_EXTERNAL_API': data.get('NO_EXTERNAL_API'), 'OFFLINE_MODE': data.get('OFFLINE_MODE'), 'ONLINE_MODE': data.get('ONLINE_MODE')}, 'personaVisual': {k: pv.get(k) for k in ['sceneTriggerMode','triggerSourcePolicy','fuzzyMatchingEnabled','nearSynonymMatchingEnabled','dailyAutoGenerateLimit','cooldownTurns','seedAvatarPath']}, 'connectedRuntime': cr}
    write_json(ROOT/'reports'/'V111_23_TOTAL_ONLINE_AUTOTRIGGER_APPLY.json', report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0
if __name__ == '__main__': raise SystemExit(main())
