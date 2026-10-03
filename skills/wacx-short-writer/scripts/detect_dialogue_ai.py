# -*- coding: utf-8 -*-
"""对话去AI腔机械闸：提取中文双引号内对话，检测禁用词/演绎式结构。
exit=0 通过 / 1 阻断 / 2 错误。
用法: python detect_dialogue_ai.py --file ch.txt
"""
import os
import sys
import argparse
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import read_text, find_banned_words, find_banned_struct, report

QUOTE_RE = re.compile(r"[\u201c\u201d]([^”\u201d]{1,200})[\u201d\u201c]")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    args = ap.parse_args()
    try:
        text = read_text(args.file)
        segs = QUOTE_RE.findall(text)
        hits = []
        for seg in segs:
            bw = find_banned_words(seg)
            bs = find_banned_struct(seg)
            for w, _ in bw:
                hits.append(("禁用词:" + w, seg[:20]))
            for s, _ in bs:
                hits.append(("结构:" + s, seg[:20]))
        if hits:
            report(hits, "dialogue_ai")
            print("EXIT=1 对话含AI腔")
            return 1
        print("EXIT=0 对话无AI腔")
        return 0
    except Exception as e:  # noqa
        print(f"EXIT=2 错误: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
