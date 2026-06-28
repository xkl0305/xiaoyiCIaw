#!/usr/bin/env python3
from __future__ import annotations
import json, tempfile, os, subprocess, sys
from pathlib import Path
VERSION='V111.52.12_FULL_LOCAL_STACK_EMBODIED_OPS_FINAL'; ROOT=Path(__file__).resolve().parents[2]

def j(p): return json.loads((ROOT/p).read_text(encoding='utf-8'))

def clean_runtime_quiet() -> None:
    cleaner = ROOT / 'scripts/clean_runtime_artifacts.py'
    if cleaner.exists():
        env = os.environ.copy()
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        env['PYTHONPATH'] = '.'
        subprocess.run([sys.executable, '-S', str(cleaner)], cwd=ROOT, env=env,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

def main():
 clean_runtime_quiet()
 checks={}
 checks['version_52_12']=(str(j('xiaoyi_persona_visual/version.json').get('version','')).startswith('V111.52.12') or str(j('xiaoyi_persona_visual/version.json').get('version','')).startswith('V111.52.13')) and (str(j('release_manifest.json').get('version','')).startswith('V111.52.12') or str(j('release_manifest.json').get('version','')).startswith('V111.52.13'))
 oc=j('openclaw.json'); checks['strict_local_runtime']=oc.get('ALLOW_NETWORK') is False and oc.get('NO_EXTERNAL_API') is True and oc.get('ONLINE_MODE') is False
 req=['core/personal_os_enterprise/local_model_stack_binding.py','core/personal_os_enterprise/embodied_action_runtime.py','core/personal_os_enterprise/trace_context.py','core/personal_os_enterprise/local_persona_image_provider.py','core/personal_os_enterprise/retention_policy.py','profiles/local_capabilities.toml','scripts/prefetch_models_prepare_machine.py','scripts/verify_model_cache_hash.py']
 checks['required_files_present']=all((ROOT/p).exists() for p in req)
 from core.personal_os_enterprise.local_model_stack_binding import local_stack_status, RECOMMENDED_STACK
 from core.personal_os_enterprise.local_providers import run_local_llm, run_local_embedding, run_local_ocr, run_local_reranker, execute_local_capability
 from core.personal_os_enterprise.embodied_action_runtime import embodied_dry_run
 from core.personal_os_enterprise.trace_context import new_trace, span
 from core.personal_os_enterprise.observability_event_bus import read_events
 from core.personal_os_enterprise.retention_policy import redact_text, retention_decision
 from core.personal_os_enterprise.local_model_registry import get_model_capability
 checks['recommended_stack_complete']={'local_llm','local_vlm','local_ocr','local_asr','local_tts','local_embedding','local_reranker','local_image_provider'} <= set(RECOMMENDED_STACK)
 checks['local_stack_no_external']=local_stack_status(ROOT).get('allow_external_fallback') is False
 with tempfile.TemporaryDirectory() as td:
  tmp=Path(td); (tmp/'profiles').mkdir(); img=tmp/'img.png'; img.write_bytes(b'png')
  (tmp/'profiles/local_capabilities.toml').write_text(r'''[local_llm]
capability="local_llm"
enabled=true
command="python3 -c 'import sys; print(sys.stdin.read().upper())'"
allow_external_fallback=false
[local_embedding]
capability="local_embedding"
enabled=true
command="python3 -c 'print([0.1,0.2])'"
allow_external_fallback=false
[local_ocr]
capability="local_ocr"
enabled=true
command="python3 -c 'print(\"OCR_OK\")'"
allow_external_fallback=false
[local_reranker]
capability="local_reranker"
enabled=true
command="python3 -c 'print([])'"
allow_external_fallback=false
[local_vlm]
capability="local_vlm"
enabled=true
endpoint="https://example.com/v1"
allow_external_fallback=false
''',encoding='utf-8')
  checks['local_llm_command_executes']=run_local_llm('abc',root=tmp).get('status')=='executed'
  checks['local_embedding_command_executes']=run_local_embedding('abc',root=tmp).get('status')=='executed'
  checks['local_ocr_command_executes']=run_local_ocr(str(img),root=tmp).get('status')=='executed'
  checks['local_reranker_executes']=run_local_reranker('q',['d'],root=tmp).get('status')=='executed'
  checks['execute_local_capability_dispatch']=execute_local_capability('local_llm',root=tmp,prompt='x').get('status')=='executed'
  checks['non_local_endpoint_rejected']=get_model_capability('local_vlm',root=tmp).get('endpoint_rejected')=='non_local_endpoint'
  dry=embodied_dry_run('点击设置按钮',root=tmp); checks['embodied_dry_run_fail_closed']=dry.get('status')=='dry_run' and dry.get('observation',{}).get('status')=='blocked'
  tr=new_trace(request_id='verify')
  with span('verify_span',trace=tr,root=tmp): pass
  checks['trace_span_events_written']=len(read_events(root=tmp))>=2
  checks['retention_redacts_secret']='[REDACTED_SECRET]' in redact_text('api_key=sk-1234567890abcdef')
  checks['retention_classifies_secret']=retention_decision('.env')['data_class']=='S0'
 clean_runtime_quiet()
 from infrastructure.packaging.source_runtime_boundary import package_clean_check
 clean=package_clean_check(ROOT); checks['package_clean']=clean.get('clean') is True
 out={'overall':'passed' if all(checks.values()) else 'failed','checks':checks,'package_clean':clean,'version':VERSION}
 print(json.dumps(out,ensure_ascii=False,indent=2)); return 0 if all(checks.values()) else 1
if __name__=='__main__': raise SystemExit(main())
