#!/usr/bin/env python3
"""
情绪桥接脚本 — 方案C：在 agent_end 后调 emotion_memory。
每次对话结束后分析用户情绪，将情绪标签追加到当天 daily .md，
并持久化到 .learnings/emotion_memories.jsonl。

用法:
  python3 scripts/emotion_bridge.py "用户消息内容"

输出到 daily .md (追加):
  - [HH:MM] 😊 emotion_type: intensity(权重)
  - [HH:MM] 😐 neutral: 0.30

依赖: scripts/galaxyos_modules/emotion_memory.py
"""

import sys
import os
import json
import re
from datetime import datetime, timezone
from pathlib import Path

# 确保能找到 emotion_memory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'galaxyos_modules'))

from emotion_memory import (
    EmotionDetector, EmotionWeightCalculator, EmotionType
)

# 情绪→emoji 映射
EMOJI_MAP = {
    EmotionType.JOY: "😊",
    EmotionType.EXCITEMENT: "🤩",
    EmotionType.ANGER: "😡",
    EmotionType.ANXIETY: "😰",
    EmotionType.SADNESS: "😢",
    EmotionType.FRUSTRATION: "😤",
    EmotionType.CURIOSITY: "🤔",
    EmotionType.NEUTRAL: "😐",
}


def get_emoji(emotion_type: EmotionType) -> str:
    return EMOJI_MAP.get(emotion_type, "❓")


def append_to_daily(daily_path: Path, line: str):
    """追加一行到 daily .md"""
    with open(daily_path, "a", encoding="utf-8") as f:
        f.write(line)


def get_daily_path() -> Path:
    """获取今日的 daily .md 路径（与 yaoyao-memory 保持一致）"""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return Path.home() / ".openclaw" / "workspace" / "memory" / f"{today}.md"


def main():
    if len(sys.argv) < 2:
        print("用法: python3 scripts/emotion_bridge.py \"用户消息\"", file=sys.stderr)
        sys.exit(1)

    user_message = sys.argv[1]
    if not user_message.strip():
        print("⚠️  empty message, skip", file=sys.stderr)
        sys.exit(0)

    # 检测情绪
    detector = EmotionDetector()
    calculator = EmotionWeightCalculator()
    emotion = detector.detect(user_message)
    weight = calculator.calculate(emotion)
    priority = calculator.get_memory_priority(emotion)

    # 构建输出
    emoji = get_emoji(emotion.type)
    now_str = datetime.now(timezone.utc).strftime("%H:%M")
    
    # 1. 持久化到 emotion_memories.jsonl
    emotion_record = {
        "id": __import__('hashlib').md5(f"{user_message}{now_str}".encode()).hexdigest()[:12],
        "content": user_message[:200],
        "emotion": emotion.to_dict(),
        "weight": weight,
        "priority": priority,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    learnings_path = Path.home() / ".openclaw" / "workspace" / ".learnings"
    learnings_path.mkdir(parents=True, exist_ok=True)
    jsonl_path = learnings_path / "emotion_memories.jsonl"
    with open(jsonl_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(emotion_record, ensure_ascii=False) + "\n")

    # 2. 追加到 daily .md
    daily_path = get_daily_path()
    # 截取短消息用于展示
    short_msg = user_message[:60].replace("\n", " ").strip()
    daily_line = f"- [{now_str}] {emoji} {emotion.type.value}({weight:.2f}) {short_msg}\n"
    
    try:
        append_to_daily(daily_path, daily_line)
    except Exception as e:
        print(f"⚠️  write daily failed: {e}", file=sys.stderr)

    # 3. stdout 输出供调用方使用
    result = {
        "emotion": emotion.type.value,
        "intensity": emotion.intensity,
        "weight": weight,
        "priority": priority,
        "emoji": emoji,
        "daily_line": daily_line.strip(),
    }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
