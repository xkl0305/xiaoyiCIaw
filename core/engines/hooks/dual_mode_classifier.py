"""
Crusheart Agent OS — Dual Mode Agent Engine (权重评分版 + P3 缓存)
替代原有的简单关键词触发，使用多维度权重累计评分
"""

import re, sys, os, time
from typing import Dict, List, Tuple, Optional

# P3: 分类结果缓存（30秒有效期）
_CLASSIFY_CACHE: Dict[str, Tuple[str, float, Optional[dict], float]] = {}
_CACHE_TTL = 30  # 秒

# 模板库懒加载
_TEMPLATE_LIB = None

# 自调优权重配置缓存（由 auto_tuning 动态更新）
_TUNING_CONFIG_CACHE = {}
_TUNING_CACHE_TTL = 5  # 5秒刷新


def _get_tuning_overrides() -> dict:
    """读取 auto_tuning 的配置覆盖"""
    now = time.time()
    cache_age = now - _TUNING_CONFIG_CACHE.get("_ts", 0)
    if cache_age < _TUNING_CACHE_TTL and _TUNING_CONFIG_CACHE:
        return _TUNING_CONFIG_CACHE
    try:
        from core.engines.tools.auto_tuning import CONFIG_PATH
        if os.path.exists(CONFIG_PATH):
            import json
            with open(CONFIG_PATH) as f:
                cfg = json.load(f)
            dual = cfg.get("dual_mode", {})
            _TUNING_CONFIG_CACHE.update({
                "_ts": now,
                "fast_weight": dual.get("fast_keyword_weight", 10),
                "agent_weight": dual.get("agent_keyword_weight", 8),
                "multi_tool_weight": dual.get("multi_tool_weight", 15),
            })
    except Exception:
        pass
    if "_ts" not in _TUNING_CONFIG_CACHE:
        _TUNING_CONFIG_CACHE["_ts"] = now
    return _TUNING_CONFIG_CACHE



def _get_template_lib():
    """懒加载模板库"""
    global _TEMPLATE_LIB
    if _TEMPLATE_LIB is None:
        try:
            sys.path.insert(0, os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace"))
            from core.engines.tools.task_template_library import get_library
            _TEMPLATE_LIB = get_library()
        except Exception:
            _TEMPLATE_LIB = False  # 标记加载失败
    return _TEMPLATE_LIB if _TEMPLATE_LIB else None

# ================================================================
# 维度权重配置
# ================================================================
# 快速模式特征词 (负权重，降低评分 = 倾向快速模式)
FAST_KEYWORDS = {
    # 纯闲聊
    "嗨": -0.3, "哈喽": -0.3, "你好": -0.3, "在吗": -0.4, "吃了没": -0.4,
    "干嘛": -0.3, "睡没": -0.3, "早": -0.2, "晚好": -0.2, "好": -0.1,
    # 简单确认
    "好的": -0.3, "可以": -0.2, "OK": -0.3, "收到": -0.3, "知道": -0.2,
    "明白": -0.2, "666": -0.4, "确实": -0.2, "对的": -0.2,
    # 简单评价
    "好看": -0.3, "好听": -0.3, "不错": -0.2, "还行": -0.3, "6": -0.3,
    "绝了": -0.3, "可以啊": -0.2,
    # 简单查询
    "是什么": -0.2, "什么是": -0.2, "在哪": -0.1, "在哪儿": -0.1,
    "谁": -0.1, "哪个": -0.1, "啥": -0.2, "什么意思": -0.1,
    "怎么用": -0.1, "能干嘛": -0.1,
    # 信息查询
    "查一下": -0.3, "查查": -0.2, "搜一下": -0.2, "搜索": -0.2,
    "找找": -0.2, "看看": -0.1, "查": -0.2, "搜": -0.2,
    "最新": -0.1, "今天": -0.1, "明天": -0.1,
    # 状态查看
    "查看": -0.2, "显示": -0.1, "打开": -0.1, "展示": -0.1,
    "列出": -0.1, "我的": -0.1, "当前": -0.1,
    # 时效要求
    "快": -0.3, "快点": -0.4, "简单说": -0.4, "直接说": -0.4,
    "快速": -0.3, "简单": -0.2,
}

# Agent模式特征词 (正权重，增加评分 = 倾向Agent模式)
AGENT_KEYWORDS = {
    # 任务型
    "写": 0.3, "创建": 0.3, "生成": 0.3, "制作": 0.3, "搞一个": 0.4,
    "做一个": 0.3, "帮我弄": 0.3, "实现": 0.4, "开发": 0.4, "编码": 0.4,
    "编写": 0.4, "编程": 0.4, "设计": 0.3, "构建": 0.3,
    # 分析型
    "分析": 0.4, "对比": 0.3, "比较": 0.3, "评估": 0.4, "判断": 0.3,
    "诊断": 0.5, "排查": 0.5, "检查": 0.2, "审核": 0.3,
    "总结": 0.3, "归纳": 0.3, "提炼": 0.3, "论证": 0.4, "推导": 0.4,
    # 复杂操作
    "部署": 0.4, "迁移": 0.4, "清理": 0.2, "优化": 0.3,
    "重构": 0.5, "整合": 0.4, "合并": 0.3, "拆分": 0.3,
    # 深度需求
    "详细": 0.4, "深入": 0.5, "好好想想": 0.5, "仔细": 0.4,
    "认真": 0.3, "全面": 0.3, "逐条": 0.3, "具体": 0.2, "完整": 0.3,
    "分析一下": 0.4, "比较一下": 0.3,
    # 问题排查
    "报错": 0.5, "错误": 0.4, "bug": 0.5, "异常": 0.4, "问题": 0.2,
    "出错了": 0.5, "不行": 0.2, "不work": 0.5, "挂了": 0.5,
    "卡住了": 0.5, "失败": 0.3, "原因": 0.2, "怎么解决": 0.4,
    # 代码/技术
    "代码": 0.5, "函数": 0.4, "类": 0.3, "接口": 0.3, "api": 0.3,
    "debug": 0.5, "调试": 0.5, "编译": 0.4,
    "git": 0.3, "repo": 0.3, "仓库": 0.3, "脚本": 0.3,
    # 多步骤
    "先": 0.3, "然后": 0.3, "依次": 0.3, "逐步": 0.3,
    "分别": 0.3, "每个都": 0.3, "同时": 0.2, "多个": 0.2,
    "步骤": 0.3, "流程": 0.3, "方案": 0.3,
    "计划": 0.3, "规划": 0.3, "架构": 0.5, "框架": 0.4,
    # 文档/创作
    "文档": 0.3, "报告": 0.3, "文章": 0.3, "博客": 0.3,
    "教程": 0.3, "指南": 0.3, "计划书": 0.3, "方案": 0.3,
}


# ================================================================
# 初始化函数（供 init_engines.py 调用）
# ================================================================
def init_dual_mode_classifier():
    """
    初始化双模式分类器 + 模板库。
    验证 classify_task 函数可用，返回初始化状态。
    """
    try:
        mode, score, _ = classify_task("你好", 0, False, False)
        lib = _get_template_lib()
        tmpl_count = lib.count()["total"] if lib else 0
        return {
            "status": "ready",
            "classify_task": classify_task.__name__,
            "templates_loaded": tmpl_count,
            "test_result": {"mode": mode, "score": score},
        }
    except Exception as e:
        raise RuntimeError(f"dual_mode_classifier 初始化失败: {e}")


def classify_task(text: str, context_length: int = 0,
                  is_followup: bool = False,
                  previous_was_agent: bool = False) -> Tuple[str, float, Optional[dict]]:
    """
    权重评分分类（P3: 30秒内相同文本直接返回缓存）

    Returns (mode: "fast"|"agent", score: float)
    score > 0 -> Agent模式, score <= 0 -> 快速模式
    """
    cache_key = text[:120]
    now = time.time()

    # 0. 首条消息标记检测：必须在缓存检查之前执行
    #    存在 .state/first_message 标记时强制 Agent 模式
    first_msg_marker = os.path.expanduser("~/.openclaw/workspace/.state/first_message")
    if os.path.exists(first_msg_marker):
        try:
            os.remove(first_msg_marker)
        except OSError:
            pass
        result = ("agent", 999.0, None)
        _CLASSIFY_CACHE[cache_key] = (*result, now)
        return result

    score = 0.0
    text_lower = text.strip()

    # 1. 关键词权重累加
    for keyword, weight in FAST_KEYWORDS.items():
        if keyword in text_lower:
            score += weight

    for keyword, weight in AGENT_KEYWORDS.items():
        if keyword in text_lower:
            score += weight

    # 2. 长度惩罚/奖励
    words_count = len(text_lower)
    if words_count > 100:
        score += 0.2  # 长文本更可能是复杂任务
    elif words_count > 50:
        score += 0.1
    elif words_count <= 5 and not is_followup:
        score -= 0.1  # 极短文本且不是追问，更可能是闲聊

    # 3. 上下文连续性
    if is_followup and previous_was_agent:
        score += 0.2  # 连续Agent模式追问

    # 4. 多工具需求判断
    multi_tool_indicators = [
        "先", "然后", "再", "接着", "之后", "顺便",
        "同时", "分别", "依次", "逐一",
    ]
    multi_count = sum(1 for ind in multi_tool_indicators if ind in text_lower)
    if multi_count >= 2:
        score += 0.2

    # 5. 问号/陈述句判断
    if text_lower.endswith("?"):
        score -= 0.05  # 问句偏向快速回答
    elif text_lower.endswith(".") or text_lower.endswith("。"):
        score += 0.1  # 陈述句更可能是任务

    # 6. 模板匹配 — 命中开发模板则强制Agent模式
    lib = _get_template_lib()
    matched_template = None
    if lib:
        matches = lib.match(text_lower)
        if matches and matches[0]["score"] >= 5:
            matched_template = matches[0]
            score = max(score, 0.3)  # 命中模板，倾向Agent模式

    # 7. 特殊指令判断
    if "快一点" in text_lower or "简单说" in text_lower or "快速" in text_lower:
        score = min(score, -0.3)  # 强制快速模式

    if "好好想想" in text_lower or "仔细分析" in text_lower:
        score = max(score, 0.5)  # 强制Agent模式

    # 7.5: 自调优权重修正（从 auto_tuning config 读取）
    tuning = _get_tuning_overrides()
    fast_kw = tuning.get("fast_weight", 10)
    agent_kw = tuning.get("agent_weight", 8)
    if fast_kw != 10 or agent_kw != 8:
        # Apply tuning factor: higher fast_weight = more likely fast
        tune_factor = (fast_kw - 10) * 0.02 - (agent_kw - 8) * 0.02
        score = score * (1 + tune_factor)

    
        # v7.0: feedback correction
        fb = _get_feedback(normalized, threshold=0.3)
        if fb:
            prev_mode = fb.get("chosen_mode", "")
            prev_tools = fb.get("actual_tools", 0)
            user_switched = fb.get("user_switched", False)
            sim = fb.get("_similarity", 0.3)
            if user_switched:
                agent_factor *= (1.0 + 0.3 * sim)
            elif prev_mode == "fast" and prev_tools >= 2:
                agent_factor *= (1.0 + 0.15 * sim)
            elif prev_mode == "agent" and prev_tools == 0:
                agent_threshold += 0.15 * sim

    # 决策
    mode = "agent" if score > 0 else "fast"
    result = (mode, round(score, 3), matched_template)
    
    # P3: 写入缓存
    _CLASSIFY_CACHE[cache_key] = (*result, now)
    # 控制缓存大小，超过100条时清理最旧的
    if len(_CLASSIFY_CACHE) > 100:
        oldest = min(_CLASSIFY_CACHE.keys(), key=lambda k: _CLASSIFY_CACHE[k][3])
        del _CLASSIFY_CACHE[oldest]
    
    return result


# ── 待办意图分类 ────────────────────────────────
_TODO_USER_PATTERNS = [
    (r"提醒(我|一下)", 10),
    (r"记得(叫|提醒|通知)(我|一下)?", 10),
    (r"通知我", 10),
    (r"(x|几|\d+)分钟(后|以)", 8),
    (r"设(置|定|个)(提醒|闹钟|定时)", 10),
    (r"帮我(记住|记着|提醒|留意)", 9),
    (r"(明天|后天|今晚|今早|下午|上午)(x|\d+)?点", 8),
    (r"(喊|叫|call)(我|一下)", 7),
    (r"创建提醒", 9),
    (r"提醒我去", 9),
]

_TODO_MY_PATTERNS = [
    (r"先放[下一]?", 9),
    (r"下次再说", 9),
    (r"(回头|以后|稍后|晚点)再(说|搞|做|处理|弄)", 9),
    (r"写(入|到|进)(todo|待办|TODO)", 10),
    (r"(记|写|加)到待办", 10),
    (r"先(记|留)(着|下|住)", 8),
    (r"(明天|后天|下周)再(搞|做|处理|弄|修|改)", 8),
    (r"下[一1]轮再做", 8),
    (r"(放|扔)到(future|backlog|以后)", 8),
    (r"这个(坑|问题|bug|改动)记住", 8),
]


def classify_todo_intent(text: str) -> dict:
    """识别待办意图并二分类

    Args:
        text: 用户消息文本

    Returns:
        {"type": "user_todo" | "my_todo" | "none", "reason": "..."}
    """
    if not text or not text.strip():
        return {"type": "none", "reason": "empty"}

    # 先检查用户待办模式（权重更高）
    user_score = 0
    for pat, weight in _TODO_USER_PATTERNS:
        if re.search(pat, text):
            user_score += weight
            if user_score >= 15:
                return {"type": "user_todo", "reason": f"命中用户待办模式，总分={user_score}"}

    # 检查我的待办模式
    my_score = 0
    for pat, weight in _TODO_MY_PATTERNS:
        if re.search(pat, text):
            my_score += weight
            if my_score >= 15:
                return {"type": "my_todo", "reason": f"命中我的待办模式，总分={my_score}"}

    # 两者都有但都不够高
    if user_score > 0 and user_score >= my_score:
        return {"type": "user_todo", "reason": f"用户待办概率较高 (user={user_score}, my={my_score})"}
    if my_score > 0 and my_score > user_score:
        return {"type": "my_todo", "reason": f"我的待办概率较高 (user={user_score}, my={my_score})"}

    return {"type": "none", "reason": f"未匹配到待办模式 (user={user_score}, my={my_score})"}


if __name__ == "__main__":

    # --test/--self-check: 基础自检（#48）
    if "--test" in sys.argv or "--self-check" in sys.argv:
        try:
            from core.engines.init.self_check import run_self_check
        except ImportError:
            print("❌ self_check 模块不可用")
            sys.exit(1)

        checks = [("import self", lambda: None)]
        sys.exit(run_self_check(__name__, __file__,
            custom_checks=checks, verbose=True))

    import sys, json
    args = [a for a in sys.argv[1:] if a not in ("--json",)]
    if args and args[0] == "--init":
        print(json.dumps({"status": "ok", "mode": "dual"}))
        sys.exit(0)

    if args and args[0] == "--todo-classify":
        if len(args) > 1:
            result = classify_todo_intent(" ".join(args[1:]))
            print(json.dumps(result, ensure_ascii=False))
            sys.exit(0)
        else:
            print(json.dumps({"type": "none", "reason": "no input"}))
            sys.exit(0)

    if args:
        text = args[0]
        mode, score, template = classify_task(text, 0, False, False)
        output = {"mode": mode, "score": round(score, 2), "template": template}
        print(json.dumps(output, ensure_ascii=False))
