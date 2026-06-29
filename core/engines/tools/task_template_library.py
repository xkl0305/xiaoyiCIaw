"""
Crusheart Performance AutoBrain v4.3.2 — Task Template Library 任务模板库
功能：预置常见任务模板，含工具链编排、输出格式、质量检查清单
精简版：仅保留开发类模板（代码审查、问题排查、方案设计）
"""

import os, json
from datetime import datetime, timedelta, timezone

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
TEMPLATE_PATH = os.path.join(WORKSPACE, ".task_templates.json")

# ====================================================================
# 预置任务模板 — 仅保留开发类
# ====================================================================
BUILTIN_TEMPLATES = {

    # -----------------------------------------------
    # 1. 代码审查
    # -----------------------------------------------
    "code_review": {
        "name": "代码审查",
        "version": "1.0",
        "description": "审查代码文件，检查代码质量、安全性、性能和规范性",
        "category": "开发",
        "tags": ["code review", "代码审查", "质量检查", "代码检查", "审核代码", "review", "code", "review code", "审一下", "审查这段"],
        "pipeline": [
            {"tool": "read", "purpose": "读取待审查代码文件"},
            {"tool": "web_search", "purpose": "查找相关最佳实践"},
        ],
        "output_format": {
            "style": "结构化列表",
            "sections": ["总体评价", "问题分类(严重/中等/建议)", "安全风险", "性能建议", "规范性检查"],
            "max_length": 1000
        },
        "quality_checks": [
            "每个问题是否有行号或代码片段引用",
            "是否区分了严重程度",
            "建议是否具体可操作",
            "是否检查了安全漏洞（SQL注入/XSS/权限）"
        ],
        "example_prompt": "帮我审查这段代码，重点检查安全性和性能问题"
    },

    # -----------------------------------------------
    # 2. 问题排查
    # -----------------------------------------------
    "troubleshooting": {
        "name": "问题排查",
        "version": "1.0",
        "description": "系统化排查和诊断技术问题、错误、异常",
        "category": "开发",
        "tags": ["debug", "troubleshooting", "问题排查", "排错", "报错", "错误", "异常", "bug", "排查", "诊断", "故障", "error", "fix", "修复"],
        "pipeline": [
            {"tool": "read", "purpose": "读取错误日志/代码"},
            {"tool": "web_search", "purpose": "搜索类似问题和解决方案"},
            {"tool": "exec", "purpose": "执行诊断命令"},
        ],
        "output_format": {
            "style": "排查步骤 + 结论",
            "sections": ["问题描述", "排查过程", "根因分析", "解决方案", "预防措施"],
            "max_length": 1200
        },
        "quality_checks": [
            "是否复现了问题",
            "根因是否有证据支持",
            "解决方案是否验证过",
            "是否记录了排查路径供后续参考"
        ],
        "example_prompt": "帮我排查这个报错，找出根因并给出修复方案"
    },

    # -----------------------------------------------
    # 3. 技术方案设计
    # -----------------------------------------------
    "design_doc": {
        "name": "技术方案设计",
        "version": "1.0",
        "description": "编写技术方案设计文档，包含架构、技术选型、实施计划",
        "category": "开发",
        "tags": ["设计文档", "架构", "方案", "design", "技术方案", "架构设计", "方案设计", "技术选型", "系统设计"],
        "pipeline": [
            {"tool": "web_search", "purpose": "调研技术选型"},
            {"tool": "writing_assistant", "purpose": "撰写方案文档"},
        ],
        "output_format": {
            "style": "正式文档",
            "sections": ["背景与目标", "技术选型对比", "架构设计", "关键设计决策", "实施计划", "风险评估"],
            "max_length": 2000
        },
        "quality_checks": [
            "技术选型是否有对比依据",
            "架构图是否有文字说明",
            "实施计划是否含里程碑",
            "是否识别了风险点"
        ],
        "example_prompt": "帮我设计一个XX系统的技术方案"
    },
}


class TaskTemplateLibrary:
    """任务模板库"""

    def __init__(self):
        self._templates = {}
        self._load()

    def _load(self):
        """加载模板（内置 + 用户自定义）"""
        self._templates.update(BUILTIN_TEMPLATES)
        if os.path.exists(TEMPLATE_PATH):
            try:
                with open(TEMPLATE_PATH) as f:
                    custom = json.load(f)
                    self._templates.update(custom)
            except (json.JSONDecodeError, IOError):
                pass

    def _save_custom(self):
        custom = {k: v for k, v in self._templates.items() if k not in BUILTIN_TEMPLATES}
        os.makedirs(os.path.dirname(TEMPLATE_PATH), exist_ok=True)
        with open(TEMPLATE_PATH, "w") as f:
            json.dump(custom, f, indent=2, ensure_ascii=False)

    def list_templates(self, category: str = None) -> dict:
        if category:
            return {k: {"name": v["name"], "description": v["description"], "tags": v["tags"]}
                    for k, v in self._templates.items() if v.get("category") == category}
        return {k: {"name": v["name"], "description": v["description"], "tags": v["tags"]}
                for k, v in self._templates.items()}

    def get(self, template_id: str) -> dict:
        return self._templates.get(template_id)

    def add(self, template_id: str, template: dict) -> bool:
        if template_id in BUILTIN_TEMPLATES:
            return False
        self._templates[template_id] = template
        self._save_custom()
        return True

    def remove(self, template_id: str) -> bool:
        if template_id in BUILTIN_TEMPLATES:
            return False
        if template_id in self._templates:
            del self._templates[template_id]
            self._save_custom()
            return True
        return False

    def match(self, user_input: str) -> list:
        """根据用户输入匹配最适合的模板"""
        results = []
        user_lower = user_input.lower()
        for tid, tmpl in self._templates.items():
            score = 0

            # 名称匹配
            if tmpl["name"].lower() in user_lower:
                score += 10

            # 标签匹配
            for tag in tmpl.get("tags", []):
                if tag.lower() in user_lower:
                    score += 5

            # 描述关键词
            for word in tmpl["description"].split():
                if word.lower() in user_lower:
                    score += 1

            if score > 0:
                results.append({
                    "id": tid,
                    "name": tmpl["name"],
                    "score": score,
                    "category": tmpl.get("category", ""),
                    "description": tmpl["description"]
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:5]

    def categories(self) -> list:
        cats = set()
        for tmpl in self._templates.values():
            c = tmpl.get("category")
            if c:
                cats.add(c)
        return sorted(cats)

    def count(self) -> dict:
        return {
            "total": len(self._templates),
            "builtin": len(BUILTIN_TEMPLATES),
            "custom": len(self._templates) - len(BUILTIN_TEMPLATES),
            "categories": len(self.categories())
        }


_library = None


def get_library() -> TaskTemplateLibrary:
    global _library
    if _library is None:
        _library = TaskTemplateLibrary()
    return _library


def init():
    library = get_library()
    stats = library.count()
    result = {
        "status": "ready",
        "templates_total": stats["total"],
        "templates_builtin": stats["builtin"],
        "templates_custom": stats["custom"],
        "categories": stats["categories"],
        "available_templates": list(library.list_templates().keys()),
        "initialized_at": datetime.now(BEIJING_TZ).isoformat()
    }
    if stats["total"] > 0:
        print(f"  📋 Task Template Library: {stats['total']} 个模板（{stats['builtin']} 内置 + {stats['custom']} 自定义），{stats['categories']} 个分类")
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
    print("\n📝 匹配测试:")
    for query in ["审一下这段代码", "排查这个报错", "设计一个微服务架构", "帮我写日报"]:
        matches = get_library().match(query)
        top = matches[0]["name"] if matches else "无匹配"
        print(f"  '{query}' → {top}")
