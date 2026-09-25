#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""memory_dump 候选恢复检测：对比转储中的关键正式区块，找出"正式文件缺失/可能待恢复"的候选。"""
import os, re, glob

WS = "/home/sandbox/.openclaw/workspace"
dump_file = os.path.join(WS, "memory_dump", "MEMORY-history-20260922.md")
formal_files = ["MEMORY.md", "TOOLS.md", "USER.md", "SOUL.md", "IDENTITY.md"]

# 关键正式区块指纹（标题关键词 + 文件归属）
# block: (名称, 识别关键词, 应归属文件)
KEY_BLOCKS = [
    ("琪琪人格手册(六章合并版)", "# 琪琪人格手册", "MEMORY.md"),
    ("主人锚/永久身份", "主人锚", "MEMORY.md"),
    ("记忆引擎切换记录", "记忆引擎切换记录", "MEMORY.md"),
    ("系统全览输出标准格式", "系统全览输出标准格式", "TOOLS.md"),
    ("MEMORY健康体检清单", "MEMORY.md)健康体检", "TOOLS.md"),
    ("message投递校验", "message 投递校验", "TOOLS.md"),
    ("长消息截断规避纪律", "长消息截断规避纪律", "TOOLS.md"),
    ("记忆引擎状态", "记忆引擎状态", "MEMORY.md"),
    ("用户偏好-技能不归档", "技能不搞自动归档", "MEMORY.md"),
    ("人格变更日志", "人格变更日志", "MEMORY.md"),
]

def has(formal, key):
    p = os.path.join(WS, formal)
    if not os.path.exists(p):
        return False, "文件不存在"
    txt = open(p, encoding="utf-8").read()
    return key in txt, "存在" if key in txt else "缺失"

dump_txt = open(dump_file, encoding="utf-8").read()

print("=== memory_dump 关键正式区块·候选恢复检测 ===\n")
print(f"{'区块':<22}{'转储':<6}{'正式文件状态':<14}{'结论'}")
print("-" * 60)
for name, key, formal in KEY_BLOCKS:
    in_dump = key in dump_txt
    in_formal, stat = has(formal, key)
    if in_dump and not in_formal:
        verdict = "⚠️ 候选待恢复"
    elif in_dump and in_formal:
        verdict = "已存在（无需恢复）"
    else:
        verdict = "转储无此区块"
    print(f"{name:<22}{'✓' if in_dump else '-':<6}{stat:<14}{verdict}")
