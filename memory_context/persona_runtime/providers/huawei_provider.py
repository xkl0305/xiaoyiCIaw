"""
Huawei Cloud / Xiaoyi Image Generation Provider

Calls the Xiaoyi skill-execute SSE endpoint at:
  {SERVICE_URL}/celia-claw/v1/sse-api/skill/execute

Authentication: x-uid + x-api-key from .xiaoyienv or env vars.
Action: seedreamBatch5 (pluginId: abf9388fed6b4df89daac71be85fc62c)
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import random
import string
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

_REQUESTS_AVAILABLE: bool | None = None
_OUT_DIR = Path.home() / ".openclaw" / "workspace" / "generated-images"

_MIME_TYPE_MAP = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}

# ── helpers ────────────────────────────────────────────────

def _read_xiaoyi_env() -> Dict[str, str]:
    env: Dict[str, str] = {}
    p = Path.home() / ".openclaw" / ".xiaoyienv"
    if not p.exists():
        return env
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return env


def _mask_key(key: str, keep_prefix: int = 8, keep_tail: int = 4) -> str:
    if not key:
        return ""
    if len(key) <= keep_prefix + keep_tail:
        return key[:2] + "****"
    return f"{key[:keep_prefix]}****{key[-keep_tail:]}"


def _check_requests_available() -> bool:
    global _REQUESTS_AVAILABLE
    if _REQUESTS_AVAILABLE is None:
        try:
            import requests  # type: ignore
            _REQUESTS_AVAILABLE = True
        except ImportError:
            _REQUESTS_AVAILABLE = False
    return _REQUESTS_AVAILABLE


def _require_requests():
    if not _check_requests_available():
        raise RuntimeError("requests dependency required for Huawei image generation")
    import requests
    return requests


def _is_remote_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _sha256(file_path: str) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _upload_file(file_path: str, object_type: str = "TEMPORARY_MATERIAL_DOC") -> str:
    """Upload local file to Xiaoyi file storage (prepare → upload → complete)."""
    requests = _require_requests()
    env = _read_xiaoyi_env()
    uid = env.get("PERSONAL_UID") or env.get("PERSONAL-UID") or ""
    api_key = env.get("PERSONAL_API_KEY") or env.get("PERSONAL-API-KEY") or ""
    if not uid or not api_key:
        return ""
    fpath = Path(file_path)
    if not fpath.exists():
        return ""

    base_url = "https://hag-drcn.op.dbankcloud.com"
    headers = {
        "Content-Type": "application/json",
        "x-uid": uid,
        "x-api-key": api_key,
        "x-request-from": "openclaw",
    }
    fsize = fpath.stat().st_size
    fhash = _sha256(str(fpath))

    # Prepare
    try:
        resp = requests.post(
            f"{base_url}/osms/v1/file/manager/prepare",
            headers=headers,
            json={
                "objectType": object_type,
                "fileName": fpath.name,
                "fileSha256": fhash,
                "fileSize": fsize,
                "fileOwnerInfo": {"uid": uid, "teamId": uid},
                "useEdge": False,
            },
            timeout=30,
        )
        if resp.status_code != 200:
            return ""
        data = resp.json()
        if data.get("code") not in (None, "", "0"):
            return ""
        object_id = data.get("objectId")
        draft_id = data.get("draftId")
        upload_infos = data.get("uploadInfos", [])
        if not object_id or not draft_id or not upload_infos:
            return ""
        upload_url = upload_infos[0]["url"]
        upload_method = upload_infos[0].get("method", "PUT").upper()
        upload_headers = upload_infos[0].get("headers", {"Content-Type": "application/octet-stream"})
    except Exception:
        return ""

    # Upload
    try:
        with open(str(fpath), "rb") as f:
            body = f.read()
        ur = requests.request(upload_method, upload_url, headers=upload_headers, data=body, timeout=120)
        if ur.status_code not in (200, 204):
            return ""
    except Exception:
        return ""

    # Complete
    try:
        cr = requests.post(
            f"{base_url}/osms/v1/file/manager/completeAndQuery",
            headers=headers,
            json={"objectId": object_id, "draftId": draft_id},
            timeout=30,
        )
        if cr.status_code != 200:
            return ""
        cd = cr.json()
        return cd.get("fileDetailInfo", {}).get("url", "") or ""
    except Exception:
        return ""


def _download_image(url: str) -> Optional[str]:
    """Download image from URL, save to output dir, return local path."""
    requests = _require_requests()
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        resp = requests.get(url, timeout=60, verify=False)
        resp.raise_for_status()
        path_lower = url.lower().split("?")[0]
        if path_lower.endswith(".jpg") or path_lower.endswith(".jpeg"):
            ext = ".jpg"
        elif path_lower.endswith(".webp"):
            ext = ".webp"
        elif path_lower.endswith(".gif"):
            ext = ".gif"
        else:
            ext = ".png"
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
        rand = "".join(random.choices(string.ascii_letters + string.digits, k=2))
        out = _OUT_DIR / f"huawei_{ts}_{rand}{ext}"
        out.write_bytes(resp.content)
        return str(out)
    except Exception:
        return None


# ── public API ──────────────────────────────────────────────

def provider_env() -> Dict[str, Any]:
    """Return Huawei provider environment status."""
    file_env = _read_xiaoyi_env()
    url = (
        os.environ.get("SERVICE_URL")
        or file_env.get("SERVICE_URL", "")
    )
    uid = (
        os.environ.get("PERSONAL_UID")
        or os.environ.get("PERSONAL-UID")
        or file_env.get("PERSONAL_UID", "")
        or file_env.get("PERSONAL-UID", "")
    )
    api_key = (
        os.environ.get("PERSONAL_API_KEY")
        or os.environ.get("PERSONAL-API-KEY")
        or file_env.get("PERSONAL_API_KEY", "")
        or file_env.get("PERSONAL-API-KEY", "")
    )
    return {
        "url": url,
        "uid": uid,
        "api_key": api_key,
        "_debug": {
            "provider_url_present": bool(url),
            "api_key_present": bool(api_key),
            "uid_present": bool(uid),
            "provider_ready": bool(url and api_key and uid),
            "api_key_masked": _mask_key(api_key),
            "uid_masked": _mask_key(uid) if uid else "",
            "missing": [
                k for k, v in {
                    "SERVICE_URL": bool(url),
                    "PERSONAL_API_KEY": bool(api_key),
                    "PERSONAL_UID": bool(uid),
                }.items()
                if not v
            ],
            "env_file_checked": str(Path.home() / ".openclaw" / ".xiaoyienv"),
            "model": "seedreamBatch5 (Huawei Cloud)",
            "provider": "huawei_xiaoyi",
        },
    }


def provider_ready() -> bool:
    env = provider_env()
    return bool(env.get("url") and env.get("api_key") and env.get("uid"))


def generate_image(
    prompt: str,
    input_image: str = "",
    size: str = "2K",
    watermark: bool = True,
    max_images: int | None = None,
    reference_weight: int = 90,
) -> Dict[str, Any]:
    """Call the Huawei/Xiaoyi image generation API via SSE skill execute.

    Returns:
        dict with keys: status, generated_image_path, generated_image_paths, etc.
    """
    env = provider_env()
    if not env.get("url") or not env.get("api_key") or not env.get("uid"):
        return {
            "status": "provider_not_ready",
            "reason": "missing_credentials",
            "missing": env.get("_debug", {}).get("missing", []),
            "provider": "huawei_xiaoyi",
            "generated_image_path": None,
            "generated_image_paths": [],
        }

    requests = _require_requests()
    trace_id = str(uuid.uuid4())
    api_url = f"{env['url'].rstrip('/')}/celia-claw/v1/sse-api/skill/execute"

    headers = {
        "Content-Type": "application/json",
        "x-skill-id": "seedream",
        "x-hag-trace-id": trace_id,
        "x-uid": env["uid"],
        "x-api-key": env["api_key"],
        "x-request-from": "openclaw",
    }

    content: Dict[str, Any] = {
        "prompt": prompt,
        "size": size,
        "watermark": watermark,
        "response_format": "url",
    }

    if input_image:
        if _is_remote_url(input_image):
            content["reference_images"] = input_image
        else:
            uploaded = _upload_file(input_image)
            if uploaded:
                content["reference_images"] = uploaded
        content["reference_weight"] = reference_weight

    if max_images is not None:
        content["max_images"] = max_images

    payload = {
        "actions": [
            {
                "actionExecutorTask": {
                    "actionName": "seedreamBatch5",
                    "content": content,
                    "pluginId": "abf9388fed6b4df89daac71be85fc62c",
                    "replyCard": False,
                },
                "actionSn": "81ef5ac1b5e74e85b90832503ea34a07",
            }
        ],
        "endpoint": {
            "countryCode": "",
            "device": {
                "deviceId": "5682d99dbb90973b775b7e9bf774ff9f",
                "phoneType": "2in1",
                "prdVer": "11.6.2.202",
            },
        },
        "session": {
            "interactionId": "0",
            "isNew": False,
            "sessionId": "xxx",
        },
        "utterance": {"original": "", "type": "text"},
        "version": "1.0",
    }

    image_urls: List[str] = []
    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=180, verify=False, stream=True)
        response.raise_for_status()

        for line in response.iter_lines():
            if not line:
                continue
            line_str = line.decode("utf-8")
            if not line_str.startswith("data:"):
                continue
            json_str = line_str[5:].strip()
            if not json_str:
                continue
            try:
                result = json.loads(json_str)
            except json.JSONDecodeError:
                continue
            ability_infos = result.get("abilityInfos", [])
            if not ability_infos:
                continue
            aer = ability_infos[0].get("actionExecutorResult", {})
            if aer.get("code") not in (None, "", "0"):
                continue
            reply = aer.get("reply", {})
            stream_info = reply.get("streamInfo", {})
            if stream_info.get("streamType") != "final":
                continue
            items = reply.get("items", [])
            if items:
                image_urls = items
            break

        if not image_urls:
            return {
                "status": "provider_returned_no_image",
                "provider": "huawei_xiaoyi",
                "generated_image_path": None,
                "generated_image_paths": [],
            }

        # Download all images
        paths: List[str] = []
        for url in image_urls:
            p = _download_image(url)
            if p:
                paths.append(p)

        result: Dict[str, Any] = {
            "status": "generated" if paths else "provider_returned_no_image",
            "provider": "huawei_xiaoyi",
            "model": "seedreamBatch5",
            "image_count": len(image_urls),
            "downloaded_count": len(paths),
            "generated_image_path": paths[0] if paths else None,
            "generated_image_paths": paths,
        }
        return result

    except Exception as e:
        return {
            "status": "provider_exception",
            "error": str(e)[:200],
            "provider": "huawei_xiaoyi",
            "generated_image_path": None,
            "generated_image_paths": [],
        }
