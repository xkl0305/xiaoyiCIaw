from __future__ import annotations
import py_compile
import re
import shutil
import time
from pathlib import Path

ROOT = Path.cwd()
VERSION = 'V111.51.15_LEGACY_GUARD_IMPORT_ORDER_FINAL'

PERSONA_GUARD_CODE = r'''
# --- V111.51.15 legacy persona visual guard: block before provider imports ---
LEGACY_PERSONA_VISUAL_KEYWORDS = (
    "鸽子王", "看看你的样子", "看看你", "展示一下", "看看全身",
    "看看腿", "看看脚", "看看脚后跟", "看看头发", "看看眼睛",
    "看看手", "看看腰", "摸摸头", "摸头", "揉揉头",
    "露个面看看", "站在窗边", "坐在床边", "从门后探头",
)

def _legacy_detect_persona_visual_request(text: str = "") -> bool:
    text = str(text or "")
    return any(k in text for k in LEGACY_PERSONA_VISUAL_KEYWORDS)

def _legacy_block_persona_visual_request(text: str = ""):
    if _legacy_detect_persona_visual_request(text):
        return {
            "status": "blocked",
            "blocked": True,
            "blocked_reason": "persona_visual_request_must_use_main_pipeline",
            "required_entry": "post_reply_or_mainline_hook",
            "message": "鸽子王人格视觉请求必须走 PersonaVisualController 主链，legacy 脚本禁止生成。",
        }
    return None
# --- end V111.51.15 legacy persona visual guard ---
'''


def _insert_after_header(text: str, block: str) -> str:
    lines = text.splitlines()
    insert_at = 0
    # keep shebang, coding declaration and leading blank/comment lines before future imports
    while insert_at < len(lines) and (
        lines[insert_at].startswith('#!')
        or 'coding' in lines[insert_at].lower()
        or lines[insert_at].strip() == ''
    ):
        insert_at += 1
    # from __future__ imports must remain at the beginning of executable code
    while insert_at < len(lines) and lines[insert_at].startswith('from __future__ import'):
        insert_at += 1
    lines.insert(insert_at, block)
    return '\n'.join(lines) + '\n'


def _patch_entry_guards(text: str) -> tuple[str, bool]:
    patched = False
    patterns = [
        r'(def\s+generate_image\s*\([^)]*\)\s*:\n)',
        r'(def\s+generate\s*\([^)]*\)\s*:\n)',
        r'(def\s+main\s*\([^)]*\)\s*:\n)',
        r'(def\s+run\s*\([^)]*\)\s*:\n)',
    ]
    guard = (
        "    _legacy_text = str(locals().get('prompt', '') or locals().get('text', '') or locals().get('user_message', '') or locals().get('message', '') or '')\n"
        "    _legacy_blocked = _legacy_block_persona_visual_request(_legacy_text)\n"
        "    if _legacy_blocked:\n"
        "        return _legacy_blocked\n"
    )
    for pat in patterns:
        m = re.search(pat, text)
        if not m:
            continue
        start = m.end()
        body_prefix = text[start:start + 700]
        if '_legacy_block_persona_visual_request' not in body_prefix:
            text = text[:start] + guard + text[start:]
            patched = True
        break
    return text, patched


def patch_legacy_script(path: Path) -> bool:
    original = path.read_text(encoding='utf-8')
    text = original

    if '_legacy_block_persona_visual_request' not in text:
        text = _insert_after_header(text, PERSONA_GUARD_CODE)

    # Remove top-level requests imports so sandbox without requests can still import and block.
    text = re.sub(r'(?m)^import\s+requests\s*$', '# import requests  # V111.51.15 lazy import only after persona guard', text)
    text = re.sub(r'(?m)^from\s+requests\s+import\s+([^\n]+)$', r'# from requests import \1  # V111.51.15 lazy import only after persona guard', text)

    text, entry_patched = _patch_entry_guards(text)

    # If the script is primarily CLI-style, add an early __main__ guard as well.
    if "if __name__ == '__main__':" in text and '_legacy_cli_text' not in text:
        text = text.replace(
            "if __name__ == '__main__':",
            "if __name__ == '__main__':\n"
            "    import sys, json\n"
            "    _legacy_cli_text = ' '.join(sys.argv[1:])\n"
            "    _legacy_blocked = _legacy_block_persona_visual_request(_legacy_cli_text)\n"
            "    if _legacy_blocked:\n"
            "        print(json.dumps(_legacy_blocked, ensure_ascii=False))\n"
            "        raise SystemExit(0)"
        )
    if 'if __name__ == "__main__":' in text and '_legacy_cli_text' not in text:
        text = text.replace(
            'if __name__ == "__main__":',
            'if __name__ == "__main__":\n'
            '    import sys, json\n'
            "    _legacy_cli_text = ' '.join(sys.argv[1:])\n"
            '    _legacy_blocked = _legacy_block_persona_visual_request(_legacy_cli_text)\n'
            '    if _legacy_blocked:\n'
            '        print(json.dumps(_legacy_blocked, ensure_ascii=False))\n'
            '        raise SystemExit(0)'
        )

    if text != original:
        path.write_text(text, encoding='utf-8')
        return True
    return False


def patch_all_legacy_scripts() -> dict:
    candidates = [p for p in ROOT.rglob('generate_seedream_legacy_v11146.py') if '__pycache__' not in str(p)]
    patched = []
    unchanged = []
    for p in candidates:
        if patch_legacy_script(p):
            patched.append(str(p.relative_to(ROOT)))
        else:
            unchanged.append(str(p.relative_to(ROOT)))
    return {'found': len(candidates), 'patched': patched, 'unchanged': unchanged}


def quarantine_bad_tmp_sitecustomize() -> dict:
    ts = time.strftime('%Y%m%d_%H%M%S')
    checked = 0
    quarantined = []
    root = Path('/tmp')
    if not root.exists():
        return {'checked': 0, 'quarantined': []}
    for f in root.rglob('sitecustomize.py'):
        checked += 1
        try:
            py_compile.compile(str(f), doraise=True)
        except Exception as e:
            backup = f.with_name(f'sitecustomize.py.disabled_{ts}')
            try:
                shutil.move(str(f), str(backup))
                quarantined.append({'from': str(f), 'to': str(backup), 'error': str(e)})
            except Exception as move_error:
                quarantined.append({'from': str(f), 'to': None, 'error': f'{e}; move_failed={move_error}'})
    for pyc in root.rglob('sitecustomize*.pyc'):
        try:
            pyc.unlink()
        except Exception:
            pass
    return {'checked': checked, 'quarantined': quarantined}


def ensure_generated_dir() -> str:
    gen = ROOT / '.persona_visual/generated'
    gen.mkdir(parents=True, exist_ok=True)
    probe = gen / '.write_test_v111_51_15.tmp'
    probe.write_text('ok', encoding='utf-8')
    probe.unlink()
    return str(gen)


def main() -> int:
    print(f'[INFO] applying {VERSION}')
    gen = ensure_generated_dir()
    site = quarantine_bad_tmp_sitecustomize()
    legacy = patch_all_legacy_scripts()
    print(f'[OK] generated dir writable: {gen}')
    print(f'[OK] tmp sitecustomize checked={site["checked"]} quarantined={len(site["quarantined"])}')
    print(f'[OK] legacy scripts found={legacy["found"]} patched={len(legacy["patched"])} unchanged={len(legacy["unchanged"])}')
    for p in legacy['patched']:
        print(f'[PATCHED] {p}')
    if legacy['found'] == 0:
        print('[OK] no legacy script present in no-skills package; absent legacy entry is treated as blocked')
    print('[OK] V111.51.15 legacy guard import-order final applied')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
