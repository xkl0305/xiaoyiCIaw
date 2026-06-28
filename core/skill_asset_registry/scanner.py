"""技能扫描器"""

from typing import List, Dict, Any
from pathlib import Path
import json
from .schemas import SkillAsset


class SkillScanner:
    """技能扫描器"""
    
    def __init__(self, skills_dir: str = "skills"):
        self.skills_dir = Path(skills_dir)
    
    def scan_all(self) -> List[SkillAsset]:
        """扫描所有技能。

        V111 no-skills 包不再携带物理 skills/ 目录；此时从
        infrastructure/inventory/skill_registry.json 读取逻辑技能资产，
        保持技能检索、分类统计和测试覆盖不依赖物理目录。
        """
        assets = []
        
        if not self.skills_dir.exists():
            return self._scan_logical_registry()
        
        for skill_path in self.skills_dir.iterdir():
            if skill_path.is_dir() and not skill_path.name.startswith("."):
                asset = self._scan_skill(skill_path)
                if asset:
                    assets.append(asset)
        
        return assets

    def _scan_logical_registry(self) -> List[SkillAsset]:
        registry_path = Path("infrastructure/inventory/skill_registry.json")
        if not registry_path.exists():
            return []
        try:
            data = json.loads(registry_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        skills = data.get("skills", {}) if isinstance(data, dict) else {}
        if not isinstance(skills, dict):
            return []
        assets: List[SkillAsset] = []
        for skill_id, meta in skills.items():
            if not isinstance(meta, dict):
                meta = {}
            description = str(meta.get("description") or meta.get("name") or skill_id)
            category = str(meta.get("category") or self._classify_skill(skill_id, description))
            assets.append(SkillAsset(
                skill_id=skill_id,
                name=str(meta.get("name") or self._format_name(skill_id)),
                category=category,
                description=description,
                side_effecting=bool(meta.get("side_effecting", False)),
                location=str(meta.get("path") or f"logical://skills/{skill_id}"),
                version=str(meta.get("version") or "1.0.0"),
            ))
        return assets
    
    def _scan_skill(self, skill_path: Path) -> SkillAsset:
        """扫描单个技能"""
        skill_id = skill_path.name
        
        # 读取 SKILL.md
        skill_md = skill_path / "SKILL.md"
        description = ""
        if skill_md.exists():
            description = self._parse_description(skill_md.read_text())
        
        # 读取 skill.py
        skill_py = skill_path / "skill.py"
        side_effecting = False
        if skill_py.exists():
            content = skill_py.read_text()
            side_effecting = "side_effect" in content.lower() or "send" in content.lower()
        
        # 分类
        category = self._classify_skill(skill_id, description)
        
        return SkillAsset(
            skill_id=skill_id,
            name=self._format_name(skill_id),
            category=category,
            description=description,
            side_effecting=side_effecting,
            location=str(skill_path),
        )
    
    def _parse_description(self, content: str) -> str:
        """解析描述"""
        lines = content.split("\n")
        for line in lines[1:10]:  # 跳过标题，取前几行
            line = line.strip()
            if line and not line.startswith("#"):
                return line[:200]
        return ""
    
    def _classify_skill(self, skill_id: str, description: str) -> str:
        """分类技能"""
        desc_lower = description.lower()
        skill_lower = skill_id.lower()
        
        categories = {
            "ai": ["ai", "llm", "gpt", "claude", "model"],
            "search": ["search", "find", "query", "web"],
            "image": ["image", "photo", "picture", "visual"],
            "document": ["doc", "pdf", "word", "excel", "ppt"],
            "video": ["video", "youtube", "media"],
            "finance": ["finance", "stock", "market", "trading"],
            "code": ["code", "git", "programming", "developer"],
            "data": ["data", "analytics", "chart", "graph"],
            "memory": ["memory", "note", "store"],
            "automation": ["automation", "schedule", "task"],
            "communication": ["message", "sms", "email", "notify"],
        }
        
        for cat, keywords in categories.items():
            for kw in keywords:
                if kw in desc_lower or kw in skill_lower:
                    return cat
        
        return "other"
    
    def _format_name(self, skill_id: str) -> str:
        """格式化名称"""
        return skill_id.replace("-", " ").replace("_", " ").title()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        assets = self.scan_all()
        
        categories = {}
        for asset in assets:
            categories[asset.category] = categories.get(asset.category, 0) + 1
        
        return {
            "total": len(assets),
            "categories": categories,
            "side_effecting": sum(1 for a in assets if a.side_effecting),
        }
