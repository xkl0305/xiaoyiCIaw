from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .capability_types import CapabilityRoute
from .local_health_check import require_capabilities
from .observability_event_bus import emit_event

PERSONA_TERMS = ['鸽子王', '小艺', '看看你', '展示一下', '摸摸头', '看看你的', '你的样子', '人格视觉']
OCR_TERMS = ['ocr', '识别文字', '图片文字', '图中文字', '截图文字', '提取文字', '扫描件', '读图中文字']
VLM_TERMS = ['截图', '看屏幕', '屏幕', '窗口', '界面', '页面', '按钮', '图里', '图片里', '看图']
ASR_TERMS = ['语音转文字', '音频识别', '听一下', '录音转文字', 'asr', 'speech to text']
TTS_TERMS = ['念出来', '读出来', '语音回复', '文字转语音', 'tts', '朗读']
EMBED_TERMS = ['知识库', '向量', '相似检索', '语义检索', 'embedding', '检索记忆']
RERANK_TERMS = ['重排', 'rerank', '排序候选', '检索排序']
IMAGE_TERMS = ['本地生图', '本地图像', '图像生成', 'persona image local', '本地出图']
FILE_SIDE_EFFECT_TERMS = ['写入文件', '保存文件', '覆盖文件', '删除文件', '改配置']
DEVICE_TERMS = ['点击', '打开应用', '操作手机', '端侧', '闹钟', '日历创建', '发消息']


def _contains(text: str, terms: List[str]) -> bool:
    low = text.lower()
    return any(t.lower() in low for t in terms)


def classify_capability_request(text: str, *, source: str = 'user_message') -> Dict[str, Any]:
    text = str(text or '').strip()
    required: List[str] = []
    optional: List[str] = []
    intent = 'local_llm_request'
    reason = 'default_text_reasoning'
    confidence = 0.55
    side_effect_action = ''

    if _contains(text, PERSONA_TERMS):
        intent = 'persona_visual_request'
        required = ['persona_visual_mainchain']
        optional = ['local_image_provider']
        reason = 'explicit_persona_visual_subject'
        confidence = 0.92
        side_effect_action = 'image_generation'
    elif _contains(text, ASR_TERMS):
        intent = 'local_asr_request'; required = ['local_asr']; reason = 'audio_to_text_terms'; confidence = 0.9
    elif _contains(text, TTS_TERMS):
        intent = 'local_tts_request'; required = ['local_tts']; reason = 'text_to_speech_terms'; confidence = 0.9; side_effect_action = 'local_provider_call'
    elif _contains(text, OCR_TERMS) and _contains(text, VLM_TERMS):
        intent = 'local_screen_understanding_request'; required = ['local_ocr','local_vlm']; reason = 'screenshot_or_image_text_understanding'; confidence = 0.88
    elif _contains(text, OCR_TERMS):
        intent = 'local_ocr_request'; required = ['local_ocr']; optional = ['local_vlm']; reason = 'ocr_terms'; confidence = 0.87
    elif _contains(text, VLM_TERMS):
        intent = 'local_vlm_request'; required = ['local_vlm']; optional = ['local_ocr']; reason = 'vision_or_gui_terms'; confidence = 0.84
    elif _contains(text, RERANK_TERMS):
        intent = 'local_reranker_request'; required = ['local_reranker']; optional = ['local_embedding']; reason = 'reranker_terms'; confidence = 0.83
    elif _contains(text, EMBED_TERMS):
        intent = 'local_retrieval_request'; required = ['local_embedding']; optional = ['local_reranker']; reason = 'semantic_retrieval_terms'; confidence = 0.82
    elif _contains(text, IMAGE_TERMS):
        intent = 'local_image_generation_request'; required = ['local_image_provider']; reason = 'local_image_generation_terms'; confidence = 0.78; side_effect_action = 'image_generation'
    elif _contains(text, FILE_SIDE_EFFECT_TERMS):
        intent = 'file_side_effect_request'; required = ['side_effect_gateway','action_guard']; reason = 'file_side_effect_terms'; confidence = 0.82; side_effect_action = 'file_write'
    elif _contains(text, DEVICE_TERMS):
        intent = 'device_action_request'; required = ['side_effect_gateway','action_guard']; reason = 'device_action_terms'; confidence = 0.82; side_effect_action = 'device_action'
    else:
        required = ['local_llm']

    route = CapabilityRoute(
        intent_type=intent,
        required_capabilities=required,
        optional_capabilities=optional,
        side_effect_action=side_effect_action,
        confidence=confidence,
        reason=reason,
        fail_closed=True,
    ).to_dict()
    route['source'] = source
    route['allow_external_fallback'] = False
    return route


def route_request(text: str, *, source: str = 'user_message', root: Optional[str | Path] = None, require_ready: bool = True) -> Dict[str, Any]:
    route = classify_capability_request(text, source=source)
    required = route.get('required_capabilities') or []
    readiness = require_capabilities(required, root=root) if require_ready else {'ok': True, 'missing': [], 'checks': {}}
    out = {
        'status': 'routed' if readiness.get('ok') else 'blocked',
        'blocked': not readiness.get('ok'),
        'blocked_reason': readiness.get('blocked_reason','') if not readiness.get('ok') else '',
        'capability_not_available': readiness.get('missing', []),
        'route': route,
        'readiness': readiness,
        'allow_external_fallback': False,
        'network_egress_attempted': False,
    }
    try:
        emit_event('capability_route_decided', {'text_preview': text[:80], **out}, root=root)
    except Exception:
        pass
    return out


def route_many(samples: List[str], *, root: Optional[str | Path] = None, require_ready: bool = False) -> Dict[str, Any]:
    return {'items': [route_request(s, root=root, require_ready=require_ready) for s in samples], 'allow_external_fallback': False}
