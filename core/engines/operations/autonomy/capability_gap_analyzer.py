"""CapabilityGapAnalyzer (v7.0 split)
"""
import os, json, logging
from typing import Dict, List, Optional, Any
from enum import Enum

class CapabilityGapAnalyzer:
    """能力差距分析 — 推断目标所需能力并对比可用能力"""

    KNOWN_CAPABILITIES = {
        "web_search", "file_read", "document_search", "code_review",
        "task_graph", "risk_judge", "result_verify", "memory_write",
        "text_reasoning", "model_routing", "image_gen", "video_gen",
    }

    CAPABILITY_RULES = [
        (["最新", "现在", "价格", "政策", "规则", "查一下", "搜索"], "web_search"),
        (["文件", "文档", "压缩包", "pdf", "docx", "zip"], "file_read"),
        (["代码", "报错", "pytest", "接口", "模块", "bug"], "code_review"),
        (["图片", "头像", "海报", "logo", "生成图片"], "image_gen"),
        (["视频", "sora", "生成视频"], "video_gen"),
        (["发邮件", "发送", "外部", "客户"], "external_action"),
        (["mcp", "connector", "api"], "connector_management"),
    ]

    def infer_required(self, goal: str) -> List[str]:
        required = ["text_reasoning", "task_graph", "risk_judge"]
        g = goal.lower()
        for keywords, cap in self.CAPABILITY_RULES:
            if any(kw in g for kw in keywords) and cap not in required:
                required.append(cap)
        return sorted(set(required))

    def analyze(self, goal: str) -> CapabilityGap:
        required = self.infer_required(goal)
        missing = [x for x in required if x not in self.KNOWN_CAPABILITIES]
        if not missing:
            status = CapabilityGapStatus.NO_GAP
            explanation = "所有能力本地可用"
        elif all(x in ["external_action", "connector_management"] for x in missing):
            status = CapabilityGapStatus.NEED_HUMAN
            explanation = "需要人工授权或连接器设置"
        else:
            status = CapabilityGapStatus.NEED_EXTENSION
            explanation = f"缺少能力: {', '.join(missing)}，可能需要安装新技能"
        return CapabilityGap(new_id("gap"), goal, required, missing, status, explanation)


# ================================================================
# 4. QualityEvaluator — 质量评估
# ================================================================

@dataclass
