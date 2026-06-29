"""Crusheart Agent OS - Skill Engine shared module (v7.0 split)
"""
"""
Crusheart Agent OS — 技能引擎三合一
  1. SkillScanner  — 技能扫描/分类/统计（来自 scan_skills.py + SkillRouter.scan()）
  2. SkillRouter   — 任务分析/路由（原 skill_router.py）
  3. SkillInvoker  — 技能自动调用（原名 SkillAutoInvoker）
"""

import os, re, json, math, hashlib, time, sys, traceback
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from collections import Counter, defaultdict
import logging

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
SKILLS_DIR = os.path.join(WORKSPACE, "skills")
SKILL_INDEX_FILE = os.path.join(WORKSPACE, ".skill_auto_index.json")

# ── UnifiedScorer 统一评分通道 ──
try:
    from core.engines.quality.unified_scorer import get_scorer as _se_get_scorer
except ImportError:
    _se_get_scorer = None


def _record_skill_invocation(skill_name: str, status: str, task_text: str):
    """将技能调用结果记录到 UnifiedScorer"""
    if _se_get_scorer is None:
        return
    try:
        scorer = _se_get_scorer()
        score_map = {"ok": 1.0, "agent_tool": 0.8, "agent": 0.5,
                     "error": 0.0, "timeout": 0.0, "unknown": 0.3}
        score = score_map.get(status, 0.5)
        scorer.record(
            source="skill_engine",
            dimension="exec_quality",
            score=score,
            context=f"SkillInvoker: {skill_name} -> {status}",
            tags=["skill_engine", skill_name, status],
            metadata={"skill_name": skill_name, "task": task_text[:100], "status": status},
        )
    except Exception:
        pass


def now_str():
    return datetime.now(BEIJING_TZ).isoformat()

# ════════════════════════════════════════════════════════════════
# 引擎1: SkillScanner — 扫描/分类/统计
# ════════════════════════════════════════════════════════════════
CATEGORY_KEYWORDS = {
    "搜索/查询": ["搜索", "查询", "查", "搜", "联网"],
    "天气": ["天气", "气象", "温度", "下雨"],
    "创作/写作": ["写作", "写", "创作", "文案", "文章", "故事"],
    "学术/论文": ["论文", "学术", "研究", "thesis", "research", "paper", "期刊", "文献", "综述"],
    "图像/视觉": ["图像", "图片", "照片", "作图"],
    "视频": ["视频", "剪辑", "录制", "vlog"],
    "音频/语音": ["音频", "语音", "音乐", "播客", "TTS"],
    "翻译": ["翻译", "英文", "日语"],
    "金融/股票": ["股票", "基金", "行情", "金融", "投资"],
    "文档/办公": ["文档", "Word", "Excel", "PPT", "PDF"],
    "开发/技术": ["编程", "代码", "开发", "部署", "Git", "Python"],
    "教育/学习": ["学习", "教育", "教学", "课程", "学生"],
    "出行/旅游": ["出行", "路线", "导航", "机票", "打车"],
    "邮件/通信": ["邮件", "发送", "Email"],
    "生活/工具": ["外卖", "优惠", "团购", "健身"],
    "系统/配置": ["配置", "设置", "安装", "更新", "插件", "技能"],
}

