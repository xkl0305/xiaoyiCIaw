from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
removed = 0
for pat in ["**/__pycache__", "**/*.pyc", ".pytest_cache"]:
    for p in ROOT.glob(pat):
        try:
            if p.is_dir():
                import shutil
                shutil.rmtree(p)
            else:
                p.unlink()
            removed += 1
        except Exception:
            pass
print({"removed": removed})
