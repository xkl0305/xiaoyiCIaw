# -*- coding: utf-8 -*-
"""Shared helpers for the wacx novel/short writer mechanical gates.

Word counting follows the user's WPS-style rule:
  count = (CJK chars + CJK punctuation) + (English word tokens, each = 1)
ASCII punctuation is NOT counted.
"""
import os
import re
import sys
import unicodedata


def read_text(path):
    if path in (None, "-"):
        return sys.stdin.read()
    with open(path, encoding="utf-8") as f:
        return f.read()


def count_words(text):
    """WPS-style: CJK chars + CJK punctuation + English words(each=1)."""
    en = len(re.findall(r"[A-Za-z0-9]+", text))
    cjk = 0
    for ch in text:
        if ch.isspace():
            continue
        if ord(ch) < 128:
            continue  # ASCII punctuation ignored; letters/digits counted via en tokens
        cjk += 1
    return cjk + en


# ---- AI-flavor banned words (verbatim from the skill's L1 list) ----
BANNED_WORDS = [
    "仿佛", "犹如", "宛若", "如同", "一丝", "一抹", "些许", "微微", "轻轻", "淡淡",
    "缓缓", "不禁", "深吸一口气", "眼中闪过", "嘴角勾起", "眉头微皱", "心中一动",
    "心头一震", "不由得", "不容置疑", "不易察觉", "显而易见",
    "不由自主", "情不自禁",
]

# ---- AI-flavor banned structural patterns ----
BANNED_STRUCT = [
    r"不是.{0,15}而是",
    r"，带着.{0,8}(力量|气息|笑意|意味|温柔)",
    r"声音不大，却带着",
    r"心中涌起一股",
    r"眼中闪过一丝",
    r"嘴角勾起一抹",
    r"[他她]知道(这|那|自己)",
]

# Quotes that are NOT the allowed Chinese double quotes “ ” (U+201C/U+201D)
FORBIDDEN_QUOTES = set(['"', "'", "\u2018", "\u2019", "\u300c", "\u300d", "\u300e", "\u300f"])


def count_dashes(text):
    return sum(1 for ch in text if ch in "\u2014\u2013")  # em-dash + en-dash


def find_banned_words(text):
    hits = []
    for w in BANNED_WORDS:
        for m in re.finditer(re.escape(w), text):
            hits.append((w, m.start()))
    return hits


def find_banned_struct(text):
    hits = []
    for p in BANNED_STRUCT:
        for m in re.finditer(p, text):
            hits.append((m.group(0), m.start()))
    return hits


def find_forbidden_quotes(text):
    hits = []
    for i, ch in enumerate(text):
        if ch in FORBIDDEN_QUOTES:
            hits.append((ch, i))
    return hits


def report(issues, label, block=True):
    if issues:
        tag = "BLOCK" if block else "WARN"
        print(f"[{tag}:{label}] {len(issues)} 处:")
        for item in issues[:20]:
            snippet = item[0] if isinstance(item[0], str) else repr(item[0])
            print(f"  - {snippet}")
    else:
        print(f"[OK:{label}] 0 处")
