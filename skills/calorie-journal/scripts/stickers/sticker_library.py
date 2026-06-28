# -*- coding: utf-8 -*-
"""
v2.5 P2 新增：贴纸库管理系统
=============================
用户贴纸库的持久化和管理功能
符合Skill规范：JSON文件存储，无外部依赖
"""

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, '.')
from .preset_stickers import get_preset_sticker, list_preset_stickers
from .sticker_renderer import StickerRenderer

# 用户贴纸库保存路径
STICKER_LIBRARY_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'user_stickers.json')

# 贴纸库最大数量限制（避免体积过大）
MAX_USER_STICKERS = 50


class StickerLibrary:
    """贴纸库管理"""
    
    def __init__(self, library_path=None):
        """
        Args:
            library_path: 贴纸库保存路径（可选）
        """
        self.library_path = library_path or STICKER_LIBRARY_PATH
        self._ensure_data_dir()
        self.stickers = self._load_library()
    
    def _ensure_data_dir(self):
        """确保data目录存在"""
        data_dir = os.path.dirname(self.library_path)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)
    
    def _load_library(self):
        """加载贴纸库"""
        if not os.path.exists(self.library_path):
            return []
        
        try:
            with open(self.library_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('stickers', [])
        except Exception as e:
            print(f"加载贴纸库失败: {e}")
            return []
    
    def _create_empty_library(self):
        """创建空贴纸库"""
        return []
    
    def _save_library(self):
        """保存贴纸库"""
        try:
            data = {
                'version': '1.0',
                'updated_at': datetime.now().isoformat(),
                'stickers': self.stickers
            }
            with open(self.library_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存贴纸库失败: {e}")
            return False
    
    def add_hand_drawn_sticker(self, name, draw_params, description=""):
        """添加用户手绘贴纸
        
        Args:
            name: 贴纸名称
            draw_params: 绘制参数（描述语言解析后的结果）
            description: 贴纸描述
            
        Returns:
            sticker_id 或 None（失败）
        """
        # 检查数量限制
        if len(self.stickers) >= MAX_USER_STICKERS:
            print(f"贴纸库已达上限 {MAX_USER_STICKERS} 个，请先删除不常用的贴纸")
            return None
        
        # 生成唯一ID
        sticker_id = f"user_{len(self.stickers) + 1:03d}"
        
        sticker_data = {
            'id': sticker_id,
            'name': name,
            'type': 'hand_drawn',
            'description': description,
            'draw_params': draw_params,
            'created_at': datetime.now().isoformat(),
            'usage_count': 0,
        }
        
        self.stickers.append(sticker_data)
        self._save_library()
        return sticker_id
    
    def add_ai_generated_sticker(self, name, image_path, description=""):
        """添加AI生成贴纸
        
        Args:
            name: 贴纸名称
            image_path: 图片路径（相对路径）
            description: 贴纸描述
            
        Returns:
            sticker_id 或 None（失败）
        """
        # 检查数量限制
        if len(self.stickers) >= MAX_USER_STICKERS:
            print(f"贴纸库已达上限 {MAX_USER_STICKERS} 个，请先删除不常用的贴纸")
            return None
        
        # 生成唯一ID
        sticker_id = f"ai_{len(self.stickers) + 1:03d}"
        
        sticker_data = {
            'id': sticker_id,
            'name': name,
            'type': 'ai_generated',
            'description': description,
            'image_path': image_path,
            'created_at': datetime.now().isoformat(),
            'usage_count': 0,
        }
        
        self.stickers.append(sticker_data)
        self._save_library()
        return sticker_id
    
    def get_sticker(self, sticker_id):
        """获取贴纸
        
        Args:
            sticker_id: 贴纸ID
            
        Returns:
            sticker_data 或 None
        """
        for sticker in self.stickers:
            if sticker.get('id') == sticker_id:
                # 更新使用次数
                sticker['usage_count'] = sticker.get('usage_count', 0) + 1
                self._save_library()
                return sticker
        return None
    
    def list_stickers(self, sticker_type=None):
        """列出贴纸
        
        Args:
            sticker_type: 可选类型（hand_drawn/ai_generated/preset）
            
        Returns:
            [sticker_data, ...]
        """
        if sticker_type == 'preset':
            # 返回预设贴纸
            from .preset_stickers import PRESET_STICKERS
            return [
                {
                    'id': sid,
                    'name': name,
                    'type': 'preset',
                    'category': category,
                }
                for sid, (func, name, category) in PRESET_STICKERS.items()
            ]
        
        if sticker_type:
            return [s for s in self.stickers if s.get('type') == sticker_type]
        
        # 返回所有用户贴纸
        return self.stickers.copy()
    
    def delete_sticker(self, sticker_id):
        """删除贴纸
        
        Args:
            sticker_id: 贴纸ID
            
        Returns:
            是否删除成功
        """
        for i, sticker in enumerate(self.stickers):
            if sticker.get('id') == sticker_id:
                # 如果是AI生成的，同时删除图片文件
                if sticker.get('type') == 'ai_generated' and 'image_path' in sticker:
                    try:
                        full_path = os.path.join(os.path.dirname(self.library_path), sticker['image_path'])
                        if os.path.exists(full_path):
                            os.remove(full_path)
                    except:
                        pass
                
                del self.stickers[i]
                self._save_library()
                return True
        return False
    
    def render_user_sticker(self, draw, sticker_id, x, y, size=28):
        """渲染用户贴纸
        
        Args:
            draw: PIL ImageDraw 对象
            sticker_id: 贴纸ID
            x: 中心点X坐标
            y: 中心点Y坐标
            size: 贴纸大小
        """
        sticker = self.get_sticker(sticker_id)
        if not sticker:
            return False
        
        if sticker['type'] == 'hand_drawn':
            # 用户手绘贴纸：根据绘制参数渲染
            self._render_hand_drawn(draw, sticker['draw_params'], x, y, size)
            return True
        elif sticker['type'] == 'ai_generated':
            # AI生成贴纸：绘制图片
            return self._render_ai_generated(draw, sticker['image_path'], x, y, size)
        
        return False
    
    def _render_hand_drawn(self, draw, draw_params, x, y, size=28):
        """渲染用户手绘贴纸（根据描述语言生成的）
        
        这个功能在 sticker_parser.py 中实现
        """
        # 由 sticker_parser 模块解析并渲染
        pass
    
    def _render_ai_generated(self, draw, image_path, x, y, size=28):
        """渲染AI生成贴纸（绘制图片）"""
        # 暂未实现
        return False
    
    def clean_unused_stickers(self, min_usage=0, days_old=30):
        """清理不常用的贴纸
        
        Args:
            min_usage: 最小使用次数（使用次数少于此的会被清理）
            days_old: 超过多少天未使用会被清理
        """
        # 暂未实现
        pass
    
    def get_statistics(self):
        """获取贴纸库统计信息"""
        preset_count = len(self.list_stickers('preset'))
        user_count = len(self.stickers)
        hand_drawn_count = len([s for s in self.stickers if s.get('type') == 'hand_drawn'])
        ai_generated_count = len([s for s in self.stickers if s.get('type') == 'ai_generated'])
        
        return {
            'preset_count': preset_count,
            'user_count': user_count,
            'hand_drawn_count': hand_drawn_count,
            'ai_generated_count': ai_generated_count,
            'max_limit': MAX_USER_STICKERS,
        }
    
    def get_help_text(self):
        """获取贴纸库帮助文本"""
        stats = self.get_statistics()
        return f"""
📦 我的贴纸库
├─ 🎨 系统预设贴纸：{stats['preset_count']} 个
├─ ✨ 我手绘的贴纸：{stats['hand_drawn_count']} 个
└─ 🤖 AI生成的贴纸：{stats['ai_generated_count']} 个

使用方法：
- "列出所有贴纸" - 查看所有可用贴纸
- "在XX位置贴XX贴纸" - 给卡片添加贴纸
- "帮我画一个XX贴纸" - 用描述语言手绘新贴纸
- "用AI生成一个XX贴纸" - 用AI生成新贴纸（需要配置API Key）
"""


# 全局贴纸库实例
_global_library = None


def get_sticker_library():
    """获取全局贴纸库实例"""
    global _global_library
    if _global_library is None:
        _global_library = StickerLibrary()
    return _global_library
