from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'profiles' / 'model_prefetch_manifest.json'

if __name__ == '__main__':
    data = json.loads(MANIFEST.read_text(encoding='utf-8'))
    print(json.dumps({
        'mode': 'dry_run_only',
        'message': '按清单在准备机手动预拉取模型；运行机保持 HF_HUB_OFFLINE/NO_EXTERNAL_API。此脚本不联网。',
        'models': data.get('models', []),
    }, ensure_ascii=False, indent=2))
