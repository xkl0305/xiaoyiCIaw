"""
Crusheart Agent OS — 系统级钩子引擎 + 权限锁定
功能：钩子注册/执行/不可绕过锁定、审计追踪
"""

import os
import json
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Callable, Any
from enum import Enum

BEIJING_TZ = timezone(timedelta(hours=8))

HOOK_DIR = os.path.expanduser("~/.openclaw/workspace/.hooks")
os.makedirs(HOOK_DIR, exist_ok=True)

AUDIT_LOG = os.path.join(HOOK_DIR, "audit_log.jsonl")


class LockLevel(Enum):
    """锁定级别"""
    OPTIONAL = "optional"       # 🔓 可选 - 钩子失败不影响主流程
    REQUIRED = "required"       # 🔒 必需 - 钩子必须执行，失败记录日志
    MANDATORY = "mandatory"     # 🔒 强制 - 不可绕过，失败则终止主流程


class HookResult:
    """钩子执行结果"""
    def __init__(self, hook_name: str, success: bool, level: LockLevel, detail: str = ""):
        self.hook_name = hook_name
        self.success = success
        self.level = level
        self.detail = detail
        self.timestamp = datetime.now(BEIJING_TZ).isoformat()

    def to_dict(self) -> Dict:
        return {
            "hook_name": self.hook_name,
            "success": self.success,
            "level": self.level.value,
            "detail": self.detail,
            "timestamp": self.timestamp,
        }


class Hook:
    """单个钩子定义"""
    def __init__(self, name: str, level: LockLevel, 
                 pre_fn: Optional[Callable] = None,
                 post_fn: Optional[Callable] = None):
        self.name = name
        self.level = level
        self.pre_fn = pre_fn      # 执行前回调
        self.post_fn = post_fn    # 执行后回调

    def execute_pre(self, context: Dict) -> HookResult:
        """执行前置钩子"""
        if self.pre_fn:
            try:
                result = self.pre_fn(context)
                return HookResult(self.name, True, self.level, result or "")
            except Exception as e:
                return HookResult(self.name, False, self.level, str(e))
        return HookResult(self.name, True, self.level, "no-op")

    def execute_post(self, context: Dict) -> HookResult:
        """执行后置钩子"""
        if self.post_fn:
            try:
                result = self.post_fn(context)
                return HookResult(self.name, True, self.level, result or "")
            except Exception as e:
                return HookResult(self.name, False, self.level, str(e))
        return HookResult(self.name, True, self.level, "no-op")


class HookEngine:
    """全局钩子引擎 — 注册/执行/审计"""

    def __init__(self):
        self._hooks: Dict[str, Hook] = {}
        self._audit_trail: List[HookResult] = []
        self._load()

    def register(self, hook: Hook):
        """注册钩子"""
        self._hooks[hook.name] = hook
        self._save()

    def unregister(self, hook_name: str):
        """注销钩子"""
        self._hooks.pop(hook_name, None)
        self._save()

    def run_pre_hooks(self, context: Dict) -> List[HookResult]:
        """
        执行所有前置钩子
        如果 MANDATORY 级别的钩子失败，返回结果中包含 blocking 标记
        """
        results = []
        for name, hook in self._hooks.items():
            result = hook.execute_pre(context)
            results.append(result)
            self._audit(result)
            # 不可绕过检测
            if not result.success and result.level == LockLevel.MANDATORY:
                result.detail = f"[BLOCKED] 不可绕过钩子 '{name}' 执行失败，主流程被终止"
                raise RuntimeError(result.detail)
        return results

    def run_post_hooks(self, context: Dict) -> List[HookResult]:
        """执行所有后置钩子"""
        results = []
        for name, hook in self._hooks.items():
            result = hook.execute_post(context)
            results.append(result)
            self._audit(result)
        return results

    def is_bypass_allowed(self, hook_name: str) -> bool:
        """检查某个钩子是否可以被绕过"""
        hook = self._hooks.get(hook_name)
        if not hook:
            return True
        return hook.level != LockLevel.MANDATORY

    def get_hook_status(self) -> List[Dict]:
        """获取所有钩子状态"""
        return [
            {
                "name": name,
                "level": hook.level.value,
                "bypass_allowed": hook.level != LockLevel.MANDATORY
            }
            for name, hook in self._hooks.items()
        ]

    def get_audit_log(self, limit: int = 10) -> List[Dict]:
        """获取最近审计日志"""
        try:
            with open(AUDIT_LOG) as f:
                lines = f.readlines()[-limit:]
                return [json.loads(l) for l in lines]
        except (FileNotFoundError, json.JSONDecodeError):
            return []
        return []

    def _audit(self, result: HookResult):
        """记录审计日志"""
        self._audit_trail.append(result)
        with open(AUDIT_LOG, "a") as f:
            f.write(json.dumps(result.to_dict(), ensure_ascii=False) + "\n")

    def _save(self):
        data = {name: {"level": hook.level.value} for name, hook in self._hooks.items()}
        with open(os.path.join(HOOK_DIR, "hooks.json"), "w") as f:
            json.dump(data, f, ensure_ascii=False)

    def _load(self):
        hook_file = os.path.join(HOOK_DIR, "hooks.json")
        if os.path.exists(hook_file):
            with open(hook_file) as f:
                data = json.load(f)
                for name, config in data.items():
                    level = LockLevel(config.get("level", "optional"))
                    self._hooks[name] = Hook(name, level)


# 快速注册系统钩子
def init_default_hooks():
    """初始化默认系统钩子"""
    engine = HookEngine()

    # 1. 安全校验钩子 — 强制不可绕过
    def security_check(ctx):
        content = str(ctx.get("content", ""))
        content_lower = content.lower()
        # 仅检测明确的绕过指令，而非单纯提及概念
        bypass_keywords = ["bypass confirmation", "绕过确认", "免确认", "不用确认"]
        if any(kw in content_lower for kw in bypass_keywords):
            raise ValueError("检测到绕过确认的尝试")
        return "security check passed"

    engine.register(Hook(
        "execution-validator",
        LockLevel.MANDATORY,
        pre_fn=security_check
    ))

    # 2. 出站消息过滤钩子 — 可选
    def outbound_filter(ctx):
        msg = str(ctx.get("message", ""))
        if len(msg) > 100000:
            return "warning: message too large"
        return "ok"

    engine.register(Hook(
        "outbound-hooks",
        LockLevel.OPTIONAL,
        post_fn=outbound_filter
    ))

    # 3. 常驻指令自检钩子 — 可选
    def standing_orders_check(ctx):
        """轻量自检：核心文件 + 系统状态"""
        import subprocess
        hook_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        check_script = os.path.join(os.path.dirname(hook_dir), "scripts", "standing_orders_check.py") if os.path.basename(hook_dir) == "quality" else os.path.expanduser("~/.openclaw/workspace/scripts/standing_orders_check.py")
        if os.path.exists(check_script):
            r = subprocess.run(["python3", check_script, "--quiet"],
                               capture_output=True, text=True, timeout=5)
            if r.returncode != 0:
                return f"standing orders check failed: {r.stderr[:100] or r.stdout[:100]}"
            return "standing orders check passed"
        return "standing_orders_check.py not found, skipping"

    engine.register(Hook(
        "standing-orders",
        LockLevel.OPTIONAL,
        pre_fn=standing_orders_check
    ))

    # 4. 消息发送审计钩子 — 强制（对应事件: message:sent）
    def message_sent_audit(ctx):
        """记录所有外发消息到审计日志"""
        msg = str(ctx.get("message", ""))[:200]
        record = {
            "event": "message:sent",
            "timestamp": datetime.now(BEIJING_TZ).isoformat(),
            "channel": str(ctx.get("channel", "unknown")),
            "preview": msg[:100],
            "success": ctx.get("success", True),
        }
        with open(os.path.join(HOOK_DIR, "messages_sent.jsonl"), "a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return "message sent: logged"

    engine.register(Hook(
        "message-sent-audit",
        LockLevel.OPTIONAL,
        post_fn=message_sent_audit
    ))

    # 5. 定时任务审计钩子 — 可选（对应事件: cron:executed）
    def cron_executed_audit(ctx):
        """记录定时任务执行结果到审计日志"""
        task_name = str(ctx.get("task_name", ctx.get("name", "unknown")))
        task_status = str(ctx.get("status", ctx.get("result", "unknown")))
        record = {
            "event": "cron:executed",
            "timestamp": datetime.now(BEIJING_TZ).isoformat(),
            "task_name": task_name,
            "status": task_status,
            "duration_ms": ctx.get("duration_ms", 0),
            "error": str(ctx.get("error", ""))[:200],
        }
        with open(os.path.join(HOOK_DIR, "cron_executed.jsonl"), "a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return f"cron executed: {task_name} -> {task_status}"

    engine.register(Hook(
        "cron-executed-audit",
        LockLevel.OPTIONAL,
        post_fn=cron_executed_audit
    ))

    # Python 接口函数：供第三方脚本调用上报 cron 执行结果
    def report_cron_event(task_name: str, status: str, duration_ms: int = 0, error: str = ""):
        """外部脚本调用的 cron 事件上报入口"""
        ctx = {
            "task_name": task_name,
            "status": status,
            "duration_ms": duration_ms,
            "error": error,
        }
        return cron_executed_audit(ctx)

    def report_message_sent(channel: str, msg: str, success: bool = True):
        """外部调用的消息发送上报入口"""
        ctx = {
            "channel": channel,
            "message": msg,
            "success": success,
        }
        return message_sent_audit(ctx)

    # 挂载到 engine 上供外部调用
    engine.report_cron_event = report_cron_event
    engine.report_message_sent = report_message_sent

    # 5b. 实时信号评分钩子（inbound）— 可选
    _inbound_cooldown: Dict[str, float] = {}  # session_key → last_auto_save_time

    def inbound_signal_score(ctx):
        """对用户消息做实时信号评分，仅极高价值消息自动触发记忆保存，同 session 有冷却"""
        try:
            from core.engines.memory.auto_memory import AutoMemory
            text = ctx.get("content", "")
            action = ctx.get("action", "")
            session_key = ctx.get("session_key", "default")
            if not text or len(text.strip()) < 30 or action not in ("respond", "query"):
                return "ok"

            # 同 session 每天最多自动存 3 条，每次间隔至少 1 小时
            last_save = inbound_signal_score._inbound_cooldown.get(session_key, 0.0)
            if time.time() - last_save < 3600:
                return "ok"

            score = AutoMemory.score_message(text)
            # 阈值从 0.70 提高到 0.90，仅极高价值消息才自动保存
            if score["score"] >= 0.90:
                auto_mem = AutoMemory()
                auto_mem.save(
                    text=text,
                    tags=[score["tag"], "auto-signal"] if score["tag"] else ["auto-signal"],
                    scene="signal-scored",
                    metadata={"signal_score": score["score"],
                              "signal_label": score["label"],
                              "auto_captured": True}
                )
                inbound_signal_score._inbound_cooldown[session_key] = time.time()
                # 同 session 每天最多 3 次
                daily_key = f"{session_key}_{datetime.now(BEIJING_TZ).strftime('%Y%m%d')}"
                inbound_signal_score._inbound_cooldown[daily_key] = inbound_signal_score._inbound_cooldown.get(daily_key, 0) + 1
            return f"[signal] score={score['score']}, tag={score['tag']}"
        except Exception as e:
            return f"signal-score: {str(e)[:40]}"

    engine.register(Hook(
        "inbound-signal-score",
        LockLevel.OPTIONAL,
        pre_fn=inbound_signal_score
    ))

    # 5c. Guardrail 执行前拦截（inbound）— 可选
    def inbound_guardrail(ctx):
        """铁律守卫：执行前拦截"""
        try:
            from core.engines.quality.iron_rules import Guardrail
            text = ctx.get("content", "")
            if not text:
                return "ok"
            if any(kw in text for kw in ["core/", "engines/", "scripts/", ".json"]):
                if "修改" in text or "编辑" in text:
                    result = Guardrail.check("", {"action_type": "system-edit"})
                    if not result.allowed:
                        return f"[Guardrail] {result.reason}"
            return "ok"
        except Exception as e:
            return f"guardrail: {str(e)[:40]}"

    engine.register(Hook(
        "inbound-guardrail",
        LockLevel.OPTIONAL,
        pre_fn=inbound_guardrail
    ))

    # 6. 定时任务审计钩子 — 可选（对应事件: cron:executed）
    # 7. 审计追踪钩子 — 强制
    def audit_trail(ctx):
        with open(os.path.join(HOOK_DIR, "sentinel.log"), "a") as f:
            f.write(json.dumps({
                "timestamp": datetime.now(BEIJING_TZ).isoformat(),
                "action": ctx.get("action", "unknown"),
                "source": ctx.get("source", "unknown"),
            }) + "\n")
        return "audit logged"

    engine.register(Hook(
        "sentinel-audit",
        LockLevel.MANDATORY,
        post_fn=audit_trail
    ))

    # 8. 出站防幻觉钩子 — 可选（生成内容后做 full_check，之后可升 REQUIRED）
    def outbound_anti_fake_check(ctx):
        """出站防幻觉校验：对生成内容执行 full_check"""
        content = str(ctx.get("content", ctx.get("message", "")))
        sources = ctx.get("sources", [])

        if not content or len(content.strip()) < 20:
            return "skipped: content too short"

        try:
            from core.engines.quality.anti_fake_validator import AntiFakeValidator
            af = AntiFakeValidator()
            result = af.full_check(content, sources)
            risk = result.get("overall_risk", "low")

            if risk in ("high", "critical"):
                return f"⚠️ outbound anti-fake: {risk} risk — {len(result.get('warnings', []))} warnings"
            return f"outbound anti-fake: {risk} risk"
        except Exception as e:
            return f"outbound anti-fake error: {str(e)[:50]}"

    engine.register(Hook(
        "outbound-anti-fake",
        LockLevel.OPTIONAL,
        post_fn=outbound_anti_fake_check
    ))

    # ────────────────────────────────────────────────────
    # 6. 写作风格迭代学习 hook
    # ────────────────────────────────────────────────────
    WRITING_STYLE_FILE = os.path.join(
        os.environ.get("OPENCLAW_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")),
        ".writing_style.md"
    )

    def load_writing_style(ctx):
        """pre-hook: 执行写作任务前加载风格规则"""
        if not os.path.exists(WRITING_STYLE_FILE):
            return "writing_style: no style file yet"
        try:
            with open(WRITING_STYLE_FILE, "r", encoding="utf-8") as f:
                rules = f.read().strip()
            if rules:
                # 注入到上下文中供后续推理使用
                ctx["_writing_style_rules"] = rules
                return f"writing_style: loaded {len(rules)} chars"
            return "writing_style: empty style file"
        except Exception as e:
            return f"writing_style: load error - {str(e)[:60]}"

    def save_writing_draft_and_learn(ctx):
        """post-hook: 保存草稿+从diff提取新风格规则"""
        content = str(ctx.get("content", ctx.get("message", "")))
        user_input = str(ctx.get("user_input", ""))
        output_file = ctx.get("_writing_output_file", "")

        if not content or len(content.strip()) < 50:
            return "writing_style: skipped (content too short)"

        try:
            # 1. 保存草稿
            drafts_dir = os.path.join(
                os.path.dirname(WRITING_STYLE_FILE), ".writing_drafts"
            )
            os.makedirs(drafts_dir, exist_ok=True)
            draft_path = os.path.join(
                drafts_dir,
                f"draft_{datetime.now(BEIJING_TZ).strftime('%Y%m%d_%H%M%S')}.md"
            )
            with open(draft_path, "w", encoding="utf-8") as f:
                f.write(content)

            # 2. 如果有旧草稿，做 diff 分析
            existing_drafts = sorted([
                os.path.join(drafts_dir, d)
                for d in os.listdir(drafts_dir)
                if d.endswith(".md") and d != os.path.basename(draft_path)
            ])

            if existing_drafts and os.path.exists(WRITING_STYLE_FILE):
                # 读取旧草稿和新草稿，用简单的行级 diff
                with open(existing_drafts[-1], "r", encoding="utf-8") as f:
                    old_content = f.read()

                old_lines = old_content.split("\n")
                new_lines = content.split("\n")

                # 简单 diff：找新增的/变长的段落
                import difflib
                diff = list(difflib.unified_diff(
                    old_lines, new_lines,
                    n=2, lineterm=""
                ))

                # 从 diff 中提取风格特征
                style_rules = []
                additions = [l[2:] for l in diff if l.startswith("+") and not l.startswith("+++")]
                for line in additions:
                    line = line.strip()
                    if not line or len(line) < 10:
                        continue
                    # 检测常见的风格变化
                    if line.endswith("。") and "？" not in line and "！" not in line:
                        style_rules.append(f"- 使用句号结尾的陈述句风格（如：{line[:30]}…）")
                    if line.startswith("-"):
                        style_rules.append(f"- 使用列表/条目化表达")
                    if "你" in line or "我" in line:
                        style_rules.append(f"- 使用第一/二人称对话感（如：{line[:30]}…）")

                if style_rules:
                    # 读取现有规则
                    try:
                        with open(WRITING_STYLE_FILE, "r", encoding="utf-8") as f:
                            existing_rules = f.read()
                    except Exception:
                        existing_rules = ""

                    # 去重写入
                    new_rules = []
                    for sr in style_rules:
                        if sr not in existing_rules:
                            new_rules.append(sr)

                    if new_rules:
                        timestamp = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M")
                        with open(WRITING_STYLE_FILE, "a", encoding="utf-8") as f:
                            f.write(f"\n## [{timestamp}] 从用户修改中学习\n")
                            f.write("\n".join(new_rules) + "\n")
                        return f"writing_style: learned {len(new_rules)} new rules from diff"

            return f"writing_style: draft saved ({os.path.basename(draft_path)})"

        except Exception as e:
            return f"writing_style: error - {str(e)[:60]}"

    engine.register(Hook(
        "writing-style",
        LockLevel.OPTIONAL,
        pre_fn=load_writing_style,
        post_fn=save_writing_draft_and_learn
    ))

    # 13. R-CCAM 查询分类钩子 — 用户输入提前分流（OPTIONAL）
    def rccam_classifier_pre(ctx):
        try:
            from core.engines.quality.rccam_classifier_engine import RCCAMClassifierEngine
            engine = RCCAMClassifierEngine()
            return engine.pre_hook(ctx)
        except Exception as e:
            logger = __import__("logging").getLogger("rccam_classifier_engine")
            logger.warning(f"rccam_classifier 加载失败: {e}")
            return "rccam_classifier: skipped"

    engine.register(Hook(
        "rccam-classifier",
        LockLevel.OPTIONAL,
        pre_fn=rccam_classifier_pre
    ))

    # 14. 防幻觉守护钩子 — 输出验证（OPTIONAL）
    def hallucination_guard_post(ctx):
        try:
            from core.engines.quality.hallucination_guard_engine import HallucinationGuardEngine
            guard = HallucinationGuardEngine()
            content = str(ctx.get("content", ""))
            if len(content) > 20:
                result = guard.validate_output(content)
                if not result["passed"]:
                    ctx["hallucination_warning"] = result
                    return f"hallucination_guard: ⚠️ {len(result.get('issues', []))} issues (risk={result.get('risk_level','unknown')})"
                return f"hallucination_guard: ✅ passed (risk={result.get('risk_level','low')})"
            return "hallucination_guard: skipped (content too short)"
        except Exception as e:
            logger = __import__("logging").getLogger("hallucination_guard_engine")
            logger.warning(f"hallucination_guard 加载失败: {e}")
            return "hallucination_guard: skipped"

    engine.register(Hook(
        "hallucination-guard",
        LockLevel.OPTIONAL,
        post_fn=hallucination_guard_post
    ))

    return engine


# 测试
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

    engine = init_default_hooks()
    print("=== 已注册钩子 ===")
    for h in engine.get_hook_status():
        print(f"  {h['name']}: level={h['level']}, bypass={h['bypass_allowed']}")

    print("\n=== 测试MANDATORY钩子不可绕过 ===")
    ctx = {"content": "bypass this confirmation", "action": "test", "source": "test"}
    results = engine.run_pre_hooks(ctx)
    for r in results:
        status = "✅" if r.success else "❌"
        print(f"  {status} {r.hook_name}: {r.detail[:50]}")

    print("\n=== 正常执行 ===")
    ctx2 = {"content": "正常操作", "action": "normal", "source": "user"}
    results2 = engine.run_pre_hooks(ctx2)
    for r in results2:
        status = "✅" if r.success else "❌"
        print(f"  {status} {r.hook_name}: {r.detail[:50]}")

    print(f"\n=== 审计日志 ===")
    for log in engine.get_audit_log(5):
        print(f"  {log['hook_name']}: {'✅' if log['success'] else '❌'}")
