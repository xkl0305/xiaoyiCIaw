from __future__ import annotations

import base64
import json
import os
import time
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional

# 屏蔽 urllib3 SSL 证书验证警告
warnings.filterwarnings('ignore', message='.*Unverified HTTPS request.*')
warnings.filterwarnings('ignore', module='urllib3')

ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = ROOT / '.persona_visual' / 'generated'
MODEL_ID = 'doubao-seedream-5-0-260128'
# 火山方舟 ARK 时，model 字段传 endpoint ID
_ENDPOINT_ID = ''


def _read_xiaoyi_env() -> Dict[str, str]:
    env: Dict[str, str] = {}
    p = Path.home() / '.openclaw' / '.xiaoyienv'
    if not p.exists():
        return env
    try:
        for line in p.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return env


def _mask_key(key: str, keep_prefix: int = 8, keep_tail: int = 4) -> str:
    if not key:
        return ''
    if len(key) <= keep_prefix + keep_tail:
        return key[:2] + '****'
    return f'{key[:keep_prefix]}****{key[-keep_tail:]}'


def _as_paths(input_image: str = '', reference_images: Optional[List[str]] = None) -> List[str]:
    out: List[str] = []
    if input_image and str(input_image) not in out:
        out.append(str(input_image))
    if reference_images:
        for item in reference_images:
            if item and str(item) not in out:
                out.append(str(item))
    return out


def _resolve_ref_path(path: str) -> Path:
    p = Path(str(path))
    if p.is_absolute():
        return p
    cwd_p = Path.cwd() / p
    if cwd_p.exists():
        return cwd_p
    root_p = ROOT / p
    if root_p.exists():
        return root_p
    return p


def _existing_reference_paths(paths: List[str]) -> List[str]:
    out: List[str] = []
    for item in paths:
        resolved = _resolve_ref_path(str(item))
        if resolved.exists():
            out.append(str(resolved))
    return out


def _path_has_persona_avatar(path: str) -> bool:
    normalized = str(path).replace('\\', '/').lower()
    name = Path(str(path)).name.lower()
    return 'seed_avatar' in name or '/persona/seed_avatar' in normalized or 'persona/seed_avatar' in normalized


def _path_has_outfit_reference(path: str) -> bool:
    normalized = str(path).replace('\\', '/').lower()
    name = Path(str(path)).name.lower()
    if _path_has_persona_avatar(path):
        return False
    return '/outfits/' in normalized or ('_reference' in name and name.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')))


def _persona_actual_reference_status(ref_paths: List[str]) -> Dict[str, Any]:
    existing = _existing_reference_paths(ref_paths)
    avatar_present = any(_path_has_persona_avatar(x) for x in existing)
    outfit_present = any(_path_has_outfit_reference(x) for x in existing)
    return {
        'reference_images_count_actual': len(existing),
        'reference_image_paths_actual': existing,
        'avatar_reference_present_actual': bool(avatar_present),
        'outfit_reference_present_actual': bool(outfit_present),
    }


def _missing_required_references_result(prompt: str, ref_paths: List[str], actual: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'status': 'blocked',
        'blocked': True,
        'blocked_reason': 'missing_required_reference_images',
        'required_entry': 'post_reply_or_mainline_hook',
        'message': '鸽子王人格视觉请求必须同时带真实可用的头像参考图和衣柜参考图，禁止只用 PVC 自报数量放行。',
        'persona_subject': PERSONA_SUBJECT,
        'generated_image_path': None,
        'output_path': None,
        'provider_status': 'blocked',
        'provider_error': 'missing_required_reference_images',
        'prompt_preview': (prompt or '')[:400],
        'payload_mode': 'image_to_image' if ref_paths else 'text_to_image',
        'model': MODEL_ID,
        'reference_images_count': len(ref_paths),
        'reference_image_paths': ref_paths,
        **actual,
    }


# ── 三通道配置 ──
# 通道 A: 华为云 SSE（xiaoyi skill-execute）
# 通道 B: 火山 ARK（OpenAI 兼容）
# 通道 C: 硅基流动（OpenAI 兼容）
# 优先级: A → B → C，尝试下一个当前通道失败时


def _load_all_channel_configs() -> List[Dict[str, Any]]:
    """Return ordered list of channel configs: Huawei -> ARK -> SiliconFlow."""
    file_env = _read_xiaoyi_env()
    channels = []

    # 通道 A: 华为云 SSE
    a_url = (
        os.environ.get('SERVICE_URL')
        or file_env.get('SERVICE_URL', '')
    )
    a_key = (
        os.environ.get('PERSONAL_API_KEY')
        or os.environ.get('PERSONAL-API-KEY')
        or file_env.get('PERSONAL_API_KEY', '')
        or file_env.get('PERSONAL-API-KEY', '')
    )
    a_uid = os.environ.get('PERSONAL_UID') or os.environ.get('PERSONAL-UID') or file_env.get('PERSONAL_UID') or file_env.get('PERSONAL-UID') or ''
    if a_url and a_key:
        channels.append({'name': 'huawei_sse', 'url': a_url, 'api_key': a_key, 'uid': a_uid, 'mode': 'sse'})

    # 通道 B: 火山 ARK
    b_url = os.environ.get('SEEDREAM_API_URL') or file_env.get('SEEDREAM_API_URL', '')
    b_key = os.environ.get('SEEDREAM_API_KEY') or file_env.get('SEEDREAM_API_KEY', '')
    if b_url and b_key:
        channels.append({'name': 'ark', 'url': b_url, 'api_key': b_key, 'uid': '', 'mode': 'openai'})

    # 通道 C: 硅基流动
    c_url = os.environ.get('SILICONFLOW_API_URL') or file_env.get('SILICONFLOW_API_URL', '')
    c_key = os.environ.get('SILICONFLOW_API_KEY') or file_env.get('SILICONFLOW_API_KEY', '')
    if c_url and c_key:
        channels.append({'name': 'siliconflow', 'url': c_url, 'api_key': c_key, 'uid': '', 'mode': 'openai'})

    return channels


def provider_env(input_image: str = '', reference_images: Optional[List[str]] = None) -> Dict[str, Any]:
    file_env = _read_xiaoyi_env()
    channels = _load_all_channel_configs()
    primary = channels[0] if channels else {}
    url = primary.get('url', '')
    api_key = primary.get('api_key', '')
    uid = primary.get('uid', '')
    ref_paths = _as_paths(input_image=input_image, reference_images=reference_images)
    exists = [Path(x).exists() for x in ref_paths]
    avatar_present = any('seed_avatar' in Path(x).name or 'avatar' in str(x).lower() for x in ref_paths)
    outfit_present = any('/outfits/' in str(x).replace('\\', '/') or '_reference' in Path(x).name for x in ref_paths)
    channel_names = [c['name'] for c in channels]
    debug = {
        'provider_url_present': bool(url),
        'api_key_present': bool(api_key),
        'seedream_api_key_present': bool(api_key),
        'seedream_api_key_masked': _mask_key(api_key),
        'seedream_api_url_present': bool(url),
        'seedream_uid_present': bool(uid),
        'uid_present': bool(uid),
        'provider_ready': bool(url and api_key),
        'missing': [name for name, ok in {'URL': bool(url), 'API_KEY': bool(api_key)}.items() if not ok],
        'input_image_exists': bool(ref_paths and exists[0]),
        'input_image_path': str(input_image or (ref_paths[0] if ref_paths else '')),
        'reference_images_count': len(ref_paths),
        'reference_image_paths': ref_paths,
        'reference_images_exist': exists,
        'avatar_reference_present': bool(avatar_present),
        'outfit_reference_present': bool(outfit_present),
        'payload_mode': 'image_to_image' if ref_paths else 'text_to_image',
        'model': MODEL_ID,
        'available_channels': channel_names,
        'active_channel': primary.get('name', 'none'),
        'channel_count': len(channels),
        'url_source': 'huawei_sse' if any(c['name'] == 'huawei_sse' for c in channels) else ('ark' if any(c['name'] == 'ark' for c in channels) else ('siliconflow' if any(c['name'] == 'siliconflow' for c in channels) else 'empty')),
        'api_key_source': 'PERSONAL_API_KEY_ENV' if os.environ.get('PERSONAL_API_KEY') else ('PERSONAL_API_KEY_FILE' if file_env.get('PERSONAL_API_KEY') else ('SEEDREAM_API_KEY_ENV' if os.environ.get('SEEDREAM_API_KEY') else ('SEEDREAM_API_KEY_FILE' if file_env.get('SEEDREAM_API_KEY') else 'empty'))),
        'env_file_checked': str(Path.home() / '.openclaw' / '.xiaoyienv'),
    }
    return {'url': url, 'api_key': api_key, 'uid': uid, '_debug': debug}


def provider_ready() -> bool:
    env = provider_env()
    return bool(env.get('url') and env.get('api_key'))


def _write_base64_image(data: str) -> str:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw = base64.b64decode(data)
    out = OUT_DIR / f'seedream_{int(time.time() * 1000)}.png'
    out.write_bytes(raw)
    return str(out)


from xiaoyi_persona_visual.policy.persona_visual_request_guard import (
    PERSONA_SUBJECT,
    block_if_persona_visual_without_main_pipeline,
)
from xiaoyi_persona_visual.policy.mainchain_proof import validate_mainchain_proof


def _image_path_from_payload(data: Dict[str, Any], max_images: int) -> Dict[str, Any]:
    ark_data = data.get('data')
    if isinstance(ark_data, list) and len(ark_data) > 0:
        ark_urls = []
        for item in ark_data[:max_images]:
            if isinstance(item, dict) and item.get('url'):
                ark_urls.append(str(item['url']))
        if ark_urls:
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            paths = []
            for url in ark_urls:
                content = _http_download(url)
                if content:
                    out = OUT_DIR / f'seedream_ark_{int(time.time() * 1000)}_{len(paths)}.png'
                    out.write_bytes(content)
                    paths.append(str(out))
            if paths:
                return {'output_path': paths[0], 'generated_image_path': paths[0], 'generated_image_paths': paths}
    if data.get('image_base64'):
        path = _write_base64_image(str(data['image_base64']))
        return {'output_path': path, 'generated_image_path': path, 'generated_image_paths': [path]}
    if data.get('images') and isinstance(data['images'], list):
        paths = []
        for item in data['images'][:max_images]:
            if isinstance(item, dict) and item.get('image_base64'):
                paths.append(_write_base64_image(str(item['image_base64'])))
            elif isinstance(item, str) and len(item) > 200:
                paths.append(_write_base64_image(item))
            elif isinstance(item, dict) and item.get('url'):
                paths.append(str(item.get('url')))
        if paths:
            return {'output_path': paths[0], 'generated_image_path': paths[0], 'generated_image_paths': paths}
    if data.get('output_path') or data.get('generated_image_path'):
        p = str(data.get('output_path') or data.get('generated_image_path'))
        return {'output_path': p, 'generated_image_path': p, 'generated_image_paths': [p]}
    return {}


def _encode_reference_images(paths: List[str]) -> List[Dict[str, str]]:
    encoded: List[Dict[str, str]] = []
    for path in paths:
        fp = _resolve_ref_path(str(path))
        if fp.exists():
            encoded.append({'type': 'base64', 'data': base64.b64encode(fp.read_bytes()).decode()})
    return encoded


def _check_requests_available() -> bool:
    try:
        import requests  # type: ignore
        return True
    except ImportError:
        return False


HTTP_CLIENT_AVAILABLE = _check_requests_available()


def _http_post_json(url: str, headers: Dict[str, str], payload: Dict[str, Any], timeout: int = 180) -> Dict[str, Any]:
    """POST JSON. Fallback to urllib if requests not available."""
    if HTTP_CLIENT_AVAILABLE:
        import requests  # type: ignore
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
            return {'status_code': resp.status_code, 'text': resp.text, 'http_client': 'requests'}
        except Exception as e:
            return {'status_code': 0, 'text': str(e), 'http_client': 'requests_error'}
    import urllib.request as _ur
    import urllib.error as _ue
    data = json.dumps(payload).encode('utf-8')
    req = _ur.Request(url, data=data, headers=headers, method='POST')
    try:
        with _ur.urlopen(req, timeout=timeout) as resp:
            return {'status_code': resp.getcode(), 'text': resp.read().decode('utf-8'), 'http_client': 'urllib_fallback'}
    except _ue.HTTPError as e:
        return {'status_code': e.code, 'text': e.read().decode('utf-8', errors='replace'), 'http_client': 'urllib_fallback'}
    except Exception as e:
        return {'status_code': 0, 'text': str(e), 'http_client': 'urllib_fallback_error'}


def _http_download(url: str, timeout: int = 60) -> Optional[bytes]:
    """Download binary data. Fallback to urllib if requests not available."""
    if HTTP_CLIENT_AVAILABLE:
        import requests  # type: ignore
        try:
            return requests.get(url, timeout=timeout).content
        except Exception:
            return None
    import urllib.request as _ur
    try:
        with _ur.urlopen(url, timeout=timeout) as resp:
            return resp.read()
    except Exception:
        return None


def _generation_start_timestamp() -> float:
    return time.time()


def _validate_output_image(path: Optional[str], start_time: float) -> Dict[str, Any]:
    """Validate generated image is fresh and from this generation turn."""
    if not path:
        return {'send_ok': False, 'blocked_send': True, 'blocked_reason': 'no_current_generated_image'}
    fp = Path(str(path))
    if not fp.exists():
        return {'send_ok': False, 'blocked_send': True, 'blocked_reason': 'no_current_generated_image'}
    mtime = fp.stat().st_mtime
    if mtime < start_time:
        return {'send_ok': False, 'blocked_send': True, 'blocked_reason': 'stale_generated_image'}
    return {'send_ok': True, 'blocked_send': False}


_SIZE_MAP: Dict[str, str] = {
    '2K': '1440x2880',
    '3K': '1920x3840',
    '4K': '4096x3072',
    '4K-wide': '3840x2160',
    '4K-portrait': '3072x4096',
    '4K-square': '4096x4096',
}

def generate_image(
    prompt: str,
    input_image: str = '',
    size: str = '2K',
    watermark: bool = False,
    max_images: int = 1,
    reference_weight: int = 100,
    negative_prompt: str = '',
    reference_images: Optional[List[str]] = None,
    channel: str = '',
    **extra: Any,
) -> Dict[str, Any]:
    persona_visual_context = extra.get('persona_visual_context', {}) or {}
    metadata = dict(extra)
    if persona_visual_context:
        metadata['persona_visual_context'] = persona_visual_context
    ref_paths = _as_paths(input_image=input_image, reference_images=reference_images)

    # ── V111.51.18: provider is a hard gate, not an auto-router ──
    # The provider must never invent persona_visual_context after being blocked.
    # Valid PVC can only be produced by post_reply/mainline_hook → PersonaVisualController.
    guard = block_if_persona_visual_without_main_pipeline(
        text=str(extra.get('text') or ''),
        prompt=prompt or '',
        metadata=metadata,
        input_image=input_image,
        reference_images=reference_images,
        persona_visual_context=persona_visual_context,
    )
    if guard.get('blocked'):
        guard.update({
            'prompt_preview': (prompt or '')[:400],
            'payload_mode': 'image_to_image' if ref_paths else 'text_to_image',
            'model': MODEL_ID,
            'reference_images_count': len(ref_paths),
            'reference_image_paths': ref_paths,
        })
        return guard

    # ── All persona detection is handled by block_if_persona_visual_without_main_pipeline above ──
    # V111.51.20: even a field-complete PVC is not enough. Provider only accepts a
    # mainchain-issued proof + real avatar/outfit references in the actual payload.
    if persona_visual_context and persona_visual_context.get('persona_visual_request') is True:
        actual_refs = _persona_actual_reference_status(ref_paths)
        if (
            actual_refs.get('reference_images_count_actual', 0) < 2
            or actual_refs.get('avatar_reference_present_actual') is not True
            or actual_refs.get('outfit_reference_present_actual') is not True
        ):
            return _missing_required_references_result(prompt=prompt, ref_paths=ref_paths, actual=actual_refs)

        proof_validation = validate_mainchain_proof(persona_visual_context, prompt or '', ref_paths, require_runtime_registry=True)
        if not proof_validation.get('valid'):
            return {
                'status': 'blocked',
                'blocked': True,
                'blocked_reason': proof_validation.get('reason') or 'invalid_mainchain_proof',
                'required_entry': 'post_reply_or_mainline_hook',
                'message': '鸽子王人格视觉请求必须由主链签发 mainchain_proof，禁止手工伪造 PVC 后直调 provider。',
                'persona_subject': PERSONA_SUBJECT,
                'generated_image_path': None,
                'output_path': None,
                'provider_status': 'blocked',
                'provider_error': proof_validation.get('reason') or 'invalid_mainchain_proof',
                'prompt_preview': (prompt or '')[:400],
                'payload_mode': 'image_to_image' if ref_paths else 'text_to_image',
                'model': MODEL_ID,
                'reference_images_count': len(ref_paths),
                'reference_image_paths': ref_paths,
                **actual_refs,
            }

    env = provider_env(input_image=input_image, reference_images=ref_paths)
    debug = env.get('_debug', {})
    if not env.get('url') or not env.get('api_key'):
        return {
            'status': 'provider_not_ready',
            'reason': 'missing_or_disabled_seedream_provider',
            'missing': debug.get('missing', []),
            'generated_image_path': None,
            'output_path': None,
            'generated_image_paths': [],
            'send_image_paths': [],
            'blocked_send': True,
            'blocked_reason': 'provider_not_ready_no_current_image',
            'prompt_preview': prompt[:400],
            'provider_env_debug': debug,
            'provider_status': 'not_ready',
            'provider_error': 'missing: ' + ','.join(debug.get('missing', [])),
            'payload_mode': debug.get('payload_mode'),
            'model': MODEL_ID,
            'persona_subject': PERSONA_SUBJECT,
            'http_client_used': 'not_started_provider_not_ready',
            'requests_available': HTTP_CLIENT_AVAILABLE,
            'generation_start_time': _generation_start_timestamp(),
        }
    # ── V111.51.21 + V10.9.0: 三通道 fallback (华为云 SSE → 火山 ARK → 硅基流动) ──
    _gen_start = _generation_start_timestamp()
    channels = _load_all_channel_configs()
    if not channels:
        return {
            'status': 'provider_not_ready',
            'reason': 'no_channels_configured',
            'generated_image_path': None,
            'output_path': None,
            'generated_image_paths': [],
            'send_image_paths': [],
            'blocked_send': True,
            'blocked_reason': 'provider_not_ready_no_current_image',
            'prompt_preview': prompt[:400],
            'provider_status': 'not_ready',
            'provider_error': 'no_channels_configured',
            'payload_mode': 'image_to_image' if ref_paths else 'text_to_image',
            'model': MODEL_ID,
            'persona_subject': PERSONA_SUBJECT if persona_visual_context else None,
        }

    # ── 通道选择：channel 参数 — 逗号分隔列表（双通道）或单通道名 ──
    # seedream-image-gen skill: 不传 channel → 三通道全开（huawei_sse → ark → siliconflow）
    # 人格视角出图: channel='ark,siliconflow' → 双通道（ark → siliconflow, 跳过 huawei_sse）
    if channel:
        names = [c.strip() for c in channel.split(',') if c.strip()]
        matched = [c for c in channels if c['name'] in names]
        if not matched:
            return {
                'status': 'channel_not_found',
                'error': f'指定通道 "{channel}" 无一可用',
                'available_channels': [c['name'] for c in channels],
                'generated_image_path': None,
                'output_path': None,
                'provider_status': 'channel_not_found',
                'payload_mode': 'image_to_image' if ref_paths else 'text_to_image',
                'model': MODEL_ID,
                'persona_subject': PERSONA_SUBJECT if persona_visual_context else None,
            }
        # 按 names 顺序重排，保留指定列表内的优先级
        name_order = {n: i for i, n in enumerate(names)}
        matched.sort(key=lambda c: name_order.get(c['name'], 999))
        channels = matched

    _last_error = ''
    _channel_used = ''
    _last_http_resp = {}
    _file_env2 = _read_xiaoyi_env()
    endpoint_id = os.environ.get('SEEDREAM_ENDPOINT_ID') or _file_env2.get('SEEDREAM_ENDPOINT_ID') or ''
    ark_model = endpoint_id or MODEL_ID

    for ch_cfg in channels:
        ch_name = ch_cfg['name']
        ch_url = ch_cfg['url']
        ch_key = ch_cfg['api_key']
        ch_mode = ch_cfg.get('mode', 'openai')

        try:
            ark_payload: Dict[str, Any] = {
                'model': ark_model if ch_mode == 'openai' else MODEL_ID,
                'prompt': prompt,
                'n': max_images or 1,
                'size': _SIZE_MAP.get(size, '1440x2880'),
            }
            if negative_prompt:
                ark_payload['negative_prompt'] = negative_prompt
            encoded_refs = _encode_reference_images(ref_paths)
            if encoded_refs:
                ark_payload['reference_images'] = encoded_refs

            if ch_mode == 'sse':
                # 华为云 SSE 走 generate_seedream 的华为 provider 逻辑
                from memory_context.persona_runtime.providers.huawei_provider import generate_image as hw_gen
                hw_result = hw_gen(
                    prompt=prompt,
                    size=size,
                    max_images=max_images,
                    reference_weight=reference_weight,
                )
                if hw_result.get('status') in ('generated',) and hw_result.get('generated_image_path'):
                    _channel_used = ch_name
                    hw_result['channel_used'] = ch_name
                    hw_result['channels_available'] = [c['name'] for c in channels]
                    return hw_result
                _last_error = f'{ch_name}: {hw_result.get("status", "unknown")}'
                continue

            # OpenAI 兼容通道（火山 ARK / 硅基流动）
            headers = {'Authorization': f"Bearer {ch_key}", 'Content-Type': 'application/json'}
            base = ch_url.rstrip('/')
            if '/v1' in base:
                api_url = base + '/images/generations'
            else:
                api_url = base + '/api/v3/images/generations'
            http_resp = _http_post_json(api_url, headers=headers, payload=ark_payload, timeout=180)
            response_status_code = http_resp.get('status_code', 0)
            response_raw_preview = (http_resp.get('text') or '')[:500]
            http_client_type = http_resp.get('http_client', 'unknown')
            if 200 <= response_status_code < 300:
                try:
                    data = json.loads(http_resp.get('text', '{}'))
                except Exception:
                    data = {'raw_text': (http_resp.get('text') or '')}
                if not isinstance(data, dict):
                    data = {'raw_result': data}
                result = dict(data)
                image_paths = _image_path_from_payload(data, max_images=max_images)
                result.update(image_paths)
                _output = str(image_paths.get('output_path') or image_paths.get('generated_image_path') or '')
                _send_check = _validate_output_image(_output, _gen_start)
                result.update({
                    'channel_used': ch_name,
                    'channels_available': [c['name'] for c in channels],
                    'response_status_code': response_status_code,
                    'provider_status': 'ok',
                    'provider_env_debug': debug,
                    'model': MODEL_ID,
                    'payload_mode': debug.get('payload_mode'),
                    'reference_images_count': len(ref_paths),
                    'reference_image_paths': ref_paths,
                    'persona_subject': PERSONA_SUBJECT if persona_visual_context else None,
                    'http_client_used': http_client_type,
                    'requests_available': HTTP_CLIENT_AVAILABLE,
                    'generation_start_time': _gen_start,
                })
                if _output and not _send_check.get('send_ok'):
                    result['status'] = 'provider_failed_no_current_image'
                    result['blocked_send'] = True
                    result['blocked_reason'] = _send_check.get('blocked_reason', 'no_current_generated_image')
                elif _output and _send_check.get('send_ok'):
                    result['status'] = result.get('status') or 'generated'
                else:
                    result['status'] = 'provider_returned_no_image'
                return result
            _last_error = f'{ch_name}: HTTP {response_status_code}'
            continue
        except Exception as e:
            _last_error = f'{ch_name}: {str(e)}'
            continue

    # 所有通道都失败了
    _file_env2b = _read_xiaoyi_env()
    return {
        'status': 'all_channels_failed',
        'error': _last_error,
        'generated_image_path': None,
        'output_path': None,
        'generated_image_paths': [],
        'channels_available': [c['name'] for c in channels],
        'last_channel_error': _last_error,
        'provider_status': 'all_failed',
        'provider_error': _last_error,
        'provider_env_debug': debug,
        'model': MODEL_ID,
        'payload_mode': debug.get('payload_mode'),
        'reference_images_count': len(ref_paths),
        'reference_image_paths': ref_paths,
        'persona_subject': PERSONA_SUBJECT if persona_visual_context else None,
        'http_client_used': 'all_failed',
        'requests_available': HTTP_CLIENT_AVAILABLE,
        'generation_start_time': _gen_start,
    }
