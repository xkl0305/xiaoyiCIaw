# -*- coding: utf-8 -*-
"""
v2.5 P3 新增：整体风格系统
===========================
8种预设手账风格，纯代码零API依赖
支持全局风格切换和用户偏好持久化

风格列表：
1. 🎋 水墨风格 - 中国风、淡雅、禅意
2. 🎨 油彩风格 - 厚涂、艺术感、色彩丰富
3. 💧 水彩风格 - 清新、透明、梦幻
4. 📜 纸张风格 - 复古、温暖、手账感
5. 🌸 少女心风格 - 粉色、可爱、梦幻
6. 🌙 暗夜风格 - 深色、星空、静谧
7. ⚡ 极简风格 - 干净、现代、清爽
8. 🌈 彩虹风格 - 活泼、元气、多巴胺
"""

import json
import os
import sys
import random
from datetime import datetime

sys.path.insert(0, '.')

# 风格配置文件路径
STYLE_CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'data', 'style_preference.json')


# ============== 颜色工具函数 ==============
def hex_to_rgb(hex_color):
    """十六进制转RGB"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    """RGB转十六进制"""
    return '#{:02x}{:02x}{:02x}'.format(*rgb)


def blend_colors(color1, color2, ratio=0.5):
    """混合两种颜色"""
    r1, g1, b1 = hex_to_rgb(color1)
    r2, g2, b2 = hex_to_rgb(color2)
    r = int(r1 * ratio + r2 * (1 - ratio))
    g = int(g1 * ratio + g2 * (1 - ratio))
    b = int(b1 * ratio + b2 * (1 - ratio))
    return rgb_to_hex((r, g, b))


# ============== 8种风格的完整配置 ==============
STYLE_CONFIGS = {
    # 1. 🎋 水墨风格
    'ink_wash': {
        'name': '水墨风格',
        'emoji': '🎋',
        'description': '中国风、淡雅、禅意',
        
        # 背景配置
        'background': {
            'type': 'gradient_noise',  # 渐变+噪点
            'colors': ['#F5F5F0', '#E8E8E0', '#DDDDD0'],
            'noise_level': 0.05,
        },
        
        # 卡片配置
        'card': {
            'fill': '#F8F8F0',
            'outline': '#4A4A4A',
            'outline_width': 1,
            'opacity': 0.95,
        },
        
        # 文字配置
        'text': {
            'title': '#2D2D2D',
            'content': '#4A4A4A',
            'secondary': '#6A6A6A',
        },
        
        # 营养条颜色
        'nutrition': {
            'protein': '#4A4A4A',
            'carbs': '#6A6A6A',
            'fat': '#8A8A8A',
            'kcal': '#3A3A3A',
        },
        
        # 装饰元素
        'decorations': ['ink_splash', 'bamboo', 'plum_blossom'],
    },
    
    # 2. 🎨 油彩风格
    'oil_paint': {
        'name': '油彩风格',
        'emoji': '🎨',
        'description': '厚涂、艺术感、色彩丰富',
        
        'background': {
            'type': 'color_blocks',  # 大色块
            'colors': ['#FFE4E1', '#E0FFFF', '#F0FFF0', '#FFF0F5'],
            'blend_mode': 'soft',
        },
        
        'card': {
            'fill': '#FFFEFA',
            'outline': '#8B4513',
            'outline_width': 3,
            'opacity': 0.9,
        },
        
        'text': {
            'title': '#8B4513',
            'content': '#5D4037',
            'secondary': '#8D6E63',
        },
        
        'nutrition': {
            'protein': '#E57373',
            'carbs': '#64B5F6',
            'fat': '#81C784',
            'kcal': '#FFB74D',
        },
        
        'decorations': ['brush_stroke', 'paint_splatter'],
    },
    
    # 3. 💧 水彩风格
    'water_color': {
        'name': '水彩风格',
        'emoji': '💧',
        'description': '清新、透明、梦幻',
        
        'background': {
            'type': 'water_stain',  # 水渍效果
            'colors': ['#E3F2FD', '#E8F5E9', '#FFF3E0', '#FCE4EC'],
            'transparency': 0.3,
        },
        
        'card': {
            'fill': '#FFFEF8',
            'outline': '#90CAF9',
            'outline_width': 2,
            'opacity': 0.85,
        },
        
        'text': {
            'title': '#1565C0',
            'content': '#424242',
            'secondary': '#757575',
        },
        
        'nutrition': {
            'protein': '#42A5F5',
            'carbs': '#66BB6A',
            'fat': '#AB47BC',
            'kcal': '#FF7043',
        },
        
        'decorations': ['water_drop', 'bubble', 'color_bleed'],
    },
    
    # 4. 📜 纸张风格
    'paper': {
        'name': '纸张风格',
        'emoji': '📜',
        'description': '复古、温暖、手账感',
        
        'background': {
            'type': 'paper_texture',  # 纸张纹理
            'colors': ['#F5E6D3', '#EDE0C8', '#F0E6D6'],
            'stains': True,  # 轻微污渍
            'crease': True,  # 折痕
        },
        
        'card': {
            'fill': '#FFFAF0',
            'outline': '#8B7355',
            'outline_width': 1,
            'opacity': 0.95,
        },
        
        'text': {
            'title': '#5D4037',
            'content': '#6D4C41',
            'secondary': '#8D6E63',
        },
        
        'nutrition': {
            'protein': '#8D6E63',
            'carbs': '#A1887F',
            'fat': '#BCAAA4',
            'kcal': '#6D4C41',
        },
        
        'decorations': ['paper_clip', 'tape', 'coffee_stain'],
    },
    
    # 5. 🌸 少女心风格
    'cute_girl': {
        'name': '少女心风格',
        'emoji': '🌸',
        'description': '粉色、可爱、梦幻',
        
        'background': {
            'type': 'gradient_dots',  # 渐变+波点
            'colors': ['#FCE4EC', '#F8BBD0', '#E1BEE7'],
            'dots': True,
            'dot_color': '#F48FB1',
        },
        
        'card': {
            'fill': '#FFF0F5',
            'outline': '#F48FB1',
            'outline_width': 2,
            'opacity': 0.95,
        },
        
        'text': {
            'title': '#C2185B',
            'content': '#880E4F',
            'secondary': '#AD1457',
        },
        
        'nutrition': {
            'protein': '#F06292',
            'carbs': '#BA68C8',
            'fat': '#4FC3F7',
            'kcal': '#FFB74D',
        },
        
        'decorations': ['lace', 'heart', 'star', 'ribbon'],
    },
    
    # 6. 🌙 暗夜风格
    'dark_night': {
        'name': '暗夜风格',
        'emoji': '🌙',
        'description': '深色、星空、静谧',
        
        'background': {
            'type': 'starry_sky',  # 星空
            'colors': ['#1A237E', '#283593', '#3949AB'],
            'stars': True,
            'moon': True,
        },
        
        'card': {
            'fill': '#283593',
            'outline': '#7986CB',
            'outline_width': 2,
            'opacity': 0.85,
        },
        
        'text': {
            'title': '#E8EAF6',
            'content': '#C5CAE9',
            'secondary': '#9FA8DA',
        },
        
        'nutrition': {
            'protein': '#64B5F6',
            'carbs': '#81C784',
            'fat': '#F48FB1',
            'kcal': '#FFD54F',
        },
        
        'decorations': ['stars', 'moon', 'glow'],
    },
    
    # 7. ⚡ 极简风格
    'minimal': {
        'name': '极简风格',
        'emoji': '⚡',
        'description': '干净、现代、清爽',
        
        'background': {
            'type': 'pure_color',  # 纯色
            'colors': ['#FAFAFA'],
        },
        
        'card': {
            'fill': '#FFFFFF',
            'outline': '#E0E0E0',
            'outline_width': 1,
            'opacity': 1.0,
        },
        
        'text': {
            'title': '#212121',
            'content': '#424242',
            'secondary': '#757575',
        },
        
        'nutrition': {
            'protein': '#2196F3',
            'carbs': '#4CAF50',
            'fat': '#FF9800',
            'kcal': '#F44336',
        },
        
        'decorations': ['thin_line', 'corner_mark'],
    },
    
    # 8. 🌈 彩虹风格
    'rainbow': {
        'name': '彩虹风格',
        'emoji': '🌈',
        'description': '活泼、元气、多巴胺',
        
        'background': {
            'type': 'rainbow_stripes',  # 彩虹条纹
            'colors': ['#FF6B6B', '#FFD93D', '#6BCB77', '#4D96FF', '#9B59B6'],
            'stripes_direction': 'diagonal',
        },
        
        'card': {
            'fill': '#FFFFFF',
            'outline': '#FF6B6B',
            'outline_width': 3,
            'opacity': 0.95,
        },
        
        'text': {
            'title': '#FF6B6B',
            'content': '#424242',
            'secondary': '#757575',
        },
        
        'nutrition': {
            'protein': '#FF6B6B',
            'carbs': '#FFD93D',
            'fat': '#6BCB77',
            'kcal': '#4D96FF',
        },
        
        'decorations': ['rainbow_arch', 'sparkle', 'confetti'],
    },
}


# ============== 背景渲染函数 ==============
def render_background(draw, style_id, width, height):
    """渲染风格背景
    
    Args:
        draw: PIL ImageDraw 对象
        style_id: 风格ID
        width: 画布宽度
        height: 画布高度
    """
    style = STYLE_CONFIGS.get(style_id, STYLE_CONFIGS['paper'])
    bg_config = style['background']
    bg_type = bg_config['type']
    colors = bg_config['colors']
    
    if bg_type == 'pure_color':
        # 纯色背景
        color = colors[0]
        draw.rectangle([0, 0, width, height], fill=color)
    
    elif bg_type == 'gradient_noise':
        # 渐变+噪点（水墨风格）
        _render_gradient_background(draw, width, height, colors)
        _add_noise(draw, width, height, level=bg_config.get('noise_level', 0.05))
    
    elif bg_type == 'color_blocks':
        # 大色块（油彩风格）
        _render_color_blocks(draw, width, height, colors)
    
    elif bg_type == 'water_stain':
        # 水渍效果（水彩风格）
        _render_water_stain(draw, width, height, colors, bg_config.get('transparency', 0.3))
    
    elif bg_type == 'paper_texture':
        # 纸张纹理
        _render_paper_texture(draw, width, height, colors, bg_config.get('stains', False))
    
    elif bg_type == 'gradient_dots':
        # 渐变+波点
        _render_gradient_background(draw, width, height, colors)
        if bg_config.get('dots', False):
            _add_dots(draw, width, height, bg_config.get('dot_color', '#F48FB1'))
    
    elif bg_type == 'starry_sky':
        # 星空背景
        _render_starry_sky(draw, width, height, colors, bg_config.get('stars', True), bg_config.get('moon', True))
    
    elif bg_type == 'rainbow_stripes':
        # 彩虹条纹
        _render_rainbow_stripes(draw, width, height, colors)


def _render_gradient_background(draw, width, height, colors):
    """渲染渐变背景"""
    steps = 50
    for i in range(steps):
        y1 = int(height * i / steps)
        y2 = int(height * (i + 1) / steps)
        ratio = i / steps
        color = blend_colors(colors[0], colors[-1], 1 - ratio)
        draw.rectangle([0, y1, width, y2], fill=color)


def _add_noise(draw, width, height, level=0.05):
    """添加噪点纹理"""
    import random
    num_points = int(width * height * level)
    for _ in range(num_points):
        x = random.randint(0, width - 1)
        y = random.randint(0, height - 1)
        gray = random.randint(200, 240)
        draw.point([x, y], fill=f'#{gray:02x}{gray:02x}{gray:02x}')


def _render_color_blocks(draw, width, height, colors):
    """渲染大色块背景"""
    num_blocks = len(colors)
    block_width = width // num_blocks
    for i, color in enumerate(colors):
        x1 = i * block_width
        x2 = (i + 1) * block_width if i < num_blocks - 1 else width
        draw.rectangle([x1, 0, x2, height], fill=color)


def _render_water_stain(draw, width, height, colors, transparency=0.3):
    """渲染水渍效果"""
    # 简单实现：几个半透明的圆形
    import random
    for color in colors:
        for _ in range(3):
            cx = random.randint(width // 4, width * 3 // 4)
            cy = random.randint(height // 4, height * 3 // 4)
            r = random.randint(width // 6, width // 3)
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)


def _render_paper_texture(draw, width, height, colors, stains=True):
    """渲染纸张纹理"""
    # 基础颜色
    draw.rectangle([0, 0, width, height], fill=colors[0])
    
    # 添加噪点
    _add_noise(draw, width, height, level=0.03)
    
    # 添加污渍
    if stains:
        import random
        for _ in range(3):
            cx = random.randint(width // 4, width * 3 // 4)
            cy = random.randint(height // 4, height * 3 // 4)
            r = random.randint(20, 50)
            stain_color = blend_colors(colors[0], '#8B7355', 0.9)
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=stain_color)


def _add_dots(draw, width, height, dot_color):
    """添加波点"""
    import random
    dot_spacing = 40
    dot_size = 4
    for y in range(0, height, dot_spacing):
        for x in range(0, width, dot_spacing):
            offset_x = random.randint(-5, 5)
            offset_y = random.randint(-5, 5)
            draw.ellipse([x + offset_x - dot_size, y + offset_y - dot_size,
                          x + offset_x + dot_size, y + offset_y + dot_size], fill=dot_color)


def _render_starry_sky(draw, width, height, colors, stars=True, moon=True):
    """渲染星空背景"""
    # 深蓝渐变
    _render_gradient_background(draw, width, height, colors)
    
    # 添加月亮
    if moon:
        moon_x = width * 3 // 4
        moon_y = height // 5
        moon_r = 30
        draw.ellipse([moon_x - moon_r, moon_y - moon_r, moon_x + moon_r, moon_y + moon_r], fill='#FFF9C4')
    
    # 添加星星
    if stars:
        import random
        for _ in range(100):
            x = random.randint(0, width)
            y = random.randint(0, height)
            size = random.randint(1, 3)
            brightness = random.randint(200, 255)
            color = f'#{brightness:02x}{brightness:02x}{brightness:02x}'
            draw.ellipse([x - size, y - size, x + size, y + size], fill=color)


def _render_rainbow_stripes(draw, width, height, colors):
    """渲染彩虹条纹"""
    num_colors = len(colors)
    stripe_width = width // num_colors
    
    for i, color in enumerate(colors):
        x1 = i * stripe_width
        x2 = (i + 1) * stripe_width if i < num_colors - 1 else width
        draw.rectangle([x1, 0, x2, height], fill=color)


# ============== 风格管理类 ==============
class StyleManager:
    """风格管理器"""
    
    def __init__(self, config_path=None):
        self.config_path = config_path or STYLE_CONFIG_PATH
        self._ensure_data_dir()
        self.current_style = self._load_preference()
    
    def _ensure_data_dir(self):
        """确保data目录存在"""
        data_dir = os.path.dirname(self.config_path)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)
    
    def _load_preference(self):
        """加载用户风格偏好"""
        if not os.path.exists(self.config_path):
            return 'paper'  # 默认纸张风格
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('style_id', 'paper')
        except Exception as e:
            print(f"加载风格偏好失败: {e}")
            return 'paper'
    
    def _save_preference(self):
        """保存用户风格偏好"""
        try:
            data = {
                'style_id': self.current_style,
                'updated_at': datetime.now().isoformat(),
            }
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存风格偏好失败: {e}")
            return False
    
    def set_style(self, style_id):
        """设置当前风格
        
        Args:
            style_id: 风格ID
            
        Returns:
            是否设置成功
        """
        if style_id in STYLE_CONFIGS:
            self.current_style = style_id
            self._save_preference()
            return True
        return False
    
    def get_style(self, style_id=None):
        """获取风格配置
        
        Args:
            style_id: 风格ID（可选，默认当前风格）
            
        Returns:
            风格配置字典
        """
        style_id = style_id or self.current_style
        return STYLE_CONFIGS.get(style_id, STYLE_CONFIGS['paper'])
    
    def list_styles(self):
        """列出所有可用风格
        
        Returns:
            [(style_id, name, emoji, description), ...]
        """
        result = []
        for style_id, config in STYLE_CONFIGS.items():
            result.append((
                style_id,
                config['name'],
                config['emoji'],
                config['description']
            ))
        return result
    
    def get_current_style_info(self):
        """获取当前风格信息"""
        config = self.get_style()
        return {
            'id': self.current_style,
            'name': config['name'],
            'emoji': config['emoji'],
            'description': config['description'],
        }
    
    def apply_background(self, draw, width, height, style_id=None):
        """应用风格背景
        
        Args:
            draw: PIL ImageDraw 对象
            width: 画布宽度
            height: 画布高度
            style_id: 风格ID（可选，默认当前风格）
        """
        style_id = style_id or self.current_style
        render_background(draw, style_id, width, height)
    
    def get_card_style(self, style_id=None):
        """获取卡片风格配置"""
        return self.get_style(style_id)['card']
    
    def get_text_style(self, style_id=None):
        """获取文字风格配置"""
        return self.get_style(style_id)['text']
    
    def get_nutrition_colors(self, style_id=None):
        """获取营养条颜色配置"""
        return self.get_style(style_id)['nutrition']


# 全局风格管理器实例
_global_style_manager = None


def get_style_manager():
    """获取全局风格管理器实例"""
    global _global_style_manager
    if _global_style_manager is None:
        _global_style_manager = StyleManager()
    return _global_style_manager


def get_style_help():
    """获取风格系统帮助文本"""
    manager = get_style_manager()
    styles = manager.list_styles()
    current = manager.get_current_style_info()
    
    help_text = "🎨 手账风格系统\n\n"
    help_text += f"当前使用: {current['emoji']} {current['name']} - {current['description']}\n\n"
    help_text += "可用风格:\n"
    
    for style_id, name, emoji, desc in styles:
        marker = "✅" if style_id == current['id'] else "  "
        help_text += f"{marker} {emoji} {name}: {desc}\n"
    
    help_text += "\n使用示例:\n"
    help_text += '  - "切换到水墨风格"\n'
    help_text += '  - "今天用彩虹风格"\n'
    help_text += '  - "列出所有风格"\n'
    
    return help_text


if __name__ == '__main__':
    # 测试
    print("=" * 60)
    print("🎨 风格系统测试")
    print("=" * 60)
    print()
    
    manager = get_style_manager()
    
    print("当前风格:")
    current = manager.get_current_style_info()
    print(f"  {current['emoji']} {current['name']} - {current['description']}")
    print()
    
    print("所有风格:")
    for style_id, name, emoji, desc in manager.list_styles():
        print(f"  {emoji} {name} ({style_id}): {desc}")
    print()
    
    print("切换到水墨风格:")
    manager.set_style('ink_wash')
    current = manager.get_current_style_info()
    print(f"  {current['emoji']} {current['name']}")
    print()
    
    print("✅ 风格系统测试通过")
    print()
    print(get_style_help())
