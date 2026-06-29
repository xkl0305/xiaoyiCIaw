"""Crusheart Agent OS - SkillRouter (v7.0 split)
"""
from core.engines.skills._common import _record_skill_invocation, now_str, WORKSPACE, SKILLS_DIR, SKILL_INDEX_FILE, CATEGORY_KEYWORDS
import os, re, json, math, hashlib, logging
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Any

class SkillRouter:
    def __init__(self, skill_dir=SKILLS_DIR):
        self.skill_dir = skill_dir
        self.skill_index = {}
        self.name_to_keywords = {}
        self.keyword_to_skills = {}
        self.category_index = {c: [] for c in CATEGORY_KEYWORDS}
        self._loaded = False
        self._merge_config_categories()
        self._auto_load()

    def _merge_config_categories(self):
        config_path = os.path.join(self.skill_dir, "..", "openclaw.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, encoding="utf-8") as f:
                    cfg = json.load(f)
                extra = cfg.get("skill_categories", {})
                if extra and isinstance(extra, dict):
                    for cat, kws in extra.items():
                        if cat not in self.category_index:
                            self.category_index[cat] = []
                        self.category_keywords.setdefault(cat, kws)
            except Exception:
                logging.exception("[skill_engine.py] suppressed")

    def _auto_load(self):
        if os.path.exists(SKILL_INDEX_FILE):
            try:
                with open(SKILL_INDEX_FILE, encoding="utf-8") as f:
                    d = json.load(f)
                self.skill_index = d.get("index", {})
                self.category_index = d.get("categories", {})
                self._loaded = True
                return
            except Exception:
                logging.exception("[skill_engine.py] suppressed")
        self.scan()

    def _save_index(self):
        d = {"index": self.skill_index, "keywords": self.name_to_keywords,
             "reverse": self.keyword_to_skills, "categories": self.category_index,
             "updated_at": now_str()}
        os.makedirs(os.path.dirname(SKILL_INDEX_FILE), exist_ok=True)
        tmp = SKILL_INDEX_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        os.replace(tmp, SKILL_INDEX_FILE)  # 原子替换

    def _parse_skill(self, name, path):
        info = {"name": name, "path": path, "description": "", "keywords": []}
        meta_path = os.path.join(path, "_meta.json")
        if os.path.exists(meta_path):
            try:
                with open(meta_path, encoding="utf-8") as f:
                    meta = json.load(f)
                info["version"] = meta.get("version","")
                info["author"] = meta.get("author","")
                info["description"] = meta.get("description","")
            except Exception:
                logging.exception("[skill_engine.py] suppressed")
        smd = os.path.join(path, "SKILL.md")
        if os.path.exists(smd):
            try:
                with open(smd, encoding="utf-8") as f:
                    content = f.read()
                dm = re.search(r'description:\s*"([^"]+)"', content)
                if dm and not info["description"]: info["description"] = dm.group(1)
                lines = content.split("\n")
                for line in lines[:40]:
                    if line.startswith("# ") and len(line)>2:
                        info.setdefault("title", line.strip("# ").strip())
                    funcs = re.findall(r'`(\w+)`', line)
                    for f in funcs:
                        if len(f) > 3 and f not in info["keywords"]: info["keywords"].append(f)
                text_only = re.sub(r'[#*`>\\-\\|\\[\\]\\(\\)]', ' ', content)
                words = re.findall(r'[一-鿿]{2,}', text_only)
                for w, c in Counter(words).most_common(5):
                    if c >= 3 and w not in info["keywords"]: info["keywords"].append(w)
            except Exception:
                logging.exception("[skill_engine.py] suppressed")
        info["keywords"] = list(set(info["keywords"]))
        return info

    def _categorize(self, name, desc, keywords):
        text = (name + " " + desc + " " + " ".join(keywords)).lower()
        matched = []
        for cat, kws in CATEGORY_KEYWORDS.items():
            for kw in kws:
                if kw.lower() in text: matched.append(cat); break
        return matched

    def scan(self):
        scanner = SkillScanner(self.skill_dir)
        count = scanner.scan()
        self.skill_index = scanner.skill_index
        self.category_index = getattr(scanner, 'category_index', {})
        self._loaded = True
        return count

    SKILL_EXTERNAL_DEPENDENCY = {
        "搜索/查询类": ["web-search", "multi-search-engine", "zero-api-key-web-search",
                        "deep-search-and-insight-synthesize", "arxiv-search",
                        "daily-ai-news", "daily-hot-news", "daily-tech-broadcast",
                        "news-extractor", "tencent-news", "baoyu-url-to-markdown"],
        "天气/位置类": ["amap-lbs-skill", "amap-jsapi-skill"],
        "图像生成类": ["seedream-image-gen", "claw-art", "baoyu-comic"],
        "视频生成类": ["seedance-video-gen", "remotion-video-toolkit", "video-generation-skill"],
        "音频/语音类": ["minimax-music-gen", "minimax-audio-gen", "tts", "voice-synthesis", "speech-to-text", "podcast-gen", "vlog-gen"],
        "翻译类": ["image-translation"],
        "金融/数据类": ["eastmoney-mx-skills-suite", "tushare-finance", "hithink-iwencai",
                        "gtht-financialsearch-skill", "gtht-realtimemarketdata-skill",
                        "gtht-ranklist-skill", "gtht-smartstockselection-skill",
                        "jrj-quote-skill", "stock-daily-analysis-pro", "trader-simulator",
                        "trading-quant", "alphaear-predictor", "alphaear-sentiment",
                        "alphaear-signal-tracker", "alphaear-news"],
        "出行/生活类": ["didi-ride-skill", "flyai-travel", "meituan-coupon-get-tool"],
        "文档/转换类": ["minimax-pdf", "pdf-toolkit-pro", "markitdown", "ppt-generator", "openmaic", "good-txt-to-hwreader"],
        "邮件/通知类": ["imap-smtp-email", "task-pusher"],
        "设备/手机类": ["gui-agent", "browser-control", "headed-browser-open-v3", "meitu-skills"],
        "写作/创作类": ["ai-writing-agent", "article-writing", "general-writing", "news-writing", "copywriter", "video-script-creator"],
        "学术/论文类": ["article-writer", "read-arxiv-paper", "arxiv-search", "deep-search-and-insight-synthesize", "su-lan-paper-daily-skill", "affaan-m-everything-claude-code-article-writing"],
        "教育类": ["k12-smart-teacher", "math-edu-assistant", "educational-video-creator", "fenbi"],
    }

    AUTONOMOUS_CAPABLE_PATTERNS = {
        "纯聊天": ["嗨", "哈喽", "你好", "在吗", "吃了没", "干嘛呢", "睡没", "早", "晚好"],
        "简单确认": ["好的", "可以", "OK", "收到", "知道", "明白", "666", "确实"],
        "简单评价": ["好看", "好听", "不错", "还行", "6", "绝了", "喜欢", "可以啊"],
        "状态查询": ["查看", "看看", "显示", "打开", "展示", "列出", "我的", "当前"],
        "配置调整": ["切换", "设置", "修改", "改成", "配置", "安装", "更新", "升级"],
    }

    def _has_external_skill_match(self, sname):
        for cat, names in self.SKILL_EXTERNAL_DEPENDENCY.items():
            if sname in names: return True
            for n in names:
                if n in sname or sname in n: return True
        return False

    def _estimate_skill_necessity(self, task_text, matched_skills):
        text = task_text.lower()
        for cat, patterns in self.AUTONOMOUS_CAPABLE_PATTERNS.items():
            for pat in patterns:
                if pat.lower() in text and not any(kw in text for kw in
                    ["写", "创建", "生成", "分析", "比较", "排查", "修复", "部署", "实现", "设计", "开发"]):
                    return {"assessment": "autonomous", "reason": f"'{cat}'类型，无需调用技能",
                            "necessity_score": 0.0, "required_skills": [], "optional_skills": []}
        text_len = len(text)
        has_task_kw = any(kw in text for kw in ["写", "创建", "生成", "制作", "搞一个", "做一个",
            "分析", "比较", "对比", "评估", "判断", "诊断", "排查", "检查", "审核", "总结",
            "归纳", "提炼", "安装", "配置", "部署", "迁移", "清理", "优化", "修复", "实现",
            "设计", "开发", "编码"])
        if not has_task_kw and text_len < 30:
            return {"assessment": "optional", "reason": "简单查询，技能可选",
                    "necessity_score": 0.2, "required_skills": [],
                    "optional_skills": [s["name"] for s in matched_skills[:3]]}
        has_external_needed = False
        optional_skills, required_skills = [], []
        for s in matched_skills:
            if self._has_external_skill_match(s["name"]):
                required_skills.append(s["name"])
                has_external_needed = True
            else:
                optional_skills.append(s["name"])
        needs_external = any(kw in text for kw in ["天气","气温","下雨","股价","股票","行情",
            "路线","导航","外卖","航班","机票","翻译","图片","音频","音乐","视频",
            "邮件","发送","手机","签到","搜索","查一下","搜一下"])
        if has_external_needed and needs_external:
            return {"assessment": "required", "reason": "任务需要外部数据/API",
                    "necessity_score": 1.0, "required_skills": required_skills,
                    "optional_skills": optional_skills}
        if has_task_kw:
            return {"assessment": "optional", "reason": "深度任务，技能可提升效率",
                    "necessity_score": 0.7, "required_skills": required_skills,
                    "optional_skills": [s["name"] for s in matched_skills[:5]]}
        return {"assessment": "optional", "reason": "未明确需要外部数据",
                "necessity_score": 0.3, "required_skills": required_skills,
                "optional_skills": optional_skills}

    def analyze_task(self, task_text):
        if not self._loaded:
            try:
                with open(SKILL_INDEX_FILE, encoding="utf-8") as f:
                    d = json.load(f)
                self.skill_index = d.get("index", {})
                self.category_index = d.get("categories", {})
                self._loaded = True
            except Exception:
                logging.exception("[skill_engine.py] suppressed")
        if not self.skill_index:
            return {"matched_categories": [], "recommended_skills": [], "task_type": "fast",
                    "all_categories": {}, "skill_count": 0}
        text = task_text.lower()
        matched_cats = [cat for cat, kws in CATEGORY_KEYWORDS.items() for kw in kws if kw.lower() in text]
        skill_scores = []
        for sname, sinfo in self.skill_index.items():
            score = 0.0; reasons = []
            if sname.lower() in text or any(w in sname.lower() for w in text.split()):
                score += 0.4; reasons.append("名称匹配")
            for kw in sinfo.get("keywords", []):
                if kw.lower() in text: score += 0.3; reasons.append(f"关键词'{kw}'"); break
            cats = self._categorize(sname, sinfo.get("description",""), sinfo.get("keywords",[]))
            for cat in cats:
                if cat in matched_cats: score += 0.2; reasons.append(f"分类'{cat}'"); break
            if any(w in sinfo.get("description","").lower() for w in text.split()):
                score += 0.1; reasons.append("描述匹配")
            if score > 0:
                skill_scores.append({"name": sname, "score": round(score,2),
                                     "reason": "; ".join(reasons[:2])})
        skill_scores.sort(key=lambda x: x["score"], reverse=True)
        task_type = "agent" if any(kw in text for kw in
            ["写","创建","生成","分析","比较","排查","修复","部署","实现","设计","开发"]) else "fast"
        necessity = self._estimate_skill_necessity(task_text, skill_scores[:10])
        return {"matched_categories": list(set(matched_cats)),
                "recommended_skills": skill_scores[:5], "task_type": task_type,
                "all_categories": {c: len(self.category_index.get(c,[])) for c in CATEGORY_KEYWORDS},
                "skill_count": len(self.skill_index),
                "necessity_assessment": necessity}

    def get_category_summary(self):
        return {c: len(self.category_index.get(c,[])) for c in CATEGORY_KEYWORDS}

    def get_all_skills_count(self):
        if not self._loaded:
            try:
                with open(SKILL_INDEX_FILE, encoding="utf-8") as f:
                    d = json.load(f)
                self.skill_index = d.get("index", {})
                self._loaded = True
            except Exception:
                logging.exception("[skill_engine.py] suppressed")
        return len(self.skill_index)


# ════════════════════════════════════════════════════════════════
# 引擎3: SkillInvoker — 技能自动调用 (原名 SkillAutoInvoker)
# ════════════════════════════════════════════════════════════════

