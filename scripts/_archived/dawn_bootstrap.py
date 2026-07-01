#!/usr/bin/env python3
"""
dawn_bootstrap.py — 每日 5:00 黎明引导

功能流程：
  1. 检测主会话是否空闲 ≥10 分钟且无用户消息
     - 活跃中 → 跳过本次初始化（不打扰用户）
     - 空闲 → 继续执行
  2. 运行引擎初始化 + 版本检查
  3. 生成系统身份
  4. 输出定制开机话术（供 agent 回复使用）

用法：
  python3 scripts/dawn_bootstrap.py          # 正常执行
  python3 scripts/dawn_bootstrap.py --dry-run  # 模拟

返回码：
  0  = 正常完成
  2  = 跳过（会话活跃）
  3  = Gateway 不可用
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")

# 允许跳过的最小空闲时间（秒）
MIN_IDLE_SECONDS = 600  # 10 分钟


def log(msg: str):
    ts = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


def get_main_sessions() -> list:
    """获取主会话列表（agent:main:direct）"""
    try:
        r = subprocess.run(
            ["openclaw", "sessions", "--json"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode != 0:
            log(f"⚠️ openclaw sessions list 失败: {r.stderr.strip()[:100]}")
            return []
        data = json.loads(r.stdout or "{}")
        if not data:
            return []
        # sessions 在 {"sessions": [...]} 结构里
        if isinstance(data, dict):
            all_sessions = data.get("sessions", [])
        elif isinstance(data, list):
            all_sessions = data
        else:
            all_sessions = []
        if not all_sessions:
            return []
        # 过滤出主会话（direct 类型 + agent:main）
        main_sessions = [
            s for s in all_sessions
            if isinstance(s, dict)
            and (s.get("kind") == "direct" or "direct" in str(s.get("key", "")))
            and "agent:main" in str(s.get("key", ""))
        ]
        return main_sessions
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
        log(f"⚠️ 获取会话列表异常: {type(e).__name__}: {str(e)[:80]}")
        return []


def check_session_active() -> tuple:
    """检测主会话是否活跃

    Returns:
        (is_active: bool, reason: str)
        is_active=True → 跳过初始化
    """
    sessions = get_main_sessions()
    if not sessions:
        log("  ℹ️  未找到主会话（Gateway 可能刚启动）")
        return False, "无主会话"

    now = time.time()
    for s in sessions:
        # 检查会话是否有正在执行的 run
        status = s.get("status", "")
        if status == "running":
            log(f"  ⏭️  检测到主会话正在执行任务 (status=running)")
            return True, "会话正在执行任务"

        # 检查是否有用户消息
        updated_at = s.get("updatedAt") or s.get("updated_at") or s.get("lastActivity", "")
        if updated_at:
            # 尝试多种时间格式
            try:
                if isinstance(updated_at, (int, float)):
                    ts = updated_at / 1000 if updated_at > 1e12 else updated_at
                else:
                    # ISO 格式
                    updated_at_str = str(updated_at).replace("Z", "+00:00")
                    dt = datetime.fromisoformat(updated_at_str)
                    ts = dt.timestamp()

                elapsed = now - ts
                if elapsed < MIN_IDLE_SECONDS:
                    remain = int(MIN_IDLE_SECONDS - elapsed)
                    log(f"  ⏭️  用户 {remain}s 内有消息活动，跳过初始化")
                    return True, f"用户 {remain}s 内活跃"
            except (ValueError, TypeError):
                log(f"  ⚠️  无法解析会话时间: {updated_at}")
                continue

    log("  ✅ 主会话空闲 ≥10 分钟，继续执行")
    return False, "会话空闲"


def run_engine_init() -> bool:
    """执行引擎初始化"""
    log("  🔧 [1/2] 引擎初始化...")
    init_py = os.path.join(WORKSPACE, "core", "engines", "init", "init_engines.py")
    if os.path.exists(init_py):
        try:
            r = subprocess.run(
                [sys.executable, init_py, "--bootstrap"],
                capture_output=True, text=True, timeout=60,
            )
            if r.returncode == 0:
                for line in r.stdout.strip().split("\n"):
                    if line.strip():
                        log(f"    {line.strip()}")
                log("  ✅ 引擎初始化完成")
                return True
            else:
                log(f"  ⚠️ 引擎初始化有异常（非阻塞）")
                for line in (r.stderr or "").strip().split("\n")[-3:]:
                    if line.strip():
                        log(f"    {line.strip()}")
                return True  # 非阻塞，视为成功
        except Exception as e:
            log(f"  ⚠️ 引擎初始化异常（非阻塞）: {e}")
            return True
    else:
        log(f"  ℹ️  init_engines.py 不存在，跳过引擎初始化")
        return True


def run_version_check() -> bool:
    """执行版本检查"""
    log("  🔧 [2/2] 版本检查...")
    vc_py = os.path.join(WORKSPACE, "scripts", "version_check.py")
    if os.path.exists(vc_py):
        try:
            r = subprocess.run(
                [sys.executable, vc_py],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode == 0:
                out = r.stdout.strip()
                if out:
                    log(f"    {out.split(chr(10))[0]}")
                log("  ✅ 版本检查完成")
                return True
            else:
                log(f"  ⚠️ 版本检查有异常（非阻塞）")
                return True
        except Exception as e:
            log(f"  ⚠️ 版本检查异常（非阻塞）: {e}")
            return True
    else:
        log(f"  ℹ️  version_check.py 不存在，跳过版本检查")
        return True


def generate_boot_message() -> str:
    """生成开机话术"""
    try:
        sys.path.insert(0, WORKSPACE)
        from core.engines.init.system_identity import get_boot_message
        return get_boot_message()
    except ImportError:
        # 兜底
        return (
            "🌅 灵枢 AutoBrain | 早安\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "🔄 引擎全部就绪 · 系统状态正常\n"
            "— 新的一天，随时待命 🤖"
        )


def main():
    dry_run = "--dry-run" in sys.argv

    log("🌅 黎明引导开始")
    log(f"   工作区: {WORKSPACE}")
    log(f"   模式: {'DRY-RUN 模拟' if dry_run else '正常执行'}")

    # ── 第1步：检测会话活跃度 ──
    print("")
    log("📡 [1/3] 会话活跃度检测...")
    is_active, reason = check_session_active()
    if is_active:
        print("")
        log(f"⏭️  跳过本次初始化 (原因: {reason})")
        print("")
        print("---BOOT_SKIP---")
        return 2

    # ── 第2步：执行引擎初始化 ──
    print("")
    log("⚙️  [2/3] 引擎初始化 + 版本检查...")
    if not dry_run:
        run_engine_init()
        run_version_check()
    else:
        log("  [DRY-RUN] 跳过引擎初始化")
        log("  [DRY-RUN] 跳过版本检查")

    # ── 第3步：生成开机话术 ──
    print("")
    log("📣 [3/3] 生成开机话术...")
    boot_msg = generate_boot_message()
    if not dry_run:
        # 刷新系统身份
        try:
            sys.path.insert(0, WORKSPACE)
            from core.engines.init.system_identity import save_identity
            identity = save_identity()
            log(f"  ✅ 系统身份已保存: {identity.get('engine', '?')} v{identity.get('version', '?')}")
        except Exception as e:
            log(f"  ⚠️ 系统身份刷新异常: {e}")

    print("")
    print("===BOOT_MESSAGE===")
    print(boot_msg)
    print("===BOOT_MESSAGE_END===")

    print("")
    log("✅ 黎明引导完成")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("")
        log("⛔ 被用户中断")
        sys.exit(1)
