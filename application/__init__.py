from __future__ import annotations
"""Root application facade.

The canonical implementation lives under ``execution.application``.  This root
package is a compatibility entrypoint for older imports that still use
``application.*``.
"""

try:
    from execution.application import *  # noqa: F401,F403
except Exception:
    pass
