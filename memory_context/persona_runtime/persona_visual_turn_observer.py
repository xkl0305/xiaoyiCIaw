from __future__ import annotations
from typing import Any, Dict


def observe_turn(
    user_message: str = "",
    assistant_message: str = "",
    lobster_message: str = "",
    reply_text: str = "",
    final_reply: str = "",
    last_reply: str = "",
    context: Dict[str, Any] | None = None,
    persona_state: Dict[str, Any] | None = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    # 龙虾/助手输出优先，其次 reply/final/last，最后才 user_message。
    candidates = [
        ("lobster_message", lobster_message),
        ("assistant_message", assistant_message),
        ("reply_text", reply_text),
        ("final_reply", final_reply),
        ("last_reply", last_reply),
        ("user_message", user_message),
    ]
    source, text = next(((k, v) for k, v in candidates if isinstance(v, str) and v.strip()), ("none", ""))
    from memory_context.persona_runtime.persona_visual_intent_predictor import predict_visual_intent
    pred = predict_visual_intent(text, context or {}, persona_state or {})
    pred["trigger_source"] = source
    pred["selected_text"] = text
    # Keep both nested prediction and legacy flattened fields. Older tests and
    # callers expect obs["mood"], obs["semantic_scene"], etc.; V111.39+ hooks use
    # obs["prediction"].
    return {
        "status": "ok",
        "trigger_source": source,
        "selected_text": text,
        "prediction": pred,
        "auto_generation_candidate": pred.get("auto_generation_candidate", False),
        "should_auto_generate": pred.get("should_auto_generate", False),
        "mood": pred.get("mood"),
        "semantic_scene": pred.get("semantic_scene"),
        "confidence": pred.get("confidence"),
        "confidence_level": pred.get("confidence_level"),
        "visual_scope": pred.get("visual_scope"),
        "purpose": pred.get("purpose"),
        "emotion_signature": pred.get("emotion_signature"),
        "expression_hints": pred.get("expression_hints"),
        "trigger_signals": pred.get("trigger_signals"),
        "signals": pred.get("signals"),
    }
