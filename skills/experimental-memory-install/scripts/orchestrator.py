#!/usr/bin/env python3
"""
orchestrator.py — experimental-memory-install skill orchestrator.

Modes:
  --mode=plan      Print bilingual `[PLAN]` summary; exit 0. Read-only.
  --mode=execute   Real install. Reads a local pre-staged tarball and then
                   runs the platform install hook. Requires --confirmed.
  --mode=reboot    Restart services / reload runtime. Requires --confirmed.

Common args:
  --version=v2026-04-30           pin version from the local cache
  --remote                        rejected for celiaclaw offline install
  --channel=stable|rc|dev         rejected for celiaclaw offline install
  --dev                           rejected for celiaclaw offline install
  --offline                       local tarball cache (default)
  --source=local-dir <path>       local dev dir, pick newest matching tarball
  --platform=openclaw|celiaclaw|celiapro
                                  override platform auto-detection
  --strict-contract               refuse fallback for pre-contract artifacts
  --skip-claw-skills              do not prompt to copy tool-skills into Claw
  --lang=zh|en                    language for [PROMPT_*] / [PLAN] strings
  --confirmed                     required for execute / reboot

Exit codes:
  0   success
  10  arg error
  20  network failure
  30  sha verification failure
  40  extract failure
  50  platform install hook failure (non-zero exit from scripts/install.sh)
  60  contract / version compat refused
  70  lock contention / disk space refusal
  99  internal error
"""
from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import json
import os
import platform as platform_mod
import re
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


# ============================================================================
# Bilingual messages — keep paired (zh/en) so we never drift.
# Skill SKILL.md sets --lang from conversation locale; default falls to en.
# ============================================================================

MSG = {
    "plan_header": {
        "zh": "[PLAN] 安装计划如下：",
        "en": "[PLAN] Install plan:",
    },
    "plan_target_version": {
        "zh": "  目标版本: {v}",
        "en": "  target version: {v}",
    },
    "plan_install_root": {
        "zh": "  安装目录: {p}",
        "en": "  install root: {p}",
    },
    "plan_will_download": {
        "zh": "  下载: {url} (约 {sz} bytes, sha256={sha})",
        "en": "  download: {url} ({sz} bytes, sha256={sha})",
    },
    "plan_tarball_dir": {
        "zh": "  tarball 缓存目录: {p}（保留供后续本地安装复用）",
        "en": "  tarball cache dir: {p} (kept for later local installs)",
    },
    # Local-dir source plan lines, picked by `source_label` set in the plan.
    # `dev`     — caller passed --source <path> (dev workflow)
    # `offline` — default local source or caller passed --offline (read
    #             from tarball cache dir, typical for production-image /
    #             no-network installs)
    "plan_local_tarball_dev": {
        "zh": "  本地 tarball: {p}",
        "en": "  local tarball: {p}",
    },
    "plan_local_tarball_offline": {
        "zh": "  离线本地包: {p}（来自 tarball 缓存目录）",
        "en": "  offline local bundle: {p} (from tarball cache dir)",
    },
    "exec_using_local_tarball_dev": {
        "zh": "[INFO] 使用本地 tarball {p}",
        "en": "[INFO] using local tarball {p}",
    },
    "exec_using_local_tarball_offline": {
        "zh": "[INFO] 使用离线本地包 {p}",
        "en": "[INFO] using offline local bundle {p}",
    },
    "plan_will_run_hook": {
        "zh": "  执行平台 install hook: {p}/scripts/install.sh",
        "en": "  run platform install hook: {p}/scripts/install.sh",
    },
    "plan_hook_actions": {
        "zh": ("    hook 内部依次:复制插件 → npm install → 合并 openclaw.json"
               "(注册记忆插件) → 保持预置 AGENTS.md 不变 → "
               "改 supervisord.conf → 同步 chat 凭据 → "
               "按配置重启 openclaw-gateway"),
        "en": ("    hook will: copy plugin → npm install → merge openclaw.json "
               "(register memory plugin) → leave pre-placed AGENTS.md untouched"
               " → patch supervisord.conf → sync chat creds → "
               "restart openclaw-gateway if configured"),
    },
    "plan_disk_required": {
        "zh": "  需要磁盘: 至少 {kb} KiB（约 3× tarball 大小）",
        "en": "  disk required: at least {kb} KiB (~3× tarball size)",
    },
    "plan_fallback_warn": {
        "zh": "  ⚠ 该版本早于 contract 定义，将走 fallback 路径（{path}）",
        "en": "  ⚠ this version predates the contract; using fallback path ({path})",
    },
    "plan_strict_refused": {
        "zh": "  ✗ 该版本无 scripts/contract.toml，且 --strict-contract 已指定 → 拒绝。",
        "en": "  ✗ this version has no scripts/contract.toml, and --strict-contract was given → refused.",
    },
    "plan_footer": {
        "zh": "[/PLAN]",
        "en": "[/PLAN]",
    },
    "prompt_action_zh": {
        "zh": "[PROMPT_ZH] 确认安装？输入 yes 继续 / no 取消",
        "en": "[PROMPT_ZH] 确认安装？输入 yes 继续 / no 取消",
    },
    "prompt_action_en": {
        "zh": "[PROMPT_EN] Confirm install? Type yes to proceed / no to cancel",
        "en": "[PROMPT_EN] Confirm install? Type yes to proceed / no to cancel",
    },
    "exec_lock_busy": {
        "zh": "[ERROR] 另一个 install 正在运行中（持有 {p}）。请等待或检查残留进程。",
        "en": "[ERROR] another install is in progress (holds {p}). Wait or check for stale processes.",
    },
    "exec_disk_short": {
        "zh": "[ERROR] 磁盘空间不足: 需 {req} KiB，仅剩 {free} KiB",
        "en": "[ERROR] not enough disk space: need {req} KiB, only {free} KiB free",
    },
    "exec_downloading": {
        "zh": "[INFO] 下载中: {url}",
        "en": "[INFO] downloading: {url}",
    },
    "exec_reuse_cached": {
        "zh": "[INFO] 复用 tarball 缓存: {p}（SHA 校验通过，跳过下载）",
        "en": "[INFO] reusing cached tarball: {p} (SHA verified, skipping download)",
    },
    "exec_cache_corrupt": {
        "zh": "[WARN] 缓存损坏 (SHA 不匹配): {p} —— 重新下载",
        "en": "[WARN] cached tarball corrupt (SHA mismatch): {p} — re-downloading",
    },
    "exec_cached_at": {
        "zh": "[INFO] tarball 已缓存到: {p}（保留供后续复用）",
        "en": "[INFO] tarball cached at: {p} (kept for future reuse)",
    },
    "exec_verifying": {
        "zh": "[INFO] 校验 SHA256...",
        "en": "[INFO] verifying SHA256...",
    },
    "exec_sha_mismatch": {
        "zh": "[ERROR] SHA256 不匹配: 预期 {want}，实际 {got}",
        "en": "[ERROR] SHA256 mismatch: expected {want}, got {got}",
    },
    "exec_extracting": {
        "zh": "[INFO] 解压到 {dst}（原子模式：先到 -tmp，再 rename）",
        "en": "[INFO] extracting to {dst} (atomic: -tmp first, then rename)",
    },
    "exec_hook_running": {
        "zh": "[INFO] 调用平台 install hook: {p}",
        "en": "[INFO] running platform install hook: {p}",
    },
    "exec_hook_failed": {
        "zh": "[ERROR] 平台 install hook 失败 (rc={rc})。日志: {log}",
        "en": "[ERROR] platform install hook failed (rc={rc}). Log: {log}",
    },
    "exec_post_install_header": {
        "zh": "[POST_INSTALL]",
        "en": "[POST_INSTALL]",
    },
    "exec_install_complete": {
        "zh": "install_complete: yes  version: {v}  install_root: {p}",
        "en": "install_complete: yes  version: {v}  install_root: {p}",
    },
    "exec_post_install_footer": {
        "zh": "[/POST_INSTALL]",
        "en": "[/POST_INSTALL]",
    },
    "reboot_prompt_zh": {
        "zh": "[PROMPT_ZH] 重启会中断当前对话通道。是否现在重启 openclaw-gateway？yes / no",
        "en": "[PROMPT_ZH] 重启会中断当前对话通道。是否现在重启 openclaw-gateway？yes / no",
    },
    "reboot_prompt_en": {
        "zh": "[PROMPT_EN] Reboot will interrupt this channel. Restart openclaw-gateway now? yes / no",
        "en": "[PROMPT_EN] Reboot will interrupt this channel. Restart openclaw-gateway now? yes / no",
    },
    "reboot_done": {
        "zh": "[INFO] 已请求 supervisorctl 重启 openclaw-gateway",
        "en": "[INFO] supervisorctl restart openclaw-gateway requested",
    },
    "manual_reboot_hint": {
        "zh": "[INFO] 跳过自动重启。手动重启命令: supervisorctl restart openclaw-gateway",
        "en": "[INFO] skipping auto-reboot. To restart later: supervisorctl restart openclaw-gateway",
    },
    "version_resolved": {
        "zh": "[INFO] 解析到目标版本: {v}",
        "en": "[INFO] resolved target version: {v}",
    },
    "platform_detected": {
        "zh": "[INFO] 检测到平台: {p}",
        "en": "[INFO] detected platform: {p}",
    },
    "version_unsupported": {
        "zh": "[ERROR] 版本 {v} 既不在 supported 范围也不在 fallback 列表里。最低: {min}",
        "en": "[ERROR] version {v} is neither in supported range nor in fallback list. Min: {min}",
    },
    "contract_version_unsupported": {
        "zh": "[ERROR] tarball contract_version={ct} 不在技能 supported {sup} 内。请升级技能 bundle: cd $skills_dir && git pull",
        "en": "[ERROR] tarball contract_version={ct} not in skill supported {sup}. Upgrade the skill bundle: cd $skills_dir && git pull",
    },
}


def msg(key: str, lang: str, **kw) -> str:
    """Format a localized message; fall back to en if zh missing."""
    try:
        return MSG[key][lang].format(**kw)
    except KeyError:
        return MSG[key]["en"].format(**kw)


# ============================================================================
# Repo-level paths + compat config
# ============================================================================

SCRIPT_PATH = Path(__file__).absolute()
REAL_SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
REAL_SCRIPT_DIR = REAL_SCRIPT_PATH.parent
SKILL_ROOT = SCRIPT_PATH.parents[1]
REAL_SKILL_ROOT = REAL_SCRIPT_PATH.parents[1]
REPO_ROOT = (
    REAL_SCRIPT_PATH.parents[4]
    if len(REAL_SCRIPT_PATH.parents) > 4
    else REAL_SKILL_ROOT
)   # …/GaussPD_Skills/ when running from a full checkout.
# Module-level paths default to celiaclaw layout. The orchestrator routes
# per-platform later in build_plan / _execute_locked; for celiaclaw and
# openclaw the only difference is the leading $CELIA_CONFIG_DIR.
MEMORY_PLUGIN_ID = "memory-celia"


def _module_default_config_dir() -> Path:
    return Path(os.environ.get("CELIA_CONFIG_DIR", "/home/sandbox/.openclaw")).expanduser()

DEFAULT_INSTALL_ROOT = Path(os.environ.get("CELIA_INSTALL_ROOT", "")).expanduser() \
    if os.environ.get("CELIA_INSTALL_ROOT") \
    else (_module_default_config_dir() / "extensions" / "celia_memory")
LOG_DIR = Path(os.environ.get("CELIA_LOG_DIR", "")).expanduser() \
    if os.environ.get("CELIA_LOG_DIR") \
    else (_module_default_config_dir() / "logs" / "celia_memory")
LOCK_FILE = DEFAULT_INSTALL_ROOT / ".lock"
INSTALL_DIRS_PARENT = DEFAULT_INSTALL_ROOT / "install"  # install/<version>/, install/current, install/previous
BACKUP_DIR = DEFAULT_INSTALL_ROOT / "backups"


def load_compat() -> dict:
    candidates: list[Path] = []
    if os.environ.get("CELIA_COMPAT_VERSION_PATH"):
        candidates.append(Path(os.environ["CELIA_COMPAT_VERSION_PATH"]))
    candidates.extend([
        SCRIPT_DIR / "compat-version.toml",
        SKILL_ROOT / "compat-version.toml",
        REAL_SCRIPT_DIR / "compat-version.toml",
        REAL_SKILL_ROOT / "compat-version.toml",
        REPO_ROOT / "compat-version.toml",
        _module_default_config_dir() / "compat-version.toml",
    ])

    seen: set[Path] = set()
    for p in candidates:
        p = p.expanduser()
        if p in seen:
            continue
        seen.add(p)
        if p.exists():
            with p.open("rb") as f:
                return tomllib.load(f)
    tried = ", ".join(str(p) for p in seen)
    die(99, f"compat-version.toml missing; tried: {tried}")


# ============================================================================
# Logging / audit
# ============================================================================

def now_ts() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def audit_log(line: str, log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a") as f:
        f.write(f"[{datetime.now().isoformat(timespec='seconds')}] {line}\n")


def emit(line: str, log_path: Path | None = None) -> None:
    """Print to stderr (for human/agent visibility) + audit log if open."""
    print(line, file=sys.stderr)
    if log_path is not None:
        audit_log(line, log_path)


def die(code: int, line: str, log_path: Path | None = None) -> None:
    emit(line, log_path)
    sys.exit(code)


# ============================================================================
# Version comparator (multi-build-per-day aware)
# ============================================================================

VERSION_RE = re.compile(
    r"^v(?P<y>\d{4})-(?P<mo>\d{2})-(?P<d>\d{2})"
    # Suffixes seen in GaussPD_Artifacts:
    #   c1, c2     — promoted stable cohorts
    #   rc1..rcN   — release candidates (most current published assets)
    #   dev-<sha>  — automatic dev builds (optionally with -smoke / -<extra>)
    r"(?:-(?P<suffix>c\d+|rc\d+|dev-[0-9a-f]+(?:-[a-z0-9]+)?))?$"
)


def parse_version(v: str) -> tuple:
    """Return sortable tuple (y, mo, d, channel_rank, ordinal, raw).

    Channel rank within the same date: dev < rc < plain < c. Rationale:
    rc is "release candidate" (precedes plain daily), c is "promoted
    cohort" (succeeds plain). Unrecognized suffixes return rank=-1, which
    callers may treat as a parse failure.
    """
    m = VERSION_RE.match(v)
    if not m:
        return (0, 0, 0, -1, 0, v)
    y, mo, d = int(m["y"]), int(m["mo"]), int(m["d"])
    suffix = m["suffix"] or ""
    if not suffix:
        rank, ordinal = 2, 0     # plain daily
    elif suffix.startswith("dev"):
        rank, ordinal = 0, 0     # dev < everything
    elif suffix.startswith("rc"):
        rank, ordinal = 1, int(suffix[2:])  # rcN, ordered numerically
    elif suffix.startswith("c"):
        rank, ordinal = 3, int(suffix[1:])  # cN > plain
    else:
        rank, ordinal = -1, 0
    return (y, mo, d, rank, ordinal, v)


def cmp_version(a: str, b: str) -> int:
    pa, pb = parse_version(a), parse_version(b)
    return (pa > pb) - (pa < pb)


# ============================================================================
# Platform + glibc detection
# ============================================================================

def detect_platform(override: str | None) -> str:
    """celiaclaw / openclaw / celiapro."""
    if override:
        return override
    # celiaclaw 沙盒最稳的指纹：/home/sandbox + supervisord.conf
    if Path("/home/sandbox").is_dir() and Path("/home/sandbox/supervisord.conf").exists():
        return "celiaclaw"
    # 否则按通用 OpenClaw 推断（用户可用 --platform 显式覆盖）
    if Path(os.path.expanduser("~/.openclaw")).is_dir():
        return "openclaw"
    return "openclaw"   # safe default; install.sh will create dirs as needed


def detect_glibc() -> tuple[int, int] | None:
    """Returns (major, minor) on Linux; None on macOS/other."""
    if platform_mod.system() != "Linux":
        return None
    try:
        out = subprocess.check_output(["ldd", "--version"], text=True,
                                      stderr=subprocess.STDOUT, timeout=5)
        m = re.search(r"(\d+)\.(\d+)", out.splitlines()[0])
        return (int(m.group(1)), int(m.group(2))) if m else None
    except Exception:
        return None


def pick_libc_floor(glibc: tuple[int, int] | None) -> str:
    """Map host glibc → artifact name suffix (modern | manylinux_2_28)."""
    if glibc is None:
        # macOS / unknown — modern is fine for plugins; full variants unused on Mac
        return "modern"
    if glibc >= (2, 35):
        return "modern"
    if glibc >= (2, 28):
        return "manylinux_2_28"
    return "too_old"


# ============================================================================
# Lock + disk
# ============================================================================

class Lock:
    """Exclusive file lock under DEFAULT_INSTALL_ROOT to prevent concurrent installs."""
    def __init__(self, path: Path):
        self.path = path
        self.fh = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fh = open(self.path, "w")
        try:
            fcntl.flock(self.fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.fh.close()
            self.fh = None
            raise
        return self

    def __exit__(self, *a):
        if self.fh is not None:
            try:
                fcntl.flock(self.fh.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass
            self.fh.close()


def free_kib(path: Path) -> int:
    while not path.exists():
        path = path.parent
    st = os.statvfs(str(path))
    return (st.f_bavail * st.f_frsize) // 1024


# ============================================================================
# Remote fetch (manifest + tarball)
# ============================================================================

def http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "experimental-memory-install/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()
    except urllib.error.URLError as e:
        die(20, f"[ERROR] download failed: {url}: {e}")


# GaussPD_Artifacts 的 raw URL 被 GitCode SPA 拦截（无 auth 头会返回壳页面），
# 而 API v5 又强制 private-token。最稳的路径是 shallow git clone 后从工作树
# 直接读：本地缓存 <DEFAULT_INSTALL_ROOT>/_artifacts-mirror/，1 小时内沿用，过期再 fetch。
ARTIFACTS_CACHE = DEFAULT_INSTALL_ROOT / "_artifacts-mirror"
CACHE_MAX_AGE_SECONDS = 60 * 60   # 1h


# Sparse-checkout paths needed by the plan / fetch-manifest path. The
# heavy `releases/` subtree (where forks using local_package.sh
# --direct-push commit tarball blobs) is INTENTIONALLY excluded so
# the cold-start clone doesn't lazy-fetch tens of MB of tarballs the
# plan phase never reads. Worktree-tarball reads in the execute phase
# expand this on demand via _ensure_release_in_worktree.
_ARTIFACTS_PLAN_SPARSE_PATHS = [
    "index",
    "latest-stable.txt",
    "latest-rc.txt",
    "latest-dev.txt",
]


def _ensure_artifacts_mirror() -> Path:
    """Shallow + sparse clone (or refresh) GaussPD_Artifacts; return its worktree.

    Repo URL overridable via env CELIA_ARTIFACTS_REPO_URL — useful for forks
    that publish releases to a different mirror (e.g. when a contributor
    uses `integration/celiaclaw/local_package.sh --direct-push` to commit
    a tarball into their own GaussPD_Artifacts fork). Default points at
    upstream CayleyVanguard/GaussPD_Artifacts.

    Cold start uses --no-checkout --sparse to materialize ONLY index/ +
    latest-*.txt (~5MB / ~900 files), instead of the full ~31MB working
    tree (which `--filter=blob:none` alone would lazy-fetch on auto-checkout
    because all worktree files trigger blob fetches). Plan-phase reads
    only touch these sparse paths; the worktree-tarball path in execute
    expands sparse-checkout to add the requested release dir on demand.
    """
    repo_url = os.environ.get(
        "CELIA_ARTIFACTS_REPO_URL",
        "https://gitcode.com/CayleyVanguard/GaussPD_Artifacts.git",
    )
    if ARTIFACTS_CACHE.exists():
        try:
            current = subprocess.check_output(
                ["git", "-C", str(ARTIFACTS_CACHE), "remote", "get-url", "origin"],
                stderr=subprocess.DEVNULL, text=True,
            ).strip()
        except subprocess.CalledProcessError:
            current = ""
        if current != repo_url:
            shutil.rmtree(ARTIFACTS_CACHE, ignore_errors=True)
    if not ARTIFACTS_CACHE.exists():
        ARTIFACTS_CACHE.parent.mkdir(parents=True, exist_ok=True)
        rc = subprocess.call(
            ["git", "clone", "--depth=1", "--filter=blob:none",
             "--no-checkout", "--sparse", repo_url, str(ARTIFACTS_CACHE)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        if rc != 0:
            die(20, f"[ERROR] git clone artifacts mirror failed (rc={rc})")
        # Cone-mode sparse-checkout limited to the small subset plan needs.
        subprocess.call(
            ["git", "-C", str(ARTIFACTS_CACHE), "sparse-checkout", "init", "--cone"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        subprocess.call(
            ["git", "-C", str(ARTIFACTS_CACHE), "sparse-checkout", "set",
             *_ARTIFACTS_PLAN_SPARSE_PATHS],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        subprocess.call(
            ["git", "-C", str(ARTIFACTS_CACHE), "checkout", "main"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return ARTIFACTS_CACHE
    # Refresh if stale
    head_path = ARTIFACTS_CACHE / ".git" / "FETCH_HEAD"
    age = time.time() - head_path.stat().st_mtime if head_path.exists() else 1e9
    if age > CACHE_MAX_AGE_SECONDS:
        subprocess.call(
            ["git", "-C", str(ARTIFACTS_CACHE), "fetch", "--depth=1", "origin", "main"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        subprocess.call(
            ["git", "-C", str(ARTIFACTS_CACHE), "reset", "--hard", "origin/main"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    return ARTIFACTS_CACHE


def _ensure_release_in_worktree(mirror: Path, version: str) -> bool:
    """Add `releases/<version>/` to sparse-checkout so the worktree-first
    tarball read path in _execute_locked can find the file. No-op (and
    returns the dir's existence as-is) when the cache wasn't cloned in
    sparse mode (legacy caches from before the sparse optimization). Cone
    mode's `sparse-checkout add` is incremental — already-present paths
    are kept.
    """
    if (mirror / ".git" / "info" / "sparse-checkout").exists():
        subprocess.call(
            ["git", "-C", str(mirror), "sparse-checkout", "add",
             f"releases/{version}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    return (mirror / "releases" / version).is_dir()


def fetch_pointer(remote: dict, channel: str) -> str:
    """Read latest-{stable,rc,dev}.txt → version string."""
    mirror = _ensure_artifacts_mirror()
    fn_map = {
        "stable": "latest-stable.txt",
        "rc":     "latest-rc.txt",
        "dev":    "latest-dev.txt",
    }
    fn = fn_map.get(channel, "latest-stable.txt")
    p = mirror / fn
    if not p.exists():
        die(20, f"[ERROR] pointer file missing in mirror: {p}")
    return p.read_text().strip()


def fetch_manifest(remote: dict, version: str, plat: str, arch: str) -> dict:
    """Read index/<v>/<plat>/<arch>/manifest.toml → parsed dict."""
    mirror = _ensure_artifacts_mirror()
    p = mirror / "index" / version / plat / arch / "manifest.toml"
    if not p.exists():
        die(20, f"[ERROR] manifest missing in mirror: {p}")
    with p.open("rb") as f:
        return tomllib.load(f)


def pick_artifact(manifest: dict, want_artifact: str) -> dict:
    """Find the [[artifact]] entry matching want_artifact (e.g. 'plugins', 'full')."""
    for a in manifest.get("artifact", []):
        if a.get("artifact") == want_artifact:
            return a
    raise KeyError(f"no artifact '{want_artifact}' in manifest")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


# ============================================================================
# Local-source mode
# ============================================================================

def _local_tarball_candidates(local_dir: Path, plat: str, arch: str,
                              version: str | None = None) -> list[Path]:
    """Return newest matching local tarballs under local_dir."""
    version_glob = version if version else "*"
    return sorted(
        local_dir.glob(f"celia_memory.{version_glob}.{plat}.{arch}.*.tar.gz"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def find_local_tarball(local_dir: Path, plat: str, arch: str,
                       version: str | None = None) -> Path:
    """Pick the newest matching local tarball under local_dir."""
    candidates = _local_tarball_candidates(local_dir, plat, arch, version)
    if not candidates:
        suffix = f" version={version}" if version else ""
        die(10, f"[ERROR] no matching tarball under {local_dir} "
                f"for {plat}/{arch}{suffix}")
    return candidates[0]


# ============================================================================
# Extraction (atomic)
# ============================================================================

def safe_extract(tarball: Path, dst: Path) -> None:
    """Extract atomically: tar to <dst>-tmp/, then rename to <dst>/.

    Refuses to extract members whose path escapes dst (path traversal guard).
    """
    tmp = dst.parent / (dst.name + "-tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    with tarfile.open(tarball, "r:gz") as tf:
        for member in tf.getmembers():
            target = (tmp / member.name).resolve()
            if not str(target).startswith(str(tmp.resolve())):
                raise RuntimeError(f"refusing to extract outside dst: {member.name}")
        tf.extractall(tmp)   # nosec — guard above; no Python 3.12 filter for compat
    # tarball wraps everything in one top-level dir like
    # `celia_memory_<v>_<plat>_<arch>/`; strip it so dst is the content root.
    children = list(tmp.iterdir())
    if len(children) == 1 and children[0].is_dir():
        inner = children[0]
        for item in inner.iterdir():
            shutil.move(str(item), str(tmp / item.name))
        inner.rmdir()
    if dst.exists():
        shutil.rmtree(dst)
    tmp.rename(dst)


# ============================================================================
# openclaw.json placeholder resolution (post-extract / post-merge)
# ============================================================================
#
# Tarball ships openclaw.json with `serverBinaryPath` written as the literal
# string `${CELIA_INSTALL_ROOT}/bin/celia_memory_mcp_server`. The platform install.sh
# `patch_openclaw_config` step merges that string into the production
# openclaw.json verbatim — but the matching `CELIA_INSTALL_ROOT` env var is
# never written to any persistent surface (no `~/.bashrc` line, no
# `[program:openclaw-gateway] environment=` token in supervisord.conf). The
# install.sh's only `environment=` injections are CURL_CA_BUNDLE,
# CELIA_LOG_FILE, OPENAI_CHAT_*, and CELIA_CHAT_UID — `CELIA_INSTALL_ROOT` is
# absent.
#
# Effect: openclaw-gateway restarts cleanly, agent reports "services
# restarted: yes", but the moment gateway actually tries to spawn the MCP
# server using the path from openclaw.json, the placeholder expands to
# empty (or stays literal, depending on the gateway's parser) → the spawn
# fails → no MCP server, no `celia_memory.db`, no working memory plugin.
# The user has to set CELIA_INSTALL_ROOT by hand and restart again.
#
# Skill-side fix: resolve the placeholder *inside the JSON* both before the
# hook merges (so fresh installs get a concrete absolute path written into
# production openclaw.json) and after (so reinstalls over a previously
# broken config self-heal — `patch_openclaw_config` won't overwrite an
# existing memory-celia entry, so the pre-hook step alone isn't enough).


def _celia_install_root_value(install_root: Path) -> str:
    """The active value to substitute for `${CELIA_INSTALL_ROOT}`.

    Returns the `install/current` symlink path (NOT install_root, which is
    version-pinned). With the new layout the celiaclaw install hook lifts
    contents from `openclaw/` to install_root top level, so binaries live
    at `<install_root>/bin/celia_memory_mcp_server`. By writing `current` into
    openclaw.json + supervisord.conf instead of the version-pinned dir, an
    upgrade only has to swing the `current` symlink — no rewrite of those
    consumer configs needed, and a hook failure that doesn't swing leaves
    `current` still pointing at the previous good version (= self-healing
    rollback for the binary path layer).

    `install_root` is unused in the return but kept in the signature for
    backward compatibility with any caller threading a per-install dir.
    """
    del install_root  # silence unused warning; kept in signature for compat
    return str(INSTALL_DIRS_PARENT / "current")


def _staging_install_root_value(install_root: Path) -> str:
    """Return the version-pinned root used while the hook is still running."""
    return str(install_root)


def _substitute_install_root_in_json(json_path: Path,
                                     install_root: Path,
                                     log_path: Path | None = None,
                                     install_root_value: str | None = None) -> bool:
    """Replace `${CELIA_INSTALL_ROOT}` literals in three Celia-owned subtrees:

      - `plugins.load.paths`             (load order references)
      - `plugins.entries.memory-celia`    (runtime config, incl. serverBinaryPath)
      - `plugins.installs.memory-celia`   (install-record sourcePath/installPath)

    Why JSON-aware (not blanket text replace): keep the substitution
    contained to memory-celia's footprint, so we don't mutate other
    plugins' incidental same-named placeholders, and so the JSON stays
    well-formed. Idempotent: a clean file (no placeholder) is a no-op.

    Returns True iff anything changed.
    """
    if not json_path.exists():
        return False
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        if log_path is not None:
            emit(f"[WARN] cannot parse {json_path} for placeholder fix: {e}",
                 log_path)
        return False

    placeholder = "${CELIA_INSTALL_ROOT}"
    replacement = install_root_value or _celia_install_root_value(install_root)
    changed = False

    def _walk(node):
        nonlocal changed
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(v, str) and placeholder in v:
                    node[k] = v.replace(placeholder, replacement)
                    changed = True
                else:
                    _walk(v)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                if isinstance(v, str) and placeholder in v:
                    node[i] = v.replace(placeholder, replacement)
                    changed = True
                else:
                    _walk(v)

    plugins = data.get("plugins") if isinstance(data.get("plugins"), dict) else {}
    # 1. plugins.entries.memory-celia (full subtree — includes nested config)
    entry = plugins.get("entries", {}).get("memory-celia")
    if isinstance(entry, dict):
        _walk(entry)
    # 2. plugins.installs.memory-celia
    inst = plugins.get("installs", {}).get("memory-celia")
    if isinstance(inst, dict):
        _walk(inst)
    # 3. plugins.load.paths — only walk this list (not all of load.*)
    load = plugins.get("load")
    if isinstance(load, dict):
        paths = load.get("paths")
        if isinstance(paths, list):
            for i, v in enumerate(paths):
                if isinstance(v, str) and placeholder in v:
                    paths[i] = v.replace(placeholder, replacement)
                    changed = True

    if changed:
        json_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        if log_path is not None:
            emit(f"[INFO] resolved ${{CELIA_INSTALL_ROOT}} → {replacement} "
                 f"in {json_path}", log_path)
    return changed


def _detect_config_dir(plat: str) -> Path:
    """Production openclaw.json's parent dir, per-platform.

    Mirrors what the celiaclaw install.sh hook reads (matching its defaults
    so we look at the same file the hook just wrote). `CELIA_CONFIG_DIR`
    env wins when set.
    """
    env = os.environ.get("CELIA_CONFIG_DIR")
    if env:
        return Path(env).expanduser()
    if plat == "celiaclaw":
        return Path("/home/sandbox/.openclaw")
    return Path(os.path.expanduser("~/.openclaw"))


def _detect_plugin_dir(plat: str) -> Path:
    """Where the platform install hook lays the runtime artifacts
    (`bin/celia_memory_mcp_server`, `memory-plugin/`, `shared/`, `celiaclaw/`).
    Under the new layout this equals the active install root via the
    `current` symlink — i.e. `$CELIA_INSTALL_ROOT/install/current`.
    `CELIA_PLUGIN_DIR` env wins when set (orchestrator usually sets it to
    the version-pinned dir before invoking the hook so the hook writes to
    a deterministic location).
    """
    env = os.environ.get("CELIA_PLUGIN_DIR")
    if env:
        return Path(env).expanduser()
    return INSTALL_DIRS_PARENT / "current"


def _resolve_tarball_dir(plat: str, override: str | None = None) -> Path:
    """Resolve the Celia tarball cache directory for `plat`.

    This directory holds tarballs (and `.sha256` sidecars) — both ones
    pre-staged by the image-build pipeline (the default local source) and
    ones downloaded by `experimental-memory-install` from the remote channel
    (cached for reuse).

    Priority:
      1. explicit override (caller-passed, e.g. dev `--source <dir>`)
      2. $CELIA_TARBALL_DIR env (recommended)
      3. $CELIA_PREBUILT_DIR env (compatibility alias, keep honoring it
         so existing image-build scripts don't break)
      4. <_detect_config_dir(plat)>/extensions/celia_memory/package  (default)
    """
    if override:
        return Path(override).expanduser().resolve()
    env = os.environ.get("CELIA_TARBALL_DIR") or os.environ.get("CELIA_PREBUILT_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return (_detect_config_dir(plat) / "extensions" / "celia_memory" / "package").resolve()


def _prune_tarball_cache(staging_dir: Path, plat: str, keep: int,
                         log_path: Path) -> None:
    """Keep the most recent `keep` `celia_memory.*.{plat}.*.tar.gz` files
    (by mtime) under `staging_dir`; delete older ones plus their
    `.sha256` sidecars. Best-effort: failures are logged, not raised.

    Only called from the remote-download path; image-mode installs never
    prune (the operator owns that directory).
    """
    if keep <= 0:
        return
    try:
        candidates = sorted(
            staging_dir.glob(f"celia_memory.*.{plat}.*.tar.gz"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for stale in candidates[keep:]:
            try:
                stale.unlink()
            except OSError:
                continue
            sidecar = stale.with_suffix(stale.suffix + ".sha256")
            try:
                sidecar.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass
            emit(f"[INFO] pruned stale tarball {stale.name}", log_path)
    except OSError as e:
        emit(f"[WARN] tarball cache prune failed: {e}", log_path)


def _prune_install_roots(install_dirs_parent: Path, log_path: Path) -> None:
    """Keep only the dirs targeted by `current` and `previous` symlinks under
    `install_dirs_parent`; delete other version dirs. Best-effort.
    """
    try:
        keep_targets = set()
        for link_name in ("current", "previous"):
            link = install_dirs_parent / link_name
            try:
                if link.is_symlink():
                    target = link.resolve(strict=False)
                    if target.exists():
                        keep_targets.add(target)
            except OSError:
                continue
        # Snapshot the listing first; iterdir behavior under concurrent
        # rmtree of children isn't well-defined.
        try:
            entries = list(install_dirs_parent.iterdir())
        except OSError as e:
            emit(f"[WARN] install root prune: cannot list {install_dirs_parent}: {e}",
                 log_path)
            return
        for entry in entries:
            if entry.is_symlink() or not entry.is_dir():
                continue
            try:
                if entry.resolve() in keep_targets:
                    continue
            except OSError:
                continue
            shutil.rmtree(entry, ignore_errors=True)
            emit(f"[INFO] pruned old install root {entry.name}", log_path)
    except OSError as e:
        emit(f"[WARN] install root prune failed: {e}", log_path)


def _atomic_symlink_replace(link: Path, target: Path) -> None:
    """Atomically replace `link` with a symlink to `target`."""
    tmp = link.with_name(f".{link.name}.tmp.{os.getpid()}")
    if tmp.is_symlink() or tmp.exists():
        if tmp.is_dir() and not tmp.is_symlink():
            shutil.rmtree(tmp, ignore_errors=True)
        else:
            tmp.unlink()
    tmp.symlink_to(target)
    if link.exists() and not link.is_symlink():
        shutil.rmtree(link, ignore_errors=True)
    tmp.replace(link)


# Source skill dir names are deployed as-is. Keep aliases only for old tarballs
# from the short-name / celia-memory-name periods; this is compatibility, not a
# whitelist. Any new valid skill dir shipped under celiaclaw/skills/ is deployed.
_SKILL_SOURCE_ALIASES = {
    "celia-memory-install": "experimental-memory-install",
    "install-memory": "experimental-memory-install",
    "celia-memory-install-online": "experimental-memory-install-online",
    "celia-memory-upgrade": "experimental-memory-upgrade",
    "upgrade-memory": "experimental-memory-upgrade",
    "celia-memory-uninstall": "experimental-memory-uninstall",
    "uninstall-memory": "experimental-memory-uninstall",
    "celia-memory-status": "experimental-memory-status",
    "memory-status": "experimental-memory-status",
}


def _deploy_skills(install_root: Path, config_dir: Path, log_path: Path) -> None:
    """Copy celiaclaw skills from the tarball into workspace/skills.

    The Docker/celiaclaw package currently ships only experimental-memory-install,
    but this deploy step is intentionally generic: future valid skill dirs under
    celiaclaw/skills/ are deployed automatically without code changes.

    Also cleans up legacy-named bootstrap copies the user's agent may have
    dropped into workspace/skills/ before kicking off the install.
    """
    src_skills = install_root / "celiaclaw" / "skills"
    if not src_skills.is_dir():
        emit(f"[WARN] tarball ships no skills/ ({src_skills} missing); "
             f"skipping skill deploy", log_path)
        return
    dst_root = config_dir / "workspace" / "skills"
    dst_root.mkdir(parents=True, exist_ok=True)
    deployed = 0
    for src in sorted(src_skills.iterdir(), key=lambda p: p.name):
        if not src.is_dir():
            continue
        if not (src / "SKILL.md").is_file():
            emit(f"[WARN] skipping non-skill directory {src}", log_path)
            continue
        canonical = _SKILL_SOURCE_ALIASES.get(src.name, src.name)
        if canonical != src.name:
            emit(f"[INFO] tarball uses legacy skill name {src.name}; "
                 f"deploying as {canonical}", log_path)
        dst = dst_root / canonical
        if dst.is_symlink() or dst.exists():
            try:
                if dst.is_symlink() or dst.is_file():
                    dst.unlink()
                else:
                    shutil.rmtree(dst)
            except OSError as e:
                emit(f"[WARN] could not clear {dst}: {e}", log_path)
                continue
        shutil.copytree(src, dst, symlinks=True)
        emit(f"[INFO] deployed skill {canonical} → {dst}", log_path)
        deployed += 1
        # Remove any bootstrap copy left under a previous name for the same skill.
        if canonical != src.name:
            bootstrap = dst_root / src.name
            if (bootstrap.is_dir()
                    and bootstrap.resolve() != dst.resolve()):
                shutil.rmtree(bootstrap, ignore_errors=True)
                emit(f"[INFO] removed legacy bootstrap copy {bootstrap}",
                     log_path)
    if deployed == 0:
        emit(f"[WARN] no valid skill dirs found under {src_skills}", log_path)


def _bootstrap_was_skipped(install_log: Path) -> bool:
    """True iff a legacy hook gave up on the temp MCP port-bind wait.

    The legacy warn line contains `30s 内未就绪`; non-celiaclaw retry
    code uses that marker to decide whether to retry.
    """
    if not install_log.exists():
        return False
    try:
        text = install_log.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return "30s 内未就绪" in text


def _xiaoyi_chat_env(config_dir: Path, openclaw_cfg: dict | None = None) -> dict:
    """Parse `<config_dir>/.xiaoyienv` into the OPENAI_CHAT_* env vars
    legacy retry code exports for the temp MCP.

    Falls back to `models.providers.<primary>` from openclaw_cfg when
    .xiaoyienv is missing or incomplete (e.g. user removed the legacy
    .xiaoyienv after migrating to OpenClaw-native provider config).
    Returns an empty dict only when BOTH sources are empty (caller
    treats absence as "skip chat-dependent migration").

    Same .xiaoyienv parsing rules install.sh uses: strip optional
    matching outer quotes, ignore blank/comment lines.
    """
    f = config_dir / ".xiaoyienv"
    vals: dict = {}
    if f.exists():
        try:
            for raw in f.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                v = v.strip()
                if (len(v) >= 2 and v[0] == v[-1]
                        and v[0] in ("'", '"')):
                    v = v[1:-1]
                vals[k.strip()] = v
        except OSError:
            pass

    su  = vals.get("SERVICE_URL", "")
    ak  = vals.get("PERSONAL_API_KEY", "")
    uid = vals.get("PERSONAL_UID", "")

    # Derive model from agents.defaults.model.primary; provider name
    # is the same string before "/", and we'll borrow chat from
    # models.providers.<provider> if .xiaoyienv lacks su/ak.
    model = "LLM_GLM5"  # legacy default for .xiaoyienv path
    provider_name = ""
    if isinstance(openclaw_cfg, dict):
        primary = ((openclaw_cfg.get("agents", {}) or {})
                   .get("defaults", {}).get("model", {}).get("primary", ""))
        if isinstance(primary, str) and "/" in primary:
            provider_name, derived_model = primary.split("/", 1)
            if derived_model:
                model = derived_model

    # Fall back to models.providers.<primary> when .xiaoyienv missing
    # critical fields. xiaoyi-style providers carry the real SK in
    # headers["x-api-key"] (top-level apiKey is often a placeholder).
    if (not su or not ak or not uid) and provider_name and isinstance(openclaw_cfg, dict):
        provider = ((openclaw_cfg.get("models", {}) or {})
                    .get("providers", {}) or {}).get(provider_name) or {}
        if not su and isinstance(provider.get("baseUrl"), str):
            su = provider["baseUrl"]
        if not ak:
            phdrs = provider.get("headers", {}) or {}
            hk = phdrs.get("x-api-key") if isinstance(phdrs, dict) else None
            if isinstance(hk, str) and hk:
                ak = hk
            elif isinstance(provider.get("apiKey"), str) and provider["apiKey"]:
                ak = provider["apiKey"]
        if not uid:
            phdrs = provider.get("headers", {}) or {}
            puid = phdrs.get("x-uid") if isinstance(phdrs, dict) else None
            if isinstance(puid, str) and puid:
                uid = puid

    if not (su and ak):
        return {}

    # .xiaoyienv 来源没带后缀,需要补 /celia-claw/v1/sse-api;直接来自
    # provider.baseUrl 通常已经是完整 URL,不重复追加。
    if "/celia-claw/" not in su:
        base = su.rstrip("/") + "/celia-claw/v1/sse-api"
    else:
        base = su

    out = {
        "OPENAI_CHAT_BASE_URL": base,
        "OPENAI_CHAT_API_KEY":  ak,
        "OPENAI_CHAT_MODEL":    model,
    }
    if uid:
        out["CELIA_CHAT_UID"] = uid
    return out


def _plugins_obj(data: dict) -> dict:
    plugins = data.get("plugins")
    return plugins if isinstance(plugins, dict) else {}


def _memory_plugin_load_paths(data: dict) -> list[str]:
    plugins = _plugins_obj(data)
    load = plugins.get("load")
    paths = load.get("paths") if isinstance(load, dict) else []
    if not isinstance(paths, list):
        return []
    return [
        item for item in paths
        if isinstance(item, str) and item.rstrip("/").endswith("/memory-plugin")
    ]


def _is_stale_celia_memory_path(path: str) -> bool:
    normalized = path.rstrip("/")
    return (
        "/celia_memory/" in normalized
        and "/install/" in normalized
        and not normalized.endswith("/install/current/memory-plugin")
    )


def _is_managed_memory_plugin_path(value) -> bool:
    return isinstance(value, str) and value.rstrip("/").endswith(
        "/memory-plugin",
    )


def _is_managed_memory_entry(name, entry, active_memory_id) -> bool:
    if name == MEMORY_PLUGIN_ID or name == active_memory_id:
        return True
    if not isinstance(name, str) or not name.startswith("memory-"):
        return False
    if not isinstance(entry, dict):
        return False

    cfg = entry.get("config")
    if isinstance(cfg, dict):
        owned_keys = ("serverBinaryPath", "dbPath", "vectorDim", "embed", "chat")
        if any(key in cfg for key in owned_keys):
            return True

    hooks = entry.get("hooks")
    return isinstance(hooks, dict) and hooks.get("allowConversationAccess") is True


def _clean_managed_memory_allow_list(plugins: dict,
                                     stale_names: set[str]) -> bool:
    allow = plugins.get("allow")
    if not isinstance(allow, list):
        return False

    cleaned = []
    seen = set()
    for item in allow:
        if item in stale_names:
            continue
        if item not in seen:
            cleaned.append(item)
            seen.add(item)
    if MEMORY_PLUGIN_ID not in seen:
        cleaned.append(MEMORY_PLUGIN_ID)
    if cleaned == allow:
        return False
    plugins["allow"] = cleaned
    return True


def _has_memory_celia_runtime_config(data: dict) -> bool:
    plugins = data.get("plugins")
    if not isinstance(plugins, dict):
        return False
    slots = plugins.get("slots")
    if isinstance(slots, dict) and slots.get("memory") == MEMORY_PLUGIN_ID:
        return True
    entries = plugins.get("entries")
    if isinstance(entries, dict) and isinstance(
        entries.get(MEMORY_PLUGIN_ID), dict,
    ):
        return True
    installs = plugins.get("installs")
    if isinstance(installs, dict) and isinstance(
        installs.get(MEMORY_PLUGIN_ID), dict,
    ):
        return True
    return bool(_memory_plugin_load_paths(data))


def _memory_celia_runtime_config_needs_repair(data: dict) -> bool:
    plugins = data.get("plugins")
    if not isinstance(plugins, dict):
        return True
    slots = plugins.get("slots")
    if not isinstance(slots, dict) or slots.get("memory") != MEMORY_PLUGIN_ID:
        return True
    entries = plugins.get("entries")
    if not isinstance(entries, dict):
        return True
    entry = entries.get(MEMORY_PLUGIN_ID)
    if not isinstance(entry, dict) or entry.get("enabled") is not True:
        return True
    cfg = entry.get("config")
    if not isinstance(cfg, dict):
        return True
    for key in ("serverBinaryPath", "dbPath"):
        value = cfg.get(key)
        if not isinstance(value, str) or not value or "${" in value:
            return True
    load_paths = _memory_plugin_load_paths(data)
    if not load_paths:
        return True
    return any(_is_stale_celia_memory_path(path) for path in load_paths)


def _load_memory_celia_runtime_template(install_root: Path) -> dict:
    candidates = (
        install_root / "openclaw" / "config" / "openclaw.json",
        install_root / "openclaw.json",
    )
    for path in candidates:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(data, dict) and _has_memory_celia_runtime_config(data):
            return data
    return {}


def _resolve_celia_runtime_placeholders(node, config_dir: Path,
                                       install_root: Path,
                                       install_root_value: str | None = None):
    root_value = install_root_value or _celia_install_root_value(install_root)
    replacements = {
        "${CELIA_CONFIG_ROOT}": str(config_dir),
        "${CELIA_CONFIG_DIR}": str(config_dir),
        "${CELIA_INSTALL_ROOT}": root_value,
        "${CELIA_PLUGIN_ROOT}": root_value,
    }
    if isinstance(node, str):
        out = node
        for placeholder, value in replacements.items():
            out = out.replace(placeholder, value)
        return out
    if isinstance(node, list):
        return [
            _resolve_celia_runtime_placeholders(
                item, config_dir, install_root, install_root_value,
            )
            for item in node
        ]
    if isinstance(node, dict):
        return {
            key: _resolve_celia_runtime_placeholders(
                value, config_dir, install_root, install_root_value,
            )
            for key, value in node.items()
        }
    return node


def _merge_memory_celia_runtime_config(data: dict, template: dict,
                                      config_dir: Path,
                                      install_root: Path,
                                      install_root_value: str | None = None) -> bool:
    changed = False
    plugins = data.setdefault("plugins", {})
    if not isinstance(plugins, dict):
        plugins = {}
        data["plugins"] = plugins
        changed = True

    slots = plugins.get("slots")
    if not isinstance(slots, dict):
        slots = {}
        plugins["slots"] = slots
        changed = True
    existing_slots = plugins.get("slots")
    active_memory_id = (
        existing_slots.get("memory")
        if isinstance(existing_slots, dict)
        else None
    )

    if slots.get("memory") != MEMORY_PLUGIN_ID:
        slots["memory"] = MEMORY_PLUGIN_ID
        changed = True

    src_plugins = template.get("plugins")
    if not isinstance(src_plugins, dict):
        src_plugins = {}

    load = plugins.get("load")
    if not isinstance(load, dict):
        load = {}
        plugins["load"] = load
        changed = True
    paths = load.get("paths")
    if not isinstance(paths, list):
        paths = []
        changed = True
    desired_paths = _memory_plugin_load_paths(template)
    if not desired_paths:
        root_value = install_root_value or _celia_install_root_value(install_root)
        desired_paths = [
            str(Path(root_value) / "memory-plugin"),
        ]
    desired_paths = _resolve_celia_runtime_placeholders(
        desired_paths, config_dir, install_root, install_root_value,
    )
    cleaned_paths = []
    seen_paths = set()
    for path in paths:
        if not isinstance(path, str):
            changed = True
            continue
        if _is_managed_memory_plugin_path(path) and path not in desired_paths:
            changed = True
            continue
        if path in seen_paths:
            changed = True
            continue
        cleaned_paths.append(path)
        seen_paths.add(path)
    for path in desired_paths:
        if isinstance(path, str) and path not in seen_paths:
            cleaned_paths.append(path)
            seen_paths.add(path)
            changed = True
    if cleaned_paths != paths:
        load["paths"] = cleaned_paths
        changed = True

    entries = plugins.get("entries")
    if not isinstance(entries, dict):
        entries = {}
        plugins["entries"] = entries
        changed = True
    src_entries = src_plugins.get("entries")
    src_entry = (
        src_entries.get(MEMORY_PLUGIN_ID)
        if isinstance(src_entries, dict)
        else None
    )
    if isinstance(src_entry, dict):
        src_entry = _resolve_celia_runtime_placeholders(
            src_entry, config_dir, install_root, install_root_value,
        )
    stale_names: set[str] = set()
    if isinstance(active_memory_id, str) and active_memory_id != MEMORY_PLUGIN_ID:
        stale_names.add(active_memory_id)
    for name, entry in list(entries.items()):
        if _is_managed_memory_entry(name, entry, active_memory_id):
            stale_names.add(name)
            del entries[name]
            changed = True
    if isinstance(src_entries, dict):
        for name, entry in src_entries.items():
            if name != MEMORY_PLUGIN_ID and name not in entries:
                entries[name] = copy.deepcopy(entry)
                changed = True
    if isinstance(src_entry, dict):
        next_entry = copy.deepcopy(src_entry)
        next_entry["enabled"] = True
        if entries.get(MEMORY_PLUGIN_ID) != next_entry:
            entries[MEMORY_PLUGIN_ID] = next_entry
            changed = True

    src_installs = src_plugins.get("installs")
    src_install = (
        src_installs.get(MEMORY_PLUGIN_ID)
        if isinstance(src_installs, dict)
        else None
    )
    if isinstance(src_install, dict):
        installs = plugins.get("installs")
        if not isinstance(installs, dict):
            installs = {}
            plugins["installs"] = installs
            changed = True
        src_install = _resolve_celia_runtime_placeholders(
            src_install, config_dir, install_root, install_root_value,
        )
        for name in stale_names:
            if name in installs:
                del installs[name]
                changed = True
        if installs.get(MEMORY_PLUGIN_ID) != src_install:
            installs[MEMORY_PLUGIN_ID] = copy.deepcopy(src_install)
            changed = True
    changed = _clean_managed_memory_allow_list(plugins, stale_names) or changed

    return changed


def _enforce_memory_celia_runtime_config(config_dir: Path,
                                        install_root: Path | None = None,
                                        log_path: Path | None = None,
                                        install_root_value: str | None = None) -> bool:
    """Repair the production runtime config owned by memory-celia."""
    cfg_path = config_dir / "openclaw.json"
    if not cfg_path.exists():
        return False
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        emit(f"[WARN] cannot parse {cfg_path} for slot repair: {e}", log_path)
        return False

    if install_root is None:
        install_root = INSTALL_DIRS_PARENT / "current"
    template = _load_memory_celia_runtime_template(install_root)
    if not template and not _has_memory_celia_runtime_config(data):
        return False
    if not template and not _memory_celia_runtime_config_needs_repair(data):
        return False

    changed = _merge_memory_celia_runtime_config(
        data, template, config_dir, install_root, install_root_value,
    )

    if changed:
        cfg_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        emit(f"[INFO] repaired memory-celia runtime config in {cfg_path}",
             log_path)
    return changed


def _memory_celia_llm_base_urls(data: dict) -> list[tuple[str, str]]:
    """Return configured memory-celia chat/embed base URLs."""
    cfg = ((_plugins_obj(data).get("entries", {}) or {})
           .get("memory-celia", {}).get("config", {})) or {}
    if not isinstance(cfg, dict):
        return []
    out: list[tuple[str, str]] = []
    for name in ("chat", "embed"):
        block = cfg.get(name)
        if not isinstance(block, dict):
            continue
        base = block.get("baseUrl")
        if isinstance(base, str) and base:
            out.append((name, base))
    return out


def _local_openai_probe_url(base_url: str) -> str | None:
    """Build a `/v1/models` probe URL for loopback OpenAI-compatible bases."""
    parsed = urllib.parse.urlparse(base_url)
    if parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
        return None
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        return base + "/models"
    marker = "/v1/"
    if marker in base:
        return base.split(marker, 1)[0] + "/v1/models"
    return base + "/models"


def _warn_if_local_openai_proxy_unreachable(
        config_dir: Path, log_path: Path | None = None) -> None:
    """Warn when memory-celia points at an unavailable local OpenAI proxy."""
    cfg_path = config_dir / "openclaw.json"
    if not cfg_path.exists():
        return
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        emit(f"[WARN] cannot parse {cfg_path} for LLM proxy probe: {e}",
             log_path)
        return

    seen: set[str] = set()
    for label, base in _memory_celia_llm_base_urls(data):
        if "${" in base:
            emit(f"[WARN] memory-celia.config.{label}.baseUrl unresolved: "
                 f"{base}", log_path)
            continue
        probe_url = _local_openai_probe_url(base)
        if not probe_url or probe_url in seen:
            continue
        seen.add(probe_url)
        try:
            with urllib.request.urlopen(probe_url, timeout=1.5) as resp:
                status = getattr(resp, "status", 200)
            if status >= 400:
                emit(f"[WARN] local OpenAI proxy probe returned HTTP "
                     f"{status}: {probe_url}", log_path)
            else:
                emit(f"[INFO] local OpenAI proxy reachable: {probe_url}",
                     log_path)
        except (urllib.error.URLError, OSError) as e:
            emit(f"[WARN] local OpenAI proxy unreachable for memory-celia "
                 f"({label}): {probe_url} ({e}); raw mem_conversation rows "
                 f"can queue, but extraction/indexing will stall", log_path)


def _verify_runtime_paths(config_dir: Path,
                          install_root: Path,
                          log_path: Path | None) -> tuple[bool, list[str]]:
    """Post-install sanity check on the production memory-celia config.

    Two paths must hold for memory to actually work after gateway restart:
      - serverBinaryPath: file exists and is executable (gateway spawns it
        as a child process; missing/non-exec file is the symptom the user
        hit — celia_memory.db never gets created).
      - dbPath: parent dir exists or can be created (sqlite open() needs it).

    Both must be free of unresolved `${...}` placeholders — if any survive
    here, our substitution missed and the install is broken.

    Returns (ok, problems). Caller decides whether to die or warn.
    """
    cfg_path = config_dir / "openclaw.json"
    problems: list[str] = []

    if not cfg_path.exists():
        problems.append(f"production openclaw.json not found at {cfg_path}")
        return False, problems
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        problems.append(f"cannot parse {cfg_path}: {e}")
        return False, problems

    plugins = _plugins_obj(data)
    slots = plugins.get("slots") if isinstance(plugins.get("slots"), dict) else {}
    if slots.get("memory") != "memory-celia":
        problems.append(
            "plugins.slots.memory is not memory-celia "
            f"(current={slots.get('memory', '<missing>')!r})"
        )

    load_paths = _memory_plugin_load_paths(data)
    if not load_paths:
        problems.append("plugins.load.paths has no memory-plugin entry")
    for path in load_paths:
        if "${" in path:
            problems.append(
                f"memory-plugin load path has unresolved placeholder: {path}"
            )
            continue
        if _is_stale_celia_memory_path(path):
            problems.append(f"memory-plugin load path is stale: {path}")
            continue
        index_js = Path(path).expanduser() / "index.js"
        if not index_js.is_file():
            problems.append(f"memory-plugin runtime JS missing: {index_js}")

    entries = (
        plugins.get("entries")
        if isinstance(plugins.get("entries"), dict)
        else {}
    )
    entry = entries.get("memory-celia")
    if not isinstance(entry, dict):
        problems.append(
            f"memory-celia entry missing in {cfg_path}; merge step failed?"
        )
        return False, problems
    if entry.get("enabled") is not True:
        problems.append(
            "plugins.entries.memory-celia.enabled is not true "
            f"(current={entry.get('enabled', '<missing>')!r})"
        )

    cfg = entry.get("config")
    if not isinstance(cfg, dict):
        problems.append(
            f"memory-celia.config missing in {cfg_path}; merge step failed?"
        )
        return False, problems

    bin_path = cfg.get("serverBinaryPath", "")
    if not bin_path:
        problems.append("serverBinaryPath is empty in production openclaw.json")
    elif "${" in bin_path:
        problems.append(
            f"serverBinaryPath has unresolved placeholder: {bin_path}"
        )
    else:
        bp = Path(bin_path)
        if not bp.is_file():
            problems.append(
                f"serverBinaryPath points to missing file: {bin_path}"
            )
        elif not os.access(bp, os.X_OK):
            try:
                mode = bp.stat().st_mode
                bp.chmod(mode | 0o111)
                emit(f"[INFO] repaired executable bit on {bin_path}", log_path)
            except OSError as e:
                problems.append(
                    "serverBinaryPath is not executable and chmod repair "
                    f"failed: {bin_path} ({e})"
                )
            if not os.access(bp, os.X_OK):
                problems.append(
                    f"serverBinaryPath is not executable: {bin_path}"
                )

    db_path = cfg.get("dbPath", "")
    if "${" in db_path:
        problems.append(f"dbPath has unresolved placeholder: {db_path}")
    elif db_path:
        try:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            problems.append(
                f"cannot prepare dbPath parent ({db_path}): {e}"
            )

    return (len(problems) == 0), problems


# ============================================================================
# Historical-memory migration retry (non-celiaclaw legacy path)
# ============================================================================
#
# Legacy platform hooks may still attempt historical-memory import through
# a temp celia_memory_mcp_server. celiaclaw no longer runs automatic migration, so
# the skill layer must not start a second temp MCP when it sees old skip
# markers in install logs.


def _retry_skipped_bootstrap(plat: str,
                             install_root: Path,
                             log_path: Path) -> None:
    """Re-run non-celiaclaw historical-memory migration if hook skipped it.

    Reuses install.sh's already-persisted artifacts:
      - <plugin_dir>/celia_memory_mcp_server   (binary)
      - <plugin_dir>/migrate_openclaw/ (tool, dropped by persist_migrate_tool)
    Reads embed creds + dbPath + userId from the merged production
    openclaw.json — single source of truth, matching whatever
    patch_openclaw_config + our placeholder substitution wrote.

    Idempotent: migrate_openclaw uses an on-disk manifest, so re-running
    only retries entries that didn't already complete.
    """
    if plat == "celiaclaw":
        if _bootstrap_was_skipped(log_path):
            emit("[INFO] retry-bootstrap: celiaclaw no longer runs "
                 "historical-memory migration; skip skill-side temp MCP",
                 log_path)
        return

    if not _bootstrap_was_skipped(log_path):
        return

    config_dir     = _detect_config_dir(plat)
    plugin_dir     = _detect_plugin_dir(plat)
    workspace_root = config_dir / "workspace"
    cfg_path       = config_dir / "openclaw.json"
    migrate_dir    = plugin_dir / "migrate_openclaw"
    mcp_bin        = plugin_dir / "bin" / "celia_memory_mcp_server"

    if not workspace_root.is_dir() or not cfg_path.exists():
        return
    if not migrate_dir.is_dir() or not mcp_bin.is_file():
        emit("[WARN] retry-bootstrap: persisted migrate_openclaw or "
             f"celia_memory_mcp_server missing under {plugin_dir}; cannot retry",
             log_path)
        return

    # Pull config from the production file. _verify_runtime_paths already
    # validated that this exists and parses; we re-read here to keep the
    # retry self-contained (one less argument to thread).
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        emit(f"[WARN] retry-bootstrap: cannot read {cfg_path}: {e}", log_path)
        return
    mgsd = (cfg.get("plugins", {}).get("entries", {})
                .get("memory-celia", {}).get("config", {})) or {}
    db_path  = mgsd.get("dbPath")
    embed    = mgsd.get("embed", {}) or {}
    user_id  = mgsd.get("userId") or "openclaw-user"

    # 优先级链（高 → 低,仅两档,与 memory-plugin/index.ts 保持一致）：
    #   1. memory-celia.config.embed.{baseUrl,apiKey,model}（JSON literal/${VAR}）
    #   2. agents.defaults.memorySearch.remote.{baseUrl,apiKey} + memorySearch.model
    # apiKey 字段:xiaoyi 风格 OpenClaw 配置中,顶层 apiKey 经常是字面量
    # 占位符（如 "apikey"）,真实 SK 凭据在 headers["x-api-key"]。
    # 优先 headers["x-api-key"],后退到顶层 apiKey。
    def _pick_real_apikey(headers, top_level):
        if isinstance(headers, dict):
            hk = headers.get("x-api-key")
            if isinstance(hk, str) and hk:
                return hk
        if isinstance(top_level, str) and top_level:
            return top_level
        return None

    ms_search  = ((cfg.get("agents", {}) or {})
                  .get("defaults", {}).get("memorySearch", {}) or {})
    ms_enabled = bool(ms_search.get("enabled", True))
    ms_inner   = (ms_search.get("remote", {}) or {}) if ms_enabled else {}
    ms_headers = ms_inner.get("headers", {}) or {}
    ms_apikey  = _pick_real_apikey(ms_headers, ms_inner.get("apiKey")) if ms_enabled else None
    ms_baseurl = ms_inner.get("baseUrl") if ms_enabled else None
    ms_model   = ms_search.get("model")  if ms_enabled else None
    ms_uid     = ms_headers.get("x-uid") if ms_enabled else None

    def _resolve_json_only(val):
        """${VAR} 严格解析 → 非空字面量 → 空串。不读 env。"""
        if isinstance(val, str) and "${" in val:
            return re.sub(r"\$\{([^}]+)\}",
                          lambda m: os.environ.get(m.group(1), ""),
                          val)
        if isinstance(val, str) and val:
            return val
        return ""

    def _resolve(val, ms_val) -> str:
        """两档 fallback：cfg.embed (JSON literal/${VAR}) → memorySearch."""
        return (_resolve_json_only(val)
                or (ms_val if isinstance(ms_val, str) and ms_val else ""))

    embed_base_url = _resolve(embed.get("baseUrl"), ms_baseurl)
    embed_api_key  = _resolve(embed.get("apiKey"),  ms_apikey)
    embed_model    = _resolve(embed.get("model"),   ms_model)
    # sandbox uid 走 CELIA_CHAT_UID（chat env 已经会从 .xiaoyienv 注入）,
    # 此处仅在 memorySearch 提供了 headers["x-uid"] 时把 chatUid 覆盖为
    # memorySearch 的值;C 端 mcp_main 复用 chatUid 作 embedUid。
    sandbox_uid    = ms_uid if isinstance(ms_uid, str) and ms_uid else ""

    if not (db_path and embed_base_url and embed_api_key and embed_model):
        emit("[WARN] retry-bootstrap: embed creds missing — checked "
             "memory-celia.config.embed and agents.defaults.memorySearch; "
             "skipping", log_path)
        return

    # Find migration targets. install.sh supports two layouts:
    #   single-user: USER.md / Memory.md sit at workspace_root
    #   multi-user:  workspace_root/<uid>/USER.md ...
    memory_files = ("USER.md", "Memory.md", "MEMORY.md", "memory.md")
    targets: list = []
    if any((workspace_root / m).exists() for m in memory_files):
        targets.append((workspace_root, user_id))
    else:
        try:
            children = sorted(workspace_root.iterdir())
        except OSError:
            children = []
        for sub in children:
            if (sub.is_dir()
                    and any((sub / m).exists() for m in memory_files)):
                targets.append((sub, sub.name))

    if not targets:
        emit("[INFO] retry-bootstrap: bootstrap was skipped, but no "
             "USER.md/Memory.md files exist under "
             f"{workspace_root} — nothing to migrate", log_path)
        return

    emit(f"[INFO] retry-bootstrap: install.sh's 30s budget was exceeded; "
         f"retrying migration for {len(targets)} workspace(s) with a "
         f"longer port-bind budget", log_path)

    # Build env: same shape install.sh's bootstrap built (embed creds
    # exported so the child mcp server inherits them; chat creds optional).
    env = os.environ.copy()
    env["OPENAI_EMBED_BASE_URL"] = embed_base_url
    env["OPENAI_EMBED_API_KEY"]  = embed_api_key
    env["OPENAI_EMBED_MODEL"]    = embed_model
    if isinstance(mgsd.get("vectorDim"), int):
        env["CELIA_VECTOR_DIM"] = str(mgsd["vectorDim"])
    env.update(_xiaoyi_chat_env(config_dir, openclaw_cfg=cfg))
    # memorySearch.headers["x-uid"] 优先级高于 _xiaoyi_chat_env（PERSONAL_UID）；
    # C 端 mcp_main 把 chatUid 同步复用作 embedUid 触发 sandbox 头。
    if sandbox_uid:
        env["CELIA_CHAT_UID"] = sandbox_uid

    # Stop openclaw-gateway so the production MCP server (just spawned by
    # install.sh's restart_services) releases its SQLite WAL lock. Two
    # writers on the same DB technically works under WAL but the
    # contention can manifest as SQLITE_BUSY mid-migration; safer to pause.
    # Restart in the finally block.
    gateway_paused = False
    if shutil.which("supervisorctl"):
        try:
            subprocess.run(
                ["supervisorctl", "stop", "openclaw-gateway"],
                timeout=30, check=False,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            time.sleep(2)
            gateway_paused = True
        except Exception as e:
            emit(f"[WARN] retry-bootstrap: stop gateway failed: {e}",
                 log_path)

    proc = None
    try:
        # Allocate ephemeral port (same trick install.sh uses).
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]

        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        server_log = LOG_DIR / f"retry-bootstrap-server-{now_ts()}.log"
        with server_log.open("w") as srv_log:
            proc = subprocess.Popen(
                [str(mcp_bin), "--http", str(port), str(db_path)],
                env=env,
                stdout=srv_log, stderr=subprocess.STDOUT,
            )

        # Wait up to 180s — six times install.sh's 30s budget. Bail early
        # if the process exits, that's a hard failure not a slow start.
        ok = False
        for _ in range(180):
            if proc.poll() is not None:
                emit(f"[WARN] retry-bootstrap: temp MCP exited early "
                     f"(rc={proc.returncode}); see {server_log}", log_path)
                return
            try:
                with socket.socket() as s:
                    s.settimeout(0.5)
                    s.connect(("127.0.0.1", port))
                ok = True
                break
            except OSError:
                time.sleep(1)
        if not ok:
            emit(f"[WARN] retry-bootstrap: temp MCP didn't bind even with "
                 f"180s; see {server_log}; giving up", log_path)
            return

        emit(f"[INFO] retry-bootstrap: temp MCP up on :{port}; "
             "starting migration", log_path)

        # Run migrate per target. Per install.sh's _run_migrate_one: cwd
        # at plugin_dir (where migrate_openclaw lives), PYTHONPATH set so
        # `python3 -m migrate_openclaw.migrate ...` resolves.
        run_env = env.copy()
        run_env["CELIA_BASE_URL"] = f"http://127.0.0.1:{port}"
        existing_pp = run_env.get("PYTHONPATH", "")
        run_env["PYTHONPATH"] = (str(plugin_dir)
                                 + (os.pathsep + existing_pp
                                    if existing_pp else ""))

        migrated = 0
        for ws, uid in targets:
            cmd = ["python3", "-m", "migrate_openclaw.migrate", "run",
                   "--workspace", str(ws),
                   "--agent-id", uid, "--user-id", uid,
                   "--out-dir", str(ws / ".celia_migrate")]
            try:
                res = subprocess.run(
                    cmd, env=run_env, cwd=str(plugin_dir),
                    capture_output=True, text=True, timeout=600,
                )
            except subprocess.TimeoutExpired:
                emit(f"[WARN] retry-bootstrap: migrate user={uid} "
                     "timed out after 600s", log_path)
                continue
            if res.returncode == 0:
                migrated += 1
                emit(f"[INFO] retry-bootstrap: migrated user={uid}",
                     log_path)
            else:
                tail = (res.stderr or res.stdout or "")[-500:]
                emit(f"[WARN] retry-bootstrap: migrate user={uid} "
                     f"rc={res.returncode}; tail:\n{tail}", log_path)

        emit(f"[INFO] retry-bootstrap: migrated {migrated}/{len(targets)} "
             "workspace(s)", log_path)

    finally:
        # Always tear down what we started, in the right order.
        if proc is not None:
            try:
                proc.terminate()
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                try:
                    proc.wait(timeout=5)
                except Exception:
                    pass
            except Exception:
                pass
        if gateway_paused and shutil.which("supervisorctl"):
            try:
                subprocess.run(
                    ["supervisorctl", "start", "openclaw-gateway"],
                    timeout=30, check=False,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                emit("[INFO] retry-bootstrap: openclaw-gateway restarted",
                     log_path)
            except Exception as e:
                emit("[WARN] retry-bootstrap: failed to restart gateway: "
                     f"{e} — run `supervisorctl start openclaw-gateway` "
                     "manually", log_path)


# ============================================================================
# Plan / execute / reboot modes
# ============================================================================

SOURCE_POLICY_OFFLINE_ONLY = "offline-only"
def resolve_source_policy() -> str:
    """Return the source policy implied by the skill directory.

    celiaclaw `experimental-memory-install` is permanently offline-only.
    """
    return SOURCE_POLICY_OFFLINE_ONLY


def _pick_local_tarball(local_dir: Path, plat: str,
                        version: str | None = None) -> tuple[Path, str]:
    """Best-effort lookup: try arch=any first, then host arch. Returns
    (path, arch). Dies (10) if nothing matches.
    """
    chosen_tarball = None
    chosen_arch = None
    for arch in ("any", host_arch()):
        candidates = _local_tarball_candidates(local_dir, plat, arch, version)
        if candidates:
            chosen_tarball = candidates[0]
            chosen_arch = arch
            break
    if chosen_tarball is None:
        version_part = version if version else "*"
        die(10, f"[ERROR] no celia_memory.{version_part}.{plat}.<arch>.*.tar.gz "
                f"under {local_dir}")
    return chosen_tarball, chosen_arch


def build_plan(args, lang) -> dict:
    """Resolve everything that's known *before* we touch the filesystem.

    Three source modes:
      - offline    default for lifecycle actions; pull tarball from the
                   platform tarball cache dir ($CELIA_TARBALL_DIR), fail if
                   missing. No remote, no fallback.
      - local-dir  caller passed --source <path>; dev workflow.
      - remote     not supported by the celiaclaw install skill.
    """
    compat = load_compat()
    remote = compat["remote"]
    plat = detect_platform(args.platform)
    glibc = detect_glibc()
    libc_floor = pick_libc_floor(glibc)
    policy = resolve_source_policy()
    # local-dir mode: caller-supplied directory (dev workflow)
    if args.source_local_dir:
        local_dir = Path(args.source_local_dir).expanduser().resolve()
        chosen_tarball, chosen_arch = _pick_local_tarball(
            local_dir, plat, args.version)
        version = chosen_tarball.name.split(".", 5)[1]
        return {
            "mode_resolution": "local-dir",
            "source_label": "dev",
            "tarball_dir": str(local_dir),
            "local_tarball": str(chosen_tarball),
            "version": version,
            "platform": plat,
            "arch": chosen_arch,
            "compat": compat,
            "lang": lang,
        }

    remote_requested = args.remote or args.dev or bool(args.channel)
    if policy == SOURCE_POLICY_OFFLINE_ONLY and remote_requested:
        die(10, "[ERROR] experimental-memory-install is offline-only and cannot use "
                "remote/network install flags in celiaclaw.")

    # offline mode: default unless remote was explicitly requested. Reads from
    # the tarball cache dir, no network and no fallback.
    if args.offline or not remote_requested:
        staging = _resolve_tarball_dir(plat)
        if not staging.exists():
            die(10, f"[ERROR] tarball cache dir not found: {staging}\n"
                    f"        Set $CELIA_TARBALL_DIR, pre-stage a tarball, "
                    f"or use --source to point at a local release directory.")
        chosen_tarball, chosen_arch = _pick_local_tarball(
            staging, plat, args.version)
        version = chosen_tarball.name.split(".", 5)[1]
        return {
            "mode_resolution": "local-dir",
            "source_label": "offline",
            "tarball_dir": str(staging),
            "local_tarball": str(chosen_tarball),
            "version": version,
            "platform": plat,
            "arch": chosen_arch,
            "compat": compat,
            "lang": lang,
        }

    # remote mode: explicit opt-in only
    if args.version:
        version = args.version
    else:
        # Default remote channel: rc. Stable channel currently has no published
        # release assets in GitCode (latest-stable.txt → v2026-04-30-c1 → 404);
        # we route to latest-rc.txt until the release pipeline catches up.
        # Override with --channel=<name> or --version=<vTAG> for explicit
        # pinning.
        channel = "dev" if args.dev else (args.channel or "rc")
        version = fetch_pointer(remote, channel)
    emit(msg("version_resolved", lang, v=version))
    emit(msg("platform_detected", lang, p=plat))

    # Sanity-check the version string parses. Legacy fallback (pre-contract
    # tarballs without scripts/contract.toml) has been retired — contract is
    # required from now on; the per-version min_artifact_version /
    # fallback_artifact_versions gates have been dropped.
    if parse_version(version)[3] < 0:
        die(60, msg("version_unsupported", lang, v=version, min="(parseable v…)"))

    # arch + variant decision
    arch = pick_arch(plat)
    variant = pick_variant(plat, libc_floor)
    manifest = fetch_manifest(remote, version, plat, arch)
    artifact = pick_artifact(manifest, variant)

    install_root = INSTALL_DIRS_PARENT / version
    return {
        "mode_resolution": "remote",
        "source_label": "remote",
        "tarball_dir": str(_resolve_tarball_dir(plat)),
        "version": version,
        "platform": plat,
        "arch": arch,
        "variant": variant,
        "libc_floor": libc_floor,
        "manifest": manifest,
        "artifact": artifact,
        "install_root": install_root,
        "compat": compat,
        "lang": lang,
    }


def host_arch() -> str:
    m = platform_mod.machine().lower()
    if m in ("x86_64", "amd64"):
        return "linux-amd64"
    if m in ("aarch64", "arm64"):
        return "linux-arm64"
    return "any"


def pick_arch(plat: str) -> str:
    """Default arch per platform (full variants need linux-*)."""
    if plat == "celiaclaw" and platform_mod.system() == "Linux":
        return host_arch()
    return "any"


def pick_variant(plat: str, libc_floor: str) -> str:
    """Default variant per platform; celiaclaw on Linux gets full."""
    if plat == "celiaclaw" and platform_mod.system() == "Linux":
        return "full" if libc_floor == "modern" else f"full-{libc_floor}"
    return "plugins"


def run_plan(args, lang: str) -> int:
    p = build_plan(args, lang)
    print(msg("plan_header", lang))
    print(msg("plan_target_version", lang, v=p["version"]))
    print(msg("plan_install_root", lang,
              p=str(INSTALL_DIRS_PARENT / p["version"])))
    if p["mode_resolution"] == "remote":
        a = p["artifact"]
        print(msg("plan_will_download", lang,
                  url=a["download_url"], sz=a["size_bytes"], sha=a["sha256"][:12] + "…"))
        print(msg("plan_tarball_dir", lang, p=p["tarball_dir"]))
        print(msg("plan_disk_required", lang, kb=(a["size_bytes"] * 3) // 1024))
    else:
        # local-dir resolution: pick wording by `source_label` set in the plan.
        # --offline → "offline"; dev workflow (--source) → "dev".
        label = p.get("source_label", "dev")
        if label not in ("dev", "offline"):
            label = "dev"
        print(msg(f"plan_local_tarball_{label}", lang, p=p["local_tarball"]))
    print(msg("plan_will_run_hook", lang,
              p=str(INSTALL_DIRS_PARENT / p["version"])))
    print(msg("plan_hook_actions", lang))
    print(msg("plan_footer", lang))
    print(msg("prompt_action_zh", lang))
    print(msg("prompt_action_en", lang))
    return 0


def run_execute(args, lang: str) -> int:
    if not args.confirmed:
        die(10, "[ERROR] --confirmed required for --mode=execute")

    log_path = LOG_DIR / f"install-{now_ts()}.log"
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    try:
        with Lock(LOCK_FILE):
            return _execute_locked(args, lang, log_path)
    except BlockingIOError:
        die(70, msg("exec_lock_busy", lang, p=str(LOCK_FILE)), log_path)


def _execute_locked(args, lang: str, log_path: Path) -> int:
    p = build_plan(args, lang)
    install_root = INSTALL_DIRS_PARENT / p["version"]
    install_root.parent.mkdir(parents=True, exist_ok=True)

    # ---- 1. Acquire tarball ----
    if p["mode_resolution"] == "local-dir":
        tarball_path = Path(p["local_tarball"])
        label = p.get("source_label", "dev")
        if label not in ("dev", "offline"):
            label = "dev"
        emit(msg(f"exec_using_local_tarball_{label}", lang, p=str(tarball_path)),
             log_path)
        # Optional sidecar SHA verification — defensive parse: malformed
        # sidecar (empty / no whitespace tokens / unreadable) is treated as
        # "no sidecar" rather than crashing with IndexError or OSError.
        sha_sidecar = tarball_path.with_suffix(tarball_path.suffix + ".sha256")
        if sha_sidecar.exists():
            want = ""
            try:
                want = sha_sidecar.read_text().strip().split()[0]
            except (OSError, IndexError):
                emit(f"[WARN] sidecar {sha_sidecar} unreadable / empty — skipping SHA check",
                     log_path)
            if want:
                emit(msg("exec_verifying", lang), log_path)
                got = sha256_file(tarball_path)
                if got != want:
                    die(30, msg("exec_sha_mismatch", lang, want=want, got=got), log_path)
    else:
        a = p["artifact"]
        staging_dir = Path(p["tarball_dir"])
        staging_dir.mkdir(parents=True, exist_ok=True)
        tarball_name = a["download_url"].rsplit("/", 1)[-1]
        target = staging_dir / tarball_name
        sidecar = target.with_suffix(target.suffix + ".sha256")

        # Cache-reuse path: existing tarball + sidecar both pinning the
        # manifest's SHA → just verify and skip the download.
        cached_ok = False
        if target.exists() and sidecar.exists():
            cached_sha = ""
            try:
                cached_sha = sidecar.read_text().strip().split()[0]
            except (OSError, IndexError):
                # malformed/empty sidecar → treat as cache miss (re-download)
                cached_sha = ""
            if cached_sha == a["sha256"]:
                emit(msg("exec_verifying", lang), log_path)
                got = sha256_file(target)
                if got == a["sha256"]:
                    emit(msg("exec_reuse_cached", lang, p=str(target)), log_path)
                    tarball_path = target
                    cached_ok = True
                else:
                    emit(msg("exec_cache_corrupt", lang, p=str(target)), log_path)

        if not cached_ok:
            # Worktree-first path: a fork using
            # `integration/celiaclaw/local_package.sh --direct-push` commits
            # tarballs straight into its GaussPD_Artifacts fork's main, so
            # the file is sitting in the cloned mirror's worktree and we
            # can read it without going over HTTP. (GitCode's anonymous raw
            # URLs return SPA HTML for blobs; api/v5/repos/.../raw requires
            # a private-token that http_get doesn't send. Worktree read
            # bypasses both issues.) CI-built manifests publish tarballs as
            # release-asset blobs that are NOT in git, so the worktree path
            # is missing → we fall through to http_get below, preserving
            # the standard upstream-CI flow.
            mirror = _ensure_artifacts_mirror()
            # Sparse-mode caches don't materialize releases/ by default
            # (cold-start optimization). Expand sparse-checkout to include
            # this version's release dir before probing — no-op on legacy
            # non-sparse caches.
            _ensure_release_in_worktree(mirror, p["version"])
            worktree_tarball = mirror / "releases" / p["version"] / a["filename"]
            if worktree_tarball.exists():
                emit(f"[INFO] using worktree tarball: {worktree_tarball}", log_path)
                emit(msg("exec_verifying", lang), log_path)
                got = sha256_file(worktree_tarball)
                if got != a["sha256"]:
                    die(30, msg("exec_sha_mismatch", lang, want=a["sha256"], got=got),
                        log_path)
                # Stage the worktree tarball into the cache dir + write
                # sidecar so the next install of the same version hits the
                # fast cache-reuse path above (skipping even the worktree read).
                shutil.copy2(worktree_tarball, target)
                sidecar.write_text(a["sha256"] + "\n")
                emit(msg("exec_cached_at", lang, p=str(target)), log_path)
                tarball_path = target
                cached_ok = True

        if not cached_ok:
            # Disk precheck — staging dir lives on the same partition as
            # most user dirs; we measure from DEFAULT_INSTALL_ROOT to keep
            # the check consistent with where extract will land.
            req_kib = (a["size_bytes"] * 3) // 1024
            free = free_kib(DEFAULT_INSTALL_ROOT)
            if free < req_kib:
                die(70, msg("exec_disk_short", lang, req=req_kib, free=free), log_path)

            # Download to staging dir; write atomically via .partial.
            emit(msg("exec_downloading", lang, url=a["download_url"]), log_path)
            body = http_get(a["download_url"])
            partial = target.with_suffix(target.suffix + ".partial")
            partial.write_bytes(body)

            emit(msg("exec_verifying", lang), log_path)
            got = sha256_file(partial)
            if got != a["sha256"]:
                try:
                    partial.unlink()
                except OSError:
                    pass
                die(30, msg("exec_sha_mismatch", lang, want=a["sha256"], got=got),
                    log_path)
            partial.replace(target)
            sidecar.write_text(a["sha256"] + "\n")
            emit(msg("exec_cached_at", lang, p=str(target)), log_path)
            tarball_path = target

    # ---- 2. Atomic extract ----
    emit(msg("exec_extracting", lang, dst=install_root), log_path)
    try:
        safe_extract(tarball_path, install_root)
    except Exception as e:
        die(40, f"[ERROR] extract failed: {e}", log_path)

    # ---- 3. Contract version check ----
    # Legacy pre-contract fallback retired; tarball MUST ship scripts/contract.toml.
    contract_path = install_root / "scripts" / "contract.toml"
    if not contract_path.exists():
        die(60, f"[ERROR] tarball missing scripts/contract.toml at {contract_path};"
                f" pre-contract artifacts no longer supported", log_path)
    ct = tomllib.loads(contract_path.read_text())
    cv = ct.get("contract_version")
    sup = p["compat"].get("supported_contract_versions", [1])
    if cv not in sup:
        die(60, msg("contract_version_unsupported", lang, ct=cv, sup=sup), log_path)
    hook_script = install_root / "scripts" / "install.sh"

    # ---- 3b. Pre-flight: bridge tarball-layout vs install.sh-expected paths ----
    # The platform install.sh reads `$INSTALL_DIR/openclaw.json` for the
    # source config to merge into the production openclaw.json (the
    # critical clean_source_openclaw_config + patch_openclaw_config steps,
    # which register the `memory-celia` plugin entry). qian_kk-era tarballs
    # put openclaw.json at the top of the archive; new contract-era tarballs
    # ship it at `openclaw/config/openclaw.json` instead, but install.sh
    # was not updated to match — so the merge silently no-ops.
    #
    # Mirror the deeper file up to the top level so the merge step finds it.
    # Use a copy, not a symlink: this bridge is mutated to version-pinned
    # staging paths for hook safety, while the deep config remains the
    # placeholder template used after current is atomically switched.
    src_top = install_root / "openclaw.json"
    src_deep = install_root / "openclaw" / "config" / "openclaw.json"
    bridged_top_openclaw = False
    original_top_openclaw: bytes | None = None
    if not src_top.exists() and src_deep.exists():
        try:
            shutil.copy2(src_deep, src_top)
            bridged_top_openclaw = True
            emit(f"[INFO] bridged openclaw.json: {src_top} ← {src_deep}",
                 log_path)
        except OSError as e:
            emit(f"[WARN] could not bridge openclaw.json: {e}", log_path)
    if src_top.exists() and not bridged_top_openclaw:
        try:
            original_top_openclaw = src_top.read_bytes()
        except OSError as e:
            emit(f"[WARN] could not snapshot openclaw.json bridge: {e}",
                 log_path)

    # ---- 3c. Pre-flight: resolve ${CELIA_INSTALL_ROOT} in source openclaw.json ----
    # See the long comment at the top of the placeholder-resolution section
    # for context on why the hook can't be relied on to handle this. We
    # rewrite the source file the hook is about to read, so patch_openclaw_config
    # merges memory-celia into production, it lands with a concrete absolute
    # path that doesn't require any runtime env var.
    staging_root_value = _staging_install_root_value(install_root)
    active_root_value = _celia_install_root_value(install_root)
    if src_top.exists():
        _substitute_install_root_in_json(
            src_top, install_root, log_path, staging_root_value,
        )

    # ---- 3d. Keep install/current untouched while the hook is running ----
    # The hook receives a version-pinned CELIA_INSTALL_ROOT, so any hot reload
    # during the hook sees complete files under install_root instead of a
    # half-installed active symlink. `current` is switched atomically only after
    # the hook succeeds.

    # ---- 4. Run platform install hook ----
    emit(msg("exec_hook_running", lang, p=str(hook_script)), log_path)
    config_dir = _detect_config_dir(p["platform"])
    env = os.environ.copy()
    env["CELIA_CONFIG_DIR"] = str(config_dir)
    env["CELIA_EXTRACT_ROOT"] = str(install_root)
    env["CELIA_LOG_FILE_PATH"] = str(log_path)
    # Pass the resolved value through to the hook env too — defense in
    # depth so any sub-step inside install.sh that may grow a dependency
    # on this var (e.g. supervisord injection) sees the same path the JSON
    # substitution used. Harmless if no consumer reads it.
    env["CELIA_INSTALL_ROOT"] = staging_root_value
    rc = subprocess.call(["bash", str(hook_script)], env=env)
    if rc != 0:
        die(50, msg("exec_hook_failed", lang, rc=rc, log=str(log_path)), log_path)
    if bridged_top_openclaw and src_top.exists():
        try:
            src_top.unlink()
        except OSError as e:
            emit(f"[WARN] could not remove staged openclaw.json bridge: {e}",
                 log_path)
    elif original_top_openclaw is not None:
        try:
            src_top.write_bytes(original_top_openclaw)
        except OSError as e:
            emit(f"[WARN] could not restore openclaw.json template: {e}",
                 log_path)

    # ---- 4b. Post-hook: defensive substitute on production openclaw.json ----
    # `patch_openclaw_config` keeps an existing memory-celia entry in dst
    # untouched (line 888 of install.sh: `if k not in dst...`), so a
    # reinstall over a previously broken config wouldn't pick up our
    # pre-hook fix on its own. Scan dst, replace any residual placeholder.
    # Idempotent — silently no-ops on a clean dst.
    _substitute_install_root_in_json(
        config_dir / "openclaw.json", install_root, log_path,
        staging_root_value,
    )
    _enforce_memory_celia_runtime_config(
        config_dir, install_root, log_path, staging_root_value,
    )

    # ---- 4c. Symlink swing: current → install_root, previous → old current ----
    # MUST run BEFORE verify (4d). The hook writes openclaw.json with
    # version-pinned paths while it runs. After it succeeds, switch current
    # atomically and rewrite the production config to use current, so future
    # upgrades only need to swing this symlink. On re-install of the same
    # version, current already points at install_root, so the previous-swap
    # branch no-ops.
    current_link  = INSTALL_DIRS_PARENT / "current"
    previous_link = INSTALL_DIRS_PARENT / "previous"
    if current_link.is_symlink():
        old_target = current_link.resolve(strict=False)
        old_target_alive = old_target.exists() and old_target != install_root.resolve()
        if old_target_alive:
            # Promote old current → previous (only if old still exists; we
            # don't want to chain previous → dangling target).
            if previous_link.is_symlink() or previous_link.exists():
                try:
                    if previous_link.is_dir() and not previous_link.is_symlink():
                        shutil.rmtree(previous_link, ignore_errors=True)
                    else:
                        previous_link.unlink()
                except OSError:
                    pass
            try:
                _atomic_symlink_replace(previous_link, old_target)
                emit(f"[INFO] {previous_link} → {old_target}", log_path)
            except OSError as e:
                emit(f"[WARN] could not set previous symlink: {e}", log_path)
        elif not old_target.exists():
            # Old current was dangling — drop any stale previous too so
            # _prune_install_roots can't accidentally keep stale targets.
            if previous_link.is_symlink():
                try:
                    previous_link.unlink()
                    emit(f"[INFO] cleared stale previous symlink (old current was dangling)",
                         log_path)
                except OSError:
                    pass
    if current_link.exists() and not current_link.is_symlink():
        # Plain dir (shouldn't happen) — defensive cleanup
        shutil.rmtree(current_link, ignore_errors=True)
    _atomic_symlink_replace(current_link, install_root)
    emit(f"[INFO] {current_link} → {install_root}", log_path)

    # Rewrite production config back to the stable active path now that the
    # symlink is live. This keeps future upgrades config-free: they only swing
    # install/current.
    _enforce_memory_celia_runtime_config(
        config_dir, install_root, log_path, active_root_value,
    )

    # ---- 4d. Verify runtime-critical paths in production config ----
    # If serverBinaryPath / dbPath aren't both sane after the hook +
    # placeholder substitution + symlink swing, the install is broken —
    # gateway will be up but the MCP server never spawns and celia_memory.db
    # never materializes. Fail loudly instead of printing
    # services_restarted: yes on a broken state. Reusing exit 50
    # (platform-install-hook failure) since the symptom is "hook completed
    # but produced an unworkable result".
    ok, problems = _verify_runtime_paths(config_dir, install_root, log_path)
    if not ok:
        for prob in problems:
            emit(f"[ERROR] post-install check: {prob}", log_path)
        die(50,
            f"[ERROR] post-install verification failed ({len(problems)} "
            f"issue(s)). Memory plugin is not usable in this state. "
            f"See log: {log_path}",
            log_path)
    _warn_if_local_openai_proxy_unreachable(config_dir, log_path)

    # ---- 4e. Retry legacy migration on non-celiaclaw platforms if skipped ---
    # celiaclaw no longer performs historical-memory migration. Keep this
    # best-effort retry for older non-celiaclaw hooks that still emit the
    # 30s temp MCP skip marker.
    _retry_skipped_bootstrap(p["platform"], install_root, log_path)

    # ---- 5. Deploy skills into workspace/skills/experimental-memory-* ----
    # Done after symlink swing so any skill machinery that reads `current`
    # sees the new layout.
    config_dir = _detect_config_dir(p["platform"])
    _deploy_skills(install_root, config_dir, log_path)

    # ---- 6. Tarball cache retention (remote downloads only) ----
    # Offline-mode skips tarball prune — the operator owns the cache dir and
    # may have multiple tarballs intentionally pre-staged for testing.
    if p.get("source_label") == "remote":
        try:
            keep = int(os.environ.get("CELIA_TARBALL_RETENTION", "3"))
        except ValueError:
            keep = 3
        staging_dir = Path(p["tarball_dir"])
        if keep > 0 and staging_dir.exists():
            _prune_tarball_cache(staging_dir, p["platform"], keep, log_path)

    # ---- 7. Install-root retention: keep only current + previous ----
    # Independent of source_label — the layout invariant is "two roots max".
    _prune_install_roots(INSTALL_DIRS_PARENT, log_path)

    # ---- 8. Print POST_INSTALL block ----
    # The platform install.sh normally runs restart_services. Docker deployment
    # can set CELIA_SKIP_GATEWAY_RESTART=1 and let the deployment process start
    # or restart openclaw-gateway once after all bootstrap scripts finish.
    print(msg("exec_post_install_header", lang))
    print(msg("exec_install_complete", lang, v=p["version"], p=str(install_root)))
    if os.environ.get("CELIA_SKIP_GATEWAY_RESTART", "0") == "1":
        print("services_restarted: no (CELIA_SKIP_GATEWAY_RESTART=1)")
    else:
        print("services_restarted: yes (by install hook)")
    print(msg("exec_post_install_footer", lang))
    return 0


def run_reboot(args, lang: str) -> int:
    if not args.confirmed:
        die(10, "[ERROR] --confirmed required for --mode=reboot")
    plat = detect_platform(args.platform)
    log_path = LOG_DIR / f"reboot-{now_ts()}.log"
    cur = _current_installed(plat)
    if cur:
        config_dir = _detect_config_dir(plat)
        install_root = INSTALL_DIRS_PARENT / cur
        _enforce_memory_celia_runtime_config(config_dir, install_root, log_path)
    if plat == "celiaclaw":
        if shutil.which("supervisorctl"):
            subprocess.call(["supervisorctl", "restart", "openclaw-gateway"])
            emit(msg("reboot_done", lang), log_path)
            return 0
        emit(msg("manual_reboot_hint", lang), log_path)
        return 0
    # openclaw / celiapro have no canonical service; print hint
    emit(msg("manual_reboot_hint", lang), log_path)
    return 0


# ============================================================================
# Entrypoint
# ============================================================================

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mode",
                    choices=["plan", "execute", "reboot"],
                    required=True)
    ap.add_argument("--version")
    ap.add_argument("--dev", action="store_true")
    ap.add_argument("--remote", action="store_true",
                    help="Download from GaussPD_Artifacts. Without this, "
                         "install/upgrade default to the local tarball cache.")
    ap.add_argument("--channel", choices=["stable", "rc", "dev"],
                    help="Remote channel to resolve; implies --remote.")
    ap.add_argument("--source", dest="source_local_dir")
    ap.add_argument("--offline", action="store_true",
                    help="Install from a tarball pre-staged in the platform "
                         "tarball cache dir ($CELIA_TARBALL_DIR, default "
                         "$CELIA_CONFIG_DIR/extensions/celia_memory/package/). "
                         "No network. This is the default for lifecycle "
                         "actions unless --remote / --channel / --dev is used.")
    ap.add_argument("--platform", choices=["openclaw", "celiaclaw", "celiapro"])
    ap.add_argument("--strict-contract", action="store_true")
    ap.add_argument("--skip-claw-skills", action="store_true")
    ap.add_argument("--lang", choices=["zh", "en"],
                    default=os.environ.get("CELIA_LANG", "en"))
    ap.add_argument("--confirmed", action="store_true")
    args = ap.parse_args()

    if args.dev and (args.version or args.channel):
        die(10, "[ERROR] --dev is mutually exclusive with --version / --channel")
    if args.channel and args.version:
        die(10, "[ERROR] --channel and --version are mutually exclusive")
    if args.source_local_dir and (args.remote or args.channel or args.dev):
        die(10, "[ERROR] --source is mutually exclusive with "
                "--remote / --channel / --dev")
    if args.offline and (args.remote or args.channel or args.dev):
        die(10, "[ERROR] --offline is mutually exclusive with --remote / --channel / --dev")

    lang = args.lang
    handlers = {
        "plan": run_plan,
        "execute": run_execute,
        "reboot": run_reboot,
    }
    try:
        return handlers[args.mode](args, lang)
    except SystemExit:
        raise
    except Exception as e:
        die(99, f"[ERROR] internal: {e!r}")
    return 99


if __name__ == "__main__":
    sys.exit(main())
