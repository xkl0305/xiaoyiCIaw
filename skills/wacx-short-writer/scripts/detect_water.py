# -*- coding: utf-8 -*-
"""去水感机械半检：>200字长段且无对话/无生理反应/纯静态铺陈(或零星动作仍大量铺陈)>=max-water段 -> exit=1。
exit=0 通过 / 1 阻断 / 2 错误。
用法: python detect_water.py --file ch.txt [--max-water 3]
"""
import os
import sys
import argparse
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import read_text, count_words

QUOTE = re.compile(r"[\u201c\u201d]")
# Multi-char bodily-sensation phrases only — single chars like 青/红/白/凉/汗
# are far too common in scenery ("青山""红日""白发""凉风") and cause water to
# be wrongly excluded. Require a real physiological context to count.
PHYSIO = re.compile(
    r"(心跳|出汗|盗汗|喉结|喉咙|哽咽|呼吸|窒息|渗血|流血|颤抖|发抖|流泪|落泪|"
    r"泛红|涨红|惨白|发青|发凉|冰凉|滚烫|发烫|刺痛|疼痛|酸麻|麻木|寒战|冷汗)"
)
ACTION_VB = re.compile(
    r"(走|跑|跳|站|坐|躺|拿|抓|推|拉|打|踢|踩|扑|冲|挡|挥|甩|抬|低|转|看|盯|听|闻|摸|吃|喝|说|笑|哭|喊|叫|扔|摔|撞|咬|掐|捏|扯|撕|劈|砍|刺)"
)


def is_water(para):
    n = count_words(para)
    if n <= 200:
        return False
    if QUOTE.search(para):
        return False  # 有对话
    if PHYSIO.search(para):
        return False  # 有生理反应
    if len(ACTION_VB.findall(para)) >= 2:
        return False  # 有真实动作
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--max-water", type=int, default=3)
    args = ap.parse_args()
    try:
        text = read_text(args.file)
        paras = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
        water = [p for p in paras if is_water(p)]
        if len(water) >= args.max_water:
            print(f"发现 {len(water)} 段水段(>200字无对话/无生理反应/无动作) >= {args.max_water}：")
            for w in water[:5]:
                print(f"  - {w[:30]}…")
            print("EXIT=1 水段超阈值")
            return 1
        print(f"EXIT=0 水段 {len(water)} < {args.max_water}")
        return 0
    except Exception as e:  # noqa
        print(f"EXIT=2 错误: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
