"""
Crusheart Agent OS — Compat Registry: 自动发现 + 依赖解析 + 注册
功能：
  1. 扫描 plugins/ 目录下的 plugin.json 清单
  2. 拓扑排序解析依赖关系
  3. 自动导入模块并注册至 PluginRegistry
  4. 持久化注册状态
"""

import os
import sys
import json
import importlib.util
from datetime import datetime, timezone, timedelta
from typing import Optional
from core.engines.compat.compat_engine import CompatEngine

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
PLUGINS_DIR = os.path.join(WORKSPACE, "plugins")
COMPAT_REGISTRY_PATH = os.path.join(WORKSPACE, ".compat_registry.json")

# ── 扫描发现 ──────────────────────────────────────────────


def discover_manifests(plugins_dir: str = PLUGINS_DIR) -> list[dict]:
    """扫描 plugins/ 目录下所有 plugin.json，返回清单列表"""
    if not os.path.isdir(plugins_dir):
        return []

    manifests = []
    for entry in sorted(os.listdir(plugins_dir)):
        plugin_dir = os.path.join(plugins_dir, entry)
        if not os.path.isdir(plugin_dir):
            continue
        manifest_path = os.path.join(plugin_dir, "plugin.json")
        if not os.path.isfile(manifest_path):
            continue
        try:
            with open(manifest_path) as f:
                manifest = json.load(f)
            if not isinstance(manifest, dict) or "name" not in manifest:
                continue
            manifest["_dir"] = plugin_dir
            manifest["_manifest_path"] = manifest_path
            manifests.append(manifest)
        except (json.JSONDecodeError, IOError) as e:
            print(f"  ⚠️  跳过 {manifest_path}: {e}")

    return manifests


# ── 依赖解析（拓扑排序） ──────────────────────────────────


def _topological_sort(manifests: list[dict]) -> list[dict]:
    """按依赖关系拓扑排序，确保依赖先加载"""
    name_map = {m["name"]: m for m in manifests}
    visited = set()
    sorted_list = []

    def _dfs(name: str, path: set):
        if name in visited:
            return
        if name in path:
            print(f"  ⚠️  检测到循环依赖: {' → '.join(path | {name})}")
            return
        manifest = name_map.get(name)
        if not manifest:
            return
        path.add(name)
        for dep in manifest.get("dependencies", []):
            _dfs(dep, path)
        path.remove(name)
        visited.add(name)
        sorted_list.append(manifest)

    for m in manifests:
        if m["name"] not in visited:
            _dfs(m["name"], set())

    return sorted_list


# ── 模块动态导入 ──────────────────────────────────────────


def _import_plugin_class(manifest: dict) -> Optional[type]:
    """从 manifest 指定的 module + class 动态导入并返回类"""
    module_path = manifest.get("module", "")
    class_name = manifest.get("class", "")

    if not module_path or not class_name:
        print(f"  ⚠️  {manifest['name']}: 缺少 module 或 class 字段")
        return None

    # 将路径转换为 Python 模块名：去掉 .py，替换 / 为 .
    module_name = module_path.replace("/", ".").rstrip(".").removesuffix("py")
    plugin_dir = manifest.get("_dir", "")

    try:
        # 确保插件目录在 sys.path 中
        if plugin_dir and plugin_dir not in sys.path:
            sys.path.append(plugin_dir)

        spec = importlib.util.spec_from_file_location(module_name, os.path.join(WORKSPACE, module_path))
        if spec is None:
            # 尝试直接从 sys.path 导入
            try:
                mod = importlib.import_module(module_name)
            except ModuleNotFoundError:
                print(f"  ❌  {manifest['name']}: 无法加载模块 {module_path}")
                return None
        else:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

        cls = getattr(mod, class_name, None)
        if cls is None:
            print(f"  ❌  {manifest['name']}: 模块中未找到类 {class_name}")
            return None

        return cls
    except Exception as e:
        print(f"  ❌  {manifest['name']}: 导入失败: {e}")
        return None


# ── 自动注册 ──────────────────────────────────────────────


def auto_discover(plugins_dir: str = PLUGINS_DIR) -> dict:
    """自动扫描并注册所有第三方引擎
    
    Args:
        plugins_dir: 插件目录路径
        
    Returns:
        {"registered": [名称列表], "failed": [错误信息列表]}
    """
    from core.engines.tools.plugin_sdk import get_registry, PluginEngine

    registry = get_registry()
    manifests = discover_manifests(plugins_dir)

    if not manifests:
        print("  📭 Compat Layer: 未发现第三方引擎清单")
        return {"registered": [], "failed": []}

    # 拓扑排序
    sorted_manifests = _topological_sort(manifests)
    print(f"  📋 Compat Layer: 发现 {len(sorted_manifests)} 个引擎清单")

    registered = []
    failed = []

    for manifest in sorted_manifests:
        name = manifest["name"]
        version = manifest.get("version", "0.0.0")
        description = manifest.get("description", "")

        # 跳过已注册的
        if registry.get(name):
            print(f"  ⏭️  {name}: 已注册，跳过")
            registered.append(name)
            continue

        # 尝试导入 CompatEngine 实现类
        cls = _import_plugin_class(manifest)
        engine = None

        if cls is not None and issubclass(cls, CompatEngine):
            # 实现了 CompatEngine 接口 — 实例化
            try:
                engine = cls()
                ok = engine.on_install()
                if not ok:
                    failed.append(f"{name}: on_install() 返回 False")
                    continue
            except Exception as e:
                failed.append(f"{name}: 实例化失败: {e}")
                continue

        # 回退：用 PluginEngine 包装
        if engine is None:
            engine = PluginEngine(name, version, description)
            engine.priority = manifest.get("priority", 50)

        # 注册到 PluginRegistry
        ok = registry.register(engine)
        if ok:
            # 自动启用
            registry.enable(name)
            registered.append(name)
        else:
            failed.append(f"{name}: 注册失败（可能已存在）")

    # 保存兼容层状态
    _save_compat_state(registered, failed)

    total = len(registered)
    if total > 0:
        print(f"  ✅ Compat Layer: {total} 个引擎注册并启用")
    if failed:
        print(f"  ⚠️  {len(failed)} 个引擎注册失败:")
        for f in failed:
            print(f"     ❌ {f}")

    return {"registered": registered, "failed": failed}


# ── 生成脚手架 ────────────────────────────────────────────


def scaffold(name: str, hooks: list[str] = None, dependencies: list[str] = None):
    """生成引擎脚手架：plugin.json + main.py

    Args:
        name: 引擎名称（目录名也是这个）
        hooks: 要注册的钩子列表，如 ["on_message", "on_decision"]
        dependencies: 依赖的其他引擎名称列表
    """
    hooks = hooks or []
    dependencies = dependencies or []

    from core.engines.tools.plugin_sdk import create_plugin

    plugin_dir = os.path.join(PLUGINS_DIR, name)
    manifest_path = os.path.join(plugin_dir, "plugin.json")
    main_path = os.path.join(plugin_dir, "main.py")

    if os.path.exists(plugin_dir):
        print(f"  ⚠️  目录已存在: {plugin_dir}")
        return False

    os.makedirs(plugin_dir, exist_ok=True)

    # 写入 plugin.json
    manifest = {
        "name": name,
        "version": "1.0.0",
        "description": f"{name} 引擎",
        "module": f"plugins/{name}/main.py",
        "class": f"{name.capitalize().replace('-', '').replace('_', '')}Engine",
        "dependencies": dependencies,
        "hooks": hooks,
        "priority": 50
    }
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"  ✅ 已创建: {manifest_path}")

    # 写入 main.py 骨架
    class_name = manifest["class"]
    hook_imports = ""
    hook_stubs = ""
    for hook in hooks:
        if hook == "on_message":
            hook_stubs += """
    def on_message(self, message: str, context: dict) -> Optional[dict]:
        \"\"\"消息预处理钩子\"\"\"
        return None
"""
        elif hook == "on_decision":
            hook_stubs += """
    def on_decision(self, task_type: str, confidence: float) -> Optional[dict]:
        \"\"\"决策后处理钩子\"\"\"
        return None
"""
        elif hook == "on_error":
            hook_stubs += """
    def on_error(self, error: Exception) -> None:
        \"\"\"错误处理钩子\"\"\"
        pass
"""
    if hook_stubs:
        hook_imports = "from typing import Optional\n\n"

    main_content = f'''"""
{name} — 兼容层引擎
"""
{hook_imports}
from core.engines.compat.compat_engine import CompatEngine


class {class_name}(CompatEngine):
    """{name} 引擎"""

    @property
    def name(self) -> str:
        return "{name}"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "{name} 引擎"

    @property
    def priority(self) -> int:
        return {manifest["priority"]}

    @property
    def dependencies(self) -> list:
        return {json.dumps(dependencies)}
{hook_stubs}
'''
    with open(main_path, "w") as f:
        f.write(main_content.lstrip())
    print(f"  ✅ 已创建: {main_path}")

    print(f"\n  📦 引擎 '{name}' 脚手架已生成")
    print(f"     目录: {plugin_dir}")
    print(f"     要启用请在 engines.json 中注册，或运行 auto_discover()")
    return True


# ── 持久化 ──────────────────────────────────────────────


def _save_compat_state(registered: list, failed: list):
    """保存兼容层注册状态"""
    state = {
        "last_updated": datetime.now(BEIJING_TZ).isoformat(),
        "registered_count": len(registered),
        "failed_count": len(failed),
        "registered": registered,
        "failed": failed,
    }
    os.makedirs(os.path.dirname(COMPAT_REGISTRY_PATH), exist_ok=True)
    with open(COMPAT_REGISTRY_PATH, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def get_compat_state() -> dict:
    """获取兼容层状态"""
    if not os.path.exists(COMPAT_REGISTRY_PATH):
        return {"registered_count": 0, "registered": []}
    with open(COMPAT_REGISTRY_PATH) as f:
        return json.load(f)


# ── main ──────────────────────────────────────────────────


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

    import sys as _sys

    if len(_sys.argv) > 1 and _sys.argv[1] == "discover":
        result = auto_discover()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif len(_sys.argv) > 2 and _sys.argv[1] == "scaffold":
        scaffold(
            name=_sys.argv[2],
            hooks=_sys.argv[3].split(",") if len(_sys.argv) > 3 else [],
            dependencies=_sys.argv[4].split(",") if len(_sys.argv) > 4 else [],
        )
    else:
        print("用法:")
        print("  python3 -m core.engines.compat.compat_registry discover  # 扫描注册")
        print("  python3 -m core.engines.compat.compat_registry scaffold <名称> [钩子列表] [依赖列表]")
