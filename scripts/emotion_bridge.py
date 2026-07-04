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

from typing import Dict
import hashlib
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


def batch_analyze_daily_file(daily_path: Path) -> Dict:
    """
    批量分析当日 daily .md 中的对话情绪。
    读取 daily 文件中的对话行，逐条检测情绪并汇总统计。
    返回统计结果。
    """
    if not daily_path.exists():
        return {"status": "skip", "reason": "no daily file"}

    detector = EmotionDetector()
    calculator = EmotionWeightCalculator()
    
    # 读取 daily 文件中的对话行（跳过标题行、系统行）
    conversation_lines = []
    with open(daily_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # 提取用户原始消息（去掉行首的 - [HH:MM] 前缀）
            # 格式: - [HH:MM] 🧠 content 或 - [HH:MM] 💾 content
            clean = re.sub(r'^- \[\d{2}:\d{2}\]\s*[^\s]*\s*', '', line)
            if clean and len(clean) > 5:
                conversation_lines.append(clean)
    
    if not conversation_lines:
        return {"status": "skip", "reason": "no conversation lines"}
    
    # 批量检测
    emotions_found = {}
    total_weight = 0.0
    total_intensity = 0.0
    count = 0
    
    jsonl_path = Path.home() / ".openclaw" / "workspace" / ".learnings" / "emotion_memories.jsonl"
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    now_str = datetime.now(timezone.utc).strftime("%H:%M")
    
    with open(jsonl_path, "a", encoding="utf-8") as jsonl_f:
        for msg in conversation_lines:
            emotion = detector.detect(msg)
            weight = calculator.calculate(emotion)
            priority = calculator.get_memory_priority(emotion)
            
            et = emotion.type.value
            emotions_found[et] = emotions_found.get(et, 0) + 1
            total_weight += weight
            total_intensity += emotion.intensity
            count += 1
            
            record = {
                "id": hashlib.md5(f"{msg}{now_str}".encode()).hexdigest()[:12],
                "content": msg[:200],
                "emotion": emotion.to_dict(),
                "weight": weight,
                "priority": priority,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            jsonl_f.write(json.dumps(record, ensure_ascii=False) + "\n")
    
    # 汇总
    dominant = max(emotions_found, key=emotions_found.get) if emotions_found else "neutral"
    avg_w = round(total_weight / count, 2) if count else 0
    result = {
        "status": "ok",
        "total_lines": count,
        "dominant_emotion": dominant,
        "emotion_distribution": emotions_found,
        "avg_weight": avg_w,
        "avg_intensity": round(total_intensity / count, 2) if count else 0,
        "daily_file": str(daily_path),
    }
    
    # 追加一行到 daily .md 尾部
    emoji = get_emoji(EmotionType[dominant.upper()] if dominant.upper() in EmotionType.__members__ else EmotionType.NEUTRAL)
    daily_line = f"\n### 📊 今日情绪汇总\n- 总对话条数: {count}\n- 主导情绪: {emoji} {dominant} ({round(emotions_found[dominant]/count*100, 1)}%)\n- 平均权重: {avg_w}\n"
    try:
        append_to_daily(daily_path, daily_line)
    except Exception:
        pass
    
    return result


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
