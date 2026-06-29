#!/usr/bin/env python3
"""
remote_install.py — standalone online installer for celiaclaw Docker.

This script intentionally does not call:
  - experimental-memory-install/scripts/install.sh
  - experimental-memory-install/scripts/orchestrator.py
  - GaussPD_Memory release tarball scripts/install.sh

It downloads a celiaclaw release from GaussPD_Artifacts and performs the
minimal runtime install steps directly.
"""
from __future__ import annotations

import argparse
import copy
import fcntl
import getpass
import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


EXIT_ARG = 10
EXIT_NET = 20
EXIT_SHA = 30
EXIT_EXTRACT = 40
EXIT_INSTALL = 50
EXIT_CONTRACT = 60
EXIT_LOCK = 70
EXIT_INTERNAL = 99

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent

CONFIG_DIR = Path(
    os.environ.get("CELIA_CONFIG_DIR", "/home/sandbox/.openclaw")
).expanduser()
INSTALL_ROOT = Path(
    os.environ.get("CELIA_INSTALL_ROOT", CONFIG_DIR / "extensions" / "celia_memory")
).expanduser()
INSTALL_PARENT = INSTALL_ROOT / "install"
TARBALL_DIR = Path(
    os.environ.get("CELIA_TARBALL_DIR", INSTALL_ROOT / "package")
).expanduser()
LOG_DIR = Path(
    os.environ.get("CELIA_LOG_DIR", CONFIG_DIR / "logs" / "celia_memory")
).expanduser()
LOCK_FILE = INSTALL_ROOT / ".online-install.lock"
ARTIFACTS_CACHE = INSTALL_ROOT / "_artifacts-online-mirror"
PLAN_SPARSE = [
    "latest-stable.txt",
    "latest-rc.txt",
    "latest-dev.txt",
    "index/**",
]
DEFAULT_GATEWAY_SERVICE = "openclaw-gateway"
DEFAULT_SUPERVISORD_CONF = "/home/sandbox/supervisord.conf"
TRUTHY_VALUES = {"1", "true", "yes", "on"}
MEMORY_PLUGIN_ID = "memory-celia"


def NowTs() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def Emit(line: str, logPath: Path | None = None) -> None:
    print(line, file=sys.stderr)
    if logPath is not None:
        logPath.parent.mkdir(parents=True, exist_ok=True)
        with logPath.open("a", encoding="utf-8") as out:
            out.write(f"[{datetime.now().isoformat(timespec='seconds')}] {line}\n")


def Die(code: int, line: str, logPath: Path | None = None) -> None:
    Emit(line, logPath)
    sys.exit(code)


def RunCommand(cmd: list[str], code: int, label: str,
               logPath: Path | None = None, cwd: Path | None = None) -> None:
    Emit(f"[CMD] {' '.join(cmd)}", logPath)
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if logPath is not None and proc.stdout:
        with logPath.open("a", encoding="utf-8") as out:
            out.write(proc.stdout)
    if proc.returncode != 0:
        Die(code, f"[ERROR] {label} failed rc={proc.returncode}", logPath)


def EnvEnabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in TRUTHY_VALUES


def GatewayService(args) -> str:
    return (
        args.gateway_service
        or os.environ.get("CELIA_GATEWAY_SERVICE")
        or DEFAULT_GATEWAY_SERVICE
    )


def RestartHealthUrl(args) -> str:
    return args.restart_health_url or os.environ.get(
        "CELIA_OPENCLAW_HEALTHCHECK_URL",
        "",
    )


def SkipRestartRequested(args) -> bool:
    return args.skip_gateway_restart or EnvEnabled("CELIA_SKIP_GATEWAY_RESTART")


def AllowNonCeliaclaw(args) -> bool:
    return args.allow_non_celiaclaw or EnvEnabled("CELIA_ALLOW_NON_CELIACLAW")


def RestartDelaySeconds(logPath: Path | None = None) -> int:
    raw = os.environ.get("CELIA_RESTART_DELAY", "5")
    try:
        value = int(raw)
    except ValueError:
        Emit(f"[WARN] invalid CELIA_RESTART_DELAY={raw!r}; use 5s", logPath)
        return 5
    return max(0, min(value, 300))


def SupervisordConfPath() -> Path:
    return Path(
        os.environ.get("CELIA_SUPERVISORD_CONF", DEFAULT_SUPERVISORD_CONF)
    ).expanduser()


def RunCommandCapture(cmd: list[str], timeout: int = 10) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, proc.stdout or ""
    except FileNotFoundError:
        return 127, f"{cmd[0]}: not found\n"
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        return 124, f"{output}\ncommand timed out after {timeout}s\n"


def ShellCommand(cmd: list[str]) -> str:
    return " ".join(shlex.quote(str(item)) for item in cmd)


def WriteText(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def CommandVersion(command: str) -> dict:
    path = shutil.which(command)
    result = {"path": path, "rc": None, "output": ""}
    if path is None:
        return result
    rc, output = RunCommandCapture([command, "--version"], timeout=5)
    result["rc"] = rc
    result["output"] = output.strip()
    return result


def FileFingerprint(path: Path) -> dict:
    info = {
        "path": str(path),
        "exists": path.exists(),
        "is_file": path.is_file(),
        "is_dir": path.is_dir(),
        "sha256": None,
        "size": None,
    }
    if path.is_file():
        info["sha256"] = Sha256File(path)
        info["size"] = path.stat().st_size
    return info


def HasSupervisorctlConfig(cmd: list[str]) -> bool:
    return any(item == "-c" or item.startswith("-c") for item in cmd)


def BuildSupervisorctlController(kind: str, path: str | None,
                                 baseCmd: list[str],
                                 probe: dict | None = None) -> dict:
    conf = SupervisordConfPath()
    command = list(baseCmd)
    if conf.exists() and not HasSupervisorctlConfig(command):
        command.extend(["-c", str(conf)])
    return {
        "available": True,
        "kind": kind,
        "path": path,
        "base_command": list(baseCmd),
        "command": command,
        "supervisord_conf": str(conf),
        "supervisord_conf_exists": conf.exists(),
        "probe": probe or {},
    }


def MissingSupervisorctlController(reason: str,
                                   probe: dict | None = None) -> dict:
    conf = SupervisordConfPath()
    return {
        "available": False,
        "kind": "missing",
        "path": None,
        "base_command": None,
        "command": None,
        "supervisord_conf": str(conf),
        "supervisord_conf_exists": conf.exists(),
        "reason": reason,
        "probe": probe or {},
    }


def ResolveSupervisorctlController() -> dict:
    override = os.environ.get("CELIA_SUPERVISORCTL_COMMAND", "").strip()
    if override:
        try:
            baseCmd = shlex.split(override)
        except ValueError as exc:
            return MissingSupervisorctlController(
                "invalid_CELIA_SUPERVISORCTL_COMMAND",
                {"error": str(exc), "raw": override},
            )
        if not baseCmd:
            return MissingSupervisorctlController(
                "empty_CELIA_SUPERVISORCTL_COMMAND",
                {"raw": override},
            )
        return BuildSupervisorctlController(
            "env_override",
            shutil.which(baseCmd[0]),
            baseCmd,
            {"raw": override},
        )

    supervisorPath = shutil.which("supervisorctl")
    if supervisorPath is not None:
        return BuildSupervisorctlController(
            "path",
            supervisorPath,
            [supervisorPath],
        )

    pythonPath = shutil.which("python3")
    probe = {"python3_path": pythonPath}
    if pythonPath is None:
        return MissingSupervisorctlController("python3_not_found", probe)

    rc, output = RunCommandCapture(
        [pythonPath, "-c", "import supervisor.supervisorctl"],
        timeout=5,
    )
    probe["python_supervisorctl_rc"] = rc
    probe["python_supervisorctl_output"] = output.strip()
    if rc == 0:
        return BuildSupervisorctlController(
            "python_module",
            pythonPath,
            [pythonPath, "-m", "supervisor.supervisorctl"],
            probe,
        )
    return MissingSupervisorctlController("supervisorctl_not_found", probe)


def PlanSummary(plan: dict | None, args=None) -> dict | None:
    if not plan:
        return None
    artifact = plan.get("artifact", {})
    filename = artifact.get("filename")
    if not filename and artifact.get("download_url"):
        filename = artifact["download_url"].rsplit("/", 1)[-1]
    requested = {}
    if args is not None:
        requested = {
            "channel": args.channel,
            "dev": args.dev,
            "version": args.version,
            "variant": args.variant,
        }
    return {
        "requested": requested,
        "resolved": {
            "channel": plan.get("channel"),
            "version": plan.get("version"),
            "variant": plan.get("variant"),
            "arch": plan.get("arch"),
        },
        "artifact": {
            "filename": filename,
            "download_url": artifact.get("download_url"),
            "sha256": artifact.get("sha256"),
        },
        "install_root": str(plan.get("installRoot")),
        "current_root": str(plan.get("currentRoot")),
        "tarball_dir": str(plan.get("tarballDir")),
    }


def OpenClawConfigSummary() -> dict:
    cfgPath = CONFIG_DIR / "openclaw.json"
    summary = {
        "path": str(cfgPath),
        "exists": cfgPath.exists(),
        "parse_error": None,
        "plugin_load_path_count": None,
        "celia_load_paths": [],
        "memory_celia_enabled": None,
        "memory_celia_config": {},
    }
    if not cfgPath.exists():
        return summary
    try:
        cfg = LoadJson(cfgPath)
    except Exception as exc:
        summary["parse_error"] = str(exc)
        return summary

    plugins = cfg.get("plugins", {})
    load = plugins.get("load", {}) if isinstance(plugins, dict) else {}
    paths = load.get("paths", []) if isinstance(load, dict) else []
    if isinstance(paths, list):
        summary["plugin_load_path_count"] = len(paths)
        summary["celia_load_paths"] = [
            item for item in paths if IsCeliaMemoryPluginPath(item)
        ]

    entries = plugins.get("entries", {}) if isinstance(plugins, dict) else {}
    entry = entries.get("memory-celia", {}) if isinstance(entries, dict) else {}
    if not isinstance(entry, dict):
        return summary
    summary["memory_celia_enabled"] = bool(entry.get("enabled"))
    memCfg = entry.get("config", {})
    if isinstance(memCfg, dict):
        configSummary = {}
        for key in ("serverBinaryPath", "dbPath"):
            if isinstance(memCfg.get(key), str):
                configSummary[key] = memCfg[key]
        chat = memCfg.get("chat", {})
        headers = chat.get("headers", {}) if isinstance(chat, dict) else {}
        if isinstance(headers, dict):
            configSummary["chat_header_keys"] = sorted(headers.keys())
        summary["memory_celia_config"] = configSummary
    return summary


def CollectSupervisorStatus(diagDir: Path, stage: str,
                            service: str) -> dict:
    controller = ResolveSupervisorctlController()
    servicePath = diagDir / f"supervisor-status-{stage}.txt"
    allPath = diagDir / f"supervisor-status-all-{stage}.txt"
    if not controller["available"]:
        reason = controller.get("reason", "supervisorctl_not_found")
        WriteText(servicePath, f"supervisorctl unavailable: {reason}\n")
        WriteText(allPath, f"supervisorctl unavailable: {reason}\n")
        return {
            "supervisorctl_path": None,
            "controller": controller,
            "service": service,
            "service_rc": 127,
            "all_rc": 127,
            "restart_capable": False,
            "restart_block_reason": reason,
            "service_status_file": str(servicePath),
            "all_status_file": str(allPath),
        }

    command = controller["command"]
    serviceRc, serviceOut = RunCommandCapture(
        [*command, "status", service],
        timeout=10,
    )
    allRc, allOut = RunCommandCapture([*command, "status"], timeout=10)
    WriteText(servicePath, serviceOut)
    WriteText(allPath, allOut)
    restartCapable = serviceRc == 0
    return {
        "supervisorctl_path": controller["path"],
        "controller": controller,
        "service": service,
        "service_rc": serviceRc,
        "all_rc": allRc,
        "restart_capable": restartCapable,
        "restart_block_reason": None if restartCapable else "service_status_failed",
        "service_status_file": str(servicePath),
        "all_status_file": str(allPath),
    }


def CeliaclawFingerprint(supervisorStatus: dict) -> dict:
    supervisordConf = SupervisordConfPath()
    homeSandbox = Path("/home/sandbox")
    serviceReady = supervisorStatus.get("service_rc") == 0
    matched = (
        homeSandbox.exists()
        and (supervisordConf.exists() or serviceReady)
    )
    return {
        "matched": matched,
        "home_sandbox_exists": homeSandbox.exists(),
        "supervisord_conf": str(supervisordConf),
        "supervisord_conf_exists": supervisordConf.exists(),
        "gateway_service_ready": serviceReady,
    }


def WriteEnvironmentSnapshot(stage: str, installRoot: Path, args,
                             diagDir: Path, logPath: Path,
                             plan: dict | None = None) -> dict:
    service = GatewayService(args)
    supervisorStatus = CollectSupervisorStatus(diagDir, stage, service)
    fingerprint = CeliaclawFingerprint(supervisorStatus)
    snapshot = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "stage": stage,
        "platform": args.platform,
        "argv": sys.argv[1:],
        "plan": PlanSummary(plan, args),
        "cwd": os.getcwd(),
        "user": getpass.getuser(),
        "uid": os.getuid() if hasattr(os, "getuid") else None,
        "home": str(Path.home()),
        "python": sys.version,
        "config_dir": str(CONFIG_DIR),
        "install_root": str(installRoot),
        "current_symlink": str(INSTALL_PARENT / "current"),
        "gateway_service": service,
        "restart_delay_seconds": RestartDelaySeconds(logPath),
        "healthcheck_url": RestartHealthUrl(args),
        "celiaclaw_fingerprint": fingerprint,
        "supervisor": supervisorStatus,
        "openclaw_config": OpenClawConfigSummary(),
        "commands": {
            "node": CommandVersion("node"),
            "npm": CommandVersion("npm"),
            "git": CommandVersion("git"),
        },
        "paths": {
            "openclaw_json": FileFingerprint(CONFIG_DIR / "openclaw.json"),
            "agents_md": FileFingerprint(
                CONFIG_DIR / "workspace" / "AGENTS.md"
            ),
            "current_memory_plugin": FileFingerprint(
                INSTALL_PARENT / "current" / "memory-plugin"
            ),
            "current_memory_plugin_index": FileFingerprint(
                INSTALL_PARENT / "current" / "memory-plugin" / "index.js"
            ),
            "current_celia_memory_mcp_server": FileFingerprint(
                INSTALL_PARENT / "current" / "bin" / "celia_memory_mcp_server"
            ),
            "install_memory_plugin": FileFingerprint(
                installRoot / "memory-plugin"
            ),
            "install_memory_plugin_index": FileFingerprint(
                installRoot / "memory-plugin" / "index.js"
            ),
            "install_celia_memory_mcp_server": FileFingerprint(
                installRoot / "bin" / "celia_memory_mcp_server"
            ),
        },
    }
    snapshotPath = diagDir / f"{stage}-snapshot.json"
    WriteText(snapshotPath, json.dumps(snapshot, indent=2, ensure_ascii=False))
    envLines = [
        f"stage={stage}",
        f"timestamp={snapshot['timestamp']}",
        f"platform={args.platform}",
        f"cwd={snapshot['cwd']}",
        f"user={snapshot['user']}",
        f"uid={snapshot['uid']}",
        f"home={snapshot['home']}",
        f"CELIA_CONFIG_DIR={CONFIG_DIR}",
        f"CELIA_INSTALL_ROOT={INSTALL_ROOT}",
        f"CELIA_TARBALL_DIR={TARBALL_DIR}",
        f"CELIA_LOG_DIR={LOG_DIR}",
        f"gateway_service={service}",
        f"supervisorctl={supervisorStatus['supervisorctl_path']}",
        f"supervisorctl_kind="
        f"{supervisorStatus['controller'].get('kind')}",
        f"supervisorctl_command="
        f"{supervisorStatus['controller'].get('command')}",
        f"supervisor_service_rc={supervisorStatus['service_rc']}",
        f"supervisor_all_rc={supervisorStatus['all_rc']}",
        f"restart_capable={supervisorStatus['restart_capable']}",
        f"restart_block_reason={supervisorStatus['restart_block_reason']}",
        f"celiaclaw_fingerprint={fingerprint['matched']}",
        f"supervisord_conf={fingerprint['supervisord_conf']}",
        f"supervisord_conf_exists={fingerprint['supervisord_conf_exists']}",
        f"openclaw_json_sha256="
        f"{snapshot['paths']['openclaw_json']['sha256']}",
        f"agents_md_sha256={snapshot['paths']['agents_md']['sha256']}",
        f"snapshot_json={snapshotPath}",
    ]
    WriteText(diagDir / f"env-{stage}.txt", "\n".join(envLines) + "\n")
    Emit(f"[INFO] wrote {stage} diagnostics: {snapshotPath}", logPath)
    return snapshot


def PreflightEnvironment(plan: dict, args, diagDir: Path,
                         logPath: Path) -> dict:
    snapshot = WriteEnvironmentSnapshot(
        "preflight",
        plan["installRoot"],
        args,
        diagDir,
        logPath,
        plan,
    )
    fingerprint = snapshot["celiaclaw_fingerprint"]
    if fingerprint["matched"] or SkipRestartRequested(args):
        return snapshot
    if AllowNonCeliaclaw(args):
        Emit("[WARN] non-celiaclaw fingerprint allowed by override", logPath)
        return snapshot
    Die(
        EXIT_ARG,
        "[ERROR] celiaclaw supervisor fingerprint missing; rerun with "
        "--skip-gateway-restart to install without auto restart, or set "
        "CELIA_ALLOW_NON_CELIACLAW=1 only after confirming this deployment",
        logPath,
    )


class InstallLock:
    def __init__(self, path: Path):
        self.path = path
        self.handle = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("w")
        try:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.handle.close()
            raise
        return self

    def __exit__(self, *_args):
        if self.handle:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            self.handle.close()


def LoadCompat() -> dict:
    candidates = [
        SCRIPT_DIR / "compat-version.toml",
        SKILL_ROOT / "compat-version.toml",
    ]
    for path in candidates:
        if path.exists():
            with path.open("rb") as handle:
                return tomllib.load(handle)
    Die(EXIT_INTERNAL, "compat-version.toml missing")


def HostArch() -> str:
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        return "linux-amd64"
    if machine in ("aarch64", "arm64"):
        return "linux-arm64"
    return "any"


def DetectGlibc() -> tuple[int, int] | None:
    if platform.system() != "Linux":
        return None
    try:
        out = subprocess.check_output(
            ["ldd", "--version"],
            stderr=subprocess.STDOUT,
            text=True,
            timeout=5,
        )
    except Exception:
        return None
    match = re.search(r"(\d+)\.(\d+)", out.splitlines()[0])
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def LdconfigOutput() -> str:
    for command in (["ldconfig", "-p"], ["/sbin/ldconfig", "-p"]):
        try:
            return subprocess.check_output(
                command,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=5,
            )
        except Exception:
            continue
    return ""


def HasSharedLibrary(soname: str) -> bool:
    if platform.system() != "Linux":
        return False

    if soname in LdconfigOutput():
        return True

    searchDirs = [
        "/lib64",
        "/usr/lib64",
        "/lib",
        "/usr/lib",
        "/lib/x86_64-linux-gnu",
        "/usr/lib/x86_64-linux-gnu",
        "/lib/aarch64-linux-gnu",
        "/usr/lib/aarch64-linux-gnu",
    ]
    return any((Path(item) / soname).exists() for item in searchDirs)


def PreferManylinuxVariant() -> bool:
    glibc = DetectGlibc()
    if glibc is not None and glibc < (2, 34):
        return True

    hasSsl3 = HasSharedLibrary("libssl.so.3")
    hasSsl11 = HasSharedLibrary("libssl.so.1.1")
    return hasSsl11 and not hasSsl3


def DefaultVariant() -> str:
    if PreferManylinuxVariant():
        return "full-manylinux_2_28"
    return "full"


def VariantArch(variant: str) -> str:
    return "any" if variant == "plugins" else HostArch()


def CacheTtlSeconds() -> int:
    raw = os.environ.get("CELIA_ARTIFACTS_CACHE_TTL", "300")
    try:
        return max(0, int(raw))
    except ValueError:
        return 300


def GitRepoUrl() -> str:
    return os.environ.get(
        "CELIA_ARTIFACTS_REPO_URL",
        "https://gitcode.com/CayleyVanguard/GaussPD_Artifacts.git",
    )


def RunGit(cmd: list[str], label: str) -> None:
    proc = subprocess.run(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if proc.returncode != 0:
        Die(EXIT_NET, f"[ERROR] {label} failed rc={proc.returncode}")


def SetSparse(paths: list[str]) -> None:
    RunGit(
        ["git", "-C", str(ARTIFACTS_CACHE), "sparse-checkout", "set",
         "--no-cone", *paths],
        "git sparse-checkout set",
    )


def EnsureArtifactsMirror() -> Path:
    repoUrl = GitRepoUrl()
    if ARTIFACTS_CACHE.exists():
        proc = subprocess.run(
            ["git", "-C", str(ARTIFACTS_CACHE), "remote", "get-url", "origin"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        current = proc.stdout.strip() if proc.returncode == 0 else ""
        if current != repoUrl:
            shutil.rmtree(ARTIFACTS_CACHE, ignore_errors=True)

    if not ARTIFACTS_CACHE.exists():
        ARTIFACTS_CACHE.parent.mkdir(parents=True, exist_ok=True)
        RunGit(
            ["git", "clone", "--depth=1", "--filter=blob:none",
             "--no-checkout", repoUrl, str(ARTIFACTS_CACHE)],
            "git clone artifacts",
        )
        RunGit(
            ["git", "-C", str(ARTIFACTS_CACHE), "sparse-checkout",
             "init", "--no-cone"],
            "git sparse-checkout init",
        )
        SetSparse(PLAN_SPARSE)
        RunGit(
            ["git", "-C", str(ARTIFACTS_CACHE), "checkout", "main"],
            "git checkout main",
        )
        return ARTIFACTS_CACHE

    headPath = ARTIFACTS_CACHE / ".git" / "FETCH_HEAD"
    age = time.time() - headPath.stat().st_mtime if headPath.exists() else 1e9
    if age > CacheTtlSeconds():
        RunGit(
            ["git", "-C", str(ARTIFACTS_CACHE), "fetch", "--depth=1",
             "origin", "main"],
            "git fetch artifacts",
        )
        RunGit(
            ["git", "-C", str(ARTIFACTS_CACHE), "reset", "--hard",
             "origin/main"],
            "git reset artifacts",
        )
        SetSparse(PLAN_SPARSE)
    return ARTIFACTS_CACHE


def EnsureReleaseInMirror(version: str) -> None:
    EnsureArtifactsMirror()
    SetSparse([*PLAN_SPARSE, f"releases/{version}/**"])


def FetchPointer(channel: str) -> str:
    mirror = EnsureArtifactsMirror()
    pointer = mirror / f"latest-{channel}.txt"
    if not pointer.exists():
        Die(EXIT_NET, f"[ERROR] remote pointer missing: {pointer}")
    return pointer.read_text(encoding="utf-8").strip()


def FetchManifest(version: str, arch: str) -> dict:
    mirror = EnsureArtifactsMirror()
    path = mirror / "index" / version / "celiaclaw" / arch / "manifest.toml"
    if not path.exists():
        Die(EXIT_NET, f"[ERROR] manifest missing: {path}")
    with path.open("rb") as handle:
        return tomllib.load(handle)


def PickArtifact(manifest: dict, requested: str) -> dict:
    candidates = [requested]
    if requested == "full":
        candidates.append("full-manylinux_2_28")
    elif requested == "full-manylinux_2_28":
        candidates.append("full")
    for name in candidates:
        for artifact in manifest.get("artifact", []) or []:
            if artifact.get("artifact") == name:
                return dict(artifact)
    Die(EXIT_NET, f"[ERROR] no artifact {requested} in manifest")


def ResolvePlan(args) -> dict:
    channel = "dev" if args.dev else (args.channel or "rc")
    version = args.version or FetchPointer(channel)
    variant = args.variant or DefaultVariant()
    arch = VariantArch(variant)
    manifest = FetchManifest(version, arch)
    artifact = PickArtifact(manifest, variant)
    return {
        "version": version,
        "channel": channel,
        "variant": artifact.get("artifact", variant),
        "arch": arch,
        "manifest": manifest,
        "artifact": artifact,
        "installRoot": INSTALL_PARENT / version,
        "currentRoot": INSTALL_PARENT / "current",
        "tarballDir": TARBALL_DIR,
    }


def Sha256File(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def HttpGet(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "experimental-memory-install-online/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return resp.read()
    except urllib.error.URLError as exc:
        Die(EXIT_NET, f"[ERROR] download failed: {url}: {exc}")


def AcquireTarball(plan: dict, logPath: Path) -> Path:
    artifact = plan["artifact"]
    filename = artifact.get("filename")
    if not filename:
        filename = artifact["download_url"].rsplit("/", 1)[-1]
    target = TARBALL_DIR / filename
    sidecar = target.with_suffix(target.suffix + ".sha256")
    want = artifact["sha256"]
    TARBALL_DIR.mkdir(parents=True, exist_ok=True)

    if target.exists() and sidecar.exists():
        cached = sidecar.read_text(encoding="utf-8").strip().split()[0]
        if cached == want and Sha256File(target) == want:
            Emit(f"[INFO] reusing cached tarball: {target}", logPath)
            return target
        Emit(f"[WARN] cached tarball sha mismatch, refreshing: {target}",
             logPath)

    EnsureReleaseInMirror(plan["version"])
    worktree = (
        ARTIFACTS_CACHE / "releases" / plan["version"] / filename
    )
    if worktree.exists():
        Emit(f"[INFO] using worktree tarball: {worktree}", logPath)
        if Sha256File(worktree) != want:
            Die(EXIT_SHA, f"[ERROR] SHA256 mismatch for {worktree}", logPath)
        shutil.copy2(worktree, target)
        sidecar.write_text(want + "\n", encoding="utf-8")
        return target

    url = artifact["download_url"]
    Emit(f"[INFO] downloading: {url}", logPath)
    partial = target.with_suffix(target.suffix + ".partial")
    partial.write_bytes(HttpGet(url))
    got = Sha256File(partial)
    if got != want:
        partial.unlink(missing_ok=True)
        Die(EXIT_SHA, f"[ERROR] SHA256 mismatch: want={want} got={got}",
            logPath)
    partial.replace(target)
    sidecar.write_text(want + "\n", encoding="utf-8")
    return target


def SafeExtract(tarball: Path, dst: Path) -> None:
    tmp = dst.parent / (dst.name + "-tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    try:
        with tarfile.open(tarball, "r:gz") as tf:
            root = tmp.resolve()
            for member in tf.getmembers():
                target = (tmp / member.name).resolve()
                if not str(target).startswith(str(root)):
                    raise RuntimeError(
                        f"refusing to extract outside dst: {member.name}"
                    )
            tf.extractall(tmp)
        children = list(tmp.iterdir())
        if len(children) == 1 and children[0].is_dir():
            inner = children[0]
            for item in inner.iterdir():
                shutil.move(str(item), str(tmp / item.name))
            inner.rmdir()
        if dst.exists():
            shutil.rmtree(dst)
        tmp.rename(dst)
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise


def LoadJson(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def WriteJson(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def ResolveValue(value: str, installRoot: Path) -> str:
    currentRoot = str(INSTALL_PARENT / "current")
    return (
        value.replace("${CELIA_INSTALL_ROOT}", currentRoot)
        .replace("${CELIA_PLUGIN_ROOT}", currentRoot)
        .replace("${CELIA_CONFIG_ROOT}", str(CONFIG_DIR))
        .replace("${CELIA_CONFIG_DIR}", str(CONFIG_DIR))
    )


def ResolvePlaceholders(node, installRoot: Path):
    if isinstance(node, dict):
        return {key: ResolvePlaceholders(val, installRoot)
                for key, val in node.items()}
    if isinstance(node, list):
        return [ResolvePlaceholders(val, installRoot) for val in node]
    if isinstance(node, str):
        return ResolveValue(node, installRoot)
    return node


def DeepMerge(dst, src):
    if not isinstance(dst, dict) or not isinstance(src, dict):
        return src
    for key, value in src.items():
        dst[key] = DeepMerge(dst[key], value) if key in dst else value
    return dst


def IsCeliaMemoryPluginPath(value) -> bool:
    return (
        isinstance(value, str)
        and value.endswith("/memory-plugin")
        and ("/celia_memory/" in value or "${CELIA_INSTALL_ROOT}" in value)
    )


def IsManagedMemoryPluginPath(value) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.rstrip("/")
    return normalized.endswith("/memory-plugin")


def IsManagedMemoryEntry(name, entry, activeMemoryId) -> bool:
    if name == MEMORY_PLUGIN_ID or name == activeMemoryId:
        return True
    if not isinstance(name, str) or not name.startswith("memory-"):
        return False
    if not isinstance(entry, dict):
        return False
    cfg = entry.get("config")
    if isinstance(cfg, dict):
        ownedKeys = ("serverBinaryPath", "dbPath", "vectorDim", "embed", "chat")
        if any(key in cfg for key in ownedKeys):
            return True
    hooks = entry.get("hooks")
    return isinstance(hooks, dict) and hooks.get("allowConversationAccess") is True


def CleanManagedMemoryAllowList(plugins: dict, staleNames: set[str]) -> None:
    allow = plugins.get("allow")
    if not isinstance(allow, list):
        return
    cleaned = []
    seen = set()
    for item in allow:
        if item in staleNames:
            continue
        if item not in seen:
            cleaned.append(item)
            seen.add(item)
    if MEMORY_PLUGIN_ID not in seen:
        cleaned.append(MEMORY_PLUGIN_ID)
    plugins["allow"] = cleaned


def MergeOpenClawConfig(installRoot: Path, logPath: Path) -> None:
    source = installRoot / "openclaw" / "config" / "openclaw.json"
    overlay = installRoot / "celiaclaw" / "config" / "openclaw.json"
    target = CONFIG_DIR / "openclaw.json"
    if not source.exists():
        Die(EXIT_INSTALL, f"[ERROR] release missing {source}", logPath)

    src = ResolvePlaceholders(LoadJson(source), installRoot)
    over = ResolvePlaceholders(LoadJson(overlay), installRoot)
    dst = LoadJson(target)
    if target.exists():
        backup = target.with_suffix(target.suffix + f".bak.{NowTs()}")
        shutil.copy2(target, backup)
        Emit(f"[INFO] backed up openclaw.json: {backup}", logPath)

    dstPlugins = dst.setdefault("plugins", {})
    srcPlugins = src.get("plugins", {}) if isinstance(src.get("plugins"), dict) else {}
    existingSlots = dstPlugins.get("slots")
    activeMemoryId = (
        existingSlots.get("memory")
        if isinstance(existingSlots, dict)
        else None
    )

    if isinstance(src.get("agents"), dict):
        dstAgents = dst.setdefault("agents", {})
        DeepMerge(dstAgents, src["agents"])

    if isinstance(srcPlugins.get("slots"), dict):
        dstSlots = dstPlugins.setdefault("slots", {})
        dstSlots.update(srcPlugins["slots"])

    if isinstance(srcPlugins.get("load"), dict):
        dstLoad = dstPlugins.setdefault("load", {})
        currentPaths = dstLoad.get("paths")
        if not isinstance(currentPaths, list):
            currentPaths = []
        desired = [
            item for item in srcPlugins["load"].get("paths", [])
            if IsCeliaMemoryPluginPath(item)
        ]
        cleaned = []
        seen = set()
        desiredSet = set(desired)
        for item in currentPaths:
            if IsManagedMemoryPluginPath(item) and item not in desiredSet:
                continue
            if item not in seen:
                cleaned.append(item)
                seen.add(item)
        for item in desired:
            if item not in seen:
                cleaned.append(item)
                seen.add(item)
        dstLoad["paths"] = cleaned

    srcEntries = srcPlugins.get("entries")
    staleNames = set()
    if isinstance(activeMemoryId, str) and activeMemoryId != MEMORY_PLUGIN_ID:
        staleNames.add(activeMemoryId)
    if isinstance(srcEntries, dict):
        dstEntries = dstPlugins.setdefault("entries", {})
        for name, entry in list(dstEntries.items()):
            if IsManagedMemoryEntry(name, entry, activeMemoryId):
                staleNames.add(name)
                del dstEntries[name]
        for name, entry in srcEntries.items():
            if name != MEMORY_PLUGIN_ID and name not in dstEntries:
                dstEntries[name] = copy.deepcopy(entry)
        if isinstance(srcEntries.get(MEMORY_PLUGIN_ID), dict):
            dstEntries[MEMORY_PLUGIN_ID] = copy.deepcopy(
                srcEntries[MEMORY_PLUGIN_ID]
            )
            dstEntries[MEMORY_PLUGIN_ID]["enabled"] = True

    srcInstalls = srcPlugins.get("installs")
    if isinstance(srcInstalls, dict):
        dstInstalls = dstPlugins.setdefault("installs", {})
        for name in staleNames:
            dstInstalls.pop(name, None)
        for name, entry in srcInstalls.items():
            if name == MEMORY_PLUGIN_ID:
                dstInstalls[MEMORY_PLUGIN_ID] = copy.deepcopy(entry)
            else:
                dstInstalls.setdefault(name, copy.deepcopy(entry))
    CleanManagedMemoryAllowList(dstPlugins, staleNames)

    if over:
        dst = DeepMerge(dst, over)
        dst = ResolvePlaceholders(dst, installRoot)

    memCfg = (
        dst.get("plugins", {})
        .get("entries", {})
        .get(MEMORY_PLUGIN_ID, {})
        .get("config", {})
    )
    dbPath = memCfg.get("dbPath") if isinstance(memCfg, dict) else None
    if isinstance(dbPath, str) and dbPath:
        Path(dbPath).expanduser().parent.mkdir(parents=True, exist_ok=True)

    WriteJson(target, dst)
    Emit(f"[INFO] merged openclaw.json: {target}", logPath)


def LiftRuntimeLayout(installRoot: Path, logPath: Path) -> None:
    openclaw = installRoot / "openclaw"
    for name in ("memory-plugin", "shared"):
        src = openclaw / name
        dst = installRoot / name
        if src.exists():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.move(str(src), str(dst))
    binSrc = openclaw / "bin" / "celia_memory_mcp_server"
    if binSrc.exists():
        binDst = installRoot / "bin" / "celia_memory_mcp_server"
        binDst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(binSrc, binDst)
        binDst.chmod(0o755)
    if not (installRoot / "memory-plugin").is_dir():
        Die(EXIT_INSTALL, "[ERROR] memory-plugin not installed", logPath)
    if not (installRoot / "memory-plugin" / "index.js").exists():
        Die(EXIT_INSTALL, "[ERROR] memory-plugin/index.js missing", logPath)
    if binSrc.exists() and not (installRoot / "bin" / "celia_memory_mcp_server").exists():
        Die(EXIT_INSTALL, "[ERROR] celia_memory_mcp_server not installed", logPath)
    Emit(f"[INFO] runtime files staged under {installRoot}", logPath)


def InstallNpmDeps(installRoot: Path, args, logPath: Path) -> None:
    if args.skip_npm_install:
        Emit("[WARN] skipped npm install by request", logPath)
        return
    pluginDir = installRoot / "memory-plugin"
    if not (pluginDir / "package.json").exists():
        return
    if shutil.which("npm") is None:
        Die(EXIT_INSTALL, "[ERROR] npm not found; cannot install runtime deps",
            logPath)
    registry = os.environ.get("CELIA_NPM_REGISTRY", "https://registry.npmmirror.com")
    RunCommand(
        ["npm", "install", "--omit=dev", "--no-audit", "--no-fund",
         "--registry", registry],
        EXIT_INSTALL,
        "npm install",
        logPath,
        pluginDir,
    )


def ResolveAgentsSource(installRoot: Path, args) -> Path | None:
    if args.no_replace_agents:
        return None
    explicit = args.agents_md or os.environ.get("CELIA_AGENTS_MD_SRC")
    if explicit:
        return Path(explicit).expanduser()
    return installRoot / "celiaclaw" / "config" / "AGENTS.md"


def ReplaceAgentsMd(installRoot: Path, args, logPath: Path) -> None:
    source = ResolveAgentsSource(installRoot, args)
    if source is None:
        Emit("[INFO] AGENTS.md replacement skipped", logPath)
        return
    if not source.exists():
        Die(EXIT_ARG, f"[ERROR] AGENTS.md source not found: {source}", logPath)
    target = CONFIG_DIR / "workspace" / "AGENTS.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        backup = target.with_suffix(target.suffix + f".bak.{NowTs()}")
        shutil.copy2(target, backup)
        Emit(f"[INFO] backed up AGENTS.md: {backup}", logPath)
    shutil.copy2(source, target)
    Emit(f"[INFO] replaced AGENTS.md: {target} <- {source}", logPath)


def DeployBundledSkills(installRoot: Path, logPath: Path) -> None:
    sourceRoot = installRoot / "celiaclaw" / "skills"
    if not sourceRoot.is_dir():
        Emit("[WARN] release has no celiaclaw/skills; skip skill deployment",
             logPath)
        return
    targetRoot = CONFIG_DIR / "workspace" / "skills"
    targetRoot.mkdir(parents=True, exist_ok=True)
    count = 0
    for skillDir in sorted(sourceRoot.iterdir()):
        if not skillDir.is_dir() or not (skillDir / "SKILL.md").exists():
            continue
        target = targetRoot / skillDir.name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(skillDir, target, symlinks=False)
        count += 1
    Emit(f"[INFO] deployed {count} bundled skill(s) to {targetRoot}", logPath)


def SwitchCurrent(installRoot: Path, logPath: Path) -> None:
    current = INSTALL_PARENT / "current"
    previous = INSTALL_PARENT / "previous"
    oldTarget = current.resolve(strict=False) if current.is_symlink() else None
    if oldTarget and oldTarget.exists() and oldTarget != installRoot:
        tmpPrevious = previous.with_name("previous.tmp")
        tmpPrevious.unlink(missing_ok=True)
        tmpPrevious.symlink_to(oldTarget)
        tmpPrevious.replace(previous)
        Emit(f"[INFO] previous -> {oldTarget}", logPath)
    elif previous.is_symlink() and oldTarget and not oldTarget.exists():
        previous.unlink(missing_ok=True)

    if current.exists() and not current.is_symlink():
        shutil.rmtree(current)
    tmpCurrent = current.with_name("current.tmp")
    tmpCurrent.unlink(missing_ok=True)
    tmpCurrent.symlink_to(installRoot)
    tmpCurrent.replace(current)
    Emit(f"[INFO] current -> {installRoot}", logPath)


def VerifyInstall(installRoot: Path, logPath: Path) -> None:
    current = INSTALL_PARENT / "current"
    checks = [
        current / "memory-plugin" / "index.js",
        CONFIG_DIR / "openclaw.json",
        CONFIG_DIR / "workspace" / "AGENTS.md",
    ]
    for path in checks:
        if not path.exists():
            Die(EXIT_INSTALL, f"[ERROR] post-install missing: {path}", logPath)
    cfg = LoadJson(CONFIG_DIR / "openclaw.json")
    entry = (
        cfg.get("plugins", {})
        .get("entries", {})
        .get("memory-celia", {})
    )
    if not isinstance(entry, dict) or not entry.get("enabled"):
        Die(EXIT_INSTALL, "[ERROR] memory-celia entry not enabled", logPath)


def ShellPrint(text: str) -> str:
    return f"printf '%s\\n' {shlex.quote(text)}"


def WriteRestartScript(args, diagDir: Path, restartLog: Path,
                       afterStatusPath: Path, afterAllStatusPath: Path,
                       delay: int, controllerCmd: list[str]) -> Path:
    service = GatewayService(args)
    healthUrl = RestartHealthUrl(args)
    script = diagDir / "gateway-restart.sh"
    controller = ShellCommand(controllerCmd)
    lines = [
        "#!/bin/bash",
        "set +e",
        f"exec >> {shlex.quote(str(restartLog))} 2>&1",
        'printf "[gateway-restart] started_at=%s\\n" "$(date -Is)"',
        ShellPrint(f"[gateway-restart] service={service}"),
        ShellPrint(f"[gateway-restart] controller={controller}"),
        ShellPrint(f"[gateway-restart] delay_seconds={delay}"),
        f"sleep {delay}",
        ShellPrint("[gateway-restart] status_before_restart"),
        f"{controller} status {shlex.quote(service)}",
        "status_before_rc=$?",
        'printf "[gateway-restart] status_before_rc=%s\\n" "${status_before_rc}"',
        f"{controller} restart {shlex.quote(service)}",
        "restart_rc=$?",
        'printf "[gateway-restart] restart_rc=%s\\n" "${restart_rc}"',
        ShellPrint("[gateway-restart] status_after_restart"),
        (
            f"{controller} status {shlex.quote(service)} "
            f"> {shlex.quote(str(afterStatusPath))} 2>&1"
        ),
        "status_after_rc=$?",
        f"cat {shlex.quote(str(afterStatusPath))}",
        'printf "[gateway-restart] status_after_rc=%s\\n" "${status_after_rc}"',
        ShellPrint("[gateway-restart] supervisor_status_all_after"),
        (
            f"{controller} status "
            f"> {shlex.quote(str(afterAllStatusPath))} 2>&1"
        ),
        "status_all_after_rc=$?",
        f"cat {shlex.quote(str(afterAllStatusPath))}",
        (
            'printf "[gateway-restart] status_all_after_rc=%s\\n" '
            '"${status_all_after_rc}"'
        ),
    ]
    if healthUrl:
        lines.extend([
            ShellPrint(f"[gateway-restart] healthcheck_url={healthUrl}"),
            "if command -v curl >/dev/null 2>&1; then",
            (
                "  curl -fsS --max-time 5 "
                f"{shlex.quote(healthUrl)} >/dev/null"
            ),
            "  health_rc=$?",
            "else",
            "  health_rc=127",
            "  " + ShellPrint("[gateway-restart] curl_not_found"),
            "fi",
            'printf "[gateway-restart] healthcheck_rc=%s\\n" "${health_rc}"',
        ])
    else:
        lines.append(ShellPrint("[gateway-restart] healthcheck_skipped"))
    lines.extend([
        'printf "[gateway-restart] finished_at=%s\\n" "$(date -Is)"',
        "exit ${restart_rc}",
    ])
    WriteText(script, "\n".join(lines) + "\n")
    script.chmod(0o755)
    return script


def SuggestedRestartCommands(controller: dict, service: str) -> list[str]:
    command = controller.get("command")
    if isinstance(command, list) and command:
        base = ShellCommand(command)
        return [
            f"{base} status {shlex.quote(service)}",
            f"{base} restart {shlex.quote(service)}",
        ]
    conf = SupervisordConfPath()
    confArg = f"-c {shlex.quote(str(conf))} " if conf.exists() else ""
    return [
        f"python3 -m supervisor.supervisorctl {confArg}status "
        f"{shlex.quote(service)}",
        f"python3 -m supervisor.supervisorctl {confArg}restart "
        f"{shlex.quote(service)}",
        f"supervisorctl {confArg}restart {shlex.quote(service)}",
    ]


def RuntimeEffectiveStatus(restartResult: dict) -> str:
    if restartResult.get("scheduled"):
        return "pending_restart"
    return "unknown_until_gateway_restart"


def ManualRestartRequired(restartResult: dict) -> bool:
    return not restartResult.get("scheduled", False)


def WriteRestartSkipReport(args, diagDir: Path, restartResult: dict,
                           supervisorStatus: dict | None = None) -> Path:
    service = GatewayService(args)
    controller = (
        supervisorStatus.get("controller")
        if supervisorStatus is not None
        else ResolveSupervisorctlController()
    )
    if not isinstance(controller, dict):
        controller = ResolveSupervisorctlController()
    report = {
        "restart_scheduled": False,
        "manual_restart_required": ManualRestartRequired(restartResult),
        "runtime_effective": RuntimeEffectiveStatus(restartResult),
        "status": restartResult.get("status"),
        "service": service,
        "controller": controller,
        "service_status_file": restartResult.get("service_status_file"),
        "suggested_commands": SuggestedRestartCommands(controller, service),
    }
    path = diagDir / "restart-skip.json"
    WriteText(path, json.dumps(report, indent=2, ensure_ascii=False))
    return path


def ScheduleGatewayRestart(args, logPath: Path, diagDir: Path) -> dict:
    service = GatewayService(args)
    result = {
        "scheduled": False,
        "method": None,
        "service": service,
        "status": "not_requested",
        "verified": "no",
        "log": None,
        "script": None,
        "delay_seconds": None,
        "manual_restart_required": True,
        "runtime_effective": "unknown_until_gateway_restart",
    }
    if SkipRestartRequested(args):
        Emit("[INFO] gateway restart skipped", logPath)
        result["status"] = "skipped_by_request"
        skipReport = WriteRestartSkipReport(args, diagDir, result)
        result["skip_report"] = str(skipReport)
        return result

    before = CollectSupervisorStatus(diagDir, "restart-before", service)
    controller = before.get("controller", {})
    result["method"] = controller.get("kind")
    result["controller"] = controller
    if not controller.get("available"):
        Emit(
            "[WARN] supervisor controller unavailable; "
            "gateway restart not scheduled",
            logPath,
        )
        result["status"] = before.get(
            "restart_block_reason",
            "supervisorctl_not_found",
        )
        result["service_status_file"] = before["service_status_file"]
        skipReport = WriteRestartSkipReport(args, diagDir, result, before)
        result["skip_report"] = str(skipReport)
        return result
    if before["service_rc"] != 0:
        Emit(
            f"[WARN] supervisor service {service} not ready; "
            "gateway restart not scheduled",
            logPath,
        )
        result["status"] = "service_status_failed"
        result["service_status_file"] = before["service_status_file"]
        skipReport = WriteRestartSkipReport(args, diagDir, result, before)
        result["skip_report"] = str(skipReport)
        return result

    delay = RestartDelaySeconds(logPath)
    restartLog = diagDir / "gateway-restart.log"
    afterStatusPath = diagDir / "supervisor-status-restart-after.txt"
    afterAllStatusPath = diagDir / "supervisor-status-all-restart-after.txt"
    controllerCmd = controller.get("command")
    script = WriteRestartScript(args, diagDir, restartLog, afterStatusPath,
                                afterAllStatusPath, delay, controllerCmd)
    subprocess.Popen(
        ["bash", str(script)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    Emit(f"[INFO] gateway restart scheduled after {delay}s: {restartLog}",
         logPath)
    result.update({
        "scheduled": True,
        "status": "scheduled",
        "verified": "pending",
        "manual_restart_required": False,
        "runtime_effective": "pending_restart",
        "log": str(restartLog),
        "script": str(script),
        "delay_seconds": delay,
        "service_status_file": before["service_status_file"],
        "controller_command": controllerCmd,
        "after_status_file": str(afterStatusPath),
        "after_all_status_file": str(afterAllStatusPath),
    })
    return result


def WritePostInstallReport(plan: dict, args, diagDir: Path, logPath: Path,
                           restartResult: dict) -> Path:
    report = {
        "install_complete": True,
        "plan": PlanSummary(plan, args),
        "version": plan["version"],
        "install_root": str(plan["installRoot"]),
        "current": str(plan["currentRoot"]),
        "agents_replaced": not args.no_replace_agents,
        "log": str(logPath),
        "diagnostics": str(diagDir),
        "openclaw_config": OpenClawConfigSummary(),
        "manual_restart_required": ManualRestartRequired(restartResult),
        "runtime_effective": RuntimeEffectiveStatus(restartResult),
        "restart": restartResult,
    }
    path = diagDir / "post-install.json"
    WriteText(path, json.dumps(report, indent=2, ensure_ascii=False))
    return path


def RunPlan(args) -> int:
    plan = ResolvePlan(args)
    artifact = plan["artifact"]
    agents = args.agents_md or os.environ.get("CELIA_AGENTS_MD_SRC")
    agentsDesc = agents if agents else "downloaded celiaclaw/config/AGENTS.md"
    print("[PLAN] Online install plan:")
    print(f"  platform: celiaclaw")
    print(f"  channel: {plan['channel']}")
    print(f"  version: {plan['version']}")
    print(f"  arch: {plan['arch']}")
    print(f"  artifact: {plan['variant']}")
    print(f"  download: {artifact['download_url']}")
    print(f"  sha256: {artifact['sha256']}")
    print(f"  tarball cache: {plan['tarballDir']}")
    print(f"  install root: {plan['installRoot']}")
    print(f"  current symlink: {plan['currentRoot']}")
    print(f"  openclaw.json target: {CONFIG_DIR / 'openclaw.json'}")
    print(f"  AGENTS.md source: {agentsDesc}")
    print(f"  AGENTS.md target: {CONFIG_DIR / 'workspace' / 'AGENTS.md'}")
    print(f"  gateway service: {GatewayService(args)}")
    print("  install method: standalone online skill, no legacy skill/hook call")
    print("[/PLAN]")
    return 0


def RunExecute(args) -> int:
    if not args.confirmed:
        Die(EXIT_ARG, "[ERROR] --confirmed required for --mode=execute")
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    runId = NowTs()
    logPath = LOG_DIR / f"install-online-{runId}.log"
    diagDir = LOG_DIR / "diagnostics" / runId
    diagDir.mkdir(parents=True, exist_ok=True)
    try:
        with InstallLock(LOCK_FILE):
            return ExecuteLocked(args, logPath, diagDir)
    except BlockingIOError:
        Die(EXIT_LOCK, f"[ERROR] another install holds {LOCK_FILE}", logPath)


def ExecuteLocked(args, logPath: Path, diagDir: Path) -> int:
    plan = ResolvePlan(args)
    PreflightEnvironment(plan, args, diagDir, logPath)
    tarball = AcquireTarball(plan, logPath)
    installRoot = plan["installRoot"]
    INSTALL_PARENT.mkdir(parents=True, exist_ok=True)

    Emit(f"[INFO] extracting {tarball} -> {installRoot}", logPath)
    try:
        SafeExtract(tarball, installRoot)
    except Exception as exc:
        Die(EXIT_EXTRACT, f"[ERROR] extract failed: {exc}", logPath)

    contract = installRoot / "scripts" / "contract.toml"
    if not contract.exists():
        Die(EXIT_CONTRACT, f"[ERROR] missing contract: {contract}", logPath)
    contractData = tomllib.loads(contract.read_text(encoding="utf-8"))
    supported = LoadCompat().get("supported_contract_versions", [1])
    if contractData.get("contract_version") not in supported:
        Die(EXIT_CONTRACT,
            f"[ERROR] unsupported contract_version="
            f"{contractData.get('contract_version')} supported={supported}",
            logPath)

    LiftRuntimeLayout(installRoot, logPath)
    InstallNpmDeps(installRoot, args, logPath)
    MergeOpenClawConfig(installRoot, logPath)
    ReplaceAgentsMd(installRoot, args, logPath)
    DeployBundledSkills(installRoot, logPath)
    SwitchCurrent(installRoot, logPath)
    VerifyInstall(installRoot, logPath)
    WriteEnvironmentSnapshot("post-install", installRoot, args, diagDir,
                             logPath, plan)
    restartResult = ScheduleGatewayRestart(args, logPath, diagDir)
    postReport = WritePostInstallReport(plan, args, diagDir, logPath,
                                        restartResult)

    print("[POST_INSTALL]")
    print("install_complete: yes")
    print(f"version: {plan['version']}")
    print(f"install_root: {installRoot}")
    print(f"current: {plan['currentRoot']}")
    print(
        "agents_replaced: no"
        if args.no_replace_agents else "agents_replaced: yes"
    )
    print(
        "services_restarted: "
        f"{'scheduled' if restartResult['scheduled'] else 'no'}"
    )
    print(f"services_restart_status: {restartResult['status']}")
    print(f"services_restart_verified: {restartResult['verified']}")
    print(
        "manual_restart_required: "
        f"{'yes' if ManualRestartRequired(restartResult) else 'no'}"
    )
    print(f"runtime_effective: {RuntimeEffectiveStatus(restartResult)}")
    if restartResult.get("log"):
        print(f"services_restart_log: {restartResult['log']}")
    if restartResult.get("skip_report"):
        print(f"restart_skip_report: {restartResult['skip_report']}")
    print(f"log: {logPath}")
    print(f"diagnostics: {diagDir}")
    print(f"post_install_report: {postReport}")
    print("[/POST_INSTALL]")
    return 0


def BuildParser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["plan", "execute"], required=True)
    parser.add_argument("--platform", choices=["celiaclaw"], default="celiaclaw")
    parser.add_argument("--version")
    parser.add_argument("--channel", choices=["stable", "rc", "dev"])
    parser.add_argument("--dev", action="store_true")
    parser.add_argument("--variant",
                        choices=["full", "full-manylinux_2_28", "plugins"])
    parser.add_argument("--agents-md")
    parser.add_argument("--no-replace-agents", action="store_true")
    parser.add_argument("--skip-gateway-restart", action="store_true")
    parser.add_argument("--skip-npm-install", action="store_true")
    parser.add_argument("--gateway-service")
    parser.add_argument("--restart-health-url")
    parser.add_argument("--allow-non-celiaclaw", action="store_true")
    parser.add_argument("--confirmed", action="store_true")
    return parser


def Main() -> int:
    args = BuildParser().parse_args()
    if args.dev and (args.version or args.channel):
        Die(EXIT_ARG, "[ERROR] --dev conflicts with --version / --channel")
    if args.version and args.channel:
        Die(EXIT_ARG, "[ERROR] --version conflicts with --channel")
    try:
        if args.mode == "plan":
            return RunPlan(args)
        if args.mode == "execute":
            return RunExecute(args)
        Die(EXIT_ARG, f"[ERROR] unsupported mode: {args.mode}")
    except SystemExit:
        raise
    except Exception as exc:
        Die(EXIT_INTERNAL, f"[ERROR] internal: {exc!r}")


if __name__ == "__main__":
    sys.exit(Main())
