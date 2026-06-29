"""
Crusheart Agent OS — 配置有效性验证器
功能：启动时校验关键配置文件的合法性，避免运行时因配置错误导致的异常
集成：由 init_engines.py 在引擎加载前调用

验证能力：
1. 数值范围校验（min/max）
2. 路径存在性校验
3. 类型校验
4. 必填项校验
5. 依赖关系校验
6. 枚举值校验
"""

import os
import sys
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")


def log(msg: str):
    ts = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [ConfigValidator] {msg}")


# ─── 验证规则引擎 ───────────────────────────────────────

class ValidationRule:
    """单条验证规则"""
    def __init__(self, field_path: str, rule_type: str, **params):
        self.field_path = field_path  # 点号路径，如 "bootstrapMaxChars"
        self.rule_type = rule_type
        self.params = params

    def check(self, config: dict) -> Optional[str]:
        """返回 None 表示通过，返回字符串表示错误信息"""
        value = self._get_value(config)
        if value is None and self.params.get("required"):
            return f"缺少必填配置项: {self.field_path}"
        if value is None:
            return None  # 无值时跳过校验

        if self.rule_type == "type":
            expected = self.params["type"]
            if not isinstance(value, expected):
                return f"{self.field_path} 类型错误: 期望 {expected.__name__}, 实际 {type(value).__name__}"
        elif self.rule_type == "range":
            v_min = self.params.get("min")
            v_max = self.params.get("max")
            if v_min is not None and value < v_min:
                return f"{self.field_path} = {value} 低于最小值 {v_min}"
            if v_max is not None and value > v_max:
                return f"{self.field_path} = {value} 超过最大值 {v_max}"
        elif self.rule_type == "path_exists":
            resolved = os.path.join(WORKSPACE, value) if not os.path.isabs(value) else value
            if not os.path.exists(resolved):
                return f"{self.field_path} 路径不存在: {resolved}"
        elif self.rule_type == "enum":
            valid_values = self.params["values"]
            if value not in valid_values:
                return f"{self.field_path} = {value} 不在允许值列表中: {valid_values}"
        elif self.rule_type == "module_importable":
            try:
                import importlib
                importlib.import_module(value)
            except ImportError as e:
                return f"{self.field_path} 模块不可导入: {value} ({e})"
        elif self.rule_type == "class_exists":
            try:
                import importlib
                parts = value.rsplit(".", 1)
                if len(parts) == 2:
                    module = importlib.import_module(parts[0])
                    if not hasattr(module, parts[1]):
                        return f"{self.field_path} 类不存在: {value}"
            except ImportError as e:
                return f"{self.field_path} 模块不可导入: {value} ({e})"
        elif self.rule_type == "dependency":
            dep_field = self.params["depends_on"]
            dep_value = self._get_value(config, dep_field)
            condition = self.params.get("condition", "exists")
            if condition == "exists" and dep_value is None:
                return f"{self.field_path} 依赖 {dep_field}，但 {dep_field} 未配置"
            if condition == "enabled" and dep_value is False:
                return f"{self.field_path} 依赖 {dep_field} 为启用状态，但当前为禁用"
        elif self.rule_type == "non_empty_string":
            if not isinstance(value, str) or not value.strip():
                return f"{self.field_path} 不能为空字符串"
        elif self.rule_type == "non_negative":
            if value is None:
                return None
            if value < 0:
                return f"{self.field_path} = {value} 不能为负数"

        return None

    def _get_value(self, config: dict, path: Optional[str] = None) -> Any:
        path = path or self.field_path
        parts = path.split(".")
        current = config
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current


class ConfigValidator:
    """配置验证器，管理多个验证规则集"""

    def __init__(self):
        self.rulesets: dict[str, list[ValidationRule]] = {}
        self.errors: dict[str, list[str]] = {}

    def add_ruleset(self, name: str, rules: list[ValidationRule]):
        self.rulesets[name] = rules

    def validate(self, config: dict, ruleset_name: str) -> list[str]:
        """对配置执行指定规则集的校验，返回错误列表"""
        errors = []
        rules = self.rulesets.get(ruleset_name, [])
        for rule in rules:
            err = rule.check(config)
            if err:
                errors.append(err)
        self.errors[ruleset_name] = errors
        return errors

    def validate_all(self, configs: dict[str, dict]) -> dict[str, list[str]]:
        """校验多个配置"""
        all_errors = {}
        for name, config in configs.items():
            errors = self.validate(config, name)
            if errors:
                all_errors[name] = errors
        return all_errors

    def report(self, all_errors: dict[str, list[str]]) -> bool:
        """输出校验报告，返回是否有错误"""
        total_errors = sum(len(errs) for errs in all_errors.values())
        if total_errors == 0:
            log("✅ 所有配置校验通过")
            return True

        log(f"⚠️ 发现 {total_errors} 个配置问题:")
        for name, errors in all_errors.items():
            log(f"   📄 {name}:")
            for err in errors:
                log(f"      ❌ {err}")
        return False


# ─── 规则定义 ───────────────────────────────────────────

def build_openclaw_rules() -> list[ValidationRule]:
    """openclaw.json 校验规则"""
    return [
        ValidationRule("bootstrapMaxChars", "range", min=1000, max=100000),
        ValidationRule("bootstrapTotalMaxChars", "range", min=5000, max=200000),
        ValidationRule("personaVisual.confidenceThreshold", "range", min=0.0, max=1.0),
        ValidationRule("personaVisual.dailyAutoGenerateLimit", "range", min=0, max=100),
        ValidationRule("personaVisual.cooldownTurns", "range", min=0, max=50),
        ValidationRule("projectContextFiles", "type", type=list),
        ValidationRule("agents.defaults.bootstrapMaxChars", "range", min=1000, max=100000),
        ValidationRule("agents.defaults.bootstrapTotalMaxChars", "range", min=5000, max=200000),
    ]


def build_autotune_rules() -> list[ValidationRule]:
    """AutoBrain config.json 校验规则（匹配实际嵌套结构 engines.xxx.yyy）"""
    return [
        ValidationRule("engines.anti_fake.risk_threshold", "enum", values=["low", "medium", "high"]),
        ValidationRule("engines.dual_mode.default_mode", "enum", values=["fast", "agent"]),
        ValidationRule("engines.dual_mode.auto_switch", "type", type=bool),
        ValidationRule("engines.lazy_load.search_interval_ms", "range", min=50, max=10000),
        ValidationRule("engines.lazy_load.max_searches_per_task", "range", min=1, max=50),
        ValidationRule("engines.lazy_load.cache_ttl_seconds", "range", min=60, max=86400),
        ValidationRule("engines.mutex.task_timeout_seconds", "range", min=10, max=3600),
        ValidationRule("engines.mutex.max_retry", "range", min=0, max=10),
        ValidationRule("engines.memory_layer.l2_retention_days", "range", min=1, max=365),
        ValidationRule("engines.memory_layer.decay_start_days", "range", min=1, max=365),
        ValidationRule("engines.memory_layer.decay_end_days", "range", min=1, max=365),
        ValidationRule("engines.memory_layer.decay_min_weight", "range", min=0.0, max=1.0),
        ValidationRule("engines.failover.cooldown_minutes", "range", min=0, max=1440),
        ValidationRule("engines.failover.max_retries", "range", min=0, max=10),
        ValidationRule("engines.context_warning.round_threshold", "range", min=1, max=200),
        ValidationRule("engines.context_warning.toolcall_threshold", "range", min=1, max=200),
        ValidationRule("engines.judge_engine.replay_buffer_size", "range", min=1, max=500),
        ValidationRule("engines.judge_engine.min_score_for_replay", "range", min=0.0, max=1.0),
        ValidationRule("engines.decision_core.default_priority", "range", min=0, max=10),
        ValidationRule("engines.identity_drift_guard.drift_threshold", "range", min=0.0, max=1.0),
        ValidationRule("engines.session_manager.max_capsules", "range", min=1, max=500),
    ]


# ─── 引擎注册表专项校验 ───────────────────────────────

def validate_engine_registry(engines: list[dict]) -> list[str]:
    """
    校验 engines.json 中的引擎注册表
    检查：module 是否可导入、class 是否存在、enabled 类型等
    """
    errors = []
    if WORKSPACE not in sys.path:
        sys.path.insert(0, WORKSPACE)

    for i, engine in enumerate(engines):
        name = engine.get("name", f"index_{i}")

        if "name" not in engine:
            errors.append(f"引擎 [{i}] 缺少 name 字段")
            continue
        if "module" not in engine:
            errors.append(f"引擎 [{name}] 缺少 module 字段")
            continue

        module_path = engine["module"]

        try:
            import importlib
            importlib.import_module(module_path)
        except ImportError as e:
            errors.append(f"引擎 [{name}] module 不可导入: {module_path} ({e})")
            continue

        class_name = engine.get("class")
        if class_name:
            try:
                module = importlib.import_module(module_path)
                if not hasattr(module, class_name):
                    errors.append(f"引擎 [{name}] class 不存在: {module_path}.{class_name}")
            except ImportError:
                pass

        init_fn = engine.get("init_fn")
        if init_fn:
            try:
                module = importlib.import_module(module_path)
                if not hasattr(module, init_fn):
                    errors.append(f"引擎 [{name}] init_fn 不存在: {module_path}.{init_fn}")
            except ImportError:
                pass

        if "enabled" in engine and not isinstance(engine["enabled"], bool):
            errors.append(f"引擎 [{name}] enabled 字段应为 bool 类型")

    return errors


# ─── 环境变量校验 ───────────────────────────────────────

def validate_env_vars() -> list[str]:
    """校验关键环境变量的合法性"""
    errors = []

    checks = {
        "NO_EXTERNAL_API": ("true", "false"),
        "NO_REAL_SEND": ("true", "false"),
        "NO_REAL_PAYMENT": ("true", "false"),
        "NO_REAL_DEVICE": ("true", "false"),
    }

    for var, allowed in checks.items():
        value = os.environ.get(var)
        if value is not None and value.lower() not in allowed:
            errors.append(f"环境变量 {var} = '{value}' 非法，期望值: {allowed}")

    gw_url = os.environ.get("OPENCLAW_GATEWAY_URL")
    if gw_url and not gw_url.startswith("http"):
        errors.append(f"环境变量 OPENCLAW_GATEWAY_URL = '{gw_url}' 不是合法的 URL")

    return errors


# ─── 引擎依赖关系校验 ───────────────────────────────────

ENGINE_DEPENDENCIES = {
    "session_manager": ["memory_layer"],
    "goal_compiler": ["state_manager"],
    "autonomy_cycle": ["goal_compiler", "decision_core", "state_manager"],
}

# 可选依赖（推荐有但非强制）
ENGINE_RECOMMENDED = {
    "unified_judge": ["closed_loop"],

}

def validate_engine_dependencies(enabled: set) -> list[str]:
    """校验引擎依赖：如果 A 启用了但依赖的 B 没启用，报错"""
    errors = []
    for engine, deps in ENGINE_DEPENDENCIES.items():
        if engine in enabled:
            for dep in deps:
                if dep not in enabled:
                    errors.append(f"引擎 [{engine}] 依赖 [{dep}]，但 [{dep}] 未启用")
    return errors


def validate_engine_recommended(enabled: set) -> list[str]:
    """校验推荐依赖：缺少时记录警告（不影响启动）"""
    warnings = []
    for engine, deps in ENGINE_RECOMMENDED.items():
        if engine in enabled:
            for dep in deps:
                if dep not in enabled:
                    warnings.append(f"引擎 [{engine}] 推荐依赖 [{dep}]，当前未启用（可选）")
    return warnings


# ─── 主入口 ─────────────────────────────────────────────

def load_json(path: str) -> Optional[dict]:
    """安全加载 JSON 文件"""
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        log(f"❌ JSON 解析失败: {path} ({e})")
        return None


def run_full_validation() -> bool:
    """
    执行全量配置校验
    Returns: True=全部通过, False=存在错误
    """
    log("🔍 开始配置有效性验证...")
    all_pass = True

    # ── 1. openclaw.json ──
    openclaw_cfg = load_json(os.path.join(WORKSPACE, "openclaw.json"))
    if openclaw_cfg:
        validator = ConfigValidator()
        validator.add_ruleset("openclaw.json", build_openclaw_rules())
        openclaw_errors = validator.validate(openclaw_cfg, "openclaw.json")
        if openclaw_errors:
            all_pass = False
            for err in openclaw_errors:
                log(f"   ❌ [openclaw.json] {err}")
        else:
            log(f"   ✅ openclaw.json 通过")
    else:
        log(f"   ⚠️ openclaw.json 不存在，跳过校验")

    # ── 2. engines.json 注册表 ──
    engines_cfg = load_json(os.path.join(WORKSPACE, "core", "engines", "init", "engines.json"))
    if engines_cfg:
        engine_list = engines_cfg.get("engines", [])
        engine_errors = validate_engine_registry(engine_list)
        if engine_errors:
            all_pass = False
            for err in engine_errors:
                log(f"   ❌ [engines.json] {err}")
        else:
            log(f"   ✅ engines.json 通过 ({len(engine_list)} 个引擎)")
    else:
        log(f"   ⚠️ engines.json 不存在，跳过校验")

    # ── 3. AutoBrain config.json ──
    autotune_cfg = load_json(os.path.join(
        WORKSPACE, "skills", "Crusheart-AutoBrain-Turbo", "config.json"
    ))
    if autotune_cfg:
        validator2 = ConfigValidator()
        validator2.add_ruleset("autotune_config.json", build_autotune_rules())
        tune_errors = validator2.validate(autotune_cfg, "autotune_config.json")
        if tune_errors:
            all_pass = False
            for err in tune_errors:
                log(f"   ❌ [autotune_config.json] {err}")
        else:
            log(f"   ✅ AutoBrain config.json 通过")
    else:
        log(f"   ⚠️ AutoBrain config.json 不存在，跳过校验")

    # ── 4. 环境变量 ──
    env_errors = validate_env_vars()
    if env_errors:
        all_pass = False
        for err in env_errors:
            log(f"   ❌ [环境变量] {err}")
    else:
        log(f"   ✅ 环境变量通过")

    # ── 5. 引擎依赖关系 ──
    if engines_cfg:
        enabled_engines = {e["name"] for e in engine_list if e.get("enabled", True)}
        deps_errors = validate_engine_dependencies(enabled_engines)
        if deps_errors:
            all_pass = False
            for err in deps_errors:
                log(f"   ❌ [引擎依赖] {err}")
        else:
            log(f"   ✅ 引擎依赖关系通过")
        
        # 推荐依赖仅警告，不影响启动
        rec_warnings = validate_engine_recommended(enabled_engines)
        for w in rec_warnings:
            log(f"   ⚠️ [引擎依赖] {w}")

    if all_pass:
        log("✅ 验证完成，所有配置通过")
    else:
        log("⚠️ 验证完成，存在配置问题")

    return all_pass


# ─── 独立运行入口 ───────────────────────────────────────

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

    passed = run_full_validation()
    sys.exit(0 if passed else 1)
