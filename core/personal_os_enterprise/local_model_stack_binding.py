from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Optional
from .local_model_registry import model_manifest_summary
from .local_runtime_probe import probe_capability

VERSION = 'V111.52.14_ENV_LIMITED_LOCAL_MODEL_WIRING_AND_STUB_PENDING_CLOSE'

RECOMMENDED_STACK = {
    'local_llm': {'primary': 'Qwen3-4B-Instruct-2507', 'fallback': ['Qwen3-1.7B GGUF','Qwen3-8B 4bit'], 'stage': 'P1'},
    'local_vlm': {'primary': 'Qwen3-VL-4B-Instruct', 'fallback': ['Qwen2.5-VL-3B-Instruct'], 'stage': 'P1'},
    'local_ocr': {'primary': 'PaddleOCR', 'fallback': ['local OCR endpoint'], 'stage': 'P1'},
    'local_asr': {'primary': 'FunASR Paraformer', 'fallback': ['Whisper local'], 'stage': 'P1'},
    'local_tts': {'primary': 'Qwen3-TTS-0.6B', 'fallback': ['CosyVoice'], 'stage': 'P1'},
    'local_embedding': {'primary': 'BAAI/bge-m3', 'fallback': ['Qwen3-Embedding'], 'stage': 'P1'},
    'local_reranker': {'primary': 'bge-reranker-v2-m3', 'fallback': ['Qwen3-Reranker'], 'stage': 'P1'},
    'local_image_provider': {'primary': 'FLUX.1-schnell + IP-Adapter / SDXL', 'fallback': ['ComfyUI local'], 'stage': 'P2_optional'},
}

def project_root(root: Optional[str | Path] = None) -> Path:
    return Path(root).resolve() if root is not None else Path(__file__).resolve().parents[2]

def local_stack_status(root: Optional[str | Path] = None) -> Dict[str, Any]:
    rootp = project_root(root)
    probes = {cap: probe_capability(cap, root=rootp) for cap in RECOMMENDED_STACK}
    ready_list = [c for c,p in probes.items() if p.get('ready')]
    missing_list = [c for c,p in probes.items() if not p.get('ready')]
    return {
        'version': VERSION,
        'root': str(rootp),
        'recommended_stack': RECOMMENDED_STACK,
        'registry_summary': model_manifest_summary(rootp),
        'wiring_present': [c for c,p in probes.items() if p.get('checks',{}).get('enabled_declared')],
        'ready': ready_list,
        'missing': missing_list,
        'real_model_ready': False,
        'probes': probes,
        'allow_external_fallback': False,
        'network_egress_attempted': False,
        'environment_blocked': True,
        'environment_blocked_reason': (
            'no_gpu|ram_5.5g|no_cmake_gxx_make|no_sudo|hf_unreachable|'
            'modelscope_download_too_slow|no_llama_cpp_wheel|llama_binary_download_corrupted'
        ),
    }

def generate_local_capabilities_template() -> str:
    lines = ['# V111.52.14 local capability binding template (env limited - stub only)', '# Fill local paths/commands/127.0.0.1 endpoints only.', '']
    for cap, meta in RECOMMENDED_STACK.items():
        lines += [f'[{cap}]', f'capability = "{cap}"', 'enabled = false', f'provider = "{cap}_provider"', f'model = "{meta["primary"]}"', 'model_path = ""', 'endpoint = ""', 'command = ""', 'allow_external_fallback = false', '']
    return '\n'.join(lines)
