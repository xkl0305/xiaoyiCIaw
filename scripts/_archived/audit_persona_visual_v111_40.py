#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main():
    from scripts.mainline_bootstrap import enable
    from infrastructure.persona_visual_hook_bus import dispatch, status
    from memory_context.persona_runtime.persona_visual_dedupe_gate import clear_dedupe_state
    enable()
    clear_dedupe_state()
    pre = dispatch('pre_reply', reply_text='搞定了 🎉', dry_run=True)
    post1 = dispatch('post_reply', reply_text='搞定了 🎉', dry_run=True)
    post2 = dispatch('post_reply', reply_text='搞定了 🎉', dry_run=True)
    out = {
        'status': 'ok' if (pre.get('result',{}).get('generation_status') == 'precheck_only' and post2.get('result',{}).get('generation_status') == 'deduped_skip') else 'warn',
        'bus_status': status(),
        'pre': pre,
        'post1': post1,
        'post2': post2,
    }
    (ROOT/'reports').mkdir(exist_ok=True)
    (ROOT/'reports/V111_40_PERSONA_VISUAL_AUDIT.json').write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    (ROOT/'reports/V111_40_PERSONA_VISUAL_AUDIT.txt').write_text('status: '+out['status']+'\n'+json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False, indent=2))
if __name__ == '__main__':
    main()
