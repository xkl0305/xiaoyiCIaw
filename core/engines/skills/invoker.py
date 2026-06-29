"""Crusheart Agent OS - SkillInvoker (v7.0 split)
"""
import os, sys, json, traceback, subprocess, logging
from typing import Dict, Optional, Any

class SkillInvoker:
    SKILL_INVOKE_MAP = {
        "auto_memory": {"type": "cli", "script": "scripts/auto_memory.py"},
        "auto_engines": {"type": "cli", "script": "scripts/auto_engines.py"},
        "web-search": {"type": "tool", "tool": "web-search"},
        "multi-search-engine": {"type": "tool", "tool": "web-search"},
        "zero-api-key-web-search": {"type": "tool", "tool": "web_fetch"},
        "amap-lbs-skill": {"type": "tool", "tool": "location"},
        "task-pusher": {"type": "tool", "tool": "task-pusher"},
        "imap-smtp-email": {"type": "tool", "tool": "email"},
        "meitu-skills": {"type": "tool", "tool": "meitu"},
        "tushare-finance": {"type": "tool", "tool": "finance"},
        "deep-search-and-insight-synthesize": {"type": "tool", "tool": "deep-search"},
        "seedream-image-gen": {"type": "tool", "tool": "image-gen"},
        "seedance-video-gen": {"type": "tool", "tool": "video-gen"},
        "baoyu-comic": {"type": "tool", "tool": "comic-gen"},
        "minimax-music-gen": {"type": "tool", "tool": "music-gen"},
        "minimax-pdf": {"type": "tool", "tool": "pdf-convert"},
        "tts": {"type": "tool", "tool": "tts"},
        "ppt-generator": {"type": "tool", "tool": "ppt"},
        "arxiv-search": {"type": "tool", "tool": "arxiv"},
        "daily-hot-news": {"type": "tool", "tool": "hot-news"},
        "daily-ai-news": {"type": "tool", "tool": "ai-news"},
    }

    FAST_MODE_TASKS = ["纯聊天", "简单确认", "简单评价", "状态查询", "配置调整"]

    def __init__(self):
        self._invoke_log = []

    def invoke(self, skill_name: str, task_text: str, params: dict = None) -> dict:
        entry = self.SKILL_INVOKE_MAP.get(skill_name)
        if not entry:
            result = {"skill": skill_name, "status": "agent", "method": "agent_manual",
                      "note": f"技能 '{skill_name}' 无预置映射，需 Agent 手动调用"}
            _record_skill_invocation(skill_name, "agent", task_text)
            return result
        method = entry["type"]
        if method == "cli":
            result = self._invoke_cli(entry["script"], task_text, params, skill_name)
            _record_skill_invocation(skill_name, result.get("status", "error"), task_text)
            return result
        elif method == "tool":
            result = self._invoke_tool(entry["tool"], task_text, params, skill_name)
            _record_skill_invocation(skill_name, result.get("status", "unknown"), task_text)
            return result
        result = {"skill": skill_name, "status": "unknown", "result": None, "error": f"未知调用方式: {method}"}
        _record_skill_invocation(skill_name, "unknown", task_text)
        return result

    def _invoke_cli(self, script, task_text, params, skill_name):
        import subprocess
        script_path = os.path.join(WORKSPACE, script)
        if not os.path.exists(script_path):
            return {"skill": skill_name, "status": "error", "method": "cli",
                    "error": f"脚本不存在: {script_path}"}
        try:
            result = subprocess.run([sys.executable, script_path] + (params.get("args", []) if params else []),
                                     capture_output=True, text=True, timeout=30, shell=False)
            return {"skill": skill_name, "status": "ok" if result.returncode == 0 else "error",
                    "result": result.stdout.strip()[:1000] if result.stdout else result.stderr.strip()[:500],
                    "method": "cli", "returncode": result.returncode,
                    "error": result.stderr.strip()[:500] if result.returncode != 0 else None}
        except subprocess.TimeoutExpired:
            return {"skill": skill_name, "status": "timeout", "method": "cli", "error": "执行超时(30s)"}
        except Exception as e:
            return {"skill": skill_name, "status": "error", "method": "cli", "error": str(e)[:200]}

    def _invoke_tool(self, tool_name, task_text, params, skill_name):
        """尝试调用工具（预留），当前返回 agent_tool 标记以待 Agent 调度"""
        return {"skill": skill_name, "status": "agent_tool", "method": "tool",
                "tool_name": tool_name, "task_text": task_text,
                "params": params or {}, "note": f"需 Agent 调用工具 '{tool_name}'"}

    def invoke_batch(self, analysis: dict, task_text: str) -> list:
        necessity = analysis.get("necessity_assessment", {})
        assessment = necessity.get("assessment", "optional")
        recommended = analysis.get("recommended_skills", [])
        required_skills = necessity.get("required_skills", [])
        if assessment == "autonomous":
            return []
        to_invoke = set()
        for sname in required_skills:
            to_invoke.add(sname)
        if assessment == "required":
            for s in recommended:
                to_invoke.add(s["name"])
        elif assessment == "optional":
            for s in recommended:
                if s["score"] >= 0.7:
                    to_invoke.add(s["name"])
        results = []
        for sname in to_invoke:
            r = self.invoke(sname, task_text)
            self._invoke_log.append(r)
            results.append(r)
        return results

    def get_agent_tasks(self, batch_results):
        return [r for r in batch_results if r.get("status") == "agent_tool"]
    def get_completed(self, batch_results):
        return [r for r in batch_results if r.get("status") == "ok"]
    def get_errors(self, batch_results):
        return [r for r in batch_results if r.get("status") in ("error", "timeout")]
    def get_unmapped(self, batch_results):
        return [r for r in batch_results if r.get("status") == "agent"]
    def summary(self, batch_results):
        return {"total": len(batch_results), "completed": len(self.get_completed(batch_results)),
                "agent_tool": len(self.get_agent_tasks(batch_results)),
                "agent_manual": len(self.get_unmapped(batch_results)),
                "errors": len(self.get_errors(batch_results))}


# ════════════════════════════════════════════════════════════════
# CLI 入口
# ════════════════════════════════════════════════════════════════
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

    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "scan"
    if mode == "scan":
        s = SkillScanner()
        s.run_cli(sys.argv[2:])
    elif mode == "analyze":
        r = SkillRouter()
        text = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "测试任务"
        result = r.analyze_task(text)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif mode == "invoke":
        i = SkillInvoker()
        if len(sys.argv) > 2:
            r = i.invoke(sys.argv[2], " ".join(sys.argv[3:]))
            print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print("用法: python skill_engine.py [scan|analyze|invoke] [...args]")
        print("  scan     — 扫描技能目录（默认）")
        print("  analyze  — 分析任务文本")
        print("  invoke   — 调用指定技能")
