from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import time
import warnings
from datetime import datetime
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
    """Read .xiaoyienv, then fallback to TOOLS.md for SEEDREAM/ARK variables.
    TOOLS.md is git-tracked, so it survives system rebuilds that wipe .xiaoyienv.
    """
    env: Dict[str, str] = {}
    p = Path.home() / '.openclaw' / '.xiaoyienv'
    if p.exists():
        try:
            for line in p.read_text(encoding='utf-8').splitlines():
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, v = line.split('=', 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
        except Exception:
            pass

    # ═══ Fallback: TOOLS.md 兜底 SEEDREAM/ARK 变量 ═══
    # .xiaoyienv 不在 git 里，系统升级可能丢失 SEEDREAM 变量。
    # TOOLS.md 在 git 里，作为备份读取。
    if not env.get('SEEDREAM_API_URL') or not env.get('SEEDREAM_API_KEY'):
        tools_md = ROOT / 'TOOLS.md'
        if tools_md.exists():
            try:
                text = tools_md.read_text(encoding='utf-8')
                import re
                # 从 "### Seedream ARK 通道配置（火山方舟）" 区块下读取
                section_match = re.search(
                    r'### Seedream[^\n]*通道配置.*?\n(.*?)(?:###|\Z)',
                    text, re.DOTALL
                )
                if section_match:
                    section = section_match.group(1)
                    for line in section.splitlines():
                        m = re.match(r'- \*\*([A-Z_]+)\*\*:\s*`([^`]+)`', line)
                        if m:
                            key = m.group(1)
                            val = m.group(2)
                            # 只在 .xiaoyienv 缺失时补充
                            if not env.get(key) and val:
                                env[key] = val
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
    # 2026-11-13 修复：ark key 必须以 'ark-' 开头；环境变量被误注入华为 key(SK-...)时
    # 会导致 401 AuthenticationError，此处强制回退到 file_env 的方舟 key
    if b_key and not str(b_key).startswith('ark-'):
        _fb = file_env.get('SEEDREAM_API_KEY', '')
        if _fb and str(_fb).startswith('ark-'):
            b_key = _fb
        else:
            b_key = ''  # 拿不到合法方舟 key 就不注册 ark 通道，避免假通道反复 401
    if b_url and b_key:
        channels.append({'name': 'ark', 'url': b_url, 'api_key': b_key, 'uid': '', 'mode': 'openai'})

    # 通道 C: 硅基流动
    c_url = os.environ.get('SILICONFLOW_API_URL') or file_env.get('SILICONFLOW_API_URL', '')
    c_key = os.environ.get('SILICONFLOW_API_KEY') or file_env.get('SILICONFLOW_API_KEY', '')
    if c_url and c_key:
        channels.append({'name': 'siliconflow', 'url': c_url, 'api_key': c_key, 'uid': '', 'mode': 'openai'})

    # 通道 D: 小艺云端 Seedream Pro（skill-execute 协议，复用 huawei_sse 的域名与凭证）
    # 2026-11-12 新增：Pro 是独立后端 skill（x-skill-id: seedreamPro / SeedreamPro_5），
    # 与 huawei_sse 同域名同凭证，但协议不同（skill-execute SSE 而非图片直连）。
    # 排在最后作为兜底：前面通道（含审核拦截）失败时自动切 Pro（6 点/张），
    # 也可显式指定 --channel xiaoyi_pro 直连。
    if a_url and a_key and a_uid:
        channels.append({'name': 'xiaoyi_pro', 'url': a_url, 'api_key': a_key, 'uid': a_uid, 'mode': 'pro'})

    return channels


# ── 小艺云端 Seedream Pro（skill-execute 协议）────────────────────────────────
# 2026-11-12 新增。Pro 与 huawei_sse 同域名同凭证，但走 skill-execute SSE：
#   POST {SERVICE_URL}/celia-claw/v1/sse-api/skill/execute
#   headers: x-skill-id=seedreamPro, x-uid, x-api-key
#   actionName=SeedreamPro_5，pluginId 固定
# 仅支持纯文生图（参考图需先上传换取 URL，暂不在此实现）。
_PRO_SKILL_ID = 'seedreamPro'
_PRO_ACTION_NAME = 'SeedreamPro_5'
_PRO_PLUGIN_ID = 'abf9388fed6b4df89daac71be85fc62c'
_PRO_ACTION_SN = '81ef5ac1b5e74e85b90832503ea34a07'
_PRO_EXECUTE_PATH = '/celia-claw/v1/sse-api/skill/execute'


def _pro_size_from_size(size: str = '') -> str:
    """Pro 只接受 1K / 2K；其它尺寸按面积粗映射（>=200 万像素走 2K）。"""
    s = str(size or '').strip()
    if s in ('1K', '2K'):
        return s
    m = re.match(r'^(\d+)\s*[xX*]\s*(\d+)$', s)
    if m:
        px = int(m.group(1)) * int(m.group(2))
        return '2K' if px >= 2000000 else '1K'
    return '1K'


def _pro_output_dir() -> str:
    if os.environ.get('SEEDREAM_OUTPUT_DIR'):
        base = os.environ['SEEDREAM_OUTPUT_DIR']
    else:
        # 固定落到 workspace/generated-images（provider 位于 workspace/memory_context/persona_runtime/providers/）
        _ws = Path(__file__).resolve().parents[3]
        base = str(_ws / 'generated-images')
    os.makedirs(base, exist_ok=True)
    return base


def _pro_upload_file(service_url: str, api_key: str, uid: str, file_path: str) -> Optional[str]:
    """直连版参考图上传（三阶段 prepare→upload→complete），返回 fileUrl。合并自 seedream_image_gen 的 upload_file。"""
    if not os.path.isfile(file_path):
        return None
    if not _check_requests_available():
        return None
    import requests  # noqa: WPS433

    base = service_url.rstrip('/')
    hdr = {
        'x-request-from': 'openclaw',
        'x-uid': uid,
        'x-api-key': api_key,
        'Content-Type': 'application/json',
    }
    fname = os.path.basename(file_path)
    fsize = os.path.getsize(file_path)
    try:
        with open(file_path, 'rb') as f:
            fsha = hashlib.sha256(f.read()).hexdigest()
        # 阶段1 Prepare
        pp = {
            'objectType': 'TEMPORARY_MATERIAL_DOC',
            'fileName': fname,
            'fileSha256': fsha,
            'fileSize': fsize,
            'fileOwnerInfo': {'uid': uid, 'teamId': uid},
            'useEdge': False,
        }
        r = requests.post(base + '/osms/v1/file/manager/prepare', json=pp, headers=hdr, timeout=120, verify=False)
        if r.status_code != 200:
            return None
        pd = r.json()
        if pd.get('code') not in (None, '', '0'):
            return None
        oid, did = pd.get('objectId'), pd.get('draftId')
        ui = (pd.get('uploadInfos') or [{}])[0]
        up_url = ui.get('url')
        up_method = (ui.get('method') or 'PUT').upper()
        up_hdr = ui.get('headers') or {}
        if not (oid and did and up_url):
            return None
        # 阶段2 直传
        with open(file_path, 'rb') as f:
            blob = f.read()
        u = requests.request(up_method, up_url, headers=up_hdr, data=blob, timeout=120, verify=False)
        if u.status_code not in (200, 204):
            return None
        # 阶段3 CompleteAndQuery
        c = requests.post(base + '/osms/v1/file/manager/completeAndQuery', json={'objectId': oid, 'draftId': did},
                          headers=hdr, timeout=120, verify=False)
        if c.status_code != 200:
            return None
        cd = c.json()
        url = (cd.get('fileDetailInfo') or {}).get('url', '')
        return url or None
    except Exception:  # noqa: BLE001
        return None


def _generate_via_xiaoyi_pro(
    prompt: str,
    size: str = '1K',
    max_images: int = 1,
    ref_paths: Optional[List[str]] = None,
    service_url: str = '',
    api_key: str = '',
    uid: str = '',
    timeout: int = 240,
) -> Dict[str, Any]:
    """调用小艺云端 Seedream Pro。返回标准 provider 结果字典。"""
    if not _check_requests_available():
        return {'status': 'provider_failed_no_current_image', 'provider_status': 'requests_unavailable',
                'provider_error': 'requests_not_available', 'generated_image_path': None}
    import requests  # noqa: WPS433

    _size = _pro_size_from_size(size)
    content = {
        'prompt': prompt,
        'size': _size,
        'watermark': False,
        'response_format': 'url',
    }
    if ref_paths:
        _ref_urls = []
        for _rp in ref_paths:
            _u = _pro_upload_file(service_url, api_key, uid, str(_rp))
            if _u:
                _ref_urls.append(_u)
        if not _ref_urls:
            _ref_urls = None
        if _ref_urls:
            content['reference_images'] = _ref_urls
    payload = {
        'actions': [{
            'actionExecutorTask': {
                'actionName': _PRO_ACTION_NAME,
                'content': content,
                'pluginId': _PRO_PLUGIN_ID,
                'replyCard': False,
            },
            'actionSn': _PRO_ACTION_SN,
        }],
        'endpoint': {
            'countryCode': '',
            'device': {'deviceId': '5682d99dbb90973b775b7e9bf774ff9f', 'phoneType': '2in1', 'prdVer': '11.6.2.202'},
        },
        'session': {'interactionId': '0', 'isNew': False, 'sessionId': 'xxx'},
        'utterance': {'original': '', 'type': 'text'},
        'version': '1.0',
    }
    headers = {
        'Content-Type': 'application/json',
        'x-skill-id': _PRO_SKILL_ID,
        'x-request-from': 'openclaw',
        'x-hag-trace-id': f"{hashlib.sha256(str(uid).encode('utf-8')).hexdigest()[:32]}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        'x-uid': uid,
        'x-api-key': api_key,
    }
    url = service_url.rstrip('/') + _PRO_EXECUTE_PATH
    image_urls: Optional[List[str]] = None
    last_err = ''
    try:
        resp = requests.post(url, json=payload, headers=headers, stream=True, timeout=timeout, verify=False)
        resp.raise_for_status()
        for raw in resp.iter_lines():
            if not raw:
                continue
            line = raw.decode('utf-8', errors='ignore') if isinstance(raw, bytes) else str(raw)
            if not line.startswith('data:'):
                continue
            body = line[5:].strip()
            if not body:
                continue
            try:
                result = json.loads(body)
            except Exception:
                continue
            code = result.get('code', '')
            if code and str(code) not in ('0', '200'):
                last_err = f"[{code}] {result.get('desc', 'unknown')}"
                continue
            infos = result.get('abilityInfos') or []
            if not infos:
                continue
            aer = infos[0].get('actionExecutorResult') or {}
            if aer.get('code') not in (None, '', '0'):
                last_err = str(aer.get('desc') or 'actionExecutorResult_error')
                continue
            reply = aer.get('reply') or {}
            rcode = reply.get('code', '')
            if rcode and str(rcode) != '0':
                last_err = f"[{rcode}] {reply.get('desc', 'unknown')}"
                continue
            if (reply.get('streamInfo') or {}).get('streamType') == 'final':
                items = reply.get('items') or []
                if items:
                    image_urls = items
                    break
    except Exception as exc:  # noqa: BLE001
        return {
            'status': 'provider_failed_no_current_image',
            'provider_status': 'pro_request_failed',
            'provider_error': f'{type(exc).__name__}: {exc}',
            'provider_code': '',
            'provider_message': str(exc)[:300],
            'generated_image_path': None,
            'output_path': None,
            'generated_image_paths': [],
            'pro_size': _size,
        }

    if not image_urls:
        return {
            'status': 'provider_returned_no_image',
            'provider_status': 'pro_no_image',
            'provider_error': last_err or 'no_final_items',
            'provider_code': '',
            'provider_message': last_err[:300],
            'generated_image_path': None,
            'output_path': None,
            'generated_image_paths': [],
            'pro_size': _size,
        }

    out_dir = _pro_output_dir()
    saved: List[str] = []
    now = datetime.now()
    for idx, item in enumerate(image_urls[: max(1, max_images)]):
        img_url = item if isinstance(item, str) else (item.get('url') or item.get('imageUrl') or '')
        if not img_url:
            continue
        blob = _http_download(img_url, timeout=90)
        if not blob or len(blob) < 500:
            continue
        if blob[:3] == b'\xff\xd8\xff':
            ext = '.jpg'
        elif blob[:8] == b'\x89PNG\r\n\x1a\n':
            ext = '.png'
        elif blob[:4] == b'RIFF':
            ext = '.webp'
        else:
            ext = '.jpg'
        fname = f"pro_{now.strftime('%Y%m%d_%H%M%S')}_{now.strftime('%f')[:3]}_{idx}{ext}"
        fpath = os.path.join(out_dir, fname)
        with open(fpath, 'wb') as fh:
            fh.write(blob)
        saved.append(fpath)

    if not saved:
        return {
            'status': 'provider_returned_no_image',
            'provider_status': 'pro_download_failed',
            'provider_error': 'download_failed',
            'generated_image_path': None,
            'output_path': None,
            'generated_image_paths': [],
            'pro_size': _size,
        }

    return {
        'status': 'generated',
        'provider_status': 'ok',
        'generated_image_path': saved[0],
        'output_path': saved[0],
        'generated_image_paths': saved,
        'pro_size': _size,
        'provider_code': '',
        'provider_message': '',
    }


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
                _u = str(item.get('url'))
                _c = _http_download(_u)
                if _c:
                    OUT_DIR.mkdir(parents=True, exist_ok=True)
                    _o = OUT_DIR / f'seedream_sf_{int(time.time() * 1000)}_{len(paths)}.png'
                    _o.write_bytes(_c)
                    paths.append(str(_o))
                else:
                    paths.append(_u)
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
    '1K': '1024x1024',
    '1024': '1024x1024',
    '1024x1024': '1024x1024',
    '1920x1080': '1920x1080',
    '1080x1920': '1080x1920',
    '4:5': '1080x1350',
    '1080x1350': '1080x1350',
    '1920x2400': '1920x2400',
    '2700x3600': '2700x3600',
    '2K': '1440x2880',
    '3K': '1920x3840',
    '4K': '4096x3072',
    '4K-wide': '3840x2160',
    '4K-portrait': '3072x4096',
    '4K-square': '4096x4096',
    # huawei_sse 不接受 2304x4096（超范围），9:16 统一走标准 1080x1920
    '9:16': '1080x1920',
}

# 硅基流动(Kolors)自家尺寸档：官方支持 7 档（实测全通）
_SF_SIZE_MAP: Dict[str, str] = {
    '1K': '1024x1024', '1024': '1024x1024', '1024x1024': '1024x1024',
    '4:5': '768x1024', '1080x1350': '768x1024',
    '960x1280': '960x1280', '768x1024': '768x1024',
    '1024x768': '1024x768', '1280x960': '1280x960',
    '1920x1080': '1440x720', '4K': '1440x720', '4K-wide': '1440x720',
    '4096x3072': '1440x720', '3840x2160': '1440x720',
    '2K': '720x1440', '3K': '720x1440', '9:16': '720x1440',
    '1080x1920': '720x1440', '1920x2400': '720x1440', '2700x3600': '720x1440',
    '1920x3840': '720x1440', '2304x4096': '720x1440', '3072x4096': '720x1440',
    '4K-square': '1024x1024', '4096x4096': '1024x1024',
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
    # 硅基流动用自家模型名(火山 doubao-* 在硅基流动不存在会 404)
    sf_model = os.environ.get('SILICONFLOW_MODEL') or _file_env2.get('SILICONFLOW_MODEL') or 'Kwai-Kolors/Kolors'

    for ch_cfg in channels:
        ch_name = ch_cfg['name']
        ch_url = ch_cfg['url']
        ch_key = ch_cfg['api_key']
        ch_mode = ch_cfg.get('mode', 'openai')

        try:
            ark_payload: Dict[str, Any] = {
                'model': sf_model if ch_name == 'siliconflow' else (ark_model if ch_mode == 'openai' else MODEL_ID),
                'prompt': prompt,
                'n': max_images or 1,
            }
            if ch_name == 'siliconflow':
                # 硅基流动参数名是 image_size，且只认自家尺寸档
                _sf_size = _SF_SIZE_MAP.get(size, '1024x1024')
                ark_payload['image_size'] = _sf_size
            else:
                ark_payload['size'] = _SIZE_MAP.get(size, '1440x2880')
            if negative_prompt:
                ark_payload['negative_prompt'] = negative_prompt
            encoded_refs = _encode_reference_images(ref_paths)
            if encoded_refs:
                ark_payload['reference_images'] = encoded_refs

            # 通道 D: 小艺云端 Seedream Pro（skill-execute 协议，纯文生图）
            if ch_mode == 'pro':
                pro_result = _generate_via_xiaoyi_pro(
                    prompt=prompt,
                    size=size,
                    max_images=max_images,
                    ref_paths=ref_paths,
                    service_url=ch_url,
                    api_key=ch_key,
                    uid=str(ch_cfg.get('uid') or ''),
                )
                if pro_result.get('status') == 'generated' and pro_result.get('generated_image_path'):
                    _pro_out = str(pro_result.get('generated_image_path') or '')
                    _pro_valid = _validate_output_image(_pro_out, _gen_start).get('send_ok') if _pro_out else False
                    if not _pro_valid:
                        _last_error = f'{ch_name}: pro假成功(无有效落盘图)'
                        continue
                    pro_result.update({
                        'channel_used': ch_name,
                        'channels_available': [c['name'] for c in channels],
                        'provider_status': 'ok',
                        'provider_env_debug': debug,
                        'model': 'SeedreamPro_5',
                        'payload_mode': debug.get('payload_mode'),
                        'reference_images_count': len(ref_paths),
                        'reference_image_paths': ref_paths,
                        'persona_subject': PERSONA_SUBJECT if persona_visual_context else None,
                        'http_client_used': 'requests',
                        'requests_available': HTTP_CLIENT_AVAILABLE,
                        'generation_start_time': _gen_start,
                    })
                    return pro_result
                _last_error = f'{ch_name}: {pro_result.get("provider_error") or pro_result.get("status")}'
                continue

            if ch_mode == 'sse':
                # 华为云 SSE 走 generate_seedream 的华为 provider 逻辑
                from memory_context.persona_runtime.providers.huawei_provider import generate_image as hw_gen
                # size 需先映射成华为认的 WIDTHxHEIGHT（'9:16' 等比例值后端不认）
                _hw_size = _SIZE_MAP.get(str(size).strip(), '') or (
                    str(size).strip() if re.match(r'^\d+\s*[xX*]\s*\d+$', str(size).strip()) else '2K')
                hw_result = hw_gen(
                    prompt=prompt,
                    input_image=(str(ref_paths[0]) if ref_paths else ''),
                    size=_hw_size,
                    max_images=max_images,
                    reference_weight=reference_weight,
                )
                if hw_result.get('status') in ('generated',) and hw_result.get('generated_image_path'):
                    # 兜底防"SSE假成功"(2026-11-08): huawei_provider 虽已源头校验下载内容,
                    # 这里再强校验文件真实存在且为本轮新生成(与 openai 分支同标准), 双保险。
                    _hw_out = str(hw_result.get('generated_image_path') or '')
                    _hw_valid = _validate_output_image(_hw_out, _gen_start).get('send_ok') if _hw_out else False
                    if not _hw_valid:
                        hw_result['status'] = 'provider_returned_no_image'
                        hw_result['blocked_send'] = True
                        hw_result['blocked_reason'] = 'sse_fake_success_no_valid_image'
                        _last_error = f'{ch_name}: SSE假成功(无有效落盘图)'
                        continue
                    _channel_used = ch_name
                    hw_result['channel_used'] = ch_name
                    hw_result['channels_available'] = [c['name'] for c in channels]
                    return hw_result
                _last_error = f'{ch_name}: {hw_result.get("status", "unknown")}'
                _hw_code = hw_result.get('provider_code') or ''
                _hw_msg = hw_result.get('provider_message') or ''
                if _hw_code or _hw_msg:
                    _last_error += f' [{_hw_code}] {_hw_msg}'[:300]
                continue

            # OpenAI 兼容通道（火山 ARK / 硅基流动）
            headers = {'Authorization': f"Bearer {ch_key}", 'Content-Type': 'application/json'}
            base = ch_url.rstrip('/')
            # 修复(2026-10-24): SEEDREAM_API_URL 可能已含 /api/v3,防止拼接出 .../api/v3/api/v3/... 重复路径
            if base.endswith('/images/generations'):
                api_url = base
            elif base.endswith('/api/v3') or '/v1' in base:
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
            _err_body = (response_raw_preview or '').replace('\n', ' ').strip()
            _last_error = f'{ch_name}: HTTP {response_status_code}'
            if _err_body:
                _last_error += f' {_err_body[:300]}'
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
