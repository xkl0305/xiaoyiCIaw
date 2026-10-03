# -*- coding: utf-8 -*-
"""自报字数一致性闸：正文旁白自报"X字/X个字"须与紧邻引文实际字数一致。
exit=0 通过 / 1 不一致 / 2 错误。
用法: python detect_wordcount_claim.py --file ch.txt [--tol 0.15]
说明：提取「N字/N个字」后紧邻的中文双引号引文，比较实际字数；偏差>tol则阻断。
"""
import os
import sys
import argparse
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import read_text, count_words


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--tol", type=float, default=0.15)
    args = ap.parse_args()
    try:
        text = read_text(args.file)
        claims = list(re.finditer(r"(\d+)\s*个字?", text))
        bad = []
        for m in claims:
            claimed = int(m.group(1))
            rest = text[m.end(): m.end() + 400]
            seg = re.search(r"[\u201c\u201d]([^\u201d”]{1,300})[\u201d\u201c]", rest)
            if not seg:
                continue
            actual = count_words(seg.group(1))
            if actual == 0:
                continue
            if abs(actual - claimed) / max(actual, 1) > args.tol:
                bad.append((claimed, actual))
        if bad:
            print(f"发现 {len(bad)} 处自报字数不一致：")
            for c, a in bad[:20]:
                print(f"  - 自报 {c} vs 实际 {a}")
            print("EXIT=1 自报字数不一致")
            return 1
        print("EXIT=0 未检测到自报字数表述（无需校验）")
        return 0
    except Exception as e:  # noqa
        print(f"EXIT=2 错误: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
