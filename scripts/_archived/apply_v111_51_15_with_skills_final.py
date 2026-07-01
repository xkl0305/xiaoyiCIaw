from __future__ import annotations
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
VERSION = 'V111.51.15_LEGACY_GUARD_IMPORT_ORDER_FINAL_WITH_SKILLS'


def _run_base_apply() -> None:
    base = ROOT / 'scripts/apply_v111_51_15_legacy_guard_import_order_final.py'
    if base.exists():
        subprocess.run([sys.executable, '-S', str(base)], cwd=str(ROOT), check=True)


def _ensure_lazy_requests_helper(text: str) -> str:
    if 'def _require_requests():' not in text:
        marker = '}\n\ndef read_xiaoyienv():'
        helper = '''}\n\ndef _require_requests():\n    try:\n        import requests  # type: ignore\n        return requests\n    except ModuleNotFoundError as e:\n        raise RuntimeError(\n            "requests dependency is required only for non-persona legacy network calls; "\n            "persona visual requests are blocked before this point"\n        ) from e\n\n\ndef read_xiaoyienv():'''
        if marker in text:
            text = text.replace(marker, helper, 1)
    return text


def _patch_legacy_lazy_requests(path: Path) -> bool:
    original = path.read_text(encoding='utf-8')
    text = original
    text = _ensure_lazy_requests_helper(text)
    # top-level requests import must stay disabled, but non-persona paths may lazy import through helper.
    text = re.sub(r'(?m)^import\s+requests\s*$', '# import requests  # V111.51.15 lazy import only after persona guard', text)
    text = re.sub(r'(?m)^from\s+requests\s+import\s+([^\n]+)$', r'# from requests import \1  # V111.51.15 lazy import only after persona guard', text)
    # Ensure upload_file has local requests variable.
    text = text.replace('    try:\n        # 校验文件存在\n', '    try:\n        requests = _require_requests()\n        # 校验文件存在\n', 1)
    # Ensure generate_image imports requests after guard, not before.
    if 'def generate_image(' in text and 'requests = _require_requests()\n    """Call the Xiaoyi image generation API."""' not in text:
        text = text.replace(
            '    if _legacy_blocked:\n        return _legacy_blocked\n    """Call the Xiaoyi image generation API."""\n',
            '    if _legacy_blocked:\n        return _legacy_blocked\n    requests = _require_requests()\n    """Call the Xiaoyi image generation API."""\n',
            1,
        )
    # Ensure download_image lazy imports requests.
    if 'def download_image(' in text and 'requests = _require_requests()\n        response = requests.get' not in text:
        text = text.replace(
            '    try:\n        response = requests.get(url, timeout=60, verify=False)\n',
            '    try:\n        requests = _require_requests()\n        response = requests.get(url, timeout=60, verify=False)\n',
            1,
        )
    text = text.replace('blocked_reason=小艺自身形象图必须走 PersonaVisualController 主链', 'blocked_reason=鸽子王人格视觉请求必须走 PersonaVisualController 主链')
    text = text.replace("'小艺站在窗边', '小艺坐在床边', '小艺从门后探头',\n        '小艺', '鸽子王',", "'鸽子王站在窗边', '鸽子王坐在床边', '鸽子王从门后探头',\n        '鸽子王',")
    if text != original:
        path.write_text(text, encoding='utf-8')
        return True
    return False


def main() -> int:
    print(f'[INFO] applying {VERSION}')
    _run_base_apply()
    scripts = [p for p in ROOT.rglob('generate_seedream_legacy_v11146.py') if '__pycache__' not in str(p)]
    patched = []
    for p in scripts:
        if _patch_legacy_lazy_requests(p):
            patched.append(str(p.relative_to(ROOT)))
    print(f'[OK] physical legacy scripts found={len(scripts)} lazy_requests_patched={len(patched)}')
    for p in patched:
        print(f'[PATCHED] {p}')
    print('[OK] with-skills final overlay applied')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
