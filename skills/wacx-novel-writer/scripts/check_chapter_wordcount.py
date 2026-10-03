# -*- coding: utf-8 -*-
"""字数闸门：单章字数须在 [min, max] 内；可选总字数 [total-min, total-max]。
exit=0 通过 / 1 越界 / 2 参数或读取错误。
用法:
  python check_chapter_wordcount.py --file ch.txt --min 1800 --max 2200
  python check_chapter_wordcount.py --file c1.txt c2.txt ... --min 1000 --max 1400 --total-min 8000 --total-max 10000
"""
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import read_text, count_words


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", nargs="+", required=True, help="章节文件（可多个）")
    ap.add_argument("--min", type=int, required=True)
    ap.add_argument("--max", type=int, required=True)
    ap.add_argument("--total-min", type=int, default=None)
    ap.add_argument("--total-max", type=int, default=None)
    args = ap.parse_args()
    try:
        total = 0
        bad = False
        for fp in args.file:
            n = count_words(read_text(fp))
            total += n
            if not (args.min <= n <= args.max):
                print(f"  [越界] {os.path.basename(fp)} 字数 {n} 不在 [{args.min},{args.max}]")
                bad = True
        if bad:
            print("EXIT=1 字数越界")
            return 1
        if args.total_min is not None and not (args.total_min <= total <= args.total_max):
            print(f"  [越界] 总字数 {total} 不在 [{args.total_min},{args.total_max}]")
            return 1
        print(f"EXIT=0 字数校验通过（总 {total}）")
        return 0
    except Exception as e:  # noqa
        print(f"EXIT=2 错误: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
