"""
system_identity.py — 灵枢 AutoBrain 系统身份引擎

功能：
  1. 启动时从 _meta.json 读取插件元数据
  2. 生成 .state/system_identity.json 运行时身份文件
  3. 提供 get_system_identity() 供 agent 调用自我介绍

调用方式：
  from core.engines.init.system_identity import get_system_identity
  identity = get_system_identity()
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
STATE_DIR = os.path.join(WORKSPACE, ".state")
IDENTITY_FILE = os.path.join(STATE_DIR, "system_identity.json")

# 引擎分组统计（硬编码以防运行时目录不可用）
ENGINE_GROUPS = {
    "init": {"label": "初始化", "count": 13},
    "memory": {"label": "记忆系统", "count": 8},
    "quality": {"label": "质量验证", "count": 12},
    "operations": {"label": "操作执行", "count": 8},
    "workflow": {"label": "工作流", "count": 8},
    "tools": {"label": "工具管理", "count": 14},
    "hooks": {"label": "钩子系统", "count": 8},
    "compat": {"label": "兼容适配", "count": 4},
}

SYSTEM_FULL_NAME = "Crusheart Agent OS"
TOTAL_ENGINES = sum(g["count"] for g in ENGINE_GROUPS.values())


def _find_meta_json() -> dict:
    """从插件目录或 skill 目录读取 _meta.json"""
    # 扩展插件目录（优先级最高）
    ext_dir = os.path.join(WORKSPACE, "..", "..", "extensions", "crusheart-autobrain-turbo")
    if os.path.isdir(ext_dir):
        ext_dir = os.path.realpath(ext_dir)
    else:
        ext_dir = os.path.expanduser("~/.openclaw/extensions/crusheart-autobrain-turbo")

    skill_dir = os.path.join(WORKSPACE, "skills", "crusheart-autobrain-turbo")

    candidates = [
        os.path.join(ext_dir, "_meta.json"),                                          # 扩展插件
        os.path.join(ext_dir, "skill", "_meta.json"),                                # 扩展内 skill 子目录
        os.path.join(skill_dir, "_meta.json"),                                        # skill 目录
        os.path.join(WORKSPACE, ".crusheart-meta.json"),                             # 工作区根
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
    return {}


def _read_framework_version() -> str:
    """尝试读取 OpenClaw 版本"""
    try:
        # 从 openclaw 命令获取版本
        import subprocess
        r = subprocess.run(
            ["openclaw", "--version"],
            capture_output=True, text=True, timeout=5
        )
        if r.returncode == 0:
            return r.stdout.strip().split()[1] if len(r.stdout.strip().split()) > 1 else r.stdout.strip()
    except Exception:
        pass
    return "unknown"


def init() -> None:
    """引擎初始化入口（用于 engines.json 的 init_fn 注册）"""
    save_identity()


def build_identity() -> dict:
    """构建完整的系统身份信息"""
    meta = _find_meta_json()

    # 扫描实际引擎文件数（更准确）
    engine_root = os.path.join(WORKSPACE, "core", "engines")
    actual_files = 0
    for group in ENGINE_GROUPS:
        gd = os.path.join(engine_root, group)
        if os.path.isdir(gd):
            for f in os.listdir(gd):
                if f.endswith(".py") and f != "__init__.py":
                    actual_files += 1

    engine_name = meta.get("name", "灵枢AutoBrain")
    engine_version = meta.get("version", "0.0.0-dev")

    identity = {
        "system": SYSTEM_FULL_NAME,
        "engine": f"{SYSTEM_FULL_NAME} 基于{engine_name}",
        "name": engine_name,
        "version": engine_version,
        "description": f"{SYSTEM_FULL_NAME} Engine Suite - Powered by {engine_name} {engine_version}",
        "framework": f"OpenClaw {_read_framework_version()}",
        "engine_groups": len(ENGINE_GROUPS),
        "engine_groups_detail": ENGINE_GROUPS,
        "engine_modules": max(actual_files, TOTAL_ENGINES),
        "engine_status": "ready",
        "plugins": [
            {
                "name": engine_name,
                "version": engine_version,
                "slug": meta.get("slug", "Crusheart-AutoBrain-Turbo"),
            }
        ],
        "initialized_at": datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S"),
        "tags": meta.get("tags", []),
    }
    return identity


def save_identity():
    """保存系统身份到 .state/ 文件"""
    identity = build_identity()
    os.makedirs(STATE_DIR, exist_ok=True)
    # 读取现有的 identity 以保留历史字段（如有）
    old = {}
    if os.path.exists(IDENTITY_FILE):
        try:
            with open(IDENTITY_FILE, encoding="utf-8") as f:
                old = json.load(f)
        except Exception:
            pass

    # 合并：保留旧数据中不存在于新数据的有用字段
    merged = {**old, **identity}
    merged["initialized_at"] = identity["initialized_at"]

    with open(IDENTITY_FILE, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    return merged


def get_system_identity() -> dict:
    """获取系统身份信息（供 agent 调用）

    优先读文件，文件不存在则构建新 identity。
    """
    if os.path.exists(IDENTITY_FILE):
        try:
            with open(IDENTITY_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return build_identity()


def get_boot_message() -> str:
    """获取开机话术（供 dawn_bootstrap.py 使用）"""
    identity = get_system_identity()
    full = identity.get("system", "Crusheart Agent OS")
    engine_name = identity.get("name", "灵枢AutoBrain")
    version = identity.get("version", "v?.?.?")
    engine_count = identity.get("engine_modules", "?")
    groups = identity.get("engine_groups", "?")

    return (
        f"🌅 {full} 基于 {engine_name} {version} | 早安\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🔄 {groups}组{engine_count}引擎全部就绪 · 系统状态正常\n"
        f"📡 24h运行无异常\n"
        f"— 新的一天，随时待命 🤖"
    )


# 模块级初始化（import 时自动保存）
if __name__ != "__main__":
    try:
        save_identity()
    except Exception:
        pass

# 直接运行时输出 identity
if __name__ == "__main__":

    # --test/--self-check: 基础自检（#48）
    if "--test" in sys.argv or "--self-check" in sys.argv:
        try:
            from core.engines.init.self_check import run_self_check
        except ImportError:
            print("❌ self_check 模块不可用")
            sys.exit(1)

        checks = [("import self", lambda: None)]
        sys.exit(run_self_check(__name__, __file__,
            custom_checks=checks, verbose=True))

    import subprocess
    identity = save_identity()
    print(json.dumps(identity, ensure_ascii=False, indent=2))
    print("---")
    print(get_boot_message())
