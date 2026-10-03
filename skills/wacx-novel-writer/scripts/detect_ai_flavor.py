# -*- coding: utf-8 -*-
"""AI味机械闸：破折号>limit / 禁用词>0 / 引号非中文双引号 / 思考路径演绎式>0 -> exit=1。
exit=0 干净 / 1 阻断 / 2 错误。
用法: python detect_ai_flavor.py --file ch.txt [--dash-limit 5]
说明：思考路径演绎式（结论+比如/例如）为启发式，>=2 处才阻断，避免误伤合法举例。
"""
import os
import sys
import argparse
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (
    read_text,
    find_banned_words,
    find_banned_struct,
    count_dashes,
    find_forbidden_quotes,
    report,
)

THINK_PATH = [r"。比如", r"。例如", r"。譬如", r"，比如", r"，例如", r"，譬如"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--dash-limit", type=int, default=5)
    args = ap.parse_args()
    try:
        text = read_text(args.file)
        blocked = False

        bw = find_banned_words(text)
        if bw:
            report(bw, "banned_words")
            blocked = True

        bs = find_banned_struct(text)
        if bs:
            report(bs, "banned_struct")
            blocked = True

        d = count_dashes(text)
        if d > args.dash_limit:
            print(f"  [BLOCK:dash] 破折号 {d} > {args.dash_limit}")
            blocked = True
        else:
            print(f"  [OK:dash] 破折号 {d} <= {args.dash_limit}")

        fq = find_forbidden_quotes(text)
        if fq:
            report([(repr(c), i) for c, i in fq], "forbidden_quotes")
            blocked = True

        tp = 0
        for p in THINK_PATH:
            tp += len(re.findall(p, text))
        if tp >= 2:
            print(f"  [BLOCK:think_path] 演绎式结构 {tp} 处（结论+比如/例如）")
            blocked = True
        elif tp == 1:
            print(f"  [WARN:think_path] 演绎式结构 1 处（未阻断，>=2 才阻断）")

        if blocked:
            print("EXIT=1 AI味机械闸阻断")
            return 1
        print("EXIT=0 AI味机械闸通过")
        return 0
    except Exception as e:  # noqa
        print(f"EXIT=2 错误: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
