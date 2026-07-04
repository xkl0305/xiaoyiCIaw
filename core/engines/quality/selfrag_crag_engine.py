"""
SelfRAGCragEngine — Self-RAG + CRAG 检索增强生成引擎
功能：注入真实 LLM generator，在输出验证/每日维护中运行 RAG 质量校验
接线：quality 管线 → 运行时可选 query() 调用 + 每日维护批处理校验
"""

import os
import sys
import json
import logging
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("selfrag_crag_engine")

_SCRIPTS_DIR = os.path.join(
    os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace"),
    "scripts", "galaxyos_modules"
)
sys.path.insert(0, _SCRIPTS_DIR)

_ENGINE = None
BEIJING_TZ = timezone(timedelta(hours=8))


def _make_llm_generator() -> Callable:
    """创建绑定真实 LLM 的 generator 函数"""
    from core.llm_gateway.llm_gateway import LLMGateway
    gateway = LLMGateway(timeout=60)

    def _generator(query: str, context: str) -> str:
        if context:
            messages = [
                {"role": "system", "content": "你是一个基于检索增强生成的AI助手。请基于提供的上下文信息回答问题。如果上下文不足以回答问题，请明确指出。"},
                {"role": "user", "content": f"上下文：\n{context}\n\n问题：{query}"}
            ]
        else:
            messages = [
                {"role": "system", "content": "你是一个AI助手。"},
                {"role": "user", "content": query}
            ]
        result = gateway.call(messages, query=query, temperature=0.3)
        return result.content if result.success else f"LLM调用失败: {result.error}"
    
    return _generator


def _make_retriever(top_k: int = 5) -> Callable:
    """创建绑定记忆 DB 的 retriever 函数"""
    import sqlite3

    def _retriever(query: str) -> List[str]:
        results = []
        db_path = os.path.expanduser("~/.openclaw/memory/main.sqlite")
        if not os.path.exists(db_path):
            return [f"（没有可用的记忆数据库）"]
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            # 从 yaoyao_memories 检索（用 LIKE 做简单关键词匹配）
            terms = [t for t in query.replace("?","").replace("？","").split() if len(t) > 1]
            if terms:
                like_clauses = " OR ".join(f"content LIKE '%{t}%'" for t in terms)
                cur.execute(f"SELECT content FROM yaoyao_memories WHERE {like_clauses} ORDER BY created_at DESC LIMIT {top_k}")
                for row in cur.fetchall():
                    results.append(row["content"][:500])
            # 也从 chunks 检索
            if not results:
                cur.execute("SELECT text FROM chunks ORDER BY updated_at DESC LIMIT 10")
                for row in cur.fetchall():
                    results.append(row["text"][:500])
            conn.close()
        except Exception as e:
            logger.warning(f"retriever failed: {e}")
            results.append(f"（检索出错: {str(e)[:80]}）")
        return results[:top_k] if results else [f"（未找到关于 '{query}' 的相关记忆）"]
    
    return _retriever


class SelfRAGCragEngine:
    """Self-RAG + CRAG 引擎包装器"""

    def __init__(self):
        from self_rag import SelfRAG, create_self_rag
        from crag import CRAG, create_crag

        self._generator = _make_llm_generator()
        self._retriever = _make_retriever()

        self._self_rag = create_self_rag(
            retriever=self._retriever,
            generator=self._generator,
        )
        self._crag = create_crag(
            retriever=self._retriever,
            generator=self._generator,
        )

        global _ENGINE
        _ENGINE = self
        logger.info("SelfRAGCragEngine 已初始化 (generator=LLMGateway, retriever=memory_db)")

    def query_with_selfrag(self, query: str, context: Optional[str] = None) -> dict:
        """使用 Self-RAG 处理查询（含检索决策 + 来源验证 + 可靠性评估）"""
        result = self._self_rag.process(query, context)
        return {
            "answer": result.answer,
            "steps": len(result.steps),
            "retrieved": len(result.retrieved_sources) if hasattr(result, 'retrieved_sources') else 0,
            "is_reliable": result.is_reliable if hasattr(result, 'is_reliable') else True,
            "confidence": result.confidence if hasattr(result, 'confidence') else 1.0,
            "sources": result.retrieved_sources if hasattr(result, 'retrieved_sources') else [],
        }

    def query_with_crag(self, query: str, context: Optional[str] = None) -> dict:
        """使用 CRAG 处理查询（含纠错检索）"""
        result = self._crag.process(query, context)
        return {
            "answer": result.answer,
            "steps": len(result.steps),
            "retrieved": len(result.retrieved_sources) if hasattr(result, 'retrieved_sources') else 0,
            "is_reliable": result.is_reliable if hasattr(result, 'is_reliable') else True,
            "confidence": result.confidence if hasattr(result, 'confidence') else 1.0,
            "sources": result.retrieved_sources if hasattr(result, 'retrieved_sources') else [],
        }

    def _get_today_outputs(self) -> List[Dict]:
        """获取今日 agent 输出用于批处理验证"""
        outputs = []
        db_path = os.path.expanduser("~/.openclaw/memory/main.sqlite")
        if not os.path.exists(db_path):
            return outputs
        try:
            import sqlite3
            today_start = datetime.now(BEIJING_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
            today_ts = int(today_start.timestamp() * 1000)
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            # 取今日内容较长的记录作为候选
            cur.execute(
                "SELECT content, source, created_at FROM yaoyao_memories "
                "WHERE created_at >= ? AND LENGTH(content) > 50 "
                "ORDER BY created_at ASC LIMIT 30",
                (today_ts,)
            )
            for row in cur.fetchall():
                outputs.append({
                    "content": row["content"],
                    "source": row["source"],
                    "timestamp": row["created_at"] / 1000,
                })
            conn.close()
        except Exception as e:
            logger.warning(f"_get_today_outputs failed: {e}")
        return outputs

    def batch_validate(self) -> dict:
        """
        每日维护用：批量验证今日输出的可靠性
        对每条较长的输出，用 Self-RAG 的 IsSUP/IsUSE 判断内容可靠性
        """
        outputs = self._get_today_outputs()
        if not outputs:
            return {"status": "skip", "reason": "no outputs to validate", "total": 0}

        validated = 0
        issues = 0
        for item in outputs:
            try:
                result = self._self_rag.process(item["content"])
                if hasattr(result, 'is_reliable') and not result.is_reliable:
                    issues += 1
                validated += 1
            except Exception as e:
                logger.warning(f"validate failed for entry: {e}")
                issues += 1

        return {
            "status": "ok",
            "total": len(outputs),
            "validated": validated,
            "issues_found": issues,
            "reliability_rate": round((validated - issues) / max(validated, 1) * 100, 1),
        }

    def status(self) -> dict:
        return {
            "name": "selfrag_crag",
            "version": "1.0.0",
            "state": "initialized" if _ENGINE else "pending",
            "generator": "LLMGateway (real LLM)",
            "retriever": "memory_db (yaoyao_memories + chunks)",
            "wraps": ["SelfRAG", "CRAG"],
        }


def init() -> SelfRAGCragEngine:
    """engines.json init_fn 入口"""
    return SelfRAGCragEngine()
