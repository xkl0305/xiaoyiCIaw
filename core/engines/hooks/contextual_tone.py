"""
Crusheart Agent OS — 对话粘性引擎 v6.6.1
功能：根据时间段、对话轮次、考试季自动调整语气风格
v6.6.1: 同时段仅首轮问候，后续同轮对话跳过问候
在 pipeline 阶段 5.5 调用，注入 tone_hints 到 result 上下文中
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, List

BEIJING_TZ = timezone(timedelta(hours=8))

# 考试季月份
EXAM_MONTHS = {6, 12}

# 已问候过的时段标记（用于同一时段内去重）
_greeted_periods: set = set()

# 时间段语气配置
# (小时范围, 语气标签, 问候语, 说明)
TONE_CONFIG = [
    (range(5, 8),    "gentle_morning", "早",          "清晨温和轻声，刚醒不宜长篇大论"),
    (range(8, 12),   "active_morning", "早啊",        "上午积极有活力，可主动问候今日安排"),
    (range(12, 14),  "casual_noon",    "中午好",      "午间轻松友好"),
    (range(14, 18),  "efficient_afternoon", "下午好", "下午简洁高效，减少废话"),
    (range(18, 22),  "warm_evening",   "晚上好",      "傍晚温暖随意，可适当活泼"),
    (range(22, 24),  "soft_night",     "夜深了",      "深夜柔声简短，不提复杂话题"),
    (range(0, 5),    "quiet_dawn",     "这么晚了还没睡", "凌晨极简应答，提醒休息"),
]


def _get_current_period() -> tuple:
    """返回当前时段 (tone_label, greeting, description)"""
    now = datetime.now(BEIJING_TZ)
    hour = now.hour
    for hours, tone, greeting, desc in TONE_CONFIG:
        if hour in hours:
            return tone, greeting, desc
    return "default", "", "默认语气"


def reset_greeted_state():
    """重置问候状态（跨天清除旧标记），由每日维护调用"""
    global _greeted_periods
    today_labels = {tone for _, tone, _, _ in TONE_CONFIG}
    _greeted_periods = _greeted_periods & today_labels


def generate_tone_hints(
    conversation_rounds: int = 0,
    is_first_today: bool = False,
    is_exam_season: Optional[bool] = None
) -> Dict:
    """
    生成语气提示，注入 pipeline prompt 上下文

    参数：
        conversation_rounds: 当前会话已进行的对话轮次
        is_first_today: 当日首次对话
        is_exam_season: 是否考试季（None 则自动判断）

    返回：
        {
            "tone_hints": {
                "period": str,          # 时段标签
                "greeting": str,        # 推荐问候语（同一时段仅首轮，后续为空）
                "description": str,     # 语气描述
                "voice_style": str,     # 整体语气风格指引
                "is_exam_season": bool, # 是否考试季
                "is_first_today": bool, # 是否当日首轮
                "long_session": bool,   # 是否连续多轮
                "hour": int,            # 当前小时
            }
        }
    """
    global _greeted_periods

    tone, greeting, desc = _get_current_period()
    now = datetime.now(BEIJING_TZ)

    if is_exam_season is None:
        is_exam_season = now.month in EXAM_MONTHS

    long_session = conversation_rounds > 5
    hour = now.hour

    # ── 同时段问候去重：同一时段内只问候一次 ──
    if tone in _greeted_periods:
        # 已问候过，不再重复问候语
        greeting = ""
    elif is_first_today:
        # 首次对话时记录并为后续对话跳过问候
        _greeted_periods.add(tone)

    # 构建语气风格指引
    style_parts = [f"当前时段: {desc}"]

    if is_exam_season:
        style_parts.append("考试季期间，减少主动打扰，回复偏鼓励")

    if is_first_today:
        style_parts.append("当日首次对话，简短问候后自然接续上下文")
    else:
        style_parts.append("同时段已问候过，不再重复问候，直接接续话题")

    if long_session:
        style_parts.append("已连续对话多轮，注意主动询问是否有其他需要")

    if hour >= 22 or hour < 5:
        style_parts.append("深夜时段，语气柔和，注意提醒休息")

    voice_style = "；".join(style_parts)

    return {
        "tone_hints": {
            "period": tone,
            "greeting": greeting,
            "description": desc,
            "voice_style": voice_style,
            "is_exam_season": is_exam_season,
            "is_first_today": is_first_today,
            "long_session": long_session,
            "hour": hour,
        }
    }


def init() -> Dict:
    """引擎初始化入口"""
    hints = generate_tone_hints()
    tone = hints["tone_hints"]
    print(f"  🎭 Contextual Tone: {tone['period']} | {tone['description']}")
    return {
        "status": "ready",
        "period": tone["period"],
        "greeting": tone["greeting"],
        "greeted_periods": list(_greeted_periods),
        "initialized_at": datetime.now(BEIJING_TZ).isoformat()
    }


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

    result = init()
    print(result)
