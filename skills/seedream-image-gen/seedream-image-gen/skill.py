from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def run(prompt: str, input_image: str = '', size: str = '2K', dry_run: bool = False,
        negative_prompt: str = '', channel: str = '', **kwargs: Any) -> Dict[str, Any]:
    from memory_context.persona_runtime.providers.seedream_provider import provider_env, provider_ready, generate_image, _load_all_channel_configs
    env = provider_env()
    debug = env.get('_debug', {})
    input_exists = bool(input_image and Path(input_image).exists())
    debug['input_image_exists'] = input_exists
    debug['input_image_path'] = input_image or ''
    available = debug.get('available_channels', []) or [c['name'] for c in _load_all_channel_configs()]
    out = {
        'skill_id': 'seedream-image-gen',
        'provider_backed': True,
        'physical_skill_required': True,
        'payload_mode': 'image_to_image' if input_image else 'text_to_image',
        'provider': 'seedream_multichannel',
        'model': 'SeedreamBatch5 (3 channels)',
        'available_channels': available,
        'selected_channel': channel or (available[0] if available else 'none'),
        'provider_ready': provider_ready(),
        'provider_env_debug': debug,
        'prompt_preview': (prompt or '')[:300],
        'input_image': input_image,
        'input_image_exists': input_exists,
        'size': size,
    }
    if dry_run:
        out['status'] = 'dry_run_ready' if out['provider_ready'] else 'provider_not_ready'
        if not out['provider_ready']:
            missing = []
            if not debug.get('provider_url_present'):
                missing.append('SERVICE_URL/SEEDREAM_API_URL/SILICONFLOW_API_URL')
            if not debug.get('api_key_present'):
                missing.append('API_KEY')
            out['missing'] = missing
        return out
    if not out['provider_ready']:
        out['status'] = 'provider_not_ready'
        out['reason'] = 'missing_seedream_provider_env'
        return out
    res = generate_image(prompt=prompt, input_image=input_image, size=size,
                         negative_prompt=negative_prompt, channel=channel, **kwargs)
    out.update({'status': res.get('status', 'unknown'), 'provider_result': res})
    out['channel_used'] = res.get('channel_used') or channel or available[0] if available else 'none'
    out['generated_image_path'] = res.get('generated_image_path') or res.get('output_path')
    out['generated_image_paths'] = res.get('generated_image_paths') or ([out['generated_image_path']] if out.get('generated_image_path') else [])
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--prompt', required=True)
    ap.add_argument('--input-image', default='')
    ap.add_argument('--size', default='2K')
    ap.add_argument('--negative-prompt', default='')
    ap.add_argument('--channel', default='', choices=['', 'huawei_sse', 'ark', 'siliconflow'],
                    help='指定通道: huawei_sse(华为云) / ark(火山AR) / siliconflow(硅基流动)')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    print(json.dumps(run(prompt=args.prompt, input_image=args.input_image, size=args.size,
                         negative_prompt=args.negative_prompt, channel=args.channel,
                         dry_run=args.dry_run), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
