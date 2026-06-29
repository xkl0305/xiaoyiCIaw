"""
Crusheart Agent OS — EngineFactory v1.0
统一引擎工厂：engines.json 作为唯一真相来源，所有引擎初始化走此入口。

职责：
1. 加载 engines.json 配置
2. 按需懒加载（lazy_load_enforcer 协同）
3. 全量初始化（供 init_engines.py 调用）
4. 依赖校验（config_validator 协同）
5. 向后兼容：保留旧版 get_engine() 快捷方法

用法：
    from core.engines.init.engine_factory import EngineFactory
    compiler = EngineFactory.get("goal_compiler")  # 懒加载
    EngineFactory.init_all()                        # 全量初始化
"""

from __future__ import annotations

import os
import sys
import json
import importlib
import threading
import logging
from typing import Any, Dict, List, Optional, Type

logger = logging.getLogger(__name__)

WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
ENGINES_JSON = os.path.join(WORKSPACE, "core", "engines", "init", "engines.json")
ENGINE_GROUPS = ["init", "memory", "quality", "operations", "workflow", "hooks", "tools", "compat"]

# ═══════════════════════════════════════════════════════════════
# #45: 统一单例注册表 — 全局单例管理
# ═══════════════════════════════════════════════════════════════

class SingletonRegistry:
    """
    线程安全的统一单例注册表（#45）。

    用法：
        from core.engines.init.engine_factory import SingletonRegistry
        engine = SingletonRegistry.get(MyEngine, enable_cache=True)
        SingletonRegistry.reset(MyEngine)

    EngineFactory 内部已经使用此注册表管理引擎实例。
    所有引擎类优先通过 SingletonRegistry 管理单例，
    不再各自实现自定义全局 _instance。
    """

    _instances: Dict[type, Any] = {}
    _locks: Dict[type, threading.Lock] = {}
    _global_lock: threading.Lock = threading.Lock()

    @classmethod
    def get(cls, cls_type: type, **kwargs):
        """获取/创建单例"""
        if cls_type not in cls._instances:
            with cls._global_lock:
                if cls_type not in cls._instances:
                    if cls_type not in cls._locks:
                        cls._locks[cls_type] = threading.Lock()
                    with cls._locks[cls_type]:
                        cls._instances[cls_type] = cls_type(**kwargs)
        return cls._instances[cls_type]

    @classmethod
    def get_or_none(cls, cls_type: type):
        """获取已存在的单例，未初始化则返回 None"""
        return cls._instances.get(cls_type, None)

    @classmethod
    def register(cls, cls_type: type, instance: Any):
        """手动注册单例（供 EngineFactory 内部使用或测试）"""
        cls._instances[cls_type] = instance

    @classmethod
    def reset(cls, cls_type: type = None):
        """重置单例（测试用）"""
        if cls_type:
            cls._instances.pop(cls_type, None)
            cls._locks.pop(cls_type, None)
        else:
            cls._instances.clear()
            cls._locks.clear()

    @classmethod
    def is_registered(cls, cls_type: type) -> bool:
        """检查某类型是否已注册"""
        return cls_type in cls._instances

    @classmethod
    def list_all(cls) -> Dict[str, str]:
        """列出所有注册的单例（调试用）"""
        return {
            k.__name__ if hasattr(k, "__name__") else str(k):
            type(v).__name__ if hasattr(v, "__name__") else str(type(v).__name__)
            for k, v in cls._instances.items()
        }


# ── 引擎描述 ──

class EngineDescription:
    """引擎配置描述——对应 engines.json 中单个 entry"""

    __slots__ = ("name", "module", "class_name", "init_fn", "enabled", "description", "extra_init")

    def __init__(self, cfg: dict):
        self.name: str = cfg["name"]
        self.module: str = cfg.get("module", "")
        self.class_name: Optional[str] = cfg.get("class")
        self.init_fn: Optional[str] = cfg.get("init_fn")
        self.enabled: bool = cfg.get("enabled", True)
        self.description: str = cfg.get("description", "")
        self.extra_init: List[str] = cfg.get("extra_init", [])

    def __repr__(self) -> str:
        return f"<EngineDesc {self.name} {'✅' if self.enabled else '⛔'}>"


# ── 引擎工厂 ──

class EngineFactory:
    """
    唯一引擎工厂

    设计要点：
    - 单例模式，全局唯一
    - 懒加载：get() 时按需导入并缓存
    - 全量加载：init_all() 批量初始化
    - engines.json 是唯一配置来源（Orchestrator.ENGINE_REGISTRY 不再维护）
    """

    _instance: Optional["EngineFactory"] = None

    def __new__(cls) -> "EngineFactory":
        from core.engines.init.engine_factory import SingletonRegistry
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
            SingletonRegistry.register(cls, cls._instance)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._descriptions: Dict[str, EngineDescription] = {}  # name → EngineDescription
        self._instances: Dict[str, Any] = {}                   # name → engine instance
        self._import_check: Dict[str, bool] = {}               # name → importable?
        self._load_config()

    # ── 配置加载 ──

    def _load_config(self) -> None:
        """从 engines.json 加载所有引擎配置"""
        if not os.path.exists(ENGINES_JSON):
            logger.warning(f"EngineFactory: engines.json 不存在: {ENGINES_JSON}")
            return
        try:
            with open(ENGINES_JSON, encoding="utf-8") as f:
                config = json.load(f)
            for cfg in config.get("engines", []):
                desc = EngineDescription(cfg)
                self._descriptions[desc.name] = desc
                # 预先校验是否可导入
                self._import_check[desc.name] = self._check_import(desc)
            logger.info(
                f"EngineFactory: 已加载 {len(self._descriptions)} 个引擎配置"
                f" ({sum(1 for d in self._descriptions.values() if d.enabled)} 启用)"
            )
        except Exception as e:
            logger.error(f"EngineFactory: engines.json 加载失败: {e}")

    def _check_import(self, desc: EngineDescription) -> bool:
        """检查引擎模块是否可导入（不实例化）"""
        if not desc.module:
            return False
        try:
            mod = importlib.import_module(desc.module)
            if desc.class_name:
                getattr(mod, desc.class_name)
            return True
        except Exception:
            return False

    # ── 核心接口 ──

    def get(self, name: str, lazy: bool = True) -> Optional[Any]:
        """
        获取引擎实例（懒加载）

        Args:
            name: 引擎名称（对应 engines.json 中的 name）
            lazy: 是否懒加载。True 则按需初始化；False 则只返回已缓存的

        Returns:
            引擎实例，或 None（未找到/导入失败）
        """
        # 已缓存
        if name in self._instances:
            return self._instances[name]

        if not lazy:
            return None  # 不懒加载且未缓存

        desc = self._descriptions.get(name)
        if not desc:
            logger.warning(f"EngineFactory: 未找到引擎 [{name}]")
            return None
        if not desc.enabled:
            logger.debug(f"EngineFactory: 引擎 [{name}] 已禁用")
            return None

        instance = self._init_single(desc)
        if instance is not None:
            self._instances[name] = instance
        return instance

    def init_all(self, include_disabled: bool = False) -> Dict[str, Any]:
        """
        全量初始化所有启用的引擎

        Args:
            include_disabled: 是否同时初始化禁用引擎

        Returns:
            {name: instance} 字典
        """
        for name, desc in self._descriptions.items():
            if not desc.enabled and not include_disabled:
                continue
            if name not in self._instances:
                instance = self._init_single(desc)
                if instance is not None:
                    self._instances[name] = instance
        return self._instances

    def get_descriptions(self) -> Dict[str, EngineDescription]:
        """获取所有引擎配置描述"""
        return dict(self._descriptions)

    def get_status(self) -> Dict[str, bool]:
        """获取所有引擎状态（是否已初始化）"""
        return {name: name in self._instances for name in self._descriptions}

    def reload_config(self) -> None:
        """重新加载 engines.json（运行时重载）"""
        old_names = set(self._descriptions.keys())
        self._load_config()
        new_names = set(self._descriptions.keys())
        # 清理已删除引擎的缓存
        for name in old_names - new_names:
            self._instances.pop(name, None)
            self._import_check.pop(name, None)
        logger.info(f"EngineFactory: 配置已重载 ({len(self._descriptions)} 个引擎)")

    # ── 内部初始化 ──

    def _init_single(self, desc: EngineDescription) -> Optional[Any]:
        """初始化单个引擎"""
        try:
            if WORKSPACE not in sys.path:
                sys.path.insert(0, WORKSPACE)

            module = importlib.import_module(desc.module)

            if desc.init_fn:
                init_func = getattr(module, desc.init_fn)
                instance = init_func()
                logger.debug(f"EngineFactory: [{desc.name}] 通过 {desc.init_fn}() 初始化")
                # 额外初始化
                for extra in desc.extra_init:
                    extra_cls = getattr(module, extra, None)
                    if extra_cls:
                        extra_cls()
                return instance

            if desc.class_name:
                cls = getattr(module, desc.class_name)
                instance = cls()
                logger.debug(f"EngineFactory: [{desc.name}] {desc.class_name}() 实例化")
                for extra in desc.extra_init:
                    extra_cls = getattr(module, extra, None)
                    if extra_cls:
                        extra_cls()
                return instance

            logger.warning(f"EngineFactory: [{desc.name}] 没有 class 或 init_fn")
            return None

        except Exception as e:
            logger.error(f"EngineFactory: [{desc.name}] 初始化失败: {e}")
            return None


# ── 快捷函数（向后兼容 config_loader.py 的 get_engine） ──

def get_engine(name: str) -> Optional[Any]:
    """快捷获取引擎实例（向后兼容）"""
    return EngineFactory().get(name)


def register_engine(name: str, instance: Any, metadata: dict = None) -> None:
    """
    手动注册引擎实例（向后兼容）
    注意：手动注册不会写入 engines.json，仅用于测试或特殊场景
    """
    EngineFactory()._instances[name] = instance


# ── CLI ──

def main():
    import argparse
    parser = argparse.ArgumentParser(description="EngineFactory 控制台")
    parser.add_argument("action", choices=["status", "init-all", "list", "get"], nargs="?")
    parser.add_argument("name", nargs="?", help="引擎名称")
    args = parser.parse_args()

    factory = EngineFactory()

    if args.action == "status":
        status = factory.get_status()
        print(f"引擎总数: {len(factory.get_descriptions())}")
        print(f"已初始化: {sum(1 for v in status.values() if v)}")
        for name, initialized in sorted(status.items()):
            desc = factory.get_descriptions().get(name)
            icon = "✅" if initialized else "⏳"
            enabled = "🟢" if desc and desc.enabled else "⛔"
            print(f"  {enabled}{icon} {name}")
            if desc and desc.description:
                print(f"          {desc.description}")

    elif args.action == "init-all":
        instances = factory.init_all()
        print(f"已初始化 {len(instances)} 个引擎")

    elif args.action == "list":
        for name, desc in sorted(factory.get_descriptions().items()):
            enabled = "🟢" if desc.enabled else "⛔"
            print(f"  {enabled} {name} → {desc.module}:{desc.class_name or desc.init_fn or '?'}")

    elif args.action == "get":
        if not args.name:
            print("请指定引擎名称")
            return
        instance = factory.get(args.name)
        if instance:
            print(f"✅ {args.name}: {type(instance).__name__}")
        else:
            print(f"❌ {args.name}: 未找到或初始化失败")

    else:
        parser.print_help()


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

    main()
