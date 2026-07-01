#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--timeout',type=int,default=60); ap.add_argument('pytest_args',nargs=argparse.REMAINDER); args=ap.parse_args(); extra=args.pytest_args
    if extra and extra[0]=='--': extra=extra[1:]
    if not extra: extra=['--collect-only','-q','-p','no:cacheprovider']
    cmd=[sys.executable,str(ROOT/'scripts/dlx_pytest.py')]+extra
    try:
        p=subprocess.run(cmd,cwd=str(ROOT),text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=args.timeout)
        report={'status':'ok' if p.returncode==0 else 'fail','returncode':p.returncode,'timeout':False,'stdout_tail':p.stdout[-4000:],'stderr_tail':p.stderr[-4000:]}
    except subprocess.TimeoutExpired as e:
        report={'status':'timeout','returncode':124,'timeout':True,'timeout_seconds':args.timeout,'stdout_tail':(e.stdout or '')[-1000:] if isinstance(e.stdout,str) else '','stderr_tail':(e.stderr or '')[-1000:] if isinstance(e.stderr,str) else ''}
    (ROOT/'reports').mkdir(exist_ok=True); (ROOT/'reports/V111_38_PYTEST_COLLECT_GUARD.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(report,ensure_ascii=False,indent=2)); return 0 if report['status']=='ok' else int(report.get('returncode') or 1)
if __name__=='__main__': raise SystemExit(main())
