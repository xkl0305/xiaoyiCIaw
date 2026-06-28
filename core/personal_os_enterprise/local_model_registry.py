from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import tomllib
except Exception:
    tomllib = None

DEFAULT_LOCAL_MODELS: Dict[str, Dict[str, Any]] = {
    'local_llm': {
        'capability': 'local_llm', 'enabled': False, 'name': 'Qwen3 local text model',
        'preferred': ['Qwen3-4B-Instruct-2507', 'Qwen3-1.7B-GGUF'],
        'env_path': 'LOCAL_LLM_MODEL_PATH', 'endpoint_env': 'LOCAL_LLM_ENDPOINT', 'command_env': 'LOCAL_LLM_COMMAND',
    },
    'local_vlm': {
        'capability': 'local_vlm', 'enabled': False, 'name': 'Qwen3-VL local GUI model',
        'preferred': ['Qwen3-VL-4B-Instruct', 'Qwen2.5-VL-3B-Instruct'],
        'env_path': 'LOCAL_VLM_MODEL_PATH', 'endpoint_env': 'LOCAL_VLM_ENDPOINT', 'command_env': 'LOCAL_VLM_COMMAND',
    },
    'local_ocr': {
        'capability': 'local_ocr', 'enabled': False, 'name': 'PaddleOCR local OCR',
        'preferred': ['PaddleOCR'], 'env_path': 'LOCAL_OCR_MODEL_PATH', 'command_env': 'LOCAL_OCR_COMMAND',
    },
    'local_asr': {
        'capability': 'local_asr', 'enabled': False, 'name': 'FunASR / Whisper local ASR',
        'preferred': ['FunASR Paraformer', 'Whisper local'], 'env_path': 'LOCAL_ASR_MODEL_PATH', 'command_env': 'LOCAL_ASR_COMMAND',
    },
    'local_tts': {
        'capability': 'local_tts', 'enabled': False, 'name': 'Qwen3-TTS / CosyVoice local TTS',
        'preferred': ['Qwen3-TTS-0.6B', 'CosyVoice'], 'env_path': 'LOCAL_TTS_MODEL_PATH', 'command_env': 'LOCAL_TTS_COMMAND',
    },
    'local_embedding': {
        'capability': 'local_embedding', 'enabled': False, 'name': 'BGE-M3 embedding',
        'preferred': ['BAAI/bge-m3', 'Qwen3-Embedding'], 'env_path': 'LOCAL_EMBEDDING_MODEL_PATH', 'endpoint_env': 'LOCAL_EMBEDDING_ENDPOINT', 'command_env': 'LOCAL_EMBEDDING_COMMAND',
    },
    'local_reranker': {
        'capability': 'local_reranker', 'enabled': False, 'name': 'BGE reranker',
        'preferred': ['bge-reranker-v2-m3', 'Qwen3-Reranker'], 'env_path': 'LOCAL_RERANKER_MODEL_PATH', 'endpoint_env': 'LOCAL_RERANKER_ENDPOINT', 'command_env': 'LOCAL_RERANKER_COMMAND',
    },
    'local_image_provider': {
        'capability': 'local_image_provider', 'enabled': False, 'name': 'Local persona image provider',
        'preferred': ['FLUX.1-schnell + IP-Adapter', 'SDXL + IP-Adapter'], 'env_path': 'LOCAL_IMAGE_MODEL_PATH', 'endpoint_env': 'LOCAL_IMAGE_ENDPOINT', 'command_env': 'LOCAL_IMAGE_COMMAND',
    },
}


def project_root(root: Optional[str | Path] = None) -> Path:
    return Path(root).resolve() if root is not None else Path(__file__).resolve().parents[2]


def _read_toml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    raw = path.read_bytes()
    if tomllib:
        return tomllib.loads(raw.decode('utf-8'))
    # Tiny fallback for simple [section] key=value TOML used by local_capabilities.example.toml.
    data: Dict[str, Any] = {}
    cur: Dict[str, Any] = data
    for line in raw.decode('utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('[') and line.endswith(']'):
            cur = data.setdefault(line[1:-1], {})
            continue
        if '=' not in line:
            continue
        k, v = line.split('=', 1)
        k = k.strip(); v = v.strip().strip('"').strip("'")
        if v.lower() in {'true','false'}:
            cur[k] = v.lower() == 'true'
        elif v.startswith('[') and v.endswith(']'):
            cur[k] = [x.strip().strip('"').strip("'") for x in v[1:-1].split(',') if x.strip()]
        else:
            cur[k] = v
    return data


def load_local_model_registry(root: Optional[str | Path] = None) -> Dict[str, Dict[str, Any]]:
    base = {k: dict(v) for k, v in DEFAULT_LOCAL_MODELS.items()}
    cfg_path = project_root(root) / 'profiles' / 'local_capabilities.toml'
    example_path = project_root(root) / 'profiles' / 'local_capabilities.example.toml'
    data = _read_toml(cfg_path if cfg_path.exists() else example_path)
    for section, values in data.items():
        if not isinstance(values, dict):
            continue
        cap = values.get('capability') or section
        if cap in base:
            merged = dict(base[cap])
            merged.update(values)
            base[cap] = merged
    # Env overrides never create external fallback; they only point to local paths/endpoints.
    for cap, item in base.items():
        env_path = item.get('env_path')
        if env_path and os.environ.get(env_path):
            item['model_path'] = os.environ[env_path]
            item['enabled'] = True
        endpoint_env = item.get('endpoint_env')
        if endpoint_env and os.environ.get(endpoint_env):
            ep = os.environ[endpoint_env]
            if ep.startswith('http://127.0.0.1') or ep.startswith('http://localhost'):
                item['endpoint'] = ep
                item['enabled'] = True
            else:
                item['endpoint_rejected'] = 'non_local_endpoint'
        command_env = item.get('command_env')
        if command_env and os.environ.get(command_env):
            item['command'] = os.environ[command_env]
            item['enabled'] = True
        # V111.52.12: reject non-loopback endpoints from config files as well as env overrides.
        ep_cfg = str(item.get('endpoint') or '')
        if ep_cfg and not (ep_cfg.startswith('http://127.0.0.1') or ep_cfg.startswith('http://localhost') or ep_cfg.startswith('https://127.0.0.1') or ep_cfg.startswith('https://localhost')):
            item['endpoint_rejected'] = 'non_local_endpoint'
            item.pop('endpoint', None)
            item['enabled'] = False
        item['allow_external_fallback'] = False
    return base


def get_model_capability(capability: str, root: Optional[str | Path] = None) -> Dict[str, Any]:
    return load_local_model_registry(root).get(capability, {'capability': capability, 'enabled': False, 'reason': 'unknown_capability'})


def model_manifest_summary(root: Optional[str | Path] = None) -> Dict[str, Any]:
    reg = load_local_model_registry(root)
    enabled = [k for k, v in reg.items() if v.get('enabled')]
    disabled = [k for k, v in reg.items() if not v.get('enabled')]
    return {'count': len(reg), 'enabled': enabled, 'disabled': disabled, 'allow_external_fallback': False, 'registry': reg}
