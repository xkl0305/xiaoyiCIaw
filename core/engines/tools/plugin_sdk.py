"""
Crusheart Performance AutoBrain v4.3.2 — Plugin SDK 第三方引擎接口
功能：标准引擎接口规范、注册/注销、生命周期管理
"""

import os, sys, json, importlib.util, inspect
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional, Any

# 兼容层可选集成
# CompatEngine 由 compat_registry 在 auto_discover 时使用
# PluginEngine 保持独立，不强制依赖 compat 包
_HAVE_COMPAT = None

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
REGISTRY_PATH = os.path.join(WORKSPACE, ".plugin_registry.json")

# 引擎生命周期状态
PLUGIN_STATUS = ["installed", "enabled", "disabled", "errored"]


class PluginEngine:
    """第三方引擎接口基类"""

    def __init__(self, name: str, version: str, description: str = ""):
        self.name = name
        self.version = version
        self.description = description
        self.status = "installed"
        self.priority = 50  # 优先级，数字越小越先执行
        self.hooks = {}     # 注册的钩子函数
        self.metadata = {
            "name": name,
            "version": version,
            "description": description,
            "status": self.status,
            "priority": self.priority,
            "installed_at": None,
            "enabled_at": None,
            "last_error": None
        }

    def on_init(self) -> bool:
        """引擎初始化回调，返回 True 表示成功"""
        return True

    def on_enable(self) -> bool:
        """引擎启用回调"""
        return True

    def on_disable(self) -> bool:
        """引擎禁用回调"""
        return True

    def on_message(self, message: str, context: dict) -> Optional[dict]:
        """消息预处理钩子（可选覆盖）"""
        return None

    def on_decision(self, task_type: str, confidence: float) -> Optional[dict]:
        """决策后处理钩子（可选覆盖）"""
        return None

    def on_error(self, error: Exception) -> None:
        """错误处理钩子（可选覆盖）"""
        pass

    def register_hook(self, hook_name: str, handler: Callable):
        """注册自定义钩子"""
        self.hooks[hook_name] = handler
        return True

    def to_dict(self) -> dict:
        """序列化引擎信息"""
        return {
            **self.metadata,
            "hooks": list(self.hooks.keys()),
            "class_name": type(self).__name__
        }

    @classmethod
    def from_manifest(cls, manifest: dict):
        """从 plugin.json 清单构造引擎实例

        Args:
            manifest: plugin.json 解析后的字典

        Returns:
            PluginEngine 实例
        """
        engine = cls(
            name=manifest["name"],
            version=manifest.get("version", "0.0.0"),
            description=manifest.get("description", ""),
        )
        engine.priority = manifest.get("priority", 50)
        return engine


class PluginRegistry:
    """插件注册中心"""

    def __init__(self):
        self._plugins = {}
        self._load_registry()

    def _load_registry(self):
        """从持久化文件加载注册表"""
        if os.path.exists(REGISTRY_PATH):
            try:
                with open(REGISTRY_PATH) as f:
                    data = json.load(f)
                    for name, meta in data.get("plugins", {}).items():
                        if meta.get("status") == "enabled":
                            self._plugins[name] = PluginEngine(
                                name=name,
                                version=meta.get("version", "0.0.0"),
                                description=meta.get("description", "")
                            )
                            self._plugins[name].metadata = meta
            except (json.JSONDecodeError, IOError):
                pass

    def _save_registry(self):
        """保存注册表到持久化文件"""
        data = {
            "last_updated": datetime.now(BEIJING_TZ).isoformat(),
            "total": len(self._plugins),
            "plugins": {name: p.to_dict() for name, p in self._plugins.items()}
        }
        os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
        with open(REGISTRY_PATH, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def register(self, engine: PluginEngine) -> bool:
        """注册一个插件引擎"""
        if engine.name in self._plugins:
            print(f"  ⚠️ Plugin '{engine.name}' 已注册，跳过")
            return False

        engine.metadata["installed_at"] = datetime.now(BEIJING_TZ).isoformat()
        self._plugins[engine.name] = engine
        self._save_registry()
        print(f"  ✅ Plugin '{engine.name}' v{engine.version} 注册成功")
        return True

    def unregister(self, name: str) -> bool:
        """注销一个插件引擎"""
        if name not in self._plugins:
            print(f"  ⚠️ Plugin '{name}' 未注册")
            return False

        del self._plugins[name]
        self._save_registry()
        print(f"  ✅ Plugin '{name}' 已注销")
        return True

    def enable(self, name: str) -> bool:
        """启用插件"""
        if name not in self._plugins:
            print(f"  ⚠️ Plugin '{name}' 未注册")
            return False

        engine = self._plugins[name]
        if engine.status == "enabled":
            return True

        try:
            ok = engine.on_enable()
            if ok:
                engine.status = "enabled"
                engine.metadata["status"] = "enabled"
                engine.metadata["enabled_at"] = datetime.now(BEIJING_TZ).isoformat()
                self._save_registry()
                print(f"  ✅ Plugin '{name}' 已启用")
            return ok
        except Exception as e:
            engine.metadata["last_error"] = str(e)
            engine.metadata["status"] = "errored"
            self._save_registry()
            print(f"  ❌ Plugin '{name}' 启用失败: {e}")
            return False

    def disable(self, name: str) -> bool:
        """禁用插件"""
        if name not in self._plugins:
            print(f"  ⚠️ Plugin '{name}' 未注册")
            return False

        engine = self._plugins[name]
        try:
            engine.on_disable()
        except Exception:
            pass

        engine.status = "disabled"
        engine.metadata["status"] = "disabled"
        self._save_registry()
        print(f"  ✅ Plugin '{name}' 已禁用")
        return True

    def list_plugins(self, status_filter: str = None) -> list:
        """列出所有插件"""
        if status_filter:
            return [
                p.to_dict() for p in self._plugins.values()
                if p.status == status_filter
            ]
        return [p.to_dict() for p in self._plugins.values()]

    def get(self, name: str) -> Optional[PluginEngine]:
        """获取插件实例"""
        return self._plugins.get(name)

    def trigger_hook(self, hook_name: str, *args, **kwargs) -> list:
        """触发所有插件的指定钩子"""
        results = []
        for name, engine in sorted(
            self._plugins.items(),
            key=lambda x: x[1].priority
        ):
            if engine.status != "enabled":
                continue
            if hook_name in engine.hooks:
                try:
                    result = engine.hooks[hook_name](*args, **kwargs)
                    results.append({"plugin": name, "hook": hook_name, "result": result})
                except Exception as e:
                    results.append({"plugin": name, "hook": hook_name, "error": str(e)})
        return results

    def init_all(self) -> dict:
        """初始化所有已启用插件"""
        results = {"success": [], "failed": []}
        for name, engine in sorted(
            self._plugins.items(),
            key=lambda x: x[1].priority
        ):
            if engine.status != "enabled":
                continue
            try:
                ok = engine.on_init()
                if ok:
                    results["success"].append(name)
                else:
                    results["failed"].append(name)
            except Exception as e:
                results["failed"].append(f"{name}: {e}")
                engine.metadata["last_error"] = str(e)
                engine.metadata["status"] = "errored"
        self._save_registry()
        return results


# 单例
_registry = None


def get_registry() -> PluginRegistry:
    """获取全局插件注册中心单例"""
    global _registry
    if _registry is None:
        _registry = PluginRegistry()
    return _registry


def create_plugin(
    name: str,
    version: str = "1.0.0",
    description: str = "",
    priority: int = 50
) -> PluginEngine:
    """快捷创建插件引擎"""
    engine = PluginEngine(name, version, description)
    engine.priority = priority
    return engine


def init():
    """引擎初始化入口"""
    registry = get_registry()
    enabled_count = len([p for p in registry._plugins.values() if p.status == "enabled"])
    total = len(registry._plugins)
    
    result = {
        "status": "ready",
        "plugins_total": total,
        "plugins_enabled": enabled_count,
        "plugins": registry.list_plugins(),
        "initialized_at": datetime.now(BEIJING_TZ).isoformat()
    }
    
    if total > 0:
        print(f"  🔌 Plugin SDK: {enabled_count}/{total} 插件已启用")
    
    return result


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

    result = init()
    print(json.dumps(result, indent=2, ensure_ascii=False))
