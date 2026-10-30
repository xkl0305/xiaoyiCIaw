"""Stable entrypoint for the bundled MuseAI CLI.

The Xiaoyi sandbox may execute commands from an unrelated working directory,
so import the sibling package by absolute script location.
"""

from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
RUNTIME_ARCHIVE = SCRIPT_DIR / "muse_runtime.zip"
sys.path.insert(0, str(RUNTIME_ARCHIVE if RUNTIME_ARCHIVE.is_file() else SCRIPT_DIR))

from muse.cli import main  # noqa: E402


if __name__ == "__main__":
    sys.exit(main())
