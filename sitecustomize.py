from __future__ import annotations

# V111.51.23 with-skills guard: only install no-skills compatibility facade
# when the physical skills/ directory is absent.
try:
    from pathlib import Path as _Path
    _ROOT = _Path(__file__).resolve().parent
    if not (_ROOT / 'skills').exists():
        from infrastructure.no_skills_compat import install as _dlx_install_no_skills_compat
        _dlx_install_no_skills_compat()
except Exception:
    pass

import os
try:
    if os.environ.get('DALONGXIA_DISABLE_PERSONA_VISUAL_AUTOINSTALL') != '1':
        from infrastructure.persona_visual_reply_outlet import install_auto_hooks
        install_auto_hooks()
except Exception:
    pass

# Map PERSONAL-API-KEY from .xiaoyienv to SEEDREAM_API_KEY for persona visual auto-generation
try:
    env_path = os.path.expanduser('~/.openclaw/.xiaoyienv')
    if os.path.isfile(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith('PERSONAL-API-KEY='):
                    api_key = line.split('=', 1)[1].strip()
                    if api_key:
                        os.environ['SEEDREAM_API_KEY'] = api_key
                        break
except Exception:
    pass
