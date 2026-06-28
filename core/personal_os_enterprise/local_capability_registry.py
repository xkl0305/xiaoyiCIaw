from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from .capability_types import CapabilitySpec

SYSTEM_VERSION = 'V111.52.11_LOCAL_RUNTIME_METADATA_AND_ACCEPTANCE_CLOSE_FINAL'

LOCAL_CAPABILITIES: Dict[str, Dict[str, Any]] = {
    'local_llm': CapabilitySpec(
        name='local_llm', kind='local_llm', status='declared', connection_mode='local_only',
        provider='llama.cpp/vllm/pytorch_local', description='本地文本模型：规划、路由、总结、工具调用，不允许外部 API 回退',
        tags=['model','text','planner']).to_dict(),
    'local_vlm': CapabilitySpec(
        name='local_vlm', kind='local_vlm', status='declared', connection_mode='local_only',
        provider='qwen-vl/onnx_local', description='本地截图/界面/图像理解模型，供具身屏幕代理使用',
        tags=['model','vision','gui']).to_dict(),
    'local_ocr': CapabilitySpec(
        name='local_ocr', kind='local_ocr', status='declared', connection_mode='local_only',
        provider='paddleocr/local_ocr', description='本地 OCR，作为 VLM 的 deterministic fallback',
        tags=['ocr','document','screenshot']).to_dict(),
    'local_asr': CapabilitySpec(
        name='local_asr', kind='local_asr', status='declared', connection_mode='local_only',
        provider='funasr/whisper_local', description='本地语音识别，语音输入转文本', tags=['audio','asr']).to_dict(),
    'local_tts': CapabilitySpec(
        name='local_tts', kind='local_tts', status='declared', connection_mode='local_only',
        provider='qwen3-tts/cosyvoice_local', description='本地语音合成，文本转语音回复', tags=['audio','tts']).to_dict(),
    'local_embedding': CapabilitySpec(
        name='local_embedding', kind='local_embedding', status='declared', connection_mode='local_only',
        provider='bge-m3/qwen3-embedding_local', description='本地向量嵌入，用于记忆和知识库检索', tags=['embedding','memory']).to_dict(),
    'local_reranker': CapabilitySpec(
        name='local_reranker', kind='local_reranker', status='declared', connection_mode='local_only',
        provider='bge-reranker/qwen3-reranker_local', description='本地重排模型，提高检索质量', tags=['reranker','memory']).to_dict(),
    'local_image_provider': CapabilitySpec(
        name='local_image_provider', kind='local_image_provider', status='declared_optional', connection_mode='local_only',
        side_effect=True, requires_side_effect_proof=True, provider='diffusers/comfyui_local',
        description='可选本地图像 provider；P2 再接，不允许偷回外部 Seedream', tags=['image','optional','p2']).to_dict(),
    'persona_visual_mainchain': CapabilitySpec(
        name='persona_visual_mainchain', kind='persona_visual', status='existing', connection_mode='local_guarded',
        side_effect=True, requires_side_effect_proof=True, description='V111.51 人格视觉主链，继续保持 proof / wardrobe / send_guard',
        tags=['persona','visual','guarded']).to_dict(),
    'side_effect_gateway': CapabilitySpec(
        name='side_effect_gateway', kind='governance', status='active', connection_mode='local',
        description='副作用准备与执行统一入口', tags=['proof','guard']).to_dict(),
    'action_guard': CapabilitySpec(
        name='action_guard', kind='governance', status='active', connection_mode='local',
        description='通用动作守卫：未知真实动作默认按副作用处理', tags=['guard']).to_dict(),
    'send_guard': CapabilitySpec(
        name='send_guard', kind='governance', status='active', connection_mode='local',
        description='统一发送前 fresh artifact 守卫', tags=['send','artifact']).to_dict(),
    'observability_event_bus': CapabilitySpec(
        name='observability_event_bus', kind='observability', status='active', connection_mode='local_sqlite_wal',
        description='本地 SQLite WAL 事件账本', tags=['events','sqlite']).to_dict(),
}

REQUIRED_CAPABILITIES = {
    'local_llm','local_vlm','local_ocr','local_asr','local_tts','local_embedding','local_reranker',
    'persona_visual_mainchain','side_effect_gateway','action_guard','send_guard','observability_event_bus'
}

MODEL_CAPABILITY_NAMES = {'local_llm','local_vlm','local_ocr','local_asr','local_tts','local_embedding','local_reranker','local_image_provider'}


def list_capabilities(include_optional: bool = True) -> Dict[str, Dict[str, Any]]:
    if include_optional:
        return dict(LOCAL_CAPABILITIES)
    return {k: v for k, v in LOCAL_CAPABILITIES.items() if v.get('status') != 'declared_optional'}


def get_capability(name: str) -> Optional[Dict[str, Any]]:
    return LOCAL_CAPABILITIES.get(str(name or ''))


def capability_names() -> list[str]:
    return sorted(LOCAL_CAPABILITIES)


def register_capability(name: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    # In-memory registration for tests / local bootstrap. It never enables external fallback.
    item = dict(spec or {})
    item.setdefault('name', name)
    item.setdefault('status', 'declared')
    item.setdefault('connection_mode', 'local_only')
    item['allow_external_fallback'] = False
    LOCAL_CAPABILITIES[name] = item
    return item


def assert_declared_capabilities(required: Iterable[str] | None = None) -> Dict[str, Any]:
    required_set = set(required or REQUIRED_CAPABILITIES)
    missing_status = [name for name, item in LOCAL_CAPABILITIES.items() if not item.get('status')]
    missing_required = sorted(required_set - set(LOCAL_CAPABILITIES))
    external_leaks = [name for name, item in LOCAL_CAPABILITIES.items() if item.get('allow_external_fallback')]
    non_local = [name for name, item in LOCAL_CAPABILITIES.items() if 'external' in str(item.get('connection_mode','')).lower()]
    ok = not missing_status and not missing_required and not external_leaks and not non_local
    return {
        'ok': ok,
        'count': len(LOCAL_CAPABILITIES),
        'missing_status': missing_status,
        'missing_required': missing_required,
        'external_leaks': external_leaks,
        'non_local': non_local,
        'model_capabilities': sorted(MODEL_CAPABILITY_NAMES & set(LOCAL_CAPABILITIES)),
    }


def validate_registry() -> Dict[str, Any]:
    return assert_declared_capabilities()
