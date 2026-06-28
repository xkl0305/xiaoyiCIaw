#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主题包加载器
负责加载、继承、合并主题包，提供统一的接口
"""

import json
import os
from typing import Dict, Any, Optional

class ThemePackLoader:
    """主题包加载器"""
    
    def __init__(self, theme_packs_dir: str = "theme_packs"):
        self.theme_packs_dir = theme_packs_dir
        self.loaded_themes = {}
        self.current_theme = None
        self.overrides = {}
        
    def load_theme(self, theme_id: str) -> Dict[str, Any]:
        """
        加载一个主题包
        
        Args:
            theme_id: 主题包ID，对应目录名
            
        Returns:
            完整的主题包数据
        """
        theme_path = os.path.join(self.theme_packs_dir, theme_id)
        
        if not os.path.exists(theme_path):
            print(f"⚠️  主题包 {theme_id} 不存在，使用默认主题")
            return self._get_default_theme()
        
        theme_data = {}
        
        # 加载所有模块
        modules = ["naming", "character", "emotion", "quotes", "style", "stickers"]
        
        for module in modules:
            module_file = os.path.join(theme_path, f"{module}.json")
            if os.path.exists(module_file):
                with open(module_file, 'r', encoding='utf-8') as f:
                    theme_data[module] = json.load(f)
            else:
                # 使用默认模块
                theme_data[module] = self._get_default_module(module)
        
        # 应用用户覆盖
        if theme_id in self.overrides:
            theme_data = self._apply_overrides(theme_data, self.overrides[theme_id])
        
        self.loaded_themes[theme_id] = theme_data
        self.current_theme = theme_id
        
        return theme_data
    
    def set_override(self, theme_id: str, module: str, key: str, value: Any):
        """
        设置主题包覆盖
        
        Args:
            theme_id: 主题包ID
            module: 模块名（naming/character/emotion等）
            key: 要覆盖的键
            value: 新的值
        """
        if theme_id not in self.overrides:
            self.overrides[theme_id] = {}
        
        if module not in self.overrides[theme_id]:
            self.overrides[theme_id][module] = {}
        
        self.overrides[theme_id][module][key] = value
        
        # 如果已经加载了，重新加载
        if theme_id in self.loaded_themes:
            self.load_theme(theme_id)
    
    def get_nutrition_name(self, nutrition_key: str) -> Dict[str, str]:
        """获取营养项的命名"""
        if not self.current_theme:
            self.load_theme("default")
        
        naming = self.loaded_themes[self.current_theme]["naming"]
        
        if nutrition_key in naming["nutrition_names"]:
            return naming["nutrition_names"][nutrition_key]
        
        # 默认命名
        default_names = {
            "calories": {"name": "热量", "icon": "🔥", "description": "能量"},
            "protein": {"name": "蛋白质", "icon": "💪", "description": "蛋白质"},
            "carbs": {"name": "碳水化合物", "icon": "🍞", "description": "碳水"},
            "fat": {"name": "脂肪", "icon": "🥑", "description": "脂肪"},
            "fiber": {"name": "膳食纤维", "icon": "🌿", "description": "纤维"}
        }
        
        return default_names.get(nutrition_key, {"name": nutrition_key, "icon": "•", "description": ""})
    
    def get_quote(self, trigger_type: str = "general") -> str:
        """获取一条话术"""
        if not self.current_theme:
            self.load_theme("default")
        
        quotes = self.loaded_themes[self.current_theme]["quotes"]
        
        if trigger_type in quotes["triggers"]:
            import random
            return random.choice(quotes["triggers"][trigger_type]["quotes"])
        
        return quotes["default_quote"]
    
    def get_style(self, style_id: Optional[str] = None) -> Dict[str, str]:
        """获取风格配置"""
        if not self.current_theme:
            self.load_theme("default")
        
        style_pack = self.loaded_themes[self.current_theme]["style"]
        
        if style_id is None:
            style_id = style_pack.get("default_style", "paper")
        
        if style_id in style_pack["styles"]:
            return style_pack["styles"][style_id]
        
        # 默认风格
        return {
            "name": "默认",
            "background": "#f5f0e8",
            "card_bg": "#fff9f0",
            "text_color": "#5a4a3a",
            "accent_color": "#d4a574"
        }
    
    def list_available_themes(self) -> list:
        """列出所有可用的主题包"""
        if not os.path.exists(self.theme_packs_dir):
            return ["default"]
        
        themes = []
        for item in os.listdir(self.theme_packs_dir):
            item_path = os.path.join(self.theme_packs_dir, item)
            if os.path.isdir(item_path):
                themes.append(item)
        
        return themes
    
    def _get_default_theme(self) -> Dict[str, Any]:
        """获取默认主题包（内置兜底）"""
        return {
            "naming": self._get_default_module("naming"),
            "character": self._get_default_module("character"),
            "emotion": self._get_default_module("emotion"),
            "quotes": self._get_default_module("quotes"),
            "style": self._get_default_module("style"),
            "stickers": self._get_default_module("stickers")
        }
    
    def _get_default_module(self, module_name: str) -> Dict[str, Any]:
        """获取默认模块配置"""
        defaults = {
            "naming": {
                "theme_id": "default",
                "theme_name": "默认",
                "nutrition_names": {
                    "calories": {"name": "热量", "icon": "🔥", "description": "能量"},
                    "protein": {"name": "蛋白质", "icon": "💪", "description": "蛋白质"},
                    "carbs": {"name": "碳水化合物", "icon": "🍞", "description": "碳水"},
                    "fat": {"name": "脂肪", "icon": "🥑", "description": "脂肪"},
                    "fiber": {"name": "膳食纤维", "icon": "🌿", "description": "纤维"}
                }
            },
            "character": {
                "character_id": "default",
                "character_name": "饮食伙伴",
                "greetings": ["你好呀"],
                "signatures": ["你的饮食伙伴"]
            },
            "emotion": {
                "categories": {},
                "default_category": {"name": "食物", "icon": "🍽️"}
            },
            "quotes": {
                "triggers": {
                    "general": {"quotes": ["好好吃饭，好好生活"]}
                },
                "default_quote": "好好吃饭 ❤️"
            },
            "style": {
                "default_style": "paper",
                "styles": {
                    "paper": {
                        "name": "纸张",
                        "background": "#f5f0e8",
                        "card_bg": "#fff9f0",
                        "text_color": "#5a4a3a",
                        "accent_color": "#d4a574"
                    }
                }
            },
            "stickers": {
                "preset_stickers": {},
                "sticker_rules": {"max_per_card": 3}
            }
        }
        
        return defaults.get(module_name, {})
    
    def _apply_overrides(self, theme_data: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
        """应用用户覆盖"""
        for module, module_overrides in overrides.items():
            if module in theme_data:
                theme_data[module].update(module_overrides)
        
        return theme_data


# 单例实例
_theme_loader: Optional[ThemePackLoader] = None

def get_theme_loader(theme_packs_dir: str = None) -> ThemePackLoader:
    """获取主题包加载器单例"""
    global _theme_loader
    
    if _theme_loader is None:
        if theme_packs_dir is None:
            # 自动查找主题包目录
            script_dir = os.path.dirname(os.path.abspath(__file__))
            theme_packs_dir = os.path.join(script_dir, "theme_packs")
        
        _theme_loader = ThemePackLoader(theme_packs_dir)
    
    return _theme_loader
