# -*- coding: utf-8 -*-
"""开篇钩子机械闸（反懒惰开场·避雷针）：检测开篇前 window 字是否命中避雷针，命中即 exit=1。
exit=0 通过 / 1 阻断 / 2 错误。
用法: python detect_hook.py --file ch1.txt [--window 80]
说明：本闸只检测「避雷针(懒惰/信息倾倒式开场)」命中，不验证钩子是否存在；
      世界观类仅命中「世界观/纪元/这个世界/那片大陆」等明示信息倾倒句式，
      避免误伤玄幻/科幻常用名词(大陆/帝国/位面)。
"""
import os
import sys
import argparse
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import read_text

LEIBIAN = [
    (r"(雨|雪|风|晴|阴|天气|乌云|艳阳|落日)", "天气"),
    (r"(醒|起床|睁眼|睡|梦境|梦里|翻身)", "睡醒"),
    (r"(镜子|镜中|倒影|照了照)", "照镜子"),
    (r"(简历|介绍自己|我叫|我是.*?今年)", "简历"),
    (r"(世界观|纪元|这个世界|那片大陆)", "世界观"),
    (r"(早晨|早上|一天|清晨|平凡的一天|那天|寻常)", "日常"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--window", type=int, default=80)
    args = ap.parse_args()
    try:
        text = read_text(args.file)
        head = text[: args.window]
        hits = []
        for pat, label in LEIBIAN:
            m = re.search(pat, head)
            if m:
                hits.append((label, m.group(0)))
        if hits:
            print(f"开篇前{args.window}字命中避雷针：")
            for label, kw in hits:
                print(f"  - [{label}] {kw}")
            print("EXIT=1 开篇命中避雷针")
            return 1
        print(f"EXIT=0 开篇前{args.window}字未命中避雷针")
        return 0
    except Exception as e:  # noqa
        print(f"EXIT=2 错误: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
