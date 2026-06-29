"""
Crusheart Agent OS — Orchestrator v4.2
全引擎编排路由，前置/后置/完成全链路 + Trace Timeline 追踪
v4.2: 使用 EngineFactory 统一获取 engines.json 配置，移除硬编码 ENGINE_REGISTRY
"""

import os, sys, json
from datetime import datetime, timezone, timedelta

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
if WORKSPACE not in sys.path: sys.path.insert(0, WORKSPACE)


class Orchestrator:
    """引擎编排路由 — 前置/后置/完成后处理 + Trace Timeline 追踪

    ENGINE_REGISTRY 不再硬编码，统一通过 EngineFactory 从 engines.json 获取。
    兼容旧代码直接访问 ENGINE_REGISTRY 的场景。
    """

    _trace = None  # TraceTimeline 实例

    # ── 静态 getter：统一通过 EngineFactory 加载 ──
    @staticmethod
    def _get_factory():
        from core.engines.init.engine_factory import EngineFactory
        return EngineFactory()

    # ── 向后兼容：ENGINE_REGISTRY 仍可通过类名访问（从 EngineFactory 获取元数据） ──
    @classmethod
    def _build_registry(cls):
        """从 EngineFactory 动态构建 ENGINE_REGISTRY"""
        factory = cls._get_factory()
        descs = factory.get_descriptions()
        registry = []
        for name, desc in descs.items():
            if not desc.enabled:
                continue
            registry.append((
                name,
                desc.module,
                desc.class_name,
                desc.description or name,
            ))
        return registry

    ENGINE_REGISTRY = None  # 首次访问时懒加载

    @classmethod
    def _get_engine_registry(cls):
        if cls.ENGINE_REGISTRY is None:
            cls.ENGINE_REGISTRY = cls._build_registry()
        return cls.ENGINE_REGISTRY

    def __init__(self):
        self._engines = self._check()
        self._profile = {}
        self._trace_summary = {}
        try:
            from core.engines.tools.trace_timeline import TraceTimeline
            self._trace = TraceTimeline()
        except ImportError:
            self._trace = None

    def _check(self) -> dict:
        """通过 EngineFactory 检查所有引擎状态"""
        factory = self._get_factory()
        r = {}
        for name, desc in factory.get_descriptions().items():
            if not desc.enabled:
                continue
            r[name] = factory._import_check.get(name, False)
        return r

    def _get_engine_status_summary(self) -> str:
        """返回引擎可用摘要"""
        available = [k for k, v in self._engines.items() if v]
        unavailable = [k for k, v in self._engines.items() if not v]
        parts = [f"✓{len(available)}可用"]
        if unavailable:
            parts.append(f"✗{len(unavailable)}不可用:{','.join(unavailable)}")
        return " ".join(parts)

    def _maybe_enter(self, stage: str, detail: str = ""):
        """条件性 trace enter（trace 可用时）"""
        if self._trace:
            self._trace.enter(stage, detail)

    def _maybe_exit(self, stage: str, result_info: str = "") -> int:
        """条件性 trace exit，返回耗时 ms"""
        if self._trace:
            return self._trace.exit(stage, result_info)
        return 0

    def finalize(self, pipeline_result: dict) -> dict:
        """收尾：生成 profile 快照 + 写入 trace"""
        if self._trace:
            self._profile = self._trace.snapshot()
            pipeline_result["_profile"] = self._profile
            self._trace.flush(pipeline_result)
            total_ms = sum(
                v for v in self._profile.values()
                if isinstance(v, (int, float))
            )
            self._trace_summary = {
                "total_ms": total_ms,
                "logged": True,
                "events": len(self._profile),
            }
        else:
            pipeline_result["_profile"] = {}
            self._trace_summary = {"total_ms": 0, "logged": False}
        return self._trace_summary

    def pre_process(self, task_text: str, dual_mode_result: dict = None) -> dict:
        """前置处理：路由预分析"""
        self._maybe_enter("pre_process", f"task_len={len(task_text)}")
        needs_anti_fake = bool(self._engines.get("anti_fake"))
        mode = "fast"
        if dual_mode_result and isinstance(dual_mode_result, dict):
            mode = dual_mode_result.get("mode", "fast")

        result = {
            "mode": mode,
            "needs_anti_fake": needs_anti_fake,
            "engines_available": self._engines,
            "engine_summary": self._get_engine_status_summary(),
            "has_goal_compiler": self._engines.get("goal_compiler", False),
            "has_unified_judge": self._engines.get("unified_judge", False),
            "has_autonomy": self._engines.get("autonomy_cycle", False),
        }
        self._maybe_exit("pre_process", mode)
        return result

    def compile_goal(self, task_text: str, context: dict = None) -> dict:
        """目标编译（Agent 模式用）"""
        self._maybe_enter("compile_goal")
        try:
            from core.engines.workflow.engine_orchestrator import GoalCompiler
            contract = GoalCompiler().compile(task_text, context or {})
            self._maybe_exit("compile_goal", "ok")
            return {"ok": True, "contract": contract.to_dict()}
        except Exception as e:
            self._maybe_exit("compile_goal", f"error={str(e)[:50]}")
            return {"ok": False, "error": str(e)[:200]}

    def judge_action(self, action: dict, user_profile: dict = None,
                     runtime: dict = None) -> dict:
        """仲裁决策"""
        self._maybe_enter("judge_action", f"action_type={action.get('type','?')}")
        if not self._engines.get("unified_judge"):
            self._maybe_exit("judge_action", "unavailable")
            return {"decision": "allow", "note": "unified_judge 不可用"}
        try:
            from core.engines.quality.unified_judge import UnifiedJudge
            decision = UnifiedJudge().decide(action, user_profile or {},
                                             runtime or {})
            r = decision.to_dict() if hasattr(decision, 'to_dict') else {"decision": str(decision)}
            self._maybe_exit("judge_action", r.get("decision", "?"))
            return r
        except Exception as e:
            self._maybe_exit("judge_action", f"error={str(e)[:50]}")
            return {"decision": "require_approval",
                    "note": f"仲裁异常，降级为需要审批: {str(e)[:100]}"}

    def post_process(self, content: str, sources: list = None,
                    task_context: dict = None) -> dict:
        """后置处理：防幻觉校验 + 闭环验证

        Args:
            content: 模型回答内容
            sources: 引用的来源列表
            task_context: 可选的任务上下文，提供后走完整 run_verification_loop
                格式: {"goal": str, "steps": list, "start_time": str,
                       "end_time": str, "query": str, "response": str}
        """
        self._maybe_enter("post_process")
        from datetime import datetime, timezone, timedelta

        result = {"safe": True, "risk_level": "low", "verified": False,
                  "note": "", "verification": {}, "recovery": None}

        if self._engines.get("anti_fake"):
            try:
                from core.engines.quality.anti_fake_validator import AntiFakeValidator
                r = AntiFakeValidator().full_check(content, sources or [])
                if isinstance(r, dict):
                    rl = r.get("overall_risk", "low")
                    result["safe"] = rl not in ("high", "critical")
                    result["risk_level"] = rl
                    result["verification"] = {
                        "citation_precision": r.get("citation_analysis", {}).get("citation_precision", 0),
                        "unreferenced_claims": r.get("citation_analysis", {}).get("claims_without_citation", 0),
                        "warnings": r.get("citation_analysis", {}).get("warnings", []),
                    }
                    if rl == "high":
                        result["note"] = "防幻觉风险高，建议核实"
                        result["safe"] = False
            except Exception as e:
                result["note"] = f"防幻觉降级: {str(e)[:50]}"

        if self._engines.get("closed_loop"):
            try:
                from core.engines.quality.closed_loop import ClosedLoopEngine
                engine = ClosedLoopEngine()

                if task_context:
                    # 完整闭环：验证→审计→恢复→自评分
                    summary = engine.run_verification_loop(
                        goal=task_context.get("goal", ""),
                        steps=task_context.get("steps", []),
                        start_time=task_context.get("start_time",
                            datetime.now(BEIJING_TZ).isoformat()),
                        end_time=task_context.get("end_time",
                            datetime.now(BEIJING_TZ).isoformat()),
                        query=task_context.get("query", ""),
                        response=task_context.get("response", content),
                    )
                    result["verified"] = summary.success
                    result["summary"] = {
                        "total_steps": summary.total_steps,
                        "completed": summary.completed_steps,
                        "failed": summary.failed_steps,
                        "elapsed": summary.elapsed_seconds,
                        "message": summary.message,
                    }
                    result["recovery"] = [
                        s.get("recovery") for s in (task_context.get("steps") or [])
                        if s.get("recovery")
                    ]
                else:
                    # 兼容：简单验证
                    vr = engine.quick_verify({
                        "success": True, "status": "completed"
                    })
                    result["verified"] = getattr(vr, 'verified', False)
            except Exception:
                pass

        self._maybe_exit("post_process", f"safe={result['safe']},risk={result['risk_level']}")
        return result

    def finish_process(self, task_info: dict,
                      post_result: dict = None) -> dict:
        """完成后处理：自进化评估 + 上下文胶囊更新

        Args:
            task_info: 任务信息字典
            post_result: post_process 的返回结果（含 recovery 信息）
        """
        self._maybe_enter("finish_process")
        result = {"should_evolve": False, "priority": "low", "reason": "无明显价值"}

        if self._engines.get("self_evolution"):
            try:
                from core.engines.hooks.self_evolution_v3 import SelfEvolutionEngine
                eng = SelfEvolutionEngine()
                content = task_info.get("content", "")
                tools = task_info.get("tool_calls", task_info.get("tools_used", []))
                has_complex = len(tools) >= 2 if isinstance(tools, list) else False
                has_error = bool(task_info.get("error", ""))
                user_corrected = any(
                    kw in content for kw in getattr(eng, 'HIGH_TRIGGER_KEYWORDS', [])
                ) if content else False
                if user_corrected:
                    result = {"should_evolve": True, "priority": "high", "reason": "用户纠正"}
                elif has_error and has_complex:
                    result = {"should_evolve": True, "priority": "medium", "reason": "排错经验"}
                elif has_complex:
                    result = {"should_evolve": True, "priority": "low", "reason": "复杂任务完成"}
            except Exception:
                pass

        if self._engines.get("session_manager"):
            try:
                from engines.init.session_manager import ContextCapsuleManager
                ccm = ContextCapsuleManager()
                ccm.increment_interaction()
                if task_info.get("content"):
                    ccm.record_event("task_completed" if not task_info.get("error") else "task_failed",
                                     task_info["content"][:200])
            except Exception:
                pass

        self._maybe_exit("finish_process", result.get("priority", "low"))
        return result

    def record_blocker(self, blocker: str):
        """记录阻塞项到上下文胶囊"""
        if self._engines.get("session_manager"):
            try:
                from engines.init.session_manager import ContextCapsuleManager
                ContextCapsuleManager().record_blocker(blocker)
            except Exception:
                pass

    def status(self) -> dict:
        """路由状态概览"""
        # 能力健康检查
        try:
            from core.engines.quality.capability_probe import capability_health
            capability_info = capability_health()
        except Exception:
            capability_info = {'overall': 'unchecked', 'error': 'capability_probe not available'}

        return {
            'capability_health': capability_info,
            "engines_available": self._engines,
            "engine_summary": self._get_engine_status_summary(),
            "registered_count": len(self._get_engine_registry()),
            "available_count": sum(1 for v in self._engines.values() if v),
            "stages": {
                "pre_process": "双模式分类器+关键词",
                "compile_goal": "可用",
                "judge_action": "可用" if self._engines.get("unified_judge") else "未注册",
                "post_process": "可用" if self._engines.get("anti_fake") else "跳过(降级)",
                "closed_loop_verify": "可用" if self._engines.get("closed_loop") else "未注册",
                "finish_process": "可用" if self._engines.get("self_evolution") else "跳过(降级)",
                "session_manager": "可用" if self._engines.get("session_manager") else "未注册",
                "trace_timeline": "可用" if self._trace else "未加载",
                "finalize": "可用",
            },
        }


# ================================================================
# GoalContract — 结构化目标契约（原 goal_compiler.py 并入）
# ================================================================

from typing import List, Dict, Any, Optional as _Optional
from dataclasses import dataclass, asdict
from hashlib import sha256
import re


@dataclass
class GoalContract:
    """结构化目标契约"""
    goal_id: str
    raw_request: str
    objective: str
    objective_tree: List[Dict]
    constraints: List[str]
    priority: str
    time_scope: str
    risk_boundary: str
    information_sources: List[str]
    automatic_parts: List[str]
    approval_points: List[str]
    done_definition: List[str]
    created_at: str

    def to_dict(self) -> Dict:
        return asdict(self)

    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

from core.engines.memory.exec_logger import log_execution

class GoalCompiler:
    """将自然语言请求编译为结构化 GoalContract"""

    INTENT_KEYWORDS = {
        "remind": ["提醒", "记得", "别忘了", "通知我"],
        "schedule": ["日程", "安排", "预约", "会议", "日历"],
        "notify": ["通知", "推送", "发消息", "告诉"],
        "query": ["查询", "看看", "帮我查", "搜索", "查一下", "搜"],
        "automate": ["自动", "操作", "执行", "搞", "弄", "做"],
        "create": ["创建", "新建", "添加", "写", "生成", "制作"],
        "delete": ["删除", "移除", "取消", "清空"],
        "update": ["更新", "修改", "更改", "改"],
    }

    RISK_MAP = {
        "send": ["发送", "发给", "send", "短信", "邮件"],
        "money": ["付款", "支付", "转账", "购买", "买"],
        "delete": ["删除", "清空", "覆盖", "卸"],
        "install": ["安装", "pip install", "npm install"],
        "external": ["外部", "第三方", "api", "mcp", "connector"],
    }

    APPROVAL_MAP = {
        "send": "before_external_message",
        "money": "before_payment",
        "delete": "before_destructive_mutation",
        "install": "before_new_code",
        "external": "before_external_connector",
    }

    def compile(self, text: str, context: _Optional[Dict] = None) -> GoalContract:
        """编译目标"""
        if not text or not text.strip():
            raise ValueError("empty goal")
        context = context or {}
        t = ' '.join(text.strip().split())
        gid = 'goal_' + sha256(t.encode()).hexdigest()[:16]

        risks = self._detect_risks(t)
        approval_points = self._get_approvals(risks)
        tree = self._decompose_tree(t)

        risk_set = set(risks)
        if {'money', 'delete', 'install'} & risk_set:
            rb = 'L4_requires_explicit_approval'
        elif {'send', 'external'} & risk_set:
            rb = 'L3_requires_review_or_confirm'
        else:
            rb = 'L1_auto_allowed_with_audit'

        return GoalContract(
            goal_id=gid,
            raw_request=t,
            objective=re.sub(r'^(帮我|给我|请|please)\s*', '', t).strip('。.! '),
            objective_tree=tree,
            constraints=self._extract_constraints(t, context),
            priority=self._determine_priority(t, rb),
            time_scope=self._determine_time(t, context),
            risk_boundary=rb,
            information_sources=self._detect_sources(t),
            automatic_parts=self._determine_auto(rb, tree),
            approval_points=approval_points,
            done_definition=['all_task_nodes_terminal',
                             'result_verified_against_goal',
                             'memory_writeback_done'],
            created_at=datetime.now(BEIJING_TZ).isoformat(),
        )

    def _has(self, text: str, words: List[str]) -> bool:
        return any(w.lower() in text.lower() for w in words)

    def _detect_risks(self, text: str) -> List[str]:
        return [k for k, v in self.RISK_MAP.items() if self._has(text, v)] or ["low"]

    def _get_approvals(self, risks: List[str]) -> List[str]:
        return [self.APPROVAL_MAP[r] for r in risks if r in self.APPROVAL_MAP]

    def _decompose_tree(self, text: str) -> List[Dict]:
        parts = [p.strip(' 。.!？?') for p in re.split(
            r'，|,|；|;|然后|再|并且|以及|and|then', text) if p.strip(' 。.!？?')]
        return [{'node_id': f'g{i+1}', 'title': p,
                 'depends_on': [] if i == 0 else [f'g{i}'],
                 'status': 'planned'}
                for i, p in enumerate(parts[:12] or [text])]

    def _extract_constraints(self, text: str, context: Dict) -> List[str]:
        out = ['preserve_existing_behavior', 'audit_all_side_effects']
        if '不要' in text or '不能' in text:
            out.append('respect_negative_constraints')
        if context.get('no_external'):
            out.append('no_external_connectors')
        return out

    def _determine_priority(self, text: str, rb: str) -> str:
        if self._has(text, ['马上', '立刻', '紧急', 'urgent']):
            return 'high'
        return 'controlled' if rb.startswith('L4') else 'normal'

    def _determine_time(self, text: str, context: Dict) -> str:
        if context.get('time_scope'):
            return context['time_scope']
        for k, ws in [('today', ['今天', 'today']),
                      ('tomorrow', ['明天']),
                      ('week', ['本周', '下周', 'week']),
                      ('month', ['本月', '下月'])]:
            if self._has(text, ws):
                return k
        return 'unspecified'

    def _detect_sources(self, text: str) -> List[str]:
        sources = []
        if self._has(text, ['邮件', '邮箱', 'email']):
            sources.append('email')
        if self._has(text, ['日程', '会议', 'calendar']):
            sources.append('calendar')
        if self._has(text, ['文件', '文档', 'pdf', 'zip']):
            sources.append('files')
        if self._has(text, ['网页', '搜索', '查', '最新', '官网']):
            sources.append('web_or_knowledge')
        return sources or ['conversation_context']

    def _determine_auto(self, rb: str, tree: List[Dict]) -> List[str]:
        node_ids = [n['node_id'] for n in tree]
        if rb.startswith('L1'):
            return node_ids
        if rb.startswith('L4'):
            return ['analysis_and_draft_only']
        return node_ids[:-1] if len(node_ids) > 1 else ['prepare_draft_only']
