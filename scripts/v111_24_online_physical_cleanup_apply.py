#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=ROOT/'openclaw.json'
    data=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
    data['ONLINE_MODE']=True; data['OFFLINE_MODE']=False; data['NO_EXTERNAL_API']=False; data['DISABLE_LLM_API']=False; data['DISABLE_THINKING_MODE']=False
    data['NO_REAL_PAYMENT']=False; data['NO_REAL_SEND']=False; data['NO_REAL_DEVICE']=False
    runtime=data.setdefault('runtime', {})
    runtime.update({'ONLINE_MODE':True,'OFFLINE_MODE':False,'NO_EXTERNAL_API':False,'DISABLE_LLM_API':False,'DISABLE_THINKING_MODE':False,'NO_REAL_PAYMENT':False,'NO_REAL_SEND':False,'NO_REAL_DEVICE':False})
    cr=data.setdefault('connectedRuntime', {})
    cr.update({'enabled':True,'alwaysConnected':True,'defaultMode':'always_online','noPerActionOnlineAuthorization':True,'xiaoyiCapabilitiesAlwaysConnected':True,'endSideCapabilitiesAlwaysConnected':True,'deviceBridgeAlwaysConnected':True,'allowExternalProvidersWithStandingConsent':True,'offlineModeRemoved':True,'legacyOfflineFiles':'compatibility_shims_only'})
    data['runtimeMode']='online_connected'
    data['realSideEffectPolicy']={'mode':'online_connected_strong_confirmation','safeActions':'direct','externalProviderOnlineAuth':'standing_consent','sendPaymentDeleteDevice':'strong_confirmation_required','destructiveAction':'strong_confirmation_required','defaultDenyWithoutExplicitIntent':True}
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status':'ok','version':'V111.24','changed':['openclaw runtime flags forced online','nested runtime flags corrected','real side effect policy set to strong confirmation','offline files retained as compatibility shims only']}, ensure_ascii=False, indent=2))
if __name__=='__main__': main()
