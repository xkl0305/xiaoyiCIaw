"""
Crusheart Agent OS — Compat Layer: 第三方引擎标准接口抽象基类 (ABC)
功能：定义第三方引擎必须实现的生命周期方法和事件钩子
关系：plugin_sdk.PluginEngine 可选择性继承本 ABC 获得兼容层支持
"""

import abc
from typing import Optional, Callable
from datetime import datetime, timezone, timedelta

BEIJING_TZ = timezone(timedelta(hours=8))


class CompatEngine(abc.ABC):
    """第三方引擎标准接口抽象基类
    
    任何实现本 ABC 的类均可通过 compat_registry 自动发现并注册。
    生命周期: installed → enabled → running → disabled
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """引擎唯一名称（用于注册和索引）"""
        ...

    @property
    @abc.abstractmethod
    def version(self) -> str:
        """引擎版本号"""
        ...

    @property
    def description(self) -> str:
        """引擎描述（可选覆盖）"""
        return ""

    @property
    def priority(self) -> int:
        """执行优先级，数字越小越先执行（默认 50）"""
        return 50

    @property
    def dependencies(self) -> list:
        """依赖的引擎名称列表（用于加载顺序排序）"""
        return []

    def __init__(self):
        """初始化基类属性"""
        self.status = "installed"
        self._hooks = {}
        self._metadata_cache = None

    # ── 生命周期 ──────────────────────────────────────────

    def on_install(self) -> bool:
        """安装回调：引擎被首次注册时调用"""
        return True

    def on_init(self) -> bool:
        """初始化回调：系统启动时调用，返回 True 表示初始化成功"""
        return True

    def on_enable(self) -> bool:
        """启用回调：引擎被启用时调用"""
        return True

    def on_disable(self) -> bool:
        """禁用回调：引擎被禁用时调用"""
        return True

    def on_uninstall(self) -> bool:
        """卸载回调：引擎被注销前调用"""
        return True

    # ── 事件钩子 ──────────────────────────────────────────

    def on_message(self, message: str, context: dict) -> Optional[dict]:
        """消息预处理钩子：收到用户消息时触发
        返回值会被合并到处理结果中，返回 None 表示不干预
        """
        return None

    def on_decision(self, task_type: str, confidence: float) -> Optional[dict]:
        """决策后处理钩子：任务类型分类完成后触发"""
        return None

    def on_error(self, error: Exception) -> None:
        """错误处理钩子：引擎自身产生异常时触发"""
        pass

    # ── 工具方法 ──────────────────────────────────────────

    def register_hook(self, hook_name: str, handler: Callable):
        """注册自定义钩子（子类可直接使用）"""
        if not hasattr(self, '_hooks'):
            self._hooks = {}
        self._hooks[hook_name] = handler

    def get_hooks(self) -> dict:
        """获取已注册的自定义钩子"""
        return getattr(self, '_hooks', {})

    @property
    def metadata(self) -> dict:
        """兼容 PluginRegistry 的序列化元数据"""
        # 运行时动态构建，不持久化在内存
        if self._metadata_cache is None:
            self._metadata_cache = {
                "name": self.name,
                "version": self.version,
                "description": self.description,
                "status": getattr(self, 'status', 'installed'),
                "priority": self.priority,
                "installed_at": None,
                "enabled_at": None,
                "last_error": None,
            }
        return self._metadata_cache

    def to_dict(self) -> dict:
        """序列化引擎信息（兼容 PluginRegistry）"""
        return {
            **self.metadata,
            "hooks": list(self.get_hooks().keys()),
            "class_name": type(self).__name__
        }

    def to_manifest(self) -> dict:
        """生成清单数据（用于注册和持久化）"""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "priority": self.priority,
            "dependencies": self.dependencies,
            "hooks": list(self.get_hooks().keys()),
            "class_name": type(self).__name__,
            "module": type(self).__module__,
        }
