# -*- coding: utf-8 -*-
"""
v2.5 P2 新增：贴纸渲染引擎
===========================
贴纸位置系统 + 贴纸渲染逻辑
每张卡片有6个预设贴纸位：
┌─────────────────────────────────┐
│ [1: 左上角]   标题    [2: 右上角] │
│                             │
│  [3: 左中]   内容    [4: 右中] │
│                             │
│ [5: 左下角]   信息    [6: 右下角] │
└─────────────────────────────────┘
"""

import sys
sys.path.insert(0, '.')
from .preset_stickers import get_preset_sticker

# 贴纸位置定义
# (x, y) 是贴纸中心点坐标，相对于卡片左上角
STICKER_POSITIONS = {
    'default': {
        # 标准卡片位置（用于餐卡位置
        '1': (30, 30),      # 左上角
        '2': (270, 30),     # 右上角
        '3': (30, 90),      # 左中
        '4': (270, 90),     # 右中
        '5': (30, 150),     # 左下角
        '6': (270, 150),    # 右下角
    },
    
    'small': {
        # 小卡片位置（用于汇总卡）
        '1': (20, 20),      # 左上角
        '2': (220, 20),     # 右上角
        '3': (20, 70),       # 左中
        '4': (220, 70),      # 右中
        '5': (20, 120),      # 左下角
        '6': (220, 120),     # 右下角
    }
}

# 位置名称映射（方便用户理解）
POSITION_NAMES = {
    '1': '左上角',
    '2': '右上角',
    '3': '左中',
    '4': '右中',
    '5': '左下角',
    '6': '右下角',
    '左上角': '1',
    '右上角': '2',
    '左中': '3',
    '右中': '4',
    '左下角': '5',
    '右下角': '6',
}


class StickerRenderer:
    """贴纸渲染引擎"""
    
    def __init__(self, card_type='default'):
        """
        Args:
            card_type: 卡片类型（default/small）
        """
        self.card_type = card_type
        self.positions = STICKER_POSITIONS.get(card_type, STICKER_POSITIONS['default'])
        self.stickers = {}  # {position_id: sticker_info
    
    def get_position_id(self, position):
        """将位置名称转换为位置ID
        
        Args:
            position: 位置名称（如"左上角"、"1"）
            
        Returns:
            position_id 或 None
        """
        return POSITION_NAMES.get(position, position if position in self.positions else None)
    
    def add_sticker(self, position, sticker_id, sticker_source='preset'):
        """添加贴纸
        
        Args:
            position: 位置（1-6 或 左上角/右上角等）
            sticker_id: 贴纸ID
            sticker_source: 贴纸来源（preset/user_drawn/ai_generated）
        """
        pos_id = self.get_position_id(position)
        if pos_id not in self.positions:
            return False
        
        self.stickers[pos_id] = {
            'sticker_id': sticker_id,
            'source': sticker_source,
        }
        return True
    
    def remove_sticker(self, position):
        """移除贴纸
        
        Args:
            position: 位置
        """
        pos_id = self.get_position_id(position)
        if pos_id in self.stickers:
            del self.stickers[pos_id]
            return True
        return False
    
    def clear_stickers(self):
        """清空所有贴纸"""
        self.stickers = {}
    
    def render(self, draw, card_x=0, card_y=0):
        """在卡片上渲染贴纸
        
        Args:
            draw: PIL ImageDraw 对象
            card_x: 卡片左上角X坐标偏移
            card_y: 卡片左上角Y坐标偏移
        """
        for pos_id, sticker_info in self.stickers.items():
            sticker_id = sticker_info['sticker_id']
            source = sticker_info['source']
            
            # 获取贴纸位置（相对于卡片左上角）
            rel_x, rel_y = self.positions.get(pos_id, (30, 30))
            abs_x = card_x + rel_x
            abs_y = card_y + rel_y
            
            if source == 'preset':
                # 预设贴纸：调用绘制函数
                sticker_data = get_preset_sticker(sticker_id)
                if sticker_data:
                    draw_func, name, category = sticker_data
                    draw_func(draw, abs_x, abs_y, size=28)
            elif source == 'user_drawn':
                # 用户手绘贴纸：调用自定义绘制（需要额外的绘制参数
                self._render_user_drawn_sticker(draw, abs_x, abs_y, sticker_id)
            elif source == 'ai_generated':
                # AI生成贴纸：绘制图片（暂未实现）
                pass
    
    def _render_user_drawn_sticker(self, draw, x, y, sticker_id):
        """渲染用户手绘贴纸（从贴纸描述语言生成的）
        这个功能在 sticker_library.py 中实现
        """
        # 由 sticker_library 模块加载用户贴纸数据并渲染
        pass
    
    def list_positions(self):
        """列出所有可用位置
        
        Returns:
            [(position_id, position_name, x, y), ...]
        """
        result = []
        for pos_id, (x, y) in self.positions.items():
            pos_name = {v: k for k, v in POSITION_NAMES.items() if v == pos_id}
            result.append((pos_id, pos_name, x, y))
        return result
    
    def get_sticker_at(self, position):
        """获取指定位置的贴纸
        
        Args:
            position: 位置
            
        Returns:
            sticker_info 或 None
        """
        pos_id = self.get_position_id(position)
        return self.stickers.get(pos_id)
    
    def export_state(self):
        """导出当前贴纸状态（用于保存）
        
        Returns:
            {position_id: sticker_info, ...}
        """
        return self.stickers.copy()
    
    def load_state(self, state):
        """加载贴纸状态
        
        Args:
            state: export_state() 返回的数据
        """
        self.stickers = state.copy()


def get_position_help():
    """获取贴纸位置帮助文本"""
    return """
📌 可用贴纸位置：
1 - 左上角
2 - 右上角
3 - 左中
4 - 右中
5 - 左下角
6 - 右下角

使用示例：
- "在早餐卡片右上角贴面包贴纸"
- "给午餐卡片加一个爱心在左下角"
"""
