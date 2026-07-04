"""
LfmSkillBankEngine — LFM 技能库引擎 wrapper
功能：包装 galaxyos_modules.lfm_skill_bank 为 crusheart 引擎
接线：每日维护管线，从记忆轨迹自动发现/升级/维护技能
"""

import os
import sys
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("lfm_skill_bank_engine")

_SCRIPTS_DIR = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
sys.path.insert(0, os.path.join(_SCRIPTS_DIR, "scripts", "galaxyos_modules"))

_ENGINE = None

BEIJING_TZ = timezone(timedelta(hours=8))


class LfmSkillBankEngine:
    """LFM 技能库引擎包装器"""

    def __init__(self, workspace: Optional[str] = None):
        self._workspace = workspace or _SCRIPTS_DIR
        global _ENGINE
        _ENGINE = self
        logger.info(f"LfmSkillBankEngine 已初始化 (workspace={self._workspace})")

    def run_cycle(self, workspace: Optional[str] = None) -> dict:
        """运行一轮完整的 Skill Bank 周期"""
        from lfm_skill_bank import run_skill_bank_cycle
        return run_skill_bank_cycle(workspace or self._workspace)

    def feed_memories(self, memories: List[Dict], workspace: Optional[str] = None) -> dict:
        """从记忆记录批量喂入 Skill Bank"""
        if not memories:
            return {"ingested": 0, "discovered": 0, "promoted": 0, "status": "skipped"}
        from lfm_skill_bank import feed_memory_to_skill_bank
        return feed_memory_to_skill_bank(memories, workspace or self._workspace)

    def daily_feeder(self) -> dict:
        """
        每日维护专用：从今日对话记录提取记忆 → 喂养技能库。
        读取 yaoyao 记忆 DB 中今日的会话记录。
        """
        try:
            import sqlite3
            db_path = os.path.expanduser("~/.openclaw/memory/main.sqlite")
            if not os.path.exists(db_path):
                return {"status": "skip", "reason": "no memory db"}

            today_start = datetime.now(BEIJING_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
            today_ts = int(today_start.timestamp() * 1000)

            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 从 yaoyao_memories 拉取今日记忆
            memories = []
            try:
                cursor.execute(
                    "SELECT content, created_at, updated_at, source FROM yaoyao_memories WHERE created_at >= ? ORDER BY created_at ASC LIMIT 500",
                    (today_ts,)
                )
                for row in cursor.fetchall():
                    mem = {
                        "content": row["content"] or "",
                        "source": row["source"] or "conversation",
                        "timestamp": row["created_at"] / 1000,
                        "created_at": row["created_at"] / 1000,
                        "metadata": {},
                    }
                    memories.append(mem)
            except Exception as e:
                logger.warning(f"yaoyao_memories query failed: {e}")

            # 也查 chunks 表做补充
            try:
                cursor.execute(
                    "SELECT text, source, updated_at FROM chunks WHERE updated_at >= ? ORDER BY updated_at ASC LIMIT 200",
                    (today_ts,)
                )
                for row in cursor.fetchall():
                    mem = {
                        "content": row["text"] or "",
                        "source": row["source"] or "chunk",
                        "timestamp": row["updated_at"] / 1000,
                        "created_at": row["updated_at"] / 1000,
                        "metadata": {},
                    }
                    memories.append(mem)
            except Exception as e:
                logger.warning(f"chunks query failed: {e}")

            conn.close()

            if not memories:
                return {"status": "skip", "reason": "no today memories"}

            result = self.feed_memories(memories)
            result["total_memories"] = len(memories)
            result["status"] = "ok"
            return result

        except Exception as e:
            logger.error(f"daily_feeder failed: {e}", exc_info=True)
            return {"status": "error", "error": str(e)[:200]}

    def recommend(self, query: str, top_k: int = 5) -> list:
        """推荐与 query 相关的技能"""
        from lfm_skill_bank import get_skill_bank, LfmSkillBankConfig
        config = LfmSkillBankConfig(workspace=self._workspace)
        bank = get_skill_bank(config)
        return bank.recommend(query, top_k)

    def status(self) -> dict:
        from lfm_skill_bank import get_skill_bank, LfmSkillBankConfig
        config = LfmSkillBankConfig(workspace=self._workspace)
        bank = get_skill_bank(config)
        return {
            "name": "lfm_skill_bank",
            "version": "1.0.0",
            "state": "initialized" if _ENGINE else "pending",
            "n_active_skills": bank.n_active_skills,
            "n_proto_skills": bank.n_proto_skills,
        }


def init(workspace: Optional[str] = None) -> LfmSkillBankEngine:
    """engines.json init_fn 入口"""
    return LfmSkillBankEngine(workspace)
