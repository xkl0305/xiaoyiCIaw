from __future__ import annotations
"""Compatibility module for V111 no-skills packages.

This is intentionally a single file, not a physical ``skills/`` directory.  It
installs in-memory ``skills.*`` submodules for legacy imports while preserving
``not Path('skills').exists()`` package-mode checks.
"""

from infrastructure.no_skills_compat import install as _install_no_skills_compat

_result = _install_no_skills_compat()
__path__ = []  # make this module behave as a package for skills.* imports
__no_physical_skills__ = True
__compat_result__ = _result
