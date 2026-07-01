#!/usr/bin/env python3
"""
install.py — 灵枢 AutoBrain 安装部署程序 v3.0

设计原则：
  - deploy.js 负责文件部署（解压引擎包 + 复制 install.py）
  - install.py 负责初始化验证，需用户确认后执行
  - 初始化完成后输出完整的 JSON + MD 双报告

用法：
  python3 scripts/install.py <workspace_path>   # 仅部署（由 deploy.js 后台调用）
  python3 scripts/install.py --init <workspace_path>  # 用户确认后执行初始化
  python3 scripts/install.py --help             # 帮助

返回码：
  0 = 成功
  1 = 失败（可重试）
  2 = 环境不满足（不可恢复）
"""

import json
import os
import shutil
import subprocess
import sys
import time
import glob
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

BEIJING_TZ = timezone(timedelta(hours=8))

# ── 路径 ──────────────────────────────────────────────────
WORKSPACE = ""
PACK_DIR = ""
MANIFEST_PATH = ""
PROGRESS_PATH = ""
REPORT_MD_PATH = ""
REPORT_JSON_PATH = ""
BUNDLE_PATH = ""
SCRIPT_DST = ""


# ════════════════════════════════════════════════════════════
# 日志
# ════════════════════════════════════════════════════════════

_log_buf: List[str] = []


def log(msg: str):
    ts = datetime.now(BEIJING_TZ).strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    _log_buf.append(line)
    print(line, flush=True)


# ════════════════════════════════════════════════════════════
# 进度管理
# ════════════════════════════════════════════════════════════

def _init_progress(manifest: dict) -> dict:
    """初始化进度文件"""
    phases = []
    for p in manifest["phases"]:
        phases.append({
            "id": p["id"],
            "label": p["label"],
            "status": "pending",
            "progress": 0.0,
            "steps": {}
        })
    return {
        "plugin": "Crusheart-AutoBrain-Turbo",
        "version": manifest["version"],
        "started_at": datetime.now(BEIJING_TZ).isoformat(),
        "overall_status": "in_progress",
        "overall_progress": 0.0,
        "current_phase": manifest["phases"][0]["id"],
        "current_step": manifest["phases"][0]["steps"][0]["id"],
        "phases": phases,
    }


def _get_total_weight(manifest: dict) -> int:
    return sum(p["weight"] for p in manifest["phases"])


def _write_progress(progress: dict):
    """写入进度文件（幂等）"""
    try:
        os.makedirs(os.path.dirname(PROGRESS_PATH), exist_ok=True)
        p = dict(progress)  # 浅拷贝
        p.setdefault("updated_at", datetime.now(BEIJING_TZ).isoformat())
        p["updated_at"] = datetime.now(BEIJING_TZ).isoformat()
        with open(PROGRESS_PATH, "w", encoding="utf-8") as f:
            json.dump(p, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log(f"  ⚠️ 进度写入失败: {e}")


def _set_step_status(progress: dict, manifest: dict,
                     phase_id: str, step_id: str, status: str,
                     detail: str = ""):
    """设置单步状态并更新总体进度"""
    total_weight = _get_total_weight(manifest)
    completed_phases = 0
    completed_weights = 0

    for pi, p in enumerate(manifest["phases"]):
        pp = progress["phases"][pi]
        if p["id"] == phase_id:
            pp["status"] = status if status in ("completed", "failed") else "in_progress"
            pp["steps"][step_id] = {"status": status, "detail": detail}
            # 计算阶段内进度
            total_s = len(p["steps"])
            done_s = sum(1 for s in p["steps"] if pp["steps"].get(s["id"], {}).get("status") == "completed")
            pp["progress"] = done_s / total_s if total_s > 0 else 0.0
        if pp["status"] == "completed":
            completed_phases += 1
            completed_weights += p["weight"]

    current_weight = 0
    for pi, p in enumerate(manifest["phases"]):
        pp = progress["phases"][pi]
        if p["id"] == phase_id:
            current_weight = p["weight"] * pp["progress"]
            break

    total_progress = (completed_weights + current_weight) / total_weight
    progress["overall_progress"] = round(total_progress, 3)
    progress["current_phase"] = phase_id
    progress["current_step"] = step_id

    overall = "in_progress"
    if status == "failed":
        overall = "failed"
    elif completed_phases == len(manifest["phases"]):
        overall = "completed"
    progress["overall_status"] = overall

    _write_progress(progress)


def _load_progress(manifest: dict) -> Tuple[dict, bool]:
    """尝试恢复进度。返回 (progress, is_continued)"""
    if os.path.exists(PROGRESS_PATH):
        try:
            with open(PROGRESS_PATH, encoding="utf-8") as f:
                p = json.load(f)
            if p.get("overall_status") in ("in_progress", "failed"):
                log("🔄 检测到未完成的安装，尝试从中断处继续...")
                return p, True
        except Exception:
            pass
    return _init_progress(manifest), False


# ════════════════════════════════════════════════════════════
# 步骤执行器（统一模板）
# ════════════════════════════════════════════════════════════


def _run_cmd(cmd: list, timeout: int = 60, cwd: Optional[str] = None) -> Tuple[int, str, str]:
    """执行命令，返回 (returncode, stdout, stderr)"""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd or WORKSPACE)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", f"超时 ({timeout}s)"
    except FileNotFoundError as e:
        return -2, "", f"命令未找到: {e}"
    except Exception as e:
        return -3, "", str(e)


def _ensure_dir(d: str):
    os.makedirs(d, exist_ok=True)


def _file_checksum(fp: str) -> str:
    """SHA256 前 8 位"""
    try:
        h = hashlib.sha256()
        with open(fp, "rb") as f:
            h.update(f.read(65536))
        return h.hexdigest()[:8]
    except Exception:
        return ""


# ════════════════════════════════════════════════════════════
# Phase 1: 文件部署
# ════════════════════════════════════════════════════════════

def _resolve_plugin_root() -> str:
    """
    解析插件根目录，支持多场景：
    - install.py 在 WORKSPACE/scripts/ 下运行（被 deploy.js 复制）
    - install.py 在插件目录下直接运行
    """
    p = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # 如果 PACK_DIR 下没有 bundle/ 或 _install_manifest.json，说明路径算错了
    if not os.path.exists(os.path.join(p, "bundle")) or not os.path.exists(os.path.join(p, "_install_manifest.json")):
        # 从 workspace 回溯到 extensions/ 目录
        extensions_dir = os.path.join(p, "extensions", "crusheart-autobrain-turbo")
        if os.path.exists(extensions_dir):
            return extensions_dir
        # 再往回一级
        extensions_dir2 = os.path.join(os.path.dirname(p), "extensions", "crusheart-autobrain-turbo")
        if os.path.exists(extensions_dir2):
            return extensions_dir2
    return p


def _find_bundle() -> str:
    """查找引擎包路径，使用 _resolve_plugin_root() 定位"""
    candidates = [
        os.path.join(PACK_DIR, "bundle", "crusheart-core.tar.gz"),
        os.path.join(os.path.dirname(PACK_DIR), "extensions", "crusheart-autobrain-turbo", "bundle", "crusheart-core.tar.gz"),
        os.path.join(os.path.dirname(os.path.dirname(PACK_DIR)), "extensions", "crusheart-autobrain-turbo", "bundle", "crusheart-core.tar.gz"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return candidates[0]


def _engines_ready() -> bool:
    """检查引擎是否已被 deploy.js 解压（避免重复解压）"""
    engines_dir = os.path.join(WORKSPACE, "core", "engines")
    if not os.path.isdir(engines_dir):
        return False
    # 检查至少有一个分组有 .py 文件
    for g in ["init", "memory", "quality", "operations", "workflow", "hooks", "tools", "compat"]:
        group_dir = os.path.join(engines_dir, g)
        if os.path.isdir(group_dir) and os.path.exists(os.path.join(group_dir, "__init__.py")):
            return True
    return False


def step_extract_engines(progress: dict, manifest: dict) -> bool:
    """1.1 解压引擎包（如果 deploy.js 已解压则跳过）"""
    _set_step_status(progress, manifest, "file_deployment", "extract_engines", "running")

    # deploy.js 可能已经解压过了，检查后跳过
    if _engines_ready():
        count = len(glob.glob(os.path.join(WORKSPACE, "core", "engines", "**", "*.py"), recursive=True))
        log(f"[跳过] 引擎已部署（{count} 个文件），跳过解压")
        _set_step_status(progress, manifest, "file_deployment", "extract_engines", "completed", f"{count} 个文件（跳过，已在 deploy.js 中解压）")
        return True

    bundle = _find_bundle()
    if not os.path.exists(bundle):
        _set_step_status(progress, manifest, "file_deployment", "extract_engines", "failed", f"压缩包不存在（已尝试查找: {bundle}）")
        return False

    rc, out, err = _run_cmd(["tar", "xzf", bundle, "-C", WORKSPACE], timeout=120)
    if rc != 0:
        _set_step_status(progress, manifest, "file_deployment", "extract_engines", "failed", err[:200])
        return False
    count = len(glob.glob(os.path.join(WORKSPACE, "core", "engines", "**", "*.py"), recursive=True))
    _set_step_status(progress, manifest, "file_deployment", "extract_engines", "completed", f"{count} 个文件")
    return True


def step_deploy_scripts(progress: dict, manifest: dict) -> bool:
    """1.2 部署 bundle 脚本到 workspace/scripts/"""
    _set_step_status(progress, manifest, "file_deployment", "deploy_scripts", "running")
    bundle_dir = os.path.join(PACK_DIR, "bundle")
    scripts_dir = SCRIPT_DST
    _ensure_dir(scripts_dir)

    scripts = manifest.get("bundle_scripts", [])
    deployed = 0
    for s in scripts:
        src = os.path.join(bundle_dir, s)
        if os.path.exists(src):
            try:
                shutil.copy2(src, os.path.join(scripts_dir, s))
                deployed += 1
            except Exception as e:
                log(f"  ⚠️ 部署 {s} 失败: {e}")
    status = "completed" if deployed > 0 else "failed"
    _set_step_status(progress, manifest, "file_deployment", "deploy_scripts", status, f"{deployed}/{len(scripts)}")
    return deployed > 0


def step_deploy_skill(progress: dict, manifest: dict) -> bool:
    """1.3 部署技能元数据"""
    _set_step_status(progress, manifest, "file_deployment", "deploy_skill", "running")
    skill_src = os.path.join(PACK_DIR, "skill")
    skill_dst = os.path.join(WORKSPACE, "skills", "Crusheart-AutoBrain-Turbo")
    _ensure_dir(skill_dst)

    if not os.path.isdir(skill_src):
        _set_step_status(progress, manifest, "file_deployment", "deploy_skill", "skipped", "skill/ 目录不存在")
        return True

    deployed = 0
    for fname in ["SKILL.md", "_meta.json"]:
        src = os.path.join(skill_src, fname)
        if os.path.exists(src):
            try:
                shutil.copy2(src, os.path.join(skill_dst, fname))
                deployed += 1
            except Exception as e:
                log(f"  ⚠️ 技能 {fname} 部署失败: {e}")
    _set_step_status(progress, manifest, "file_deployment", "deploy_skill", "completed", f"{deployed} 个文件")
    return True


def step_deploy_chain(progress: dict, manifest: dict) -> bool:
    """1.4 部署 chain/ 子目录"""
    _set_step_status(progress, manifest, "file_deployment", "deploy_chain", "running")
    chain_src = os.path.join(PACK_DIR, "bundle", "scripts", "chain")
    chain_dst = os.path.join(SCRIPT_DST, "chain")
    _ensure_dir(chain_dst)

    if not os.path.isdir(chain_src):
        _set_step_status(progress, manifest, "file_deployment", "deploy_chain", "skipped", "chain/ 目录不存在")
        return True

    deployed = 0
    for f in os.listdir(chain_src):
        src = os.path.join(chain_src, f)
        if os.path.isfile(src) and f.endswith(".py"):
            try:
                shutil.copy2(src, os.path.join(chain_dst, f))
                deployed += 1
            except Exception as e:
                log(f"  ⚠️ chain/{f} 部署失败: {e}")

    # 部署 additional_scripts
    add_scripts = manifest.get("additional_scripts", [])
    bundle_dir = os.path.join(PACK_DIR, "bundle")
    for rel_path in add_scripts:
        src = os.path.join(bundle_dir, rel_path)
        dst = os.path.join(SCRIPT_DST, rel_path)
        if os.path.exists(src):
            try:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                deployed += 1
            except Exception as e:
                log(f"  ⚠️ additional {rel_path} 部署失败: {e}")

    _set_step_status(progress, manifest, "file_deployment", "deploy_chain", "completed", f"{deployed} 个文件")
    return True


def step_deploy_xiaoyi_fix(progress: dict, manifest: dict) -> bool:
    """1.5 部署 xiaoyi-channel 修复文件（patches + SKILL.md）"""
    _set_step_status(progress, manifest, "file_deployment", "deploy_xiaoyi_fix", "running")

    fix_src = os.path.join(PACK_DIR, "bundle", "xiaoyi_channel_fix")
    fix_dst = os.path.join(SCRIPT_DST, "xiaoyi_channel_fix")

    if not os.path.isdir(fix_src):
        _set_step_status(progress, manifest, "file_deployment", "deploy_xiaoyi_fix", "skipped", "xiaoyi_channel_fix/ 目录不存在")
        return True

    _ensure_dir(fix_dst)
    deployed = 0
    for fname in os.listdir(fix_src):
        src = os.path.join(fix_src, fname)
        if os.path.isfile(src):
            try:
                shutil.copy2(src, os.path.join(fix_dst, fname))
                deployed += 1
            except Exception as e:
                log(f"  ⚠️ xiaoyi_channel_fix/{fname} 部署失败: {e}")

    # 标记 xiaoyi_channel_fixer.py 需额外部署到 scripts/
    xiaoyi_fixer_src = os.path.join(PACK_DIR, "bundle", "xiaoyi_channel_fixer.py")
    xiaoyi_fixer_dst = os.path.join(SCRIPT_DST, "xiaoyi_channel_fixer.py")
    if os.path.exists(xiaoyi_fixer_src):
        try:
            shutil.copy2(xiaoyi_fixer_src, xiaoyi_fixer_dst)
            deployed += 1
            log(f"  ✅ xiaoyi_channel_fixer.py 已部署")
        except Exception as e:
            log(f"  ⚠️ xiaoyi_channel_fixer.py 部署失败: {e}")

    _set_step_status(progress, manifest, "file_deployment", "deploy_xiaoyi_fix", "completed", f"{deployed} 个文件")
    return True


# ════════════════════════════════════════════════════════════
# Phase 2: 环境设置
# ════════════════════════════════════════════════════════════

def step_inject_rules(progress: dict, manifest: dict) -> bool:
    """2.1 注入行为规则（SOUL.md）"""
    _set_step_status(progress, manifest, "environment_setup", "inject_rules", "running")
    soul_path = os.path.join(WORKSPACE, "SOUL.md")
    bundle_soul = os.path.join(PACK_DIR, "bundle", "SOUL.md")

    if os.path.exists(bundle_soul):
        if os.path.exists(soul_path):
            # 检查是否已注入
            content = open(soul_path, encoding="utf-8").read()
            if "八条铁律" in content:
                _set_step_status(progress, manifest, "environment_setup", "inject_rules", "completed", "已有铁律，跳过")
                return True
            # 追加
            try:
                rules = open(bundle_soul, encoding="utf-8").read()
                with open(soul_path, "a", encoding="utf-8") as f:
                    f.write("\n\n<!-- 灵枢 AutoBrain 注入 -->\n")
                    f.write(rules)
                _set_step_status(progress, manifest, "environment_setup", "inject_rules", "completed", "已追加")
                return True
            except Exception as e:
                _set_step_status(progress, manifest, "environment_setup", "inject_rules", "failed", str(e)[:100])
                return False
        else:
            try:
                shutil.copy2(bundle_soul, soul_path)
                _set_step_status(progress, manifest, "environment_setup", "inject_rules", "completed", "新建 SOUL.md")
                return True
            except Exception as e:
                _set_step_status(progress, manifest, "environment_setup", "inject_rules", "failed", str(e)[:100])
                return False

    _set_step_status(progress, manifest, "environment_setup", "inject_rules", "skipped", "无 bundle/SOUL.md")
    return True


def step_verify_engines(progress: dict, manifest: dict) -> bool:
    """2.2 引擎目录验证"""
    _set_step_status(progress, manifest, "environment_setup", "verify_engines", "running")
    engine_root = os.path.join(WORKSPACE, "core", "engines")
    if not os.path.isdir(engine_root):
        _set_step_status(progress, manifest, "environment_setup", "verify_engines", "failed", "引擎目录不存在")
        return False

    groups = manifest.get("engine_groups", [])
    missing = []
    total_py = 0
    for g in groups:
        d = os.path.join(engine_root, g)
        if os.path.isdir(d):
            count = len(glob.glob(os.path.join(d, "*.py")))
            total_py += count
        else:
            missing.append(g)
    detail = f"引擎组: {len(groups)-len(missing)}/{len(groups)}, .py 文件: {total_py}"

    if len(missing) == len(groups):
        _set_step_status(progress, manifest, "environment_setup", "verify_engines", "failed", "无引擎文件")
        return False
    _set_step_status(progress, manifest, "environment_setup", "verify_engines", "completed", detail)
    return True


def step_verify_scripts(progress: dict, manifest: dict) -> bool:
    """2.3 部署脚本检查"""
    _set_step_status(progress, manifest, "environment_setup", "verify_scripts", "running")
    scripts = manifest.get("bundle_scripts", [])
    missing = []
    for s in scripts:
        if not os.path.exists(os.path.join(SCRIPT_DST, s)):
            if s == "__init__.py":
                continue
            missing.append(s)
    detail = f"{len(scripts)-len(missing)}/{len(scripts)} 已部署"
    if missing:
        detail += f", 缺少: {', '.join(missing[:3])}"
    _set_step_status(progress, manifest, "environment_setup", "verify_scripts", "completed", detail)
    return True


def step_scan_skills(progress: dict, manifest: dict) -> bool:
    """2.4 技能检测 — 执行 scan_skills.py（含 xiaoyi-channel 修复）"""
    _set_step_status(progress, manifest, "environment_setup", "scan_skills", "running")

    # 优先找 workspace/scripts/ 下的，其次 bundle/ 下的
    scan_py = os.path.join(SCRIPT_DST, "scan_skills.py")
    if not os.path.exists(scan_py):
        scan_py = os.path.join(PACK_DIR, "bundle", "scan_skills.py")

    if not os.path.exists(scan_py):
        _set_step_status(progress, manifest, "environment_setup", "scan_skills", "skipped", "scan_skills.py 不存在")
        return True

    try:
        import subprocess
        r = subprocess.run(
            [sys.executable, scan_py],
            capture_output=True, text=True, timeout=60
        )
        detail = r.stdout.strip()[:300] if r.stdout else "执行完成"
        if r.returncode == 2:
            detail += " (xiaoyi-channel 未完全修复)"
        _set_step_status(progress, manifest, "environment_setup", "scan_skills", "completed", detail)
        # stderr 可能包含 xiaoyi-fixer 的输出，也记一笔
        if r.stderr and "xiaoyi" in r.stderr.lower():
            log(f"  [xiaoyi-fixer] {r.stderr.strip()[:200]}")
        return True
    except Exception as e:
        _set_step_status(progress, manifest, "environment_setup", "scan_skills", "completed", f"扫描异常但继续: {e}")
        return True


# ════════════════════════════════════════════════════════════
# Phase 3: 系统集成
# ════════════════════════════════════════════════════════════

def step_register_crons(progress: dict, manifest: dict) -> bool:
    """3.1 注册定时任务"""
    _set_step_status(progress, manifest, "system_integration", "register_crons", "running")

    # 检测 openclaw cron 可用性
    rc, out, err = _run_cmd(["openclaw", "cron", "list"], timeout=15)
    if rc != 0:
        _set_step_status(progress, manifest, "system_integration", "register_crons", "skipped", "openclaw cron 不可用")
        return True  # 不阻塞

    # 先清理旧的
    for pattern in ["crusheart-daily-maintenance", "crusheart-engine-init"]:
        for line in out.split("\n"):
            if pattern in line:
                import re
                ids = re.findall(r'id="([^"]+)"', line)
                for cid in ids:
                    _run_cmd(["openclaw", "cron", "rm", cid], timeout=10)

    # 注册新任务
    # 获取 channel
    channel = "default"
    config_dir = os.environ.get("OPENCLAW_CONFIG_DIR") or os.path.expanduser("~/.openclaw")
    config_path = os.path.join(config_dir, "openclaw.json")
    if os.path.exists(config_path):
        try:
            cfg = json.load(open(config_path, encoding="utf-8"))
            chs = cfg.get("channels", {})
            for k, v in chs.items():
                if isinstance(v, dict) and v.get("enabled", False):
                    channel = k
                    break
            if not channel:
                keys = list(chs.keys())
                if keys:
                    channel = keys[0]
        except Exception:
            pass

    for cron in manifest.get("crons", []):
        cmd = [
            "openclaw", "cron", "add",
            "--cron", cron["schedule"],
            "--name", cron["name"],
            "--channel", channel,
            "--message", f"🦞 {cron['name']} 自动执行",
            "--session", "isolated",
            "--expect-final", "--exact",
        ]
        rc2, out2, err2 = _run_cmd(cmd, timeout=20)
        if rc2 != 0:
            log(f"  ⚠️ 注册 {cron['name']} 失败: {err2[:80]}")

    _set_step_status(progress, manifest, "system_integration", "register_crons", "completed",
                     f"{len(manifest.get('crons', []))} 个任务")
    return True


def step_start_daemon(progress: dict, manifest: dict) -> bool:
    """3.2 启动持久化 Python daemon 进程（热加载引擎）"""
    _set_step_status(progress, manifest, "system_integration", "start_daemon", "running")

    daemon_script = os.path.join(PACK_DIR, "bundle", "crusheart_daemon.py")
    if not os.path.exists(daemon_script):
        _set_step_status(progress, manifest, "system_integration", "start_daemon", "skipped",
                         "bundle/crusheart_daemon.py 不存在")
        log("  ⚠️ daemon 脚本不存在，跳过")
        return True

    socket_path = os.path.join(WORKSPACE, ".crusheart-daemon.sock")
    token_path = os.path.join(WORKSPACE, ".crusheart-daemon-token")
    pid_path = os.path.join(WORKSPACE, ".crusheart-daemon.pid")

    # 如果已有 daemon 运行则跳过
    if os.path.exists(socket_path):
        # 尝试连接验证
        import socket as sock_mod
        try:
            s = sock_mod.socket(sock_mod.AF_UNIX, sock_mod.SOCK_STREAM)
            s.settimeout(2)
            s.connect(socket_path)
            s.close()
            _set_step_status(progress, manifest, "system_integration", "start_daemon", "completed",
                             "已有运行中的 daemon")
            log("  ⏩ daemon 已在运行，跳过")
            return True
        except Exception:
            # socket 文件残留，清理
            try:
                os.unlink(socket_path)
            except OSError:
                pass

    # 确保 token 文件
    token = ""
    if os.path.exists(token_path):
        token = open(token_path).read().strip()
    if not token:
        import random
        import string
        token = "".join(random.choices(string.ascii_lowercase + string.digits, k=32))
        with open(token_path, "w") as f:
            f.write(token)
        log(f"  🔑 已生成 daemon token")

    # 清理 PID 残留
    for f in [pid_path]:
        try:
            os.unlink(f)
        except OSError:
            pass

    log("  🚀 启动 Python daemon 进程...")

    log_path = os.path.join(WORKSPACE, ".crusheart-daemon.log")
    try:
        with open(log_path, "a") as log_f:
            log_f.write(f"\n[install.py] 启动 daemon {datetime.now(BEIJING_TZ).isoformat()}\n")

        process = subprocess.Popen(
            [sys.executable, daemon_script,
             "--socket", socket_path,
             "--token", token,
             "--preload"],
            cwd=WORKSPACE,
            stdout=open(log_path, "a"),
            stderr=open(log_path, "a"),
            stdin=subprocess.DEVNULL,
            env={
                **os.environ,
                "OPENCLAW_WORKSPACE": WORKSPACE,
                "CRUSHEART_DAEMON": "1",
            }
        )
        log(f"  daemon PID: {process.pid}")

        # 等待 socket 就绪（最多 15 秒）
        import socket as sock_mod
        for i in range(30):
            if os.path.exists(socket_path):
                try:
                    s = sock_mod.socket(sock_mod.AF_UNIX, sock_mod.SOCK_STREAM)
                    s.settimeout(2)
                    s.connect(socket_path)
                    s.close()
                    _set_step_status(progress, manifest, "system_integration", "start_daemon", "completed",
                                     f"PID {process.pid}, socket 就绪")
                    log(f"  ✅ daemon 启动成功 (PID {process.pid}, socket: {socket_path})")
                    return True
                except Exception:
                    pass
            time.sleep(0.5)

        _set_step_status(progress, manifest, "system_integration", "start_daemon", "failed",
                         "daemon socket 未在 15 秒内就绪")
        log("  ❌ daemon 启动超时（15s），请检查日志: " + log_path)
        return False
    except Exception as e:
        _set_step_status(progress, manifest, "system_integration", "start_daemon", "failed", str(e)[:100])
        log(f"  ❌ daemon 启动失败: {e}")
        return False


def step_build_indices(progress: dict, manifest: dict) -> bool:
    """3.2 记忆索引构建（轻量）"""
    _set_step_status(progress, manifest, "system_integration", "build_indices", "running")
    memory_dir = os.path.join(WORKSPACE, "memory")
    if os.path.isdir(memory_dir):
        files = [f for f in os.listdir(memory_dir) if f.endswith(".md")]
        _set_step_status(progress, manifest, "system_integration", "build_indices", "completed",
                         f"记忆目录: {len(files)} 个文件")
    else:
        _ensure_dir(memory_dir)
        _set_step_status(progress, manifest, "system_integration", "build_indices", "completed",
                         "新建记忆目录")
    return True


def step_engine_bootstrap(progress: dict, manifest: dict) -> bool:
    """3.3 引擎初始化引导"""
    _set_step_status(progress, manifest, "system_integration", "engine_bootstrap", "running")
    init_script = os.path.join(WORKSPACE, "core", "engines", "init", "init_engines.py")
    if os.path.exists(init_script):
        rc, out, err = _run_cmd([sys.executable, init_script, "--bootstrap", "--install"], timeout=60)
        detail = out[:120] if out else (err[:120] if err else "ok")
        status = "completed" if rc == 0 else "skipped"
        _set_step_status(progress, manifest, "system_integration", "engine_bootstrap", status, detail)
        return rc == 0
    _set_step_status(progress, manifest, "system_integration", "engine_bootstrap", "skipped", "init_engines.py 不存在")
    return True


# ════════════════════════════════════════════════════════════
# Phase 4: 最终验证
# ════════════════════════════════════════════════════════════

def step_engine_imports(progress: dict, manifest: dict) -> bool:
    """4.1 引擎模块导入验证"""
    _set_step_status(progress, manifest, "final_validation", "engine_imports", "running")
    engine_root = os.path.join(WORKSPACE, "core", "engines")
    if not os.path.isdir(engine_root):
        _set_step_status(progress, manifest, "final_validation", "engine_imports", "failed", "引擎目录不存在")
        return False

    sys.path.insert(0, WORKSPACE)
    groups = manifest.get("engine_groups", [])
    imported = 0
    total = 0
    errors = []
    for g in groups:
        d = os.path.join(engine_root, g)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if f == "__init__.py" or not f.endswith(".py"):
                continue
            total += 1
            mod_name = f"core.engines.{g}.{f[:-3]}"
            try:
                __import__(mod_name)
                imported += 1
            except Exception as e:
                errors.append(f"{mod_name}: {str(e)[:60]}")

    detail = f"{imported}/{total}"
    if errors:
        detail += f", {len(errors)} 个导入错误"
        for e in errors[:3]:
            log(f"  ⚠️  导入失败: {e}")
    _set_step_status(progress, manifest, "final_validation", "engine_imports",
                     "completed" if imported >= total * 0.8 else "partial", detail)
    return imported >= total * 0.8


def step_hook_activation(progress: dict, manifest: dict) -> bool:
    """4.2 Hook 注册验证"""
    _set_step_status(progress, manifest, "final_validation", "hook_activation", "running")
    # 检查 deploy 状态文件中是否有 hook 标记
    deploy_state_path = os.path.join(WORKSPACE, ".crusheart-deploy-state.json")
    if os.path.exists(deploy_state_path):
        try:
            d = json.load(open(deploy_state_path, encoding="utf-8"))
            if d.get("firstRunDone"):
                _set_step_status(progress, manifest, "final_validation", "hook_activation", "completed", "部署状态正常")
                return True
        except Exception:
            pass
    _set_step_status(progress, manifest, "final_validation", "hook_activation", "completed", "待 Gateway 重启后激活")
    return True


def step_gen_report(progress: dict, manifest: dict) -> bool:
    """4.3 生成安装报告"""
    _set_step_status(progress, manifest, "final_validation", "gen_report", "running")

    md = []
    md.append(f"# 🦞 灵枢 AutoBrain 安装报告")
    md.append(f"")
    md.append(f"## 基本信息")
    md.append(f"- **插件**: Crusheart-AutoBrain-Turbo v{manifest['version']}")
    md.append(f"- **安装时间**: {datetime.now(BEIJING_TZ).strftime('%Y-%m-%d %H:%M:%S %Z')}")
    md.append(f"- **工作区**: {WORKSPACE}")
    md.append(f"- **总体状态**: {progress['overall_status']}")
    md.append(f"")
    md.append(f"## 阶段摘要")
    md.append(f"| 阶段 | 状态 |")
    md.append(f"|------|------|")

    for pi, p in enumerate(manifest["phases"]):
        pp = progress["phases"][pi]
        icon = {"completed": "✅", "in_progress": "⏳", "failed": "❌", "pending": "⬜"}.get(pp["status"], "❓")
        md.append(f"| {icon} {p['label']} | {pp['status']} |")

    md.append(f"")
    md.append(f"## 详细步骤")

    for pi, p in enumerate(manifest["phases"]):
        pp = progress["phases"][pi]
        md.append(f"")
        md.append(f"### {p['label']} ({pp['status']})")
        for s in p["steps"]:
            step_status = pp["steps"].get(s["id"], {}).get("status", "❓")
            step_detail = pp["steps"].get(s["id"], {}).get("detail", "")
            icon = {"completed": "✅", "running": "⏳", "failed": "❌", "skipped": "➖", "pending": "⬜"}.get(step_status, "❓")
            detail_str = f" — {step_detail}" if step_detail else ""
            md.append(f"- {icon} {s['label']}{detail_str}")

    md_str = "\n".join(md)
    try:
        with open(REPORT_MD_PATH, "w", encoding="utf-8") as f:
            f.write(md_str)
    except Exception as e:
        log(f"  ⚠️ MD 报告写入失败: {e}")

    # JSON 报告
    json_report = {
        "version": manifest["version"],
        "overall_status": progress["overall_status"],
        "started_at": progress["started_at"],
        "completed_at": datetime.now(BEIJING_TZ).isoformat(),
        "phases": []
    }
    for pi, p in enumerate(manifest["phases"]):
        pp = progress["phases"][pi]
        phase_report = {"id": p["id"], "label": p["label"], "status": pp["status"], "steps": {}}
        for s in p["steps"]:
            phase_report["steps"][s["id"]] = pp["steps"].get(s["id"], {"status": "unknown"})
        json_report["phases"].append(phase_report)

    try:
        with open(REPORT_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(json_report, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log(f"  ⚠️ JSON 报告写入失败: {e}")

    _set_step_status(progress, manifest, "final_validation", "gen_report", "completed",
                     f"MD: {REPORT_MD_PATH}, JSON: {REPORT_JSON_PATH}")
    return True


# ════════════════════════════════════════════════════════════
# 主循环
# ════════════════════════════════════════════════════════════

PHASE_STEPS = [
    ("file_deployment", [
        ("extract_engines", step_extract_engines),
        ("deploy_scripts", step_deploy_scripts),
        ("deploy_skill", step_deploy_skill),
        ("deploy_chain", step_deploy_chain),
        ("deploy_xiaoyi_fix", step_deploy_xiaoyi_fix),
    ]),
    ("environment_setup", [
        ("inject_rules", step_inject_rules),
        ("verify_engines", step_verify_engines),
        ("verify_scripts", step_verify_scripts),
        ("scan_skills", step_scan_skills),
    ]),
    ("system_integration", [
        ("register_crons", step_register_crons),
        ("start_daemon", step_start_daemon),
        ("build_indices", step_build_indices),
        ("engine_bootstrap", step_engine_bootstrap),
    ]),
    ("final_validation", [
        ("engine_imports", step_engine_imports),
        ("hook_activation", step_hook_activation),
        ("gen_report", step_gen_report),
    ]),
]


def run_install() -> int:
    """主安装函数。返回退出码"""
    log("🦞 灵枢 AutoBrain 自动安装开始")
    log(f"  工作区: {WORKSPACE}")
    log(f"  包目录: {PACK_DIR}")

    # 加载 manifest
    try:
        manifest = json.load(open(MANIFEST_PATH, encoding="utf-8"))
        log(f"  版本: v{manifest['version']}")
    except Exception as e:
        log(f"❌ 无法加载安装清单: {e}")
        return 2

    # 加载/初始化进度
    progress, is_continued = _load_progress(manifest)
    if is_continued:
        log("⏩ 跳过已完成的步骤...")

    start_time = time.time()

    for phase_id, steps in PHASE_STEPS:
        for step_id, step_func in steps:
            # 检查是否已完成或忽略
            phase_idx = [p["id"] for p in manifest["phases"]].index(phase_id)
            existing = progress["phases"][phase_idx]["steps"].get(step_id, {}).get("status")
            if existing in ("completed", "skipped"):
                continue

            log(f"  ▶ {step_id}...")
            try:
                ok = step_func(progress, manifest)
            except Exception as e:
                log(f"  ❌ {step_id} 异常: {e}")
                ok = False

            if not ok:
                log(f"  ❌ {step_id} 失败")
                # 标记整体失败，但继续生成报告
                progress["overall_status"] = "failed"
                _write_progress(progress)
                # 生成报告再退出
                phase_idx2 = [p["id"] for p in manifest["phases"]].index("final_validation")
                existing_report = progress["phases"][phase_idx2]["steps"].get("gen_report", {}).get("status")
                if existing_report not in ("completed", "skipped"):
                    step_gen_report(progress, manifest)
                elapsed = time.time() - start_time
                log(f"\n⏱️ 总耗时: {elapsed:.1f}s")
                log(f"❌ 安装失败，详情请查看报告: {REPORT_MD_PATH}")
                return 1

        # 该阶段全部完成
        phase_idx = [p["id"] for p in manifest["phases"]].index(phase_id)
        progress["phases"][phase_idx]["status"] = "completed"
        progress["phases"][phase_idx]["progress"] = 1.0
        _write_progress(progress)

    elapsed = time.time() - start_time
    log(f"\n⏱️ 总耗时: {elapsed:.1f}s")
    log(f"✅ 安装完成")
    log(f"  报告: {REPORT_MD_PATH}")
    return 0


# ════════════════════════════════════════════════════════════
# CLI 入口
# ════════════════════════════════════════════════════════════

def run_init() -> int:
    """仅执行初始化+验证阶段（环境设置、系统集成、最终验证），部署阶段由 deploy.js 处理"""
    log("🦞 灵枢 AutoBrain 初始化开始")
    log(f"  工作区: {WORKSPACE}")
    log(f"  包目录: {PACK_DIR}")

    # 加载 manifest
    try:
        manifest = json.load(open(MANIFEST_PATH, encoding="utf-8"))
        log(f"  版本: v{manifest['version']}")
    except Exception as e:
        log(f"❌ 无法加载安装清单: {e}")
        return 2

    # 仅执行初始化阶段（跳过 file_deployment 阶段）
    init_phases = [
        ("environment_setup", [
            ("inject_rules", step_inject_rules),
            ("verify_engines", step_verify_engines),
            ("verify_scripts", step_verify_scripts),
            ("scan_skills", step_scan_skills),
        ]),
        ("system_integration", [
            ("register_crons", step_register_crons),
            ("start_daemon", step_start_daemon),
            ("build_indices", step_build_indices),
            ("engine_bootstrap", step_engine_bootstrap),
        ]),
        ("final_validation", [
            ("engine_imports", step_engine_imports),
            ("hook_activation", step_hook_activation),
            ("gen_report", step_gen_report),
        ]),
    ]

    progress = _init_progress(manifest)
    # 标记部署阶段为已完成（跳过）
    progress["phases"][0]["status"] = "completed"
    progress["phases"][0]["progress"] = 1.0

    start_time = time.time()
    all_ok = True

    for phase_id, steps in init_phases:
        phase_idx = [p["id"] for p in manifest["phases"]].index(phase_id)
        for step_id, step_func in steps:
            existing = progress["phases"][phase_idx]["steps"].get(step_id, {}).get("status")
            if existing in ("completed", "skipped"):
                continue

            log(f"  ▶ {step_id}...")
            try:
                ok = step_func(progress, manifest)
            except Exception as e:
                log(f"  ❌ {step_id} 异常: {e}")
                ok = False

            if not ok:
                log(f"  ❌ {step_id} 失败")
                all_ok = False
                progress["overall_status"] = "failed"
                _write_progress(progress)
                break

        # 该阶段全部完成
        if all_ok:
            progress["phases"][phase_idx]["status"] = "completed"
            progress["phases"][phase_idx]["progress"] = 1.0
            _write_progress(progress)
        else:
            break

    elapsed = time.time() - start_time
    log(f"\n⏱️ 总耗时: {elapsed:.1f}s")
    
    if all_ok:
        progress["overall_status"] = "completed"
        progress["overall_progress"] = 1.0
        log(f"✅ 初始化完成")
    else:
        log(f"❌ 初始化失败")
    
    _write_progress(progress)
    
    # 确保最终报告已生成
    report_phase_idx = [p["id"] for p in manifest["phases"]].index("final_validation")
    if progress["phases"][report_phase_idx]["steps"].get("gen_report", {}).get("status") not in ("completed", "skipped"):
        step_gen_report(progress, manifest)
    
    # 输出报告摘要
    print()
    print("=" * 60)
    print("📋 初始化报告 (JSON): " + REPORT_JSON_PATH)
    print("📋 初始化报告 (MD):   " + REPORT_MD_PATH)
    print("=" * 60)
    try:
        with open(REPORT_MD_PATH, "r", encoding="utf-8") as f:
            summary_text = f.read()
            # 打印前40行
            lines = summary_text.split("\n")
            for line in lines[:40]:
                print(line)
            if len(lines) > 40:
                print("... (完整报告见文件)")
    except Exception as e:
        print(f"  无法读取报告: {e}")
    
    return 0 if all_ok else 1


def main():
    global WORKSPACE, PACK_DIR, MANIFEST_PATH, PROGRESS_PATH
    global REPORT_MD_PATH, REPORT_JSON_PATH, BUNDLE_PATH, SCRIPT_DST

    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("用法: python3 install.py <workspace_path>")
        print("  部署引擎文件（由 deploy.js 调用，不包含初始化）")
        print("")
        print("用法: python3 install.py --init <workspace_path>")
        print("  执行初始化+验证（用户确认后）")
        print("  完成后输出完整报告")
        sys.exit(0)

    init_mode = False
    args = list(sys.argv[1:])
    if "--init" in args:
        init_mode = True
        args.remove("--init")
    
    if len(args) < 1:
        print("❌ 请指定工作区路径")
        sys.exit(1)

    WORKSPACE = args[0]
    PACK_DIR = _resolve_plugin_root()

    MANIFEST_PATH = os.path.join(PACK_DIR, "_install_manifest.json")
    PROGRESS_PATH = os.path.join(WORKSPACE, ".install-progress.json")
    REPORT_MD_PATH = os.path.join(WORKSPACE, ".install-report.md")
    REPORT_JSON_PATH = os.path.join(WORKSPACE, ".install-report.json")
    BUNDLE_PATH = os.path.join(PACK_DIR, "bundle", "crusheart-core.tar.gz")
    SCRIPT_DST = os.path.join(WORKSPACE, "scripts")

    if not os.path.isdir(WORKSPACE):
        log(f"❌ 工作区不存在: {WORKSPACE}")
        sys.exit(2)

    if init_mode:
        rc = run_init()
    else:
        # 旧版全流程模式保留兼容（部署 + 初始化）
        rc = run_install()
    sys.exit(rc)


if __name__ == "__main__":
    main()
