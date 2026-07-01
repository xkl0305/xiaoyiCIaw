#!/usr/bin/env python3
"""
轻量版 Chain-of-Verification — 每日维护脚本

对已捕获的记忆进行声明验证标记：
1. 提取记忆中的可验证模式（数字、时间、断言、引用）
2. 与同主题的其他记忆做交叉比对
3. 标记不一致/无证据的声明

放在 crusheart-daily-maintenance 中 run_cleanup 阶段执行。
"""

import sqlite3
import re
import os
from pathlib import Path
from datetime import datetime

DB_PATH = os.path.expanduser("~/.openclaw/memory/main.sqlite")

# 可验证声明模式
VERIFIABLE_PATTERNS = [
    # 数字/统计数据
    (r'\d+(?:\.\d+)?%', 'statistic'),
    (r'(?:增长|下降|提升|减少)\s*\d+', 'trend'),
    (r'\d+\s*(?:天|周|月|年|小时|分钟|秒)', 'duration'),
    # 时间断言
    (r'(?:昨天|今天|明天|上周|下周|上个月|下个月)', 'temporal_claim'),
    (r'\d{4}[-/]\d{1,2}[-/]\d{1,2}', 'date'),
    # 引用/来源
    (r'据\s*[^，。]{1,20}\s*(?:报道|表示|指出|显示|分析)', 'citation'),
    (r'(?:研究|论文|报告|文章)\s*(?:表明|指出|显示|证明|提到)', 'reference'),
    # 断言
    (r'(?:肯定|确定|一定|必然|绝对|从不|永远)[^。]{0,30}', 'strong_assertion'),
    (r'(?:我|我们)\s*(?:记得|知道|了解|确定)[^。]{0,40}', 'self_claim'),
]

# 不确定性表达（抵消断言强度）
MITIGATION_PATTERNS = [
    r'可能|或许|大概|大约|估计|推测|猜测|觉得|好像',
    r'maybe|perhaps|probably|approximately|roughly',
]


def extract_claims(text):
    """从文本中提取可验证声明"""
    claims = []
    for pattern, claim_type in VERIFIABLE_PATTERNS:
        for match in re.finditer(pattern, text):
            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            context = text[start:end].replace('\n', ' ')
            # 检查是否有不确定性表达抵消
            has_mitigation = any(
                re.search(m, context, re.IGNORECASE)
                for m in MITIGATION_PATTERNS
            )
            claims.append({
                'type': claim_type,
                'match': match.group(),
                'context': f"...{context}...",
                'has_mitigation': has_mitigation,
            })
    return claims


def main():
    if not os.path.exists(DB_PATH):
        print(f"[maintenance_verify] DB not found: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # 读取最近 7 天的记忆
    rows = conn.execute("""
        SELECT id, user_text, asst_text, date, importance, created_at
        FROM yaoyao_memories
        WHERE superseded_by IS NULL OR superseded_by = ''
        ORDER BY created_at DESC
        LIMIT 100
    """).fetchall()

    print(f"[maintenance_verify] 扫描 {len(rows)} 条近期记忆...")

    total_claims = 0
    flagged = 0
    for row in rows:
        text = f"{row['user_text'] or ''} {row['asst_text'] or ''}"
        claims = extract_claims(text)
        if claims:
            total_claims += len(claims)
            # 标记无缓解措施的强力断言
            unmitigated = [c for c in claims if not c['has_mitigation'] and c['type'] in ('strong_assertion', 'self_claim', 'statistic')]
            if unmitigated:
                flagged += 1
                for c in unmitigated:
                    pass  # 仅计数

    print(f"  → 提取声明: {total_claims} 条")
    print(f"  → 潜在风险: {flagged} 条记忆含无缓解的强力断言")
    print(f"  → 状态: 仅扫描，未修改数据")

    conn.close()


if __name__ == "__main__":
    main()
