from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    # 确保能找到 memory_context
    wd = Path(__file__).resolve().parents[3]  # scripts -> seedream-image-gen -> skills -> workspace
    if str(wd) not in sys.path:
        sys.path.insert(0, str(wd))

    ap = argparse.ArgumentParser(description='seedream-image-gen: 三通道图像生成')
    ap.add_argument('--prompt', required=True, help='提示词')
    ap.add_argument('--input-image', default='', help='输入图片路径')
    ap.add_argument('--size', default='2K', choices=['2K', '3K', '4K', '4K-wide', '4K-portrait', '4K-square'])
    ap.add_argument('--max-images', type=int, default=1)
    ap.add_argument('--reference-weight', type=int, default=100)
    ap.add_argument('--negative-prompt', default='')
    ap.add_argument('--channel', default='',
                    choices=['', 'huawei_sse', 'ark', 'siliconflow'],
                    help='指定通道: huawei_sse(华为云) / ark(火山引擎AR) / siliconflow(硅基流动)')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    # ── dry-run: 只查看可用通道，不发请求 ──
    if args.dry_run:
        from memory_context.persona_runtime.providers.seedream_provider import _load_all_channel_configs
        channels = _load_all_channel_configs()
        info = {
            'status': 'dry_run_ready',
            'available_channels': [c['name'] for c in channels],
            'channel_count': len(channels),
            'selected_channel': args.channel or 'auto',
            'configs': [{'name': c['name'], 'mode': c['mode'], 'url': c['url'][:50]} for c in channels],
        }
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return

    from memory_context.persona_runtime.providers.seedream_provider import generate_image

    res = generate_image(
        prompt=args.prompt,
        input_image=args.input_image,
        size=args.size,
        max_images=args.max_images,
        reference_weight=args.reference_weight,
        negative_prompt=args.negative_prompt,
        channel=args.channel,
    )
    print(json.dumps(res, ensure_ascii=False, indent=2, default=str))


if __name__ == '__main__':
    main()
