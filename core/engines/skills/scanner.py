"""Crusheart Agent OS - SkillScanner (v7.0 split)
"""
from core.engines.skills._common import _record_skill_invocation, now_str, BEIJING_TZ, WORKSPACE, SKILLS_DIR, SKILL_INDEX_FILE, CATEGORY_KEYWORDS
import os, re, json, math, hashlib, logging
from datetime import datetime, timezone, timedelta
from collections import Counter, defaultdict

class SkillScanner:
    """技能扫描引擎：全量扫描 skills/ 目录，输出索引 JSON 和结构化统计"""

    CATEGORY_KEYWORDS = CATEGORY_KEYWORDS.copy()

    def __init__(self, skill_dir=SKILLS_DIR):
        self.skill_dir = skill_dir
        self.skill_index = {}
        self.category_index = {c: [] for c in CATEGORY_KEYWORDS}
        self._loaded = False

    def _merge_config_categories(self):
        """从 config.json 读取自定义分类"""
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

    def _parse_skill(self, name: str, path: str) -> dict:
        """解析单技能目录，提取元信息"""
        info = {"name": name, "path": path, "description": "", "keywords": [],
                "version": "", "author": "", "title": name}
        meta_path = os.path.join(path, "_meta.json")
        if os.path.exists(meta_path):
            try:
                with open(meta_path, encoding="utf-8") as f:
                    meta = json.load(f)
                info["version"] = meta.get("version", "")
                info["author"] = meta.get("author", "")
                info["description"] = meta.get("description", "")
            except Exception:
                logging.exception("[skill_engine.py] suppressed")
        smd = os.path.join(path, "SKILL.md")
        if os.path.exists(smd):
            try:
                with open(smd, encoding="utf-8") as f:
                    content = f.read()
                dm = re.search(r'description:\s*"([^"]+)"', content)
                if dm and not info["description"]:
                    info["description"] = dm.group(1)
                lines = content.split("\n")
                for line in lines[:40]:
                    if line.startswith("# ") and len(line) > 2:
                        info["title"] = line.strip("# ").strip()
                    funcs = re.findall(r'`(\w+)`', line)
                    for f in funcs:
                        if len(f) > 3 and f not in info["keywords"]:
                            info["keywords"].append(f)
                text_only = re.sub(r'[#*`>\-\|\[\]\(\)]', ' ', content)
                words = re.findall(r'[一-鿿]{2,}', text_only)
                for w, c in Counter(words).most_common(5):
                    if c >= 3 and w not in info["keywords"]:
                        info["keywords"].append(w)
            except Exception:
                logging.exception("[skill_engine.py] suppressed")
        info["keywords"] = list(set(info["keywords"]))
        return info

    def _categorize(self, name: str, desc: str, keywords: list) -> list:
        text = (name + " " + desc + " " + " ".join(keywords)).lower()
        matched = []
        for cat, kws in CATEGORY_KEYWORDS.items():
            for kw in kws:
                if kw.lower() in text:
                    matched.append(cat)
                    break
        return matched

    def scan(self) -> int:
        """全量扫描 skills/，返回技能总数"""
        self._merge_config_categories()
        self.skill_index.clear()
        self.category_index = {c: [] for c in CATEGORY_KEYWORDS}
        if not os.path.exists(self.skill_dir):
            return 0
        count = 0
        for entry in sorted(os.listdir(self.skill_dir)):
            sp = os.path.join(self.skill_dir, entry)
            if not os.path.isdir(sp) or entry.startswith(".") or entry == "__pycache__":
                continue
            info = self._parse_skill(entry, sp)
            if not info:
                continue
            self.skill_index[entry] = info
            for cat in self._categorize(entry, info.get("description", ""), info.get("keywords", [])):
                self.category_index.setdefault(cat, []).append(entry)
            count += 1
        # Save index for SkillRouter
        os.makedirs(os.path.dirname(SKILL_INDEX_FILE), exist_ok=True)
        try:
            with open(SKILL_INDEX_FILE, "w", encoding="utf-8") as f:
                json.dump({"index": self.skill_index, "categories": self.category_index,
                           "updated_at": now_str()}, f, ensure_ascii=False, indent=2)
        except Exception:
            logging.exception("[skill_engine.py] suppressed")
        self._loaded = True
        return count

    def get_stats(self) -> dict:
        """结构化统计，供 daily_maintenance 使用"""
        if not self._loaded:
            try:
                with open(SKILL_INDEX_FILE, encoding="utf-8") as f:
                    d = json.load(f)
                self.skill_index = d.get("index", {})
                self.category_index = d.get("categories", {})
                self._loaded = True
            except Exception:
                logging.exception("[skill_engine.py] suppressed")
        total = len(self.skill_index)
        cat_summary = {}
        for c, skills in self.category_index.items():
            if skills:
                cat_summary[c] = len(skills)
        return {"total_skills": total, "categories": len(cat_summary),
                "category_breakdown": cat_summary, "scanned_at": now_str()}

    def run_cli(self, args: list = None):
        """CLI 入口，替代原 scan_skills.py"""
        if args is None:
            args = sys.argv[1:]
        refresh = "--refresh" in args or "-r" in args
        if refresh:
            self.skill_index.clear()
        count = self.scan()
        if "--json" in args or "-j" in args:
            print(json.dumps(self.skill_index, ensure_ascii=False, indent=2))
        elif "--stats" in args or "-s" in args:
            stats = self.get_stats()
            print(f"技能总数: {stats['total_skills']}")
            print(f"分类数: {stats['categories']}")
            for cat, cnt in sorted(stats.get("category_breakdown", {}).items()):
                print(f"  {cat}: {cnt}个")
        else:
            print(f"✅ 扫描完成：共 {count} 个技能")
            cat_count = len(self.category_index)
            print(f"   分类：{cat_count} 个类别")
            if cat_count > 0:
                for cat in sorted(self.category_index.keys()):
                    if self.category_index[cat]:
                        print(f"     {cat}: {len(self.category_index[cat])}个")


# ════════════════════════════════════════════════════════════════
# 引擎2: SkillRouter — 任务分析 + 路由
# ════════════════════════════════════════════════════════════════

