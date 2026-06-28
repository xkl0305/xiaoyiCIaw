# -*- coding: utf-8 -*-
"""
v2.5 P2 新增：贴纸描述语言解析器
====================================
简单的自然语言贴纸描述解析器
让用户用自然语言描述来手绘新贴纸

支持的指令：
─────────────────────────────
形状：圆形、椭圆、方形、心形、星形
颜色：红、橙、黄、绿、蓝、紫、粉、黑、白、棕
装饰：加叶子、加边框、加波浪边、加蝴蝶结、加圆点

示例：
"一个红色的圆形，加一片绿色的叶子" → 苹果贴纸
"粉色的心形，加个小蝴蝶结" → 蝴蝶结爱心贴纸
"黄色的星形，加闪光效果" → 星星贴纸
"""

import re
import sys

sys.path.insert(0, '.')

# 颜色映射
COLOR_MAP = {
    '红': '#FF6B6B',
    '红色': '#FF6B6B',
    '橙': '#FFA726',
    '橙色': '#FFA726',
    '黄': '#FFD54F',
    '黄色': '#FFD54F',
    '绿': '#81C784',
    '绿色': '#81C784',
    '蓝': '#64B5F6',
    '蓝色': '#64B5F6',
    '紫': '#BA68C8',
    '紫色': '#BA68C8',
    '粉': '#F48FB1',
    '粉色': '#F48FB1',
    '黑': '#424242',
    '黑色': '#424242',
    '白': '#FFFFFF',
    '白色': '#FFFFFF',
    '棕': '#A1887F',
    '棕色': '#A1887F',
    '金': '#FFD700',
    '金色': '#FFD700',
    '银': '#E0E0E0',
    '银色': '#E0E0E0',
}

# 形状映射
SHAPE_MAP = {
    '圆': 'circle',
    '圆形': 'circle',
    '椭圆': 'ellipse',
    '椭圆形': 'ellipse',
    '方': 'rect',
    '方形': 'rect',
    '正方形': 'rect',
    '长方': 'rect',
    '长方形': 'rect',
    '心': 'heart',
    '心形': 'heart',
    '爱心': 'heart',
    '星': 'star',
    '星形': 'star',
    '星星': 'star',
    '钻石': 'diamond',
    '菱形': 'diamond',
}

# 装饰映射
DECORATION_MAP = {
    '叶子': 'leaf',
    '加叶子': 'leaf',
    '边框': 'border',
    '加边框': 'border',
    '波浪边': 'wavy_border',
    '加波浪边': 'wavy_border',
    '蝴蝶结': 'bow',
    '加蝴蝶结': 'bow',
    '圆点': 'dots',
    '加圆点': 'dots',
    '闪光': 'sparkle',
    '加闪光': 'sparkle',
    '条纹': 'stripes',
    '加条纹': 'stripes',
}


class StickerParser:
    """贴纸描述语言解析器"""
    
    def __init__(self):
        self.color_re = re.compile(r'(' + '|'.join(COLOR_MAP.keys()) + r')色?')
        self.shape_re = re.compile(r'(' + '|'.join(SHAPE_MAP.keys()) + r')形?')
        self.decoration_re = re.compile(r'(' + '|'.join(DECORATION_MAP.keys()) + r')')
    
    def parse(self, description):
        """解析贴纸描述
        
        Args:
            description: 自然语言描述（如"红色的圆形，加绿色叶子"）
            
        Returns:
            dict: 解析后的绘制参数
        """
        params = {
            'shape': 'circle',      # 默认形状
            'primary_color': '#FF69B4',  # 默认颜色
            'secondary_color': None,  # 次要颜色
            'decorations': [],        # 装饰列表
            'name': self._generate_name(description),
        }
        
        # 解析形状
        shape_match = self.shape_re.search(description)
        if shape_match:
            shape_name = shape_match.group(1)
            params['shape'] = SHAPE_MAP.get(shape_name, 'circle')
        
        # 解析所有颜色
        colors = self.color_re.findall(description)
        if colors:
            params['primary_color'] = COLOR_MAP.get(colors[0], '#FF69B4')
            if len(colors) > 1:
                params['secondary_color'] = COLOR_MAP.get(colors[1], '#4CAF50')
        
        # 解析装饰
        decorations = self.decoration_re.findall(description)
        for deco_name in decorations:
            deco = DECORATION_MAP.get(deco_name)
            if deco and deco not in params['decorations']:
                params['decorations'].append(deco)
        
        return params
    
    def _generate_name(self, description):
        """从描述生成贴纸名称"""
        # 提取关键词
        words = re.findall(r'[\u4e00-\u9fa5]{2,3}', description)
        if words:
            return ''.join(words[:3]) + '贴纸'
        return '我的贴纸'
    
    def render(self, draw, params, x, y, size=28):
        """根据参数渲染贴纸
        
        Args:
            draw: PIL ImageDraw 对象
            params: parse() 返回的绘制参数
            x: 中心点X坐标
            y: 中心点Y坐标
            size: 贴纸大小
        """
        s = size // 2
        primary_color = params['primary_color']
        secondary_color = params.get('secondary_color', '#4CAF50')
        shape = params['shape']
        decorations = params['decorations']
        
        # 绘制基础形状
        if shape == 'circle':
            draw.ellipse([x-s, y-s, x+s, y+s], fill=primary_color, outline='#333', width=1)
        elif shape == 'ellipse':
            draw.ellipse([x-s, y-s//2, x+s, y+s//2], fill=primary_color, outline='#333', width=1)
        elif shape == 'rect':
            draw.rectangle([x-s, y-s, x+s, y+s], fill=primary_color, outline='#333', width=1)
        elif shape == 'heart':
            # 心形
            draw.ellipse([x-s, y-s, x, y], fill=primary_color, outline='#333', width=1)
            draw.ellipse([x, y-s, x+s, y], fill=primary_color, outline='#333', width=1)
            draw.polygon([(x-s, y), (x+s, y), (x, y+s)], fill=primary_color, outline='#333')
        elif shape == 'star':
            # 五角星（简化版）
            draw.polygon([
                (x, y-s), (x+s//3, y-s//3), (x+s, y-s//2),
                (x+s//2, y), (x+s//2, y+s), (x, y+s//2),
                (x-s//2, y+s), (x-s//2, y), (x-s, y-s//2),
                (x-s//3, y-s//3),
            ], fill=primary_color, outline='#333', width=1)
        elif shape == 'diamond':
            # 钻石形
            draw.polygon([(x, y-s), (x+s, y), (x, y+s), (x-s, y)], fill=primary_color, outline='#333', width=1)
        
        # 绘制装饰
        for deco in decorations:
            if deco == 'leaf':
                # 加叶子
                draw.ellipse([x-s//2, y-s-4, x+s//2+4, y-s], fill=secondary_color)
                draw.line([x, y-s+2, x, y-s-2], fill='#8B4513', width=2)
            elif deco == 'border':
                # 加边框（画一个更大的圈）
                draw.ellipse([x-s-3, y-s-3, x+s+3, y+s+3], outline='#333', width=2)
            elif deco == 'bow':
                # 加蝴蝶结（画一个小蝴蝶结在上方）
                draw.ellipse([x-s//2, y-s-5, x, y-s+2], fill=secondary_color)
                draw.ellipse([x, y-s-5, x+s//2, y-s+2], fill=secondary_color)
            elif deco == 'dots':
                # 加点
                for dx, dy in [(-s//2, -s//2), (s//2, -s//2), (0, 0), (-s//2, s//2), (s//2, s//2)]:
                    draw.ellipse([x+dx-2, y+dy-2, x+dx+2, y+dy+2], fill=secondary_color)
            elif deco == 'sparkle':
                # 加闪光
                draw.line([x-s//2, y, x+s//2, y], fill=secondary_color, width=2)
                draw.line([x, y-s//2, x, y+s//2], fill=secondary_color, width=2)
            elif deco == 'stripes':
                # 加条纹
                for i in range(-2, 3):
                    draw.line([x-s, y+i*4, x+s, y+i*4], fill=secondary_color, width=1)
    
    def render_and_save(self, description):
        """解析描述并保存为贴纸
        
        Args:
            description: 自然语言描述
            
        Returns:
            (sticker_id, sticker_name, params) 或 None
        """
        from .sticker_library import get_sticker_library
        
        # 解析描述
        params = self.parse(description)
        sticker_name = params['name']
        
        # 添加到贴纸库
        library = get_sticker_library()
        sticker_id = library.add_hand_drawn_sticker(
            name=sticker_name,
            draw_params=params,
            description=description
        )
        
        return (sticker_id, sticker_name, params)


# 全局解析器实例
_global_parser = None


def get_sticker_parser():
    """获取全局解析器实例"""
    global _global_parser
    if _global_parser is None:
        _global_parser = StickerParser()
    return _global_parser


def get_help_text():
    """获取贴纸描述语言帮助文本"""
    return """
🎨 贴纸描述语言帮助

你可以这样描述你想要的贴纸：

形状：
  • 圆形、椭圆形、方形、心形、星形、菱形

颜色：
  • 红、橙、黄、绿、蓝、紫、粉、黑、白、棕、金、银

装饰：
  • 加叶子、加边框、加蝴蝶结、加圆点、加闪光、加条纹

示例：
  "一个红色的圆形，加一片绿色的叶子" → 苹果贴纸
  "粉色的心形，加个小蝴蝶结" → 蝴蝶结爱心贴纸
  "黄色的星形，加闪光效果" → 星星贴纸
  "蓝色的圆形，加白色圆点" → 波点贴纸

直接告诉我你想要什么样的贴纸，我来帮你画～
"""


if __name__ == '__main__':
    # 测试
    parser = StickerParser()
    test_descriptions = [
        "一个红色的圆形，加一片绿色的叶子",
        "粉色的心形，加个小蝴蝶结",
        "黄色的星形，加闪光效果",
        "蓝色的圆形，加白色圆点",
    ]
    for desc in test_descriptions:
        params = parser.parse(desc)
        print(f"描述: {desc}")
        print(f"  解析结果: {params}")
        print()
