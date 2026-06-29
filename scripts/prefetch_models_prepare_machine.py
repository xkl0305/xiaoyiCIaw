#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; MANIFEST=ROOT/'profiles/model_prefetch_manifest.json'
def main():
 p=argparse.ArgumentParser(); p.add_argument('--execute',action='store_true'); p.add_argument('--manifest',default=str(MANIFEST)); a=p.parse_args(); data=json.loads(Path(a.manifest).read_text(encoding='utf-8')); cmds=[]
 for m in data.get('models',[]): cmds.append([sys.executable,'-c',f"from huggingface_hub import snapshot_download; snapshot_download(repo_id={m['repo_id']!r}, local_dir={m['local_dir']!r})"])
 if not a.execute: print(json.dumps({'mode':'dry_run_prepare_machine_only','commands':cmds},ensure_ascii=False,indent=2)); return 0
 if os.environ.get('ALLOW_NETWORK')=='false' or os.environ.get('OFFLINE_MODE')=='true': print('Refusing runtime download; use prepare machine.',file=sys.stderr); return 2
 for c in cmds: subprocess.run(c,check=True)
 return 0
if __name__=='__main__': raise SystemExit(main())
