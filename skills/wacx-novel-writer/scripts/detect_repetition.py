# -*- coding: utf-8 -*-
"""重复闸门：检测近似重复句（长度>=min-len，相似度>=ratio）。
exit=0 通过 / 1 发现重复 / 2 错误。
用法: python detect_repetition.py --file ch.txt [--min-len 8] [--ratio 0.8]
"""
import os
import sys
import argparse
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import read_text


def split_sentences(text):
    parts = re.split(r"(?<=[。！？!?；;\n])", text)
    out = []
    buf = ""
    for p in parts:
        buf += p
        if p.strip().endswith(("。", "！", "？", "!", "?", "；", ";")) or p == "\n":
            if buf.strip():
                out.append(buf.strip())
            buf = ""
    if buf.strip():
        out.append(buf.strip())
    return out


def sim(a, b):
    try:
        import difflib

        return difflib.SequenceMatcher(None, a, b).ratio()
    except Exception:  # noqa
        return 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--min-len", type=int, default=8)
    ap.add_argument("--ratio", type=float, default=0.8)
    ap.add_argument("--max-hits", type=int, default=0, help=">=此值则阻断（0=任何重复都阻断）")
    args = ap.parse_args()
    try:
        sents = split_sentences(read_text(args.file))
        hits = []
        n = len(sents)
        for i in range(n):
            a = sents[i]
            if len(a) < args.min_len:
                continue
            for j in range(i + 1, n):
                b = sents[j]
                if len(b) < args.min_len:
                    continue
                if a == b or sim(a, b) >= args.ratio:
                    hits.append((a[:24], b[:24]))
        if not hits:
            print("EXIT=0 无近似重复句")
            return 0
        print(f"发现 {len(hits)} 处近似重复：")
        for a, b in hits[:20]:
            print(f"  - 「{a}…」≈「{b}…」")
        threshold = args.max_hits if args.max_hits > 0 else 1
        if len(hits) >= threshold:
            print("EXIT=1 重复超阈值")
            return 1
        print("EXIT=0 重复未超阈值")
        return 0
    except Exception as e:  # noqa
        print(f"EXIT=2 错误: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
