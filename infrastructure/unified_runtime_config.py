from __future__ import annotations
import os, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPENCLAW_JSON = ROOT / 'openclaw.json'

# V111.24: daily runtime is online-connected by default.
# High-risk side effects are governed by confirmation gates, not by offline blanket bans.
DEFAULTS = {
    'ONLINE_MODE': True,
    'OFFLINE_MODE': False,
    'NO_EXTERNAL_API': False,
    'DISABLE_LLM_API': False,
    'DISABLE_THINKING_MODE': False,
    'NO_REAL_SEND': False,
    'NO_REAL_PAYMENT': False,
    'NO_REAL_DEVICE': False,
    'bootstrapMaxChars': 8000,
    'bootstrapTotalMaxChars': 32000,
    'contextInjection': 'always',
}

_TRUE = {'1','true','yes','on','y'}
_FALSE = {'0','false','no','off','n'}

def _coerce(v):
    if isinstance(v, str):
        lv = v.strip().lower()
        if lv in _TRUE: return True
        if lv in _FALSE: return False
    return v

class UnifiedRuntimeConfig:
    def __init__(self, root: Path | None = None):
        self.root = root or ROOT
        self.file_config = self._read_file()

    def _read_file(self):
        p = self.root / 'openclaw.json'
        if not p.exists():
            return {}
        try:
            data = json.loads(p.read_text(encoding='utf-8'))
            return data if isinstance(data, dict) else {}
        except Exception as e:
            return {'_read_error': str(e)}

    def get(self, key: str, default=None):
        if key in os.environ:
            return _coerce(os.environ[key])
        # top-level openclaw.json wins; nested runtime is fallback only.
        for container in (self.file_config, self.file_config.get('runtime', {}) if isinstance(self.file_config, dict) else {}):
            if isinstance(container, dict) and key in container:
                return _coerce(container[key])
        return DEFAULTS.get(key, default)

    def is_online(self) -> bool:
        return bool(self.get('ONLINE_MODE', True)) and not bool(self.get('OFFLINE_MODE', False))

    def is_offline(self) -> bool:
        return not self.is_online()

    def no_real_side_effects(self) -> bool:
        return bool(self.get('NO_REAL_SEND', False)) or bool(self.get('NO_REAL_PAYMENT', False)) or bool(self.get('NO_REAL_DEVICE', False))

    def context_budget(self):
        return {
            'bootstrapMaxChars': int(self.get('bootstrapMaxChars', 8000) or 8000),
            'bootstrapTotalMaxChars': int(self.get('bootstrapTotalMaxChars', 32000) or 32000),
            'contextInjection': self.get('contextInjection', 'always'),
            'p0_never_trim': ['safety_red_lines','current_goal','user_preferences','recent_failures','forbidden_actions'],
            'p1_priority': ['persona_state','relationship_summary','available_tools','session_handoff'],
            'p2_trim_allowed': ['old_report_details','vintage_version_details','long_explanations'],
        }

    def summary(self):
        return {
            'online_mode': self.is_online(),
            'offline_mode': self.is_offline(),
            'no_external_api': bool(self.get('NO_EXTERNAL_API', False)),
            'disable_llm_api': bool(self.get('DISABLE_LLM_API', False)),
            'disable_thinking_mode': bool(self.get('DISABLE_THINKING_MODE', False)),
            'no_real_send': bool(self.get('NO_REAL_SEND', False)),
            'no_real_payment': bool(self.get('NO_REAL_PAYMENT', False)),
            'no_real_device': bool(self.get('NO_REAL_DEVICE', False)),
            'no_real_side_effects': self.no_real_side_effects(),
            'runtime_mode': 'online_connected',
            'side_effect_policy': (self.file_config.get('realSideEffectPolicy') if isinstance(self.file_config, dict) else None) or {'mode':'online_connected_strong_confirmation'},
            'context_budget': self.context_budget(),
        }

def get_runtime_config() -> UnifiedRuntimeConfig:
    return UnifiedRuntimeConfig()
