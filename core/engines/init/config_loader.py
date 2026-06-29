"""
Crusheart Agent OS — 统一配置加载入口 + 错误隔离体系

功能：
1. ConfigLoader — 分层配置加载（系统默认 → 用户配置 → 环境变量 → 运行时覆盖）
2. EngineError — 引擎异常体系（Init/Timeout/Dependency/Unknown）
3. safe_call — 引擎执行的安全边界装饰器

规范：所有引擎必须通过 ConfigLoader 读配置，不得自行读 json/env。
"""

import os
import sys
import json
import time
import threading
import traceback
import functools
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Callable

BEIJING_TZ = timezone(timedelta(hours=8))
OPENCLAW_HOME = os.environ.get("OPENCLAW_HOME") or os.path.expanduser("~/.openclaw")
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.join(OPENCLAW_HOME, "workspace")
DEFAULT_CONFIG_PATH = os.path.join(OPENCLAW_HOME, "openclaw.json")
AUTOTUNE_CONFIG_PATH = os.path.join(WORKSPACE, "skills", "Crusheart-AutoBrain-Turbo", "config.json")


# ═══════════════════════════════════════════════════════════
# 第一部分：引擎异常体系
# ═══════════════════════════════════════════════════════════

class EngineError(Exception):
    """引擎异常的基类"""
    def __init__(self, engine_name: str, message: str, context: dict = None):
        self.engine_name = engine_name
        self.context = context or {}
        self.timestamp = datetime.now(BEIJING_TZ).isoformat()
        super().__init__(f"[{engine_name}] {message}")


class EngineInitError(EngineError):
    """引擎初始化失败"""
    def __init__(self, engine_name: str, message: str, module_path: str = None, context: dict = None):
        self.module_path = module_path
        super().__init__(engine_name, message, context)


class EngineTimeoutError(EngineError):
    """引擎执行超时"""
    def __init__(self, engine_name: str, timeout_seconds: float, operation: str = None, context: dict = None):
        self.timeout_seconds = timeout_seconds
        self.operation = operation
        msg = f"执行超时 ({timeout_seconds}s)"
        if operation:
            msg += f" 操作: {operation}"
        super().__init__(engine_name, msg, context)


class EngineDependencyError(EngineError):
    """引擎依赖缺失或冲突"""
    def __init__(self, engine_name: str, missing_dep: str, message: str = None, context: dict = None):
        self.missing_dep = missing_dep
        msg = message or f"缺少依赖: {missing_dep}"
        super().__init__(engine_name, msg, context)


class EngineConfigError(EngineError):
    """引擎配置异常"""
    def __init__(self, engine_name: str, config_key: str, message: str = None, context: dict = None):
        self.config_key = config_key
        msg = message or f"配置项 {config_key} 异常"
        super().__init__(engine_name, msg, context)


class EngineStateError(EngineError):
    """引擎状态异常（如重复初始化、未初始化时调用）"""
    def __init__(self, engine_name: str, expected_state: str, actual_state: str, context: dict = None):
        self.expected_state = expected_state
        self.actual_state = actual_state
        msg = f"状态异常: 期望 {expected_state}, 当前 {actual_state}"
        super().__init__(engine_name, msg, context)


# ═══════════════════════════════════════════════════════════
# 第二部分：安全调用装饰器
# ═══════════════════════════════════════════════════════════

class SafetyValve:
    """
    引擎安全调用边界。
    确保引擎抛异常不会炸全局，并提供标准化的错误记录。
    """

    @staticmethod
    def call(engine_name: str, fn: Callable, *args, **kwargs) -> dict:
        """
        安全调用引擎方法。
        Returns: {"success": bool, "result": Any, "error": EngineError or None}
        """
        try:
            result = fn(*args, **kwargs)
            return {"success": True, "result": result, "error": None}
        except EngineError:
            # 引擎异常体系内的错误，直接透传
            raise
        except Exception as e:
            # 非引擎异常 → 包装为标准错误 + 打印栈
            tb = traceback.format_exc()
            wrapped = EngineError(engine_name, f"{type(e).__name__}: {e}")
            # 记录详细栈信息到上下文
            wrapped.context["traceback"] = tb
            raise wrapped from e

    @staticmethod
    def call_or_skip(engine_name: str, fn: Callable, *args, default=None, **kwargs) -> Any:
        """
        安全调用，异常时不抛，返回 default。
        用于"能跑就行"的非关键路径。
        """
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            ts = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{ts}] [SafetyValve] ⚠️ {engine_name}: {type(e).__name__} 已跳过: {e}")
            return default

    @staticmethod
    def decorate(engine_name: str):
        """
        装饰器版：@SafetyValve.decorate("engine_name")
        异常时包装为 EngineError，不会炸全局调用方（除非调用方不 catch）。
        """
        def decorator(fn):
            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                return SafetyValve.call(engine_name, fn, *args, **kwargs)
            return wrapper
        return decorator


def safe_call(engine_name: str):
    """
    快捷装饰器：@safe_call("engine_name")
    等价于 SafetyValve.decorate(engine_name)
    """
    return SafetyValve.decorate(engine_name)


# ═══════════════════════════════════════════════════════════
# 第三部分：ConfigLoader 分层配置加载
# ═══════════════════════════════════════════════════════════

# 系统默认配置（最低优先级）
SYSTEM_DEFAULTS = {
    "runtime": {
        "no_external_api": True,
        "no_real_send": True,
        "no_real_payment": True,
        "no_real_device": True,
        "gateway_url": "http://localhost:18789",
        "api_key": "",
    },
    "bootstrapMaxChars": 18000,
    "bootstrapTotalMaxChars": 40000,
    "personaVisual": {
        "enabled": True,
        "confidenceThreshold": 0.82,
        "cooldownTurns": 5,
        "dailyAutoGenerateLimit": 10,
        "externalProvider": "seedream",
        "defaultMode": "auto_with_budget",
        "generationConsentMode": "auto_with_budget",
        "autoGenerate": True,
        "autoGenerateRequiresBudget": True,
        "predictiveSuggestion": True,
        "userStandingConsent": True,
    },
    "engines": {
        "dual_mode": {"default_mode": "fast", "auto_switch": True},
        "lazy_load": {"search_interval_ms": 500, "max_searches_per_task": 5, "cache_ttl_seconds": 1800},
        "mutex": {"task_timeout_seconds": 180, "max_retry": 3},
        "memory_layer": {"l2_retention_days": 7, "decay_start_days": 30, "decay_end_days": 90, "decay_min_weight": 0.5},
        "failover": {"max_retries": 1, "cooldown_minutes": 300, "fallback_model": None},
        "judge_engine": {"replay_buffer_size": 50, "min_score_for_replay": 0.6, "auto_reflect": True},
        "context_warning": {"round_threshold": 30, "toolcall_threshold": 20, "expiry_minutes": 10},
        "decision_core": {"default_priority": 5, "max_tokens_budget": 16000},
        "identity_drift_guard": {"check_interval_minutes": 60, "drift_threshold": 0.3},
        "session_manager": {"auto_save": True, "max_capsules": 50},
    },
}

# 环境变量到配置路径的映射
ENV_MAP = {
    "NO_EXTERNAL_API": ("runtime.no_external_api", lambda v: v.lower() == "true"),
    "NO_REAL_SEND": ("runtime.no_real_send", lambda v: v.lower() == "true"),
    "NO_REAL_PAYMENT": ("runtime.no_real_payment", lambda v: v.lower() == "true"),
    "NO_REAL_DEVICE": ("runtime.no_real_device", lambda v: v.lower() == "true"),
    "OPENCLAW_GATEWAY_URL": ("runtime.gateway_url", str),
    "OPENCLAW_API_KEY": ("runtime.api_key", str),
}


class ConfigLoader:
    """
    分层配置加载器。
    优先级（低 → 高）：系统默认 < openclaw.json < autotune config.json < 环境变量 < 运行时覆盖
    线程安全：使用 threading.Lock 保护单例创建和配置加载
    """

    _instance = None
    _config = None
    _init_lock = threading.Lock()

    def __new__(cls):
        from core.engines.init.engine_factory import SingletonRegistry
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    SingletonRegistry.register(cls, cls._instance)
        return cls._instance

    def __init__(self):
        with self._init_lock:
            if self._config is None:
                self._config = self._load_all()
                self._overrides = {}  # 运行时覆盖

    def _load_all(self) -> dict:
        """加载全量配置"""
        config = self._deep_copy(SYSTEM_DEFAULTS)

        # Layer 1: openclaw.json
        file_config = self._load_json(DEFAULT_CONFIG_PATH)
        if file_config:
            self._deep_merge(config, file_config)

        # Layer 2: autotune config.json（引擎参数）
        autotune_config = self._load_json_autotune()
        if autotune_config:
            # 将 autotune 的 engines.xxx.yyy 结构 merge 进来
            self._deep_merge(config, autotune_config)

        # Layer 3: 环境变量
        for env_var, (config_path, transform) in ENV_MAP.items():
            value = os.environ.get(env_var)
            if value is not None:
                self._set_by_path(config, config_path, transform(value))

        return config

    def get(self, key: str, default: Any = None) -> Any:
        """通过点号路径获取配置，如 'engines.dual_mode.default_mode'"""
        # 运行时覆盖优先
        if key in self._overrides:
            return self._overrides[key]
        return self._get_by_path(self._config, key, default)

    def set_override(self, key: str, value: Any):
        """设置运行时覆盖配置（最高优先级，仅当前进程生效，不持久化）"""
        self._overrides[key] = value

    def clear_overrides(self):
        """清除所有运行时覆盖"""
        self._overrides.clear()

    def get_all(self) -> dict:
        """获取全量配置（含运行时覆盖）"""
        result = self._deep_copy(self._config)
        for key, value in self._overrides.items():
            self._set_by_path(result, key, value)
        return result

    # ── 内部工具方法 ──

    @staticmethod
    def _load_json(path: str) -> Optional[dict]:
        if not os.path.exists(path):
            return None
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    @staticmethod
    def _load_json_autotune() -> Optional[dict]:
        """读取 AutoBrain config.json，转换为与 openclaw.json 兼容的结构"""
        cfg = ConfigLoader._load_json(AUTOTUNE_CONFIG_PATH)
        if cfg and "engines" in cfg and isinstance(cfg["engines"], dict):
            return {"engines": cfg["engines"]}
        return cfg

    @staticmethod
    def _deep_copy(d: dict) -> dict:
        """深拷贝字典"""
        return json.loads(json.dumps(d))

    @staticmethod
    def _deep_merge(base: dict, override: dict):
        """递归合并，override 覆盖 base"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                ConfigLoader._deep_merge(base[key], value)
            else:
                base[key] = ConfigLoader._deep_copy(value) if isinstance(value, dict) else value

    @staticmethod
    def _get_by_path(d: dict, path: str, default: Any = None) -> Any:
        parts = path.split(".")
        current = d
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return default
        return current if current is not None else default

    @staticmethod
    def _set_by_path(d: dict, path: str, value: Any):
        parts = path.split(".")
        current = d
        for i, part in enumerate(parts[:-1]):
            if part not in current or not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value


# ── 快捷函数 ──

def get_config(key: str, default: Any = None) -> Any:
    """快捷获取配置"""
    return ConfigLoader().get(key, default)


def set_config(key: str, value: Any):
    """快捷设置运行时覆盖配置"""
    ConfigLoader().set_override(key, value)


# ═══════════════════════════════════════════════════════════
# 第四部分：引擎注册表（轻量版）
# ═══════════════════════════════════════════════════════════

class EngineRegistry:
    """
    轻量级引擎注册表。
    引擎通过名称注册，其他引擎通过 registry.get('xxx') 获取引用。
    替代硬编码的 from ... import 语句。
    """

    _instance = None
    _singleton_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._singleton_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._engines = {}
                    cls._instance._metadata = {}
        return cls._instance

    def register(self, name: str, instance: Any, metadata: dict = None):
        """注册引擎实例"""
        if name in self._engines:
            raise EngineStateError(name, "unregistered", "registered",
                                   {"msg": f"引擎 {name} 重复注册"})
        self._engines[name] = instance
        self._metadata[name] = {
            "registered_at": datetime.now(BEIJING_TZ).isoformat(),
            "type": type(instance).__name__,
            **(metadata or {}),
        }

    def get(self, name: str) -> Optional[Any]:
        """通过名称获取引擎实例"""
        return self._engines.get(name)

    def get_or_raise(self, name: str) -> Any:
        """获取引擎实例，不存在则抛异常"""
        instance = self._engines.get(name)
        if instance is None:
            raise EngineDependencyError("EngineRegistry", name,
                                        f"依赖的引擎 {name} 未注册")
        return instance

    def list(self) -> list[str]:
        """列出所有已注册引擎"""
        return list(self._engines.keys())

    def metadata(self, name: str = None) -> dict:
        """获取引擎元数据"""
        if name:
            return self._metadata.get(name, {})
        return self._metadata

    def unregister(self, name: str):
        """注销引擎"""
        if name in self._engines:
            del self._engines[name]
        if name in self._metadata:
            del self._metadata[name]

    def health_check(self) -> dict:
        """健康检查：返回每个引擎的状态"""
        status = {}
        for name, instance in self._engines.items():
            try:
                if hasattr(instance, "health") and callable(instance.health):
                    h = instance.health()
                    status[name] = {"status": "ok", "detail": h}
                else:
                    status[name] = {"status": "ok", "detail": "no health method"}
            except Exception as e:
                status[name] = {"status": "error", "detail": str(e)}
        return status


# ── 快捷函数 ──

def get_engine(name: str) -> Optional[Any]:
    """快捷获取已注册的引擎实例"""
    return EngineRegistry().get(name)


def register_engine(name: str, instance: Any, metadata: dict = None):
    """快捷注册引擎实例"""
    EngineRegistry().register(name, instance, metadata)


# ═══════════════════════════════════════════════════════════
# 独立运行入口：打印当前配置摘要
# ═══════════════════════════════════════════════════════════

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

    cl = ConfigLoader()
    config = cl.get_all()
    print("=" * 56)
    print("  Crusheart Agent OS — ConfigLoader 配置摘要")
    print("=" * 56)
    print(f"\n📄 配置来源:")
    print(f"   系统默认: {len(SYSTEM_DEFAULTS)} 个顶级键")
    print(f"   openclaw.json: {'✅ 已加载' if os.path.exists(DEFAULT_CONFIG_PATH) else '❌ 不存在'}")
    print(f"   autotune config.json: {'✅ 已加载' if os.path.exists(AUTOTUNE_CONFIG_PATH) else '❌ 不存在'}")
    print(f"   环境变量覆盖: {sum(1 for k in ENV_MAP if os.environ.get(k))} 个生效")
    print(f"   运行时覆盖: {len(cl._overrides)} 个")

    print(f"\n🔧 关键配置:")
    print(f"   runtime.no_external_api = {cl.get('runtime.no_external_api')}")
    print(f"   runtime.gateway_url     = {cl.get('runtime.gateway_url')}")
    print(f"   engines.dual_mode       = {cl.get('engines.dual_mode.default_mode')} (default_mode)")
    print(f"   engines.memory_layer    = {cl.get('engines.memory_layer.l2_retention_days')}d (l2_retention)")
    print(f"   engines.failover        = {cl.get('engines.failover.fallback_model')} (backup)")
    print(f"   bootstrapMaxChars       = {cl.get('bootstrapMaxChars')}")

    print(f"\n🧩 引擎注册表: {len(EngineRegistry().list())} 个引擎")
    print(f"   已注册: {EngineRegistry().list()}")
    print(f"\n✅ ConfigLoader 就绪")
