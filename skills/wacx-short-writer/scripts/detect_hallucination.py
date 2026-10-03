# -*- coding: utf-8 -*-
"""事实锚点一致性闸（反幻觉）：读取 fact_anchor.json，检查正文硬冲突。
支持的锚点 schema：
  {
    "entities": { "名称": "描述", ... },          # 软检查：名称应出现
    "constraints": ["禁止出现的表述1", ...]        # 硬检查：出现即冲突(exit=1)
  }
exit=0 通过 / 1 硬冲突 / 2 错误 / 无锚点文件时 exit=0（跳过）。
用法: python detect_hallucination.py --file ch.txt [--anchor fact_anchor.json]
"""
import os
import sys
import argparse
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import read_text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--anchor", default="fact_anchor.json")
    args = ap.parse_args()
    try:
        text = read_text(args.file)
        if not os.path.exists(args.anchor):
            print(f"EXIT=0 无锚点文件 {args.anchor}，反幻觉闸跳过（未执行，降级为LLM自评，不阻塞交付）")
            return 0
        with open(args.anchor, encoding="utf-8") as f:
            anchor = json.load(f)

        conflicts = []
        constraints = anchor.get("constraints", [])
        for c in constraints:
            if c and c in text:
                conflicts.append(c)

        missing = []
        entities = anchor.get("entities", {})
        for name in entities:
            if name and name not in text:
                missing.append(name)

        if conflicts:
            print(f"发现 {len(conflicts)} 处硬冲突：")
            for c in conflicts[:20]:
                print(f"  - 命中禁止表述：{c}")
            print("EXIT=1 事实锚点硬冲突")
            return 1
        if missing:
            print(f"[WARN] 锚点实体未在正文出现（软提示，不阻断）：{missing[:10]}")
        print("EXIT=0 事实锚点一致")
        return 0
    except Exception as e:  # noqa
        print(f"EXIT=2 错误: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
