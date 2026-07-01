#!/usr/bin/env python3
"""
Smart Forgetter — 每日维护脚本

基于重要性评分自动归档/标记低价值记忆。
运行在 crusheart-daily-maintenance 流程中。

工作原理：
1. 从 yaoyao_memories 表读取所有记忆
2. 计算重要性分数（长度 * 0.3 + 访问次数 * 0.4 + 时效性 * 0.3）
3. 低分 → 标记 superseded_by='auto_archive'
4. 低频访问 + 超旧 → 标记 superseded_by='auto_delete'

安全：
- 默认 dry_run=true，仅输出建议
- 传递 --execute 才真正执行
"""

import sqlite3
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = os.path.expanduser("~/.openclaw/memory/main.sqlite")
DRY_RUN = "--execute" not in sys.argv


def score_memory(row):
    """计算单条记忆的重要性分数"""
    memory_id, date_str, user_text, asst_text, access_count, tier, importance = row[:7]
    
    # 内容长度分 (0~0.3)
    text_len = len((user_text or "") + (asst_text or ""))
    length_score = min(text_len / 500, 1.0) * 0.3
    
    # 访问频次分 (0~0.4)
    # access_count 可能为 None
    acc = access_count or 0
    access_score = min(acc / 10, 1.0) * 0.4
    
    # 时效性分 (0~0.3)
    # 最近 7 天 = 高分，超过 90 天 = 低分
    age_score = 0.3
    if date_str:
        try:
            created = datetime.fromisoformat(date_str)
            age_days = (datetime.now(timezone.utc) - created.replace(tzinfo=timezone.utc)).days
            if age_days > 90:
                age_score = max(0.05, 0.3 * (1 - age_days / 365))
            elif age_days <= 7:
                age_score = 0.3
            else:
                age_score = 0.3 * (1 - (age_days - 7) / 83)
        except:
            pass
    
    return length_score + access_score + age_score


def main():
    if not os.path.exists(DB_PATH):
        print(f"[smart_forgetter] DB not found: {DB_PATH}")
        return
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # 读取活跃记忆（跳过已归档/已删除）
    rows = conn.execute("""
        SELECT id, date, user_text, asst_text, access_count, tier, importance, created_at
        FROM yaoyao_memories
        WHERE superseded_by IS NULL OR superseded_by = ''
    """).fetchall()
    
    print(f"[smart_forgetter] 扫描 {len(rows)} 条活跃记忆...")
    
    archive_candidates = []
    delete_candidates = []
    
    for row in rows:
        score = score_memory(row)
        memory_id = row["id"]
        
        if score < 0.15:
            delete_candidates.append((memory_id, score))
        elif score < 0.30:
            archive_candidates.append((memory_id, score))
    
    archive_candidates.sort(key=lambda x: x[1])
    delete_candidates.sort(key=lambda x: x[1])
    
    print(f"  → 建议归档: {len(archive_candidates)} 条 (score < 0.30)")
    print(f"  → 建议删除: {len(delete_candidates)} 条 (score < 0.15)")
    
    if DRY_RUN:
        print(f"\n[dry-run] 未做任何修改。传递 --execute 执行。")
    else:
        # 执行归档
        for mid, sc in archive_candidates:
            conn.execute("UPDATE yaoyao_memories SET superseded_by = 'auto_archive' WHERE id = ?", (mid,))
        for mid, sc in delete_candidates:
            conn.execute("UPDATE yaoyao_memories SET superseded_by = 'auto_delete' WHERE id = ?", (mid,))
        conn.commit()
        
        kept = len(rows) - len(archive_candidates) - len(delete_candidates)
        print(f"\n[smart_forgetter] ✅ 已执行:")
        print(f"    保留: {kept} 条")
        print(f"    归档: {len(archive_candidates)} 条")
        print(f"    删除: {len(delete_candidates)} 条")
    
    conn.close()


if __name__ == "__main__":
    main()
