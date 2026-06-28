from __future__ import annotations

METRICS_CATALOG = {
    'capability_route_total': {'type': 'counter', 'description': '能力路由次数'},
    'capability_not_available_total': {'type': 'counter', 'description': '本地能力缺失 fail-closed 次数'},
    'local_model_health_ready': {'type': 'gauge', 'description': '本地模型能力是否 ready'},
    'local_model_first_token_ms': {'type': 'histogram', 'description': '本地 LLM 首 token 延迟'},
    'local_model_tokens_per_sec': {'type': 'histogram', 'description': '本地 LLM tokens/s'},
    'ocr_latency_ms': {'type': 'histogram', 'description': 'OCR 延迟'},
    'vlm_latency_ms': {'type': 'histogram', 'description': 'VLM 延迟'},
    'asr_latency_ms': {'type': 'histogram', 'description': 'ASR 延迟'},
    'tts_rtf': {'type': 'histogram', 'description': 'TTS real-time factor'},
    'side_effect_proof_block_total': {'type': 'counter', 'description': '副作用 proof 阻断次数'},
    'send_guard_block_total': {'type': 'counter', 'description': '发送守卫阻断次数'},
}


def list_metrics():
    return dict(METRICS_CATALOG)
