"""
Crusheart Agent OS — 统一引擎初始化入口（动态加载版）
功能：根据 engines.json 配置动态初始化所有系统引擎
"""

import os
import sys
import json
import time
import importlib
from datetime import datetime, timezone, timedelta

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
ENGINE_STATE_DIR = os.path.join(WORKSPACE, ".state")
ENGINE_STATE_FILE = os.path.join(ENGINE_STATE_DIR, ".engine_state.json")
ENGINE_CONFIG_FILE = os.path.join(WORKSPACE, "core", "engines", "init", "engines.json")

# 统一配置 + 异常 + 注册表（延迟加载，__main__ 里才真正 import）
ConfigLoader = None
EngineRegistry = None
EngineError = None
EngineInitError = None
SafetyValve = None


def log(msg: str):
    ts = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


def load_engine_config():
    """加载引擎配置"""
    if not os.path.exists(ENGINE_CONFIG_FILE):
        log(f"⚠️ 引擎配置文件不存在: {ENGINE_CONFIG_FILE}")
        return []
    with open(ENGINE_CONFIG_FILE) as f:
        config = json.load(f)
    return config.get("engines", [])


def init_engine(engine_cfg: dict) -> dict:
    """
    动态初始化单个引擎
    Returns: {"name": str, "success": bool, "instance": object, "error": str}
    """
    name = engine_cfg["name"]
    module_path = engine_cfg["module"]
    class_name = engine_cfg.get("class")
    init_fn = engine_cfg.get("init_fn")
    extra_init = engine_cfg.get("extra_init", [])

    if not engine_cfg.get("enabled", True):
        log(f"⏭️ {name}: 已禁用，跳过")
        return {"name": name, "success": True, "instance": None, "error": ""}

    try:
        # 动态导入模块
        if WORKSPACE not in sys.path: sys.path.append(WORKSPACE)
        module = importlib.import_module(module_path)

        # 初始化方式1：调用指定初始化函数
        if init_fn:
            init_func = getattr(module, init_fn)
            instance = init_func()
            log(f"✅ {name}: 通过 {init_fn}() 初始化成功")
            return {"name": name, "success": True, "instance": instance, "error": ""}

        # 初始化方式2：实例化类
        if class_name:
            cls = getattr(module, class_name)
            instance = cls()
            log(f"✅ {name}: {class_name}() 实例化成功")
            
            # 额外初始化（如互斥锁的队列和检测器）
            for extra in extra_init:
                extra_cls = getattr(module, extra, None)
                if extra_cls:
                    extra_instance = extra_cls()
                    log(f"   └─ {extra} 已就绪")
            
            return {"name": name, "success": True, "instance": instance, "error": ""}

        log(f"⚠️ {name}: 未指定 class 或 init_fn，跳过")
        return {"name": name, "success": False, "instance": None, "error": "no init method specified"}

    except Exception as e:
        log(f"❌ {name} 初始化失败: {e}")
        return {"name": name, "success": False, "instance": None, "error": str(e)}


def save_state(results: list):
    """保存引擎状态"""
    state = {
        "initialized_at": datetime.now(BEIJING_TZ).isoformat(),
        "init_time": datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S"),
        "engines": [
            {
                "name": r["name"],
                "status": "ready" if r["success"] else "failed",
                "error": r.get("error", "")
            }
            for r in results
        ],
        "total": len(results),
        "success": sum(1 for r in results if r["success"]),
        "failed": sum(1 for r in results if not r["success"]),
        "status": "ready" if all(r["success"] for r in results) else "partial"
    }
    os.makedirs(os.path.dirname(ENGINE_STATE_FILE), exist_ok=True)
    with open(ENGINE_STATE_FILE, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    return state


def check_state() -> dict:
    """检查引擎初始化状态"""
    if not os.path.exists(ENGINE_STATE_FILE):
        return {"status": "uninitialized", "engine_count": 0}
    with open(ENGINE_STATE_FILE) as f:
        return json.load(f)


def needs_reinit() -> bool:
    """检查是否需要重新初始化（跳过已初始化的状态）"""
    if not os.path.exists(ENGINE_STATE_FILE):
        return True
    try:
        with open(ENGINE_STATE_FILE) as f:
            state = json.load(f)
        if state.get("status") not in ("ready", "partial"):
            return True
        init_time = state.get("initialized_at", "")
        if init_time:
            # 兼容带 Z 和 +08:00 的时区格式
            init_time_clean = init_time.replace("Z", "+08:00").split(".")[0]
            try:
                init_dt = datetime.fromisoformat(init_time_clean)
                elapsed = (datetime.now(BEIJING_TZ) - init_dt).total_seconds()
                if elapsed < 3600:  # 1 小时内已初始化过
                    return False
            except ValueError:
                pass
    except Exception:
        pass
    return True


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

    now = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")
    log("🚀 Crusheart Agent OS — 动态引擎初始化开始")

    # ── 0. 跳过检查：如果近期已初始化，跳过全量流程 ──
    if not needs_reinit():
        log("⏭️ 引擎已在近期初始化，跳过全量初始化（使用 --force 可强制重新初始化）")
        # 仅做轻量健康检查
        existing_state = check_state()
        log(f"📊 引擎状态: {existing_state.get('status', 'unknown')} ({existing_state.get('success', 0)}/{existing_state.get('total', 0)})")
        if existing_state.get("failed", 0) > 0:
            log(f"⚠️ {existing_state['failed']} 个引擎初始化失败，继续启动")
        # 刷新系统身份
        try:
            from core.engines.init.system_identity import save_identity as _si_save
            _si_save()
            log("📋 系统身份已刷新")
        except Exception:
            pass
        exit(0)

    # ── 0. 初始化统一配置入口（EngineFactory + ConfigLoader）──
    try:
        if WORKSPACE not in sys.path:
            if WORKSPACE not in sys.path: sys.path.append(WORKSPACE)
        from core.engines.init.config_loader import (
            ConfigLoader as _ConfigLoader,
            EngineRegistry as _EngineRegistry,
            EngineError as _EngineError,
            EngineInitError as _EngineInitError,
            SafetyValve as _SafetyValve,
        )
        globals()["ConfigLoader"] = _ConfigLoader
        globals()["EngineRegistry"] = _EngineRegistry
        globals()["EngineError"] = _EngineError
        globals()["EngineInitError"] = _EngineInitError
        globals()["SafetyValve"] = _SafetyValve
        config_loader = _ConfigLoader()
        log(f"📋 ConfigLoader: 统一配置入口就绪")
    except Exception as e:
        log(f"⚠️ ConfigLoader 初始化异常: {e}")

    # ── 0.5 无损升级迁移（旧版→v7 数据/状态迁移）──
    try:
        from core.engines.compat.compat_migration import migrate
        migration_result = migrate()
        if migration_result["warnings"]:
            for w in migration_result["warnings"]:
                log(f"  ⚠️  {w}")
        if migration_result["migrations_done"]:
            log(f"  ✅ 完成 {len(migration_result['migrations_done'])} 项升级迁移")
    except Exception as e:
        log(f"⚠️ 升级迁移异常（不影响引擎启动）: {e}")

    # ── 0.6 初始化 EngineFactory(统一引擎工厂）──
    try:
        from core.engines.init.engine_factory import EngineFactory
        factory = EngineFactory()
        log(f"📋 EngineFactory: {len(factory.get_descriptions())} 个引擎配置已加载")
    except Exception as e:
        log(f"⚠️ EngineFactory 初始化异常: {e}")
        factory = None

    # ── 1. 配置有效性预校验 ──
    try:
        from core.engines.init.config_validator import run_full_validation
        config_ok = run_full_validation()
        if not config_ok:
            log("⚠️ 配置校验发现问题，继续启动但请注意修复")
    except ImportError:
        log("📭 配置校验器未加载，跳过")
    except Exception as e:
        log(f"⚠️ 配置校验异常: {e}")

    # 加载引擎配置
    engine_configs = load_engine_config()
    if not engine_configs:
        log("❌ 未找到引擎配置")
        exit(1)

    log(f"📋 发现 {len(engine_configs)} 个引擎配置")

    # 逐个初始化 + 注册到 EngineFactory 和 EngineRegistry
    results = []
    engine_registry = EngineRegistry() if EngineRegistry else None
    for cfg in engine_configs:
        # 优先走 EngineFactory（统一路径）
        if factory:
            instance = factory.get(cfg["name"], lazy=False)
            if instance is not None:
                result = {"name": cfg["name"], "success": True, "instance": instance, "error": ""}
            else:
                # Fallback: 走传统 init_engine
                result = init_engine(cfg)
        else:
            result = init_engine(cfg)

        # 注册到 EngineRegistry 保持向后兼容
        if result["success"] and result["instance"] is not None:
            try:
                engine_registry and engine_registry.register(result["name"], result["instance"])
            except Exception as e:
                log(f"⚠️ 注册引擎 [{result['name']}] 到 registry 时异常: {e}")
        results.append(result)

    # 未初始化的引擎走 EngineFactory.init_all() 补全
    if factory:
        factory.init_all()
        log(f"🧩 EngineFactory: {len(factory.get_status())} 个引擎已注册")

    log(f"🧩 EngineRegistry: {len(engine_registry.list()) if engine_registry else 0} 个引擎已注册")

    # 保存状态
    state = save_state(results)

    # 输出汇总
    log(f"📊 引擎初始化完成: {state['success']}/{state['total']}")
    if state["failed"] > 0:
        log(f"⚠️ {state['failed']} 个引擎初始化失败:")
        for r in results:
            if not r["success"]:
                log(f"   ❌ {r['name']}: {r['error']}")

    log(f"✅ 引擎状态已保存 ({state['status']})")

    # 兼容层：扫描 plugins/ 目录下的第三方引擎
    try:
        from core.engines.compat.compat_registry import auto_discover
        compat_result = auto_discover()
        if compat_result["registered"]:
            log(f"🔌 兼容层: {len(compat_result['registered'])} 个第三方引擎已注册")
        if compat_result["failed"]:
            log(f"⚠️ 兼容层: {len(compat_result['failed'])} 个引擎注册失败")
    except ImportError:
        log("📭 兼容层未安装，跳过")
    except Exception as e:
        log(f"⚠️ 兼容层初始化异常: {e}")

    # 存在失败时返回非零退出码
    if state["failed"] > 0:
        exit(1)
    exit(0)
