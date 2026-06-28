#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
卡路里手账 - 饮食运动记录卡片生成器 v15
生成640×580公交卡式精美卡片组
"""

import os
from PIL import Image, ImageDraw, ImageFont
import math
from typing import Dict, List, Tuple, Any

# ==================== v2.5 自检系统 ====================
class DataSelfChecker:
    """
    饮食疗愈手账 - 数据自检系统
    在生成卡片前自动检测所有潜在数据问题
    """
    
    def __init__(self):
        self.warnings = []
        self.errors = []
        self.info = []
        
    def check_meal_data(self, meal_data: Dict[str, Any], meal_name: str = "meal") -> bool:
        """检查单餐数据完整性"""
        all_ok = True
        
        # 1. 检查必须字段
        required_fields = ['foods', 'nutrition', 'kcal']
        for field in required_fields:
            if field not in meal_data:
                self.errors.append(f"{meal_name}: 缺少必填字段 '{field}'")
                all_ok = False
        
        # 2. 检查nutrition字段
        if 'nutrition' in meal_data:
            nut = meal_data['nutrition']
            required_nutrients = ['protein', 'carb', 'fat', 'fiber']
            for nutrient in required_nutrients:
                if nutrient not in nut:
                    self.warnings.append(f"{meal_name}: nutrition缺少字段 '{nutrient}'，将使用默认值0")
                    all_ok = False
                else:
                    value = nut[nutrient]
                    if not isinstance(value, (int, float)):
                        self.errors.append(f"{meal_name}: {nutrient} 不是数字类型 (值: {value})")
                        all_ok = False
                    elif value < 0:
                        self.warnings.append(f"{meal_name}: {nutrient} 为负值 ({value}g)，请检查数据")
        
        # 3. 检查kcal
        if 'kcal' in meal_data:
            kcal = meal_data['kcal']
            if not isinstance(kcal, (int, float)):
                self.errors.append(f"{meal_name}: kcal 不是数字类型 (值: {kcal})")
                all_ok = False
            elif kcal <= 0:
                self.warnings.append(f"{meal_name}: kcal为{value}，请检查数据")
            elif kcal > 2000:
                self.warnings.append(f"{meal_name}: kcal值过大 ({kcal})，请确认是否正确")
        
        # 4. 检查foods列表
        if 'foods' in meal_data:
            foods = meal_data['foods']
            if not isinstance(foods, list):
                self.errors.append(f"{meal_name}: foods 不是列表类型")
                all_ok = False
            elif len(foods) == 0:
                self.warnings.append(f"{meal_name}: foods 列表为空")
        
        return all_ok
    
    def check_all_meals(self, all_meals: Dict[str, Dict]) -> bool:
        """检查所有餐食数据"""
        self.info.append("📋 开始数据自检...")
        
        all_ok = True
        total_foods = 0
        total_kcal = 0
        
        for meal_name, meal_data in all_meals.items():
            meal_ok = self.check_meal_data(meal_data, meal_name)
            all_ok = all_ok and meal_ok
            
            if meal_ok:
                total_kcal += meal_data.get('kcal', 0)
                total_foods += len(meal_data.get('foods', []))
        
        self.info.append(f"📊 总计: {len(all_meals)} 餐, {total_foods} 种食物, {total_kcal} kcal")
        
        # 检查总热量合理性
        if total_kcal < 500:
            self.warnings.append(f"⚠️  总热量偏低 ({total_kcal} kcal)，请确认数据是否完整")
        elif total_kcal > 5000:
            self.warnings.append(f"⚠️  总热量偏高 ({total_kcal} kcal)，请确认是否正确")
        
        return all_ok
    
    def check_platform_compatibility(self) -> bool:
        """检查平台兼容性"""
        import sys
        self.info.append(f"💻 Python版本: {sys.version.split()[0]}")
        
        # 检查PIL字体加载能力
        try:
            font = ImageFont.load_default()
            self.info.append("✅ PIL字体加载: 正常")
            return True
        except Exception as e:
            self.errors.append(f"❌ PIL字体加载失败: {e}")
            return False
    
    def check_image_dimensions(self) -> bool:
        """检查图片尺寸是否合理"""
        global CARD_WIDTH, CARD_HEIGHT
        if CARD_WIDTH < 100 or CARD_HEIGHT < 100:
            self.errors.append(f"❌ 卡片尺寸过小: {CARD_WIDTH}x{CARD_HEIGHT}")
            return False
        if CARD_WIDTH > 2000 or CARD_HEIGHT > 2000:
            self.warnings.append(f"⚠️  卡片尺寸较大: {CARD_WIDTH}x{CARD_HEIGHT}，可能影响性能")
        self.info.append(f"📐 卡片尺寸: {CARD_WIDTH}x{CARD_HEIGHT}")
        return True
    
    def run_full_check(self, all_meals: Dict[str, Dict] = None) -> Tuple[bool, str]:
        """运行完整自检"""
        self.warnings = []
        self.errors = []
        self.info = []
        
        self.info.append("=" * 50)
        self.info.append("🚀 饮食疗愈手账 v2.5 - 数据自检系统")
        self.info.append("=" * 50)
        
        # 1. 平台兼容性检查
        self.check_platform_compatibility()
        
        # 2. 图片尺寸检查
        self.check_image_dimensions()
        
        # 3. 数据检查（如果有数据）
        if all_meals:
            self.check_all_meals(all_meals)
        
        # 4. 生成报告
        self.info.append("")
        self.info.append("=" * 50)
        self.info.append("📝 自检报告")
        self.info.append("=" * 50)
        
        if self.errors:
            self.info.append(f"❌ 错误: {len(self.errors)} 项")
            for e in self.errors:
                self.info.append(f"   {e}")
        
        if self.warnings:
            self.info.append(f"⚠️  警告: {len(self.warnings)} 项")
            for w in self.warnings:
                self.info.append(f"   {w}")
        
        if not self.errors and not self.warnings:
            self.info.append("✅ 完美！所有检查通过，数据健康")
        
        self.info.append("=" * 50)
        
        # 输出到控制台
        report = "\n".join(self.info)
        print(report)
        
        # 返回结果
        success = len(self.errors) == 0
        return success, report

# 全局自检实例
self_checker = DataSelfChecker()

# v2.1 新增模块引用
try:
    from food_mood_analyzer import get_food_mood, calculate_daily_mood_summary
except ImportError:
    get_food_mood = lambda x: {"mood": "happy", "emoji": "😊", "name": "开心食物"}
    calculate_daily_mood_summary = lambda x: {}

try:
    from emoji_stickers import add_sticker, get_stickers, clear_stickers, CARD_STICKERS
except ImportError:
    add_sticker = lambda *args: False
    get_stickers = lambda x: []
    clear_stickers = lambda: None
    CARD_STICKERS = {}

try:
    from animal_blind_box import match_diet_animal, get_animal_info
except ImportError:
    match_diet_animal = lambda *args: ("小猫咪", "🐱", "不挑食不浪费，悠哉悠哉刚刚好")
    get_animal_info = lambda x: None

# ==================== 配置 ====================
CARD_WIDTH = 640
CARD_HEIGHT = 580

# 配色方案
COLORS = {
    'breakfast': {'bg': '#FFF5E6', 'accent': '#FF9F43', 'text': '#D35400'},  # 橙色早餐
    'lunch': {'bg': '#E8F8F5', 'accent': '#1ABC9C', 'text': '#16A085'},      # 绿色午餐
    'dinner': {'bg': '#E8EAFA', 'accent': '#8B5CF6', 'text': '#7C3AED'},     # 紫色晚餐
    'snack1': {'bg': '#F5EEF8', 'accent': '#9B59B6', 'text': '#8E44AD'},    # 紫色加餐1
    'snack2': {'bg': '#FDEDEC', 'accent': '#E74C3C', 'text': '#C0392B'},      # 红色加餐2
    'exercise': {'bg': '#EBF5FB', 'accent': '#3498DB', 'text': '#2980B9'},   # 蓝色运动
    'consume': {'bg': '#FEF9E7', 'accent': '#F39C12', 'text': '#D68910'},    # 暖橙消耗
    'summary': {'bg': '#EEF2FF', 'accent': '#667EEA', 'text': '#5A67D8'},    # 蓝色总结
}

# 营养模板 (减脂男/减脂女/增肌)
NUTRITION_TEMPLATES = {
    'male': {'kcal': 1500, 'protein': 113, 'carb': 150, 'fat': 50},
    'female': {'kcal': 1200, 'protein': 90, 'carb': 120, 'fat': 40},
    'muscle': {'kcal': 2200, 'protein': 165, 'carb': 248, 'fat': 61},
}

# ==================== 工具函数 ====================
def hex_to_rgb(hex_color):
    """hex转rgb"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def load_font(size, path=None):
    """加载字体"""
    if path and os.path.exists(path):
        return ImageFont.truetype(path, size)
    # 优先使用支持中文的字体（NotoColorEmoji有PIL兼容性问题）
    for font_path in ['/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc',
                      '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
                      '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
                      '/System/Library/Fonts/Apple Color Emoji.ttc',
                      '/System/Library/Fonts/Hiragino Sans GB.ttc']:
        if os.path.exists(font_path):
            return ImageFont.truetype(font_path, size)
    return ImageFont.load_default()

def load_font_regular(size):
    """加载常规字体"""
    for font_path in ['/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
                      '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc',
                      '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                      '/System/Library/Fonts/Apple Color Emoji.ttc',
                      '/System/Library/Fonts/Hiragino Sans GB.ttc']:
        if os.path.exists(font_path):
            return ImageFont.truetype(font_path, size)
    return ImageFont.load_default()

def draw_rounded_rect(draw, xy, radius, fill, outline=None, width=1):
    """绘制圆角矩形"""
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=fill, outline=outline, width=width)

def draw_progress_bar(draw, x, y, width, height, progress, fill_color, bg_color='#E0E0E0'):
    """绘制进度条"""
    # 背景
    draw.rounded_rectangle([x, y, x+width, y+height], radius=height//2, fill=bg_color)
    # 进度
    if progress > 0:
        actual_width = int(width * min(progress, 1.0))
        if actual_width > 0:
            draw.rounded_rectangle([x, y, x+actual_width, y+height], radius=height//2, fill=fill_color)

# ==================== 饮食小动物 ====================
ANIMAL_PROFILES = [
    # (id, name, emoji, slogan, condition_func, draw_func)
    # condition_func takes (protein_pct, carb_pct, fat_pct, kcal_pct, snack_count) → bool
]

def match_diet_animal(protein_pct, carb_pct, fat_pct, kcal_pct, snack_count):
    """根据营养比例匹配饮食小动物，返回 (name, emoji, slogan, draw_func)"""
    animals = [
        ('小猎豹', '🐅', '蛋白质是猎物，全速冲刺不手软',
         lambda p,c,f,k,s: p > 35 and c < 35),
        ('小仓鼠', '🐹', '腮帮子塞满碳水，圆滚滚好安心',
         lambda p,c,f,k,s: c > 55 and p < 20),
        ('小狐狸', '🦊', '什么都吃一点，精明得很到位',
         lambda p,c,f,k,s: 15 <= p <= 40 and 30 <= c <= 60 and 10 <= f <= 40),
        ('小松鼠', '🐿️', '东藏一口西囤一点，小嘴不停歇',
         lambda p,c,f,k,s: s >= 2),
        ('小兔子', '🐰', '嚼嚼绿叶就满足，轻盈感满分',
         lambda p,c,f,k,s: k < 80),
        ('小熊', '🐻', '吃得饱饱的，离冬眠又近一步',
         lambda p,c,f,k,s: f > 35 and k > 90),
    ]
    for name, emoji, slogan, cond in animals:
        if cond(protein_pct, carb_pct, fat_pct, kcal_pct, snack_count):
            return name, emoji, slogan
    return '小猫咪', '🐱', '不挑食不浪费，悠哉悠哉刚刚好'

def draw_animal_cheetah(draw, cx, cy, size=40):
    """画小猎豹 - 圆脸+小圆耳+斑点"""
    s = size
    # 脸
    draw.ellipse([cx-s, cy-s, cx+s, cy+s], fill='#F4A460', outline='#D2691E', width=2)
    # 耳朵
    draw.ellipse([cx-s+2, cy-s-8, cx-s+14, cy-s+8], fill='#F4A460', outline='#D2691E', width=1)
    draw.ellipse([cx+s-14, cy-s-8, cx+s-2, cy-s+8], fill='#F4A460', outline='#D2691E', width=1)
    # 内耳
    draw.ellipse([cx-s+5, cy-s-4, cx-s+11, cy-s+4], fill='#FFD700')
    draw.ellipse([cx+s-11, cy-s-4, cx+s-5, cy-s+4], fill='#FFD700')
    # 眼睛
    draw.ellipse([cx-12, cy-8, cx-4, cy+2], fill='white', outline='#333', width=1)
    draw.ellipse([cx+4, cy-8, cx+12, cy+2], fill='white', outline='#333', width=1)
    draw.ellipse([cx-9, cy-5, cx-5, cy+0], fill='#333')
    draw.ellipse([cx+5, cy-5, cx+9, cy+0], fill='#333')
    # 鼻子
    draw.ellipse([cx-3, cy+8, cx+3, cy+13], fill='#D2691E')
    # 泪痕(猎豹特征)
    draw.line([cx-10, cy+2, cx-6, cy+10], fill='#333', width=2)
    draw.line([cx+10, cy+2, cx+6, cy+10], fill='#333', width=2)
    # 斑点
    for dx, dy in [(-18,5), (18,5), (-10,18), (10,18), (0,22)]:
        draw.ellipse([cx+dx-2, cy+dy-2, cx+dx+2, cy+dy+2], fill='#8B4513')

def draw_animal_hamster(draw, cx, cy, size=40):
    """画小仓鼠 - 圆脸+大圆腮+小耳"""
    s = size
    # 身体/脸（更圆）
    draw.ellipse([cx-s, cy-s+5, cx+s, cy+s+5], fill='#FAEBD7', outline='#DEB887', width=2)
    # 耳朵（小圆）
    draw.ellipse([cx-s+4, cy-s-2, cx-s+16, cy-s+12], fill='#FAEBD7', outline='#DEB887', width=1)
    draw.ellipse([cx+s-16, cy-s-2, cx+s-4, cy-s+12], fill='#FAEBD7', outline='#DEB887', width=1)
    draw.ellipse([cx-s+7, cy-s+1, cx-s+13, cy-s+9], fill='#FFB6C1')
    draw.ellipse([cx+s-13, cy-s+1, cx+s-7, cy-s+9], fill='#FFB6C1')
    # 腮帮子（粉色大圆）
    draw.ellipse([cx-s+4, cy-2, cx-s+22, cy+16], fill='#FFB6C1')
    draw.ellipse([cx+s-22, cy-2, cx+s-4, cy+16], fill='#FFB6C1')
    # 眼睛
    draw.ellipse([cx-10, cy-4, cx-3, cy+4], fill='#333')
    draw.ellipse([cx+3, cy-4, cx+10, cy+4], fill='#333')
    # 高光
    draw.ellipse([cx-8, cy-3, cx-5, cy+0], fill='white')
    draw.ellipse([cx+5, cy-3, cx+8, cy+0], fill='white')
    # 鼻子
    draw.ellipse([cx-3, cy+10, cx+3, cy+14], fill='#FF69B4')
    # 嘴巴
    draw.arc([cx-6, cy+14, cx+6, cy+22], start=0, end=180, fill='#DEB887', width=1)

def draw_animal_fox(draw, cx, cy, size=40):
    """画小狐狸 - 尖耳+白色面部"""
    s = size
    # 脸
    draw.ellipse([cx-s, cy-s+5, cx+s, cy+s+5], fill='#FF8C00', outline='#CC6600', width=2)
    # 尖耳朵（三角）
    draw.polygon([(cx-s+5, cy-s+5), (cx-s+2, cy-s-18), (cx-s+18, cy-s+5)], fill='#FF8C00', outline='#CC6600')
    draw.polygon([(cx+s-18, cy-s+5), (cx+s-2, cy-s-18), (cx+s-5, cy-s+5)], fill='#FF8C00', outline='#CC6600')
    # 耳内
    draw.polygon([(cx-s+8, cy-s+3), (cx-s+5, cy-s-12), (cx-s+15, cy-s+3)], fill='#1a1a1a')
    draw.polygon([(cx+s-15, cy-s+3), (cx+s-5, cy-s-12), (cx+s-8, cy-s+3)], fill='#1a1a1a')
    # 白色面部
    draw.ellipse([cx-s+8, cy-5, cx+s-8, cy+s+3], fill='white')
    # 眼睛
    draw.ellipse([cx-14, cy-6, cx-5, cy+3], fill='#333')
    draw.ellipse([cx+5, cy-6, cx+14, cy+3], fill='#333')
    draw.ellipse([cx-11, cy-4, cx-8, cy-1], fill='white')
    draw.ellipse([cx+8, cy-4, cx+11, cy-1], fill='white')
    # 鼻子（小黑三角）
    draw.polygon([(cx-4, cy+8), (cx+4, cy+8), (cx, cy+13)], fill='#333')
    # 嘴巴
    draw.line([cx, cy+13, cx, cy+17], fill='#333', width=1)
    draw.arc([cx-8, cy+12, cx, cy+20], start=270, end=360, fill='#333', width=1)
    draw.arc([cx, cy+12, cx+8, cy+20], start=180, end=270, fill='#333', width=1)

def draw_animal_squirrel(draw, cx, cy, size=40):
    """画小松鼠 - 大尾巴+圆耳"""
    s = size
    # 大尾巴（在身后）
    draw.pieslice([cx+s-5, cy-s+10, cx+s+28, cy+s+15], start=30, end=330, fill='#CD853F', outline='#8B6914', width=2)
    # 脸
    draw.ellipse([cx-s, cy-s+5, cx+s, cy+s+5], fill='#D2B48C', outline='#A0845C', width=2)
    # 圆耳
    draw.ellipse([cx-s+2, cy-s-6, cx-s+14, cy-s+8], fill='#D2B48C', outline='#A0845C', width=1)
    draw.ellipse([cx+s-14, cy-s-6, cx+s-2, cy-s+8], fill='#D2B48C', outline='#A0845C', width=1)
    # 内耳
    draw.ellipse([cx-s+5, cy-s-2, cx-s+11, cy-s+5], fill='#DEB887')
    draw.ellipse([cx+s-11, cy-s-2, cx+s-5, cy-s+5], fill='#DEB887')
    # 白色面部
    draw.ellipse([cx-s+10, cy-5, cx+s-10, cy+s], fill='#FAEBD7')
    # 眼睛
    draw.ellipse([cx-12, cy-6, cx-4, cy+2], fill='#333')
    draw.ellipse([cx+4, cy-6, cx+12, cy+2], fill='#333')
    draw.ellipse([cx-10, cy-4, cx-7, cy-1], fill='white')
    draw.ellipse([cx+7, cy-4, cx+10, cy-1], fill='white')
    # 鼻子
    draw.ellipse([cx-3, cy+8, cx+3, cy+12], fill='#333')
    # 腮帮
    draw.ellipse([cx-s+8, cy+4, cx-s+20, cy+14], fill='#FFDAB9')
    draw.ellipse([cx+s-20, cy+4, cx+s-8, cy+14], fill='#FFDAB9')

def draw_animal_rabbit(draw, cx, cy, size=40):
    """画小兔子 - 长耳朵+白脸"""
    s = size
    # 长耳朵
    draw.ellipse([cx-14, cy-s-28, cx-4, cy-s+5], fill='white', outline='#DDD', width=2)
    draw.ellipse([cx+4, cy-s-28, cx+14, cy-s+5], fill='white', outline='#DDD', width=2)
    # 耳内粉
    draw.ellipse([cx-11, cy-s-22, cx-7, cy-s+2], fill='#FFB6C1')
    draw.ellipse([cx+7, cy-s-22, cx+11, cy-s+2], fill='#FFB6C1')
    # 脸
    draw.ellipse([cx-s, cy-s+5, cx+s, cy+s+5], fill='white', outline='#DDD', width=2)
    # 眼睛
    draw.ellipse([cx-14, cy-5, cx-5, cy+4], fill='#FF69B4')
    draw.ellipse([cx+5, cy-5, cx+14, cy+4], fill='#FF69B4')
    draw.ellipse([cx-11, cy-3, cx-8, cy+1], fill='white')
    draw.ellipse([cx+8, cy-3, cx+11, cy+1], fill='white')
    # 鼻子
    draw.ellipse([cx-3, cy+8, cx+3, cy+12], fill='#FF69B4')
    # 嘴
    draw.line([cx, cy+12, cx, cy+16], fill='#DDD', width=1)
    draw.arc([cx-6, cy+12, cx, cy+18], start=270, end=360, fill='#DDD', width=1)
    draw.arc([cx, cy+12, cx+6, cy+18], start=180, end=270, fill='#DDD', width=1)
    # 腮红
    draw.ellipse([cx-s+5, cy+4, cx-s+17, cy+12], fill='#FFE4E1')
    draw.ellipse([cx+s-17, cy+4, cx+s-5, cy+12], fill='#FFE4E1')

def draw_animal_bear(draw, cx, cy, size=40):
    """画小熊 - 圆耳+棕色圆脸"""
    s = size
    # 耳朵（大圆）
    draw.ellipse([cx-s-2, cy-s-5, cx-s+14, cy-s+14], fill='#8B6914', outline='#6B4F12', width=2)
    draw.ellipse([cx+s-14, cy-s-5, cx+s+2, cy-s+14], fill='#8B6914', outline='#6B4F12', width=2)
    # 内耳
    draw.ellipse([cx-s+1, cy-s-1, cx-s+11, cy-s+10], fill='#D2A679')
    draw.ellipse([cx+s-11, cy-s-1, cx+s-1, cy-s+10], fill='#D2A679')
    # 脸
    draw.ellipse([cx-s, cy-s+5, cx+s, cy+s+5], fill='#8B6914', outline='#6B4F12', width=2)
    # 嘴部区域
    draw.ellipse([cx-s+10, cy+2, cx+s-10, cy+s], fill='#D2A679')
    # 眼睛
    draw.ellipse([cx-14, cy-4, cx-6, cy+5], fill='#333')
    draw.ellipse([cx+6, cy-4, cx+14, cy+5], fill='#333')
    draw.ellipse([cx-12, cy-2, cx-9, cy+2], fill='white')
    draw.ellipse([cx+9, cy-2, cx+12, cy+2], fill='white')
    # 鼻子
    draw.ellipse([cx-5, cy+8, cx+5, cy+14], fill='#333')
    draw.ellipse([cx-2, cy+9, cx+2, cy+12], fill='#555')
    # 嘴巴
    draw.arc([cx-8, cy+14, cx, cy+22], start=270, end=360, fill='#6B4F12', width=1)
    draw.arc([cx, cy+14, cx+8, cy+22], start=180, end=270, fill='#6B4F12', width=1)

def draw_animal_cat(draw, cx, cy, size=40):
    """画小猫咪 - 三角耳+胡须（默认兜底）"""
    s = size
    # 耳朵（三角）
    draw.polygon([(cx-s+5, cy-s+5), (cx-s+2, cy-s-18), (cx-s+18, cy-s+5)], fill='#A9A9A9', outline='#808080')
    draw.polygon([(cx+s-18, cy-s+5), (cx+s-2, cy-s-18), (cx+s-5, cy-s+5)], fill='#A9A9A9', outline='#808080')
    # 内耳粉
    draw.polygon([(cx-s+8, cy-s+3), (cx-s+6, cy-s-12), (cx-s+15, cy-s+3)], fill='#FFB6C1')
    draw.polygon([(cx+s-15, cy-s+3), (cx+s-6, cy-s-12), (cx+s-8, cy-s+3)], fill='#FFB6C1')
    # 脸
    draw.ellipse([cx-s, cy-s+5, cx+s, cy+s+5], fill='#C0C0C0', outline='#A0A0A0', width=2)
    # 眼睛
    draw.ellipse([cx-14, cy-6, cx-5, cy+3], fill='#90EE90', outline='#333', width=1)
    draw.ellipse([cx+5, cy-6, cx+14, cy+3], fill='#90EE90', outline='#333', width=1)
    draw.ellipse([cx-10, cy-4, cx-6, cy+1], fill='#333')
    draw.ellipse([cx+6, cy-4, cx+10, cy+1], fill='#333')
    # 鼻子
    draw.polygon([(cx-3, cy+7), (cx+3, cy+7), (cx, cy+10)], fill='#FF69B4')
    # 嘴
    draw.line([cx, cy+10, cx, cy+14], fill='#808080', width=1)
    draw.arc([cx-8, cy+10, cx, cy+18], start=270, end=360, fill='#808080', width=1)
    draw.arc([cx, cy+10, cx+8, cy+18], start=180, end=270, fill='#808080', width=1)
    # 胡须
    draw.line([cx-s+5, cy+6, cx-8, cy+8], fill='#808080', width=1)
    draw.line([cx-s+3, cy+10, cx-8, cy+10], fill='#808080', width=1)
    draw.line([cx+8, cy+8, cx+s-5, cy+6], fill='#808080', width=1)
    draw.line([cx+8, cy+10, cx+s-3, cy+10], fill='#808080', width=1)
    # 腮红
    draw.ellipse([cx-s+6, cy+4, cx-s+18, cy+12], fill='#FFE4E1')
    draw.ellipse([cx+s-18, cy+4, cx+s-6, cy+12], fill='#FFE4E1')

ANIMAL_DRAW_FUNCS = {
    '小猎豹': draw_animal_cheetah,
    '小仓鼠': draw_animal_hamster,
    '小狐狸': draw_animal_fox,
    '小松鼠': draw_animal_squirrel,
    '小兔子': draw_animal_rabbit,
    '小熊': draw_animal_bear,
    '小猫咪': draw_animal_cat,
}

# ==================== v2.1 手绘彩色贴纸系统（小动物同款方案）====================
def draw_sticker_star(draw, cx, cy, size=10):
    """手绘星星 - 金黄色"""
    s = size
    # 简单的5角星用多边形画
    points = []
    for i in range(5):
        angle = i * 72 - 90  # -90让星星朝上
        import math
        outer_x = cx + s * math.cos(math.radians(angle))
        outer_y = cy + s * math.sin(math.radians(angle))
        points.append((outer_x, outer_y))
        inner_angle = angle + 36
        inner_x = cx + (s//2) * math.cos(math.radians(inner_angle))
        inner_y = cy + (s//2) * math.sin(math.radians(inner_angle))
        points.append((inner_x, inner_y))
    draw.polygon(points, fill='#FFD700', outline='#FFA500', width=1)

def draw_sticker_heart(draw, cx, cy, size=10):
    """手绘爱心 - 粉色"""
    s = size
    # 两个圆+一个三角形组成爱心
    draw.ellipse([cx-s, cy-s//2, cx, cy+s//2], fill='#FF69B4', outline='#FF1493', width=1)
    draw.ellipse([cx, cy-s//2, cx+s, cy+s//2], fill='#FF69B4', outline='#FF1493', width=1)
    draw.polygon([(cx-s, cy), (cx, cy+s), (cx+s, cy)], fill='#FF69B4', outline='#FF1493', width=1)

def draw_sticker_sun(draw, cx, cy, size=10):
    """手绘太阳 - 橙黄色"""
    s = size
    # 中心圆
    draw.ellipse([cx-s//2, cy-s//2, cx+s//2, cy+s//2], fill='#FFA500', outline='#FF8C00', width=1)
    # 光芒
    for i in range(8):
        import math
        angle = i * 45
        x1 = cx + (s//2 + 2) * math.cos(math.radians(angle))
        y1 = cy + (s//2 + 2) * math.sin(math.radians(angle))
        x2 = cx + s * math.cos(math.radians(angle))
        y2 = cy + s * math.sin(math.radians(angle))
        draw.line([(x1, y1), (x2, y2)], fill='#FFA500', width=2)

def draw_sticker_leaf(draw, cx, cy, size=10):
    """手绘叶子 - 绿色"""
    s = size
    draw.ellipse([cx-s, cy-s//2, cx+s, cy+s//2], fill='#90EE90', outline='#32CD32', width=1)
    draw.line([(cx-s, cy), (cx+s, cy)], fill='#32CD32', width=1)

def draw_sticker_flower(draw, cx, cy, size=10):
    """手绘小花朵 - 紫色"""
    s = size
    # 5个花瓣
    import math
    for i in range(5):
        angle = i * 72
        px = cx + (s//2) * math.cos(math.radians(angle))
        py = cy + (s//2) * math.sin(math.radians(angle))
        draw.ellipse([px-4, py-4, px+4, py+4], fill='#DDA0DD', outline='#BA55D3', width=1)
    # 花心
    draw.ellipse([cx-3, cy-3, cx+3, cy+3], fill='#FFD700', outline='#FFA500', width=1)

# 贴纸绘制函数字典
STICKER_DRAW_FUNCS = {
    'star': draw_sticker_star,
    'heart': draw_sticker_heart,
    'sun': draw_sticker_sun,
    'leaf': draw_sticker_leaf,
    'flower': draw_sticker_flower,
}

def draw_sticker(draw, sticker_type, x, y, size=10):
    """绘制贴纸的快捷函数"""
    func = STICKER_DRAW_FUNCS.get(sticker_type, draw_sticker_star)
    func(draw, x, y, size)

def draw_yoga_meditation(draw, x, y, color='#CCCCCC'):
    """瑜伽1：冥想坐姿 - 早餐/基础代谢"""
    rgb = hex_to_rgb(color)
    alpha = 100
    draw.ellipse([x, y, x+28, y+28], fill=(*rgb, alpha))
    draw.line([x+14, y+28, x+14, y+52], fill=(*rgb, alpha), width=3)
    draw.line([x+14, y+38, x-3, y+48], fill=(*rgb, alpha), width=3)
    draw.line([x+14, y+38, x+31, y+48], fill=(*rgb, alpha), width=3)
    draw.line([x+14, y+52, x, y+68], fill=(*rgb, alpha), width=3)
    draw.line([x+14, y+52, x+28, y+68], fill=(*rgb, alpha), width=3)

def draw_yoga_tree(draw, x, y, color='#CCCCCC'):
    """瑜伽2：树式 - 午餐/总结"""
    rgb = hex_to_rgb(color)
    alpha = 100
    draw.ellipse([x+2, y, x+26, y+24], fill=(*rgb, alpha))
    draw.line([x+14, y+24, x+14, y+48], fill=(*rgb, alpha), width=3)
    draw.line([x+14, y+34, x+2, y+43], fill=(*rgb, alpha), width=3)
    draw.line([x+14, y+34, x+26, y+43], fill=(*rgb, alpha), width=3)
    draw.line([x+14, y+48, x+14, y+68], fill=(*rgb, alpha), width=3)
    draw.line([x+14, y+50, x+26, y+58], fill=(*rgb, alpha), width=3)

def draw_yoga_downward(draw, x, y, color='#CCCCCC'):
    """瑜伽3：下犬式 - 加餐1"""
    rgb = hex_to_rgb(color)
    alpha = 100
    draw.ellipse([x+15, y+3, x+35, y+23], fill=(*rgb, alpha))
    draw.line([x+25, y+23, x+12, y+42], fill=(*rgb, alpha), width=3)
    draw.line([x+25, y+23, x+38, y+42], fill=(*rgb, alpha), width=3)
    draw.line([x+12, y+42, x+3, y+65], fill=(*rgb, alpha), width=3)
    draw.line([x+38, y+42, x+47, y+65], fill=(*rgb, alpha), width=3)

def draw_yoga_warrior(draw, x, y, color='#CCCCCC'):
    """瑜伽4：战士式 - 加餐2"""
    rgb = hex_to_rgb(color)
    alpha = 100
    draw.ellipse([x+2, y+2, x+26, y+26], fill=(*rgb, alpha))
    draw.line([x+14, y+26, x+14, y+50], fill=(*rgb, alpha), width=3)
    draw.line([x+14, y+31, x-8, y+40], fill=(*rgb, alpha), width=3)
    draw.line([x+14, y+31, x+36, y+40], fill=(*rgb, alpha), width=3)
    draw.line([x+14, y+50, x-3, y+73], fill=(*rgb, alpha), width=3)
    draw.line([x+14, y+50, x+31, y+73], fill=(*rgb, alpha), width=3)

def draw_yoga_child(draw, x, y, color='#CCCCCC'):
    """瑜伽5：婴儿式 - 运动卡"""
    rgb = hex_to_rgb(color)
    alpha = 100
    draw.ellipse([x+3, y+10, x+27, y+30], fill=(*rgb, alpha))
    draw.line([x+15, y+30, x+15, y+53], fill=(*rgb, alpha), width=3)
    draw.line([x+15, y+35, x, y+48], fill=(*rgb, alpha), width=3)
    draw.line([x+15, y+35, x+30, y+48], fill=(*rgb, alpha), width=3)
    draw.line([x+15, y+53, x-5, y+53], fill=(*rgb, alpha), width=3)
    draw.line([x+15, y+53, x+35, y+53], fill=(*rgb, alpha), width=3)

# 瑜伽动作库 - 每张卡片对应不同姿势
YOGA_POSES = {
    'breakfast': draw_yoga_meditation,  # 早餐 - 冥想
    'lunch': draw_yoga_tree,            # 午餐 - 树式
    'snack1': draw_yoga_downward,       # 加餐1 - 下犬式
    'snack2': draw_yoga_warrior,        # 加餐2 - 战士式
    'exercise': draw_yoga_child,        # 运动 - 婴儿式
    'basal': draw_yoga_meditation,      # 基础代谢 - 冥想
    'summary': draw_yoga_tree,          # 总结 - 树式
    'default': draw_yoga_meditation,
}

def draw_yoga_watermark(draw, x, y, card_type='default', color='#CCCCCC', scale=0.7):
    """绘制瑜伽人物暗纹（根据卡片类型显示不同动作）
    scale: 缩放比例，默认0.7（缩小到70%）
    """
    pose_func = YOGA_POSES.get(card_type, YOGA_POSES['default'])
    
    # 创建临时绘制上下文来实现缩放
    from PIL import Image as PILImage
    temp_size = (100, 100)  # 足够大的临时画布
    temp_img = PILImage.new('RGBA', temp_size, (0, 0, 0, 0))
    temp_draw = ImageDraw.Draw(temp_img)
    
    # 在临时画布上绘制原始大小
    pose_func(temp_draw, 10, 10, color)
    
    # 缩放
    new_size = (int(temp_size[0] * scale), int(temp_size[1] * scale))
    scaled_img = temp_img.resize(new_size, PILImage.Resampling.LANCZOS)
    
    # 粘贴到主画布
    draw._image.paste(scaled_img, (x, y), scaled_img)

# ==================== v2.2 手绘图标系统（全面替代Emoji）====================
def draw_icon_clock(draw, cx, cy, size=10, color='#666666'):
    """时钟图标"""
    s = size
    draw.ellipse([cx-s, cy-s, cx+s, cy+s], fill='white', outline=hex_to_rgb(color), width=1)
    draw.line([cx, cy, cx, cy-s+3], fill=hex_to_rgb(color), width=2)
    draw.line([cx, cy, cx+s-3, cy], fill=hex_to_rgb(color), width=2)

def draw_icon_list(draw, cx, cy, size=10, color='#666666'):
    """清单图标"""
    s = size
    draw.rectangle([cx-s, cy-s, cx+s-2, cy+s], fill='white', outline=hex_to_rgb(color), width=1)
    for i in range(3):
        draw.line([cx-s+3, cy-s+3+i*5, cx+s-6, cy-s+3+i*5], fill=hex_to_rgb(color), width=1)

def draw_icon_fire(draw, cx, cy, size=12, color='#FF6B6B'):
    """火焰图标"""
    s = size
    draw.ellipse([cx-s, cy-s+5, cx+s, cy+s], fill=hex_to_rgb(color))
    draw.ellipse([cx-s//2, cy-s, cx+s//2, cy+s//2], fill=hex_to_rgb(color))

def draw_icon_chart(draw, cx, cy, size=10, color='#666666'):
    """图表图标"""
    s = size
    draw.rectangle([cx-s, cy-s, cx+s, cy+s], fill='white', outline=hex_to_rgb(color), width=1)
    draw.rectangle([cx-s+4, cy-s+2, cx-s+8, cy+s], fill='#1ABC9C')
    draw.rectangle([cx-s+10, cy-s+6, cx-s+14, cy+s], fill='#F39C12')
    draw.rectangle([cx-s+16, cy-s+4, cx-s+20, cy+s], fill='#E74C3C')

def draw_icon_muscle(draw, cx, cy, size=12, color='#1ABC9C'):
    """肌肉图标"""
    s = size
    draw.ellipse([cx-s, cy-s//2, cx+s, cy+s//2], fill=hex_to_rgb(color))

def draw_icon_brain(draw, cx, cy, size=12, color='#F39C12'):
    """大脑图标"""
    s = size
    draw.ellipse([cx-s, cy-s//2, cx, cy+s//2], fill=hex_to_rgb(color))
    draw.ellipse([cx, cy-s//2, cx+s, cy+s//2], fill=hex_to_rgb(color))

def draw_icon_butter(draw, cx, cy, size=12, color='#E74C3C'):
    """黄油图标"""
    s = size
    draw.rectangle([cx-s, cy-s//2, cx+s, cy+s//2], fill=hex_to_rgb(color))
    draw.line([cx-s//2, cy-s//2, cx+s//2, cy+s//2], fill='white', width=2)

def draw_icon_bulb(draw, cx, cy, size=12, color='#FFD93D'):
    """灯泡/建议图标"""
    s = size
    draw.ellipse([cx-s, cy-s, cx+s, cy+s], fill=hex_to_rgb(color), outline='#FFA500', width=1)

def draw_icon_run(draw, cx, cy, size=12, color='#3498DB'):
    """跑步图标"""
    s = size
    draw.ellipse([cx-s//2, cy-s, cx+s//2, cy-s//3], fill=hex_to_rgb(color))
    draw.line([cx, cy-s//3, cx, cy+s//3], fill=hex_to_rgb(color), width=2)

def draw_icon_weight(draw, cx, cy, size=12, color='#9B59B6'):
    """举重图标"""
    s = size
    draw.rectangle([cx-s, cy-s//3, cx+s, cy], fill=hex_to_rgb(color))

def draw_icon_yoga(draw, cx, cy, size=12, color='#1ABC9C'):
    """瑜伽图标"""
    s = size
    draw.ellipse([cx-s//2, cy-s, cx+s//2, cy-s//3], fill=hex_to_rgb(color))
    draw.line([cx, cy-s//3, cx, cy+s//3], fill=hex_to_rgb(color), width=2)

def draw_icon_walk(draw, cx, cy, size=12, color='#F39C12'):
    """步行图标"""
    s = size
    draw.ellipse([cx-s//2, cy-s, cx+s//2, cy-s//3], fill=hex_to_rgb(color))
    draw.line([cx, cy-s//3, cx, cy+s//3], fill=hex_to_rgb(color), width=2)

def draw_icon_lightning(draw, cx, cy, size=12, color='#F39C12'):
    """闪电图标"""
    s = size
    draw.polygon([(cx, cy-s), (cx+s//2, cy), (cx, cy), (cx+s//2, cy+s)], fill=hex_to_rgb(color))

def draw_icon_dna(draw, cx, cy, size=12, color='#3498DB'):
    """DNA图标"""
    s = size
    draw.line([cx-s, cy-s, cx+s, cy+s], fill=hex_to_rgb(color), width=2)
    draw.line([cx+s, cy-s, cx-s, cy+s], fill=hex_to_rgb(color), width=2)

def draw_icon_warning(draw, cx, cy, size=12, color='#FF6B6B'):
    """警告图标"""
    s = size
    draw.polygon([(cx, cy-s), (cx+s, cy+s), (cx-s, cy+s)], fill=hex_to_rgb(color))

def draw_icon_check(draw, cx, cy, size=12, color='#4ECDC4'):
    """对勾图标"""
    s = size
    draw.ellipse([cx-s, cy-s, cx+s, cy+s], fill=hex_to_rgb(color))
    draw.line([cx-s+4, cy, cx-2, cy+s-3], fill='white', width=2)
    draw.line([cx-2, cy+s-3, cx+s-4, cy-s+4], fill='white', width=2)

def draw_icon_sparkle(draw, cx, cy, size=10, color='#9B59B6'):
    """闪光图标"""
    s = size
    draw_sticker_star(draw, cx, cy, s)

def draw_icon_party(draw, cx, cy, size=10, color='#E74C3C'):
    """派对图标"""
    s = size
    draw.ellipse([cx-s, cy-s, cx+s, cy+s], fill=hex_to_rgb(color))

def draw_icon_thumbsup(draw, cx, cy, size=10, color='#1ABC9C'):
    """点赞图标"""
    s = size
    draw.ellipse([cx-s, cy, cx+s, cy+s], fill=hex_to_rgb(color))

def draw_icon_fork(draw, cx, cy, size=10, color='#9B59B6'):
    """餐具图标"""
    s = size
    draw.line([cx-s//2, cy-s, cx-s//2, cy+s], fill=hex_to_rgb(color), width=2)
    draw.line([cx+s//2, cy-s, cx+s//2, cy+s], fill=hex_to_rgb(color), width=2)

# 食物图标（手绘版）
def draw_food_apple(draw, cx, cy, size=10):
    """苹果"""
    draw.ellipse([cx-size, cy-size, cx+size, cy+size], fill='#FF6B6B')

def draw_food_egg(draw, cx, cy, size=10):
    """鸡蛋"""
    draw.ellipse([cx-size, cy-size-3, cx+size, cy+size+3], fill='#FFF8DC')

def draw_food_veggie(draw, cx, cy, size=10):
    """蔬菜"""
    draw.ellipse([cx-size, cy-size//2, cx+size, cy+size//2], fill='#90EE90')

def draw_food_sweet(draw, cx, cy, size=10):
    """红薯"""
    draw.ellipse([cx-size, cy-size//2, cx+size, cy+size//2], fill='#D2691E')

def draw_food_milk(draw, cx, cy, size=10):
    """牛奶"""
    draw.rectangle([cx-size, cy-size, cx+size, cy+size], fill='white', outline='#E0E0E0')
    draw.rectangle([cx-size+2, cy-size+2, cx+size-2, cy], fill='#87CEEB')

def draw_food_banana(draw, cx, cy, size=10):
    """香蕉"""
    draw.ellipse([cx-size, cy-size//2, cx+size, cy+size//2], fill='#FFD700')

def draw_food_meat(draw, cx, cy, size=10):
    """肉"""
    draw.ellipse([cx-size, cy-size, cx+size, cy+size], fill='#CD5C5C')

def draw_food_fish(draw, cx, cy, size=10):
    """鱼"""
    draw.ellipse([cx-size, cy-size//2, cx+size, cy+size//2], fill='#4FC3F7')

# 食物图标绘制函数列表
FOOD_ICONS = [
    draw_food_apple, draw_food_egg, draw_food_veggie, draw_food_sweet,
    draw_food_milk, draw_food_banana, draw_food_meat, draw_food_fish
]

# 快捷绘制函数
def draw_icon(draw, icon_type, x, y, size=10, color=None):
    """绘制指定类型的手绘图标"""
    icon_map = {
        'clock': (draw_icon_clock, '#666666'),
        'list': (draw_icon_list, '#666666'),
        'fire': (draw_icon_fire, '#FF6B6B'),
        'chart': (draw_icon_chart, '#666666'),
        'muscle': (draw_icon_muscle, '#1ABC9C'),
        'brain': (draw_icon_brain, '#F39C12'),
        'butter': (draw_icon_butter, '#E74C3C'),
        'bulb': (draw_icon_bulb, '#FFD93D'),
        'run': (draw_icon_run, '#3498DB'),
        'weight': (draw_icon_weight, '#9B59B6'),
        'yoga': (draw_icon_yoga, '#1ABC9C'),
        'walk': (draw_icon_walk, '#F39C12'),
        'lightning': (draw_icon_lightning, '#F39C12'),
        'dna': (draw_icon_dna, '#3498DB'),
        'warning': (draw_icon_warning, '#FF6B6B'),
        'check': (draw_icon_check, '#4ECDC4'),
        'sparkle': (draw_icon_sparkle, '#9B59B6'),
        'party': (draw_icon_party, '#E74C3C'),
        'thumbsup': (draw_icon_thumbsup, '#1ABC9C'),
        'fork': (draw_icon_fork, '#9B59B6'),
    }
    func, default_color = icon_map.get(icon_type, (draw_icon_clock, '#666666'))
    use_color = color if color else default_color
    func(draw, x + size//2, y + size//2, size, use_color)

# ==================== 卡片生成 ====================
def create_base_card(card_type, title, time_label):
    """创建基础卡片"""
    colors = COLORS[card_type]
    bg_color = hex_to_rgb(colors['bg'])
    
    # 创建卡片
    img = Image.new('RGBA', (CARD_WIDTH, CARD_HEIGHT), (*bg_color, 255))
    draw = ImageDraw.Draw(img)
    
    # 顶部圆角装饰条
    draw.rounded_rectangle([0, 0, CARD_WIDTH, 8], radius=4, fill=hex_to_rgb(colors['accent']))
    
    # 标题区域
    title_font = load_font(28)
    tag_font = load_font(14)
    time_font = load_font(12)
    
    # 标签背景
    tag_x, tag_y = 25, 20
    draw.rounded_rectangle([tag_x, tag_y, tag_x+70, tag_y+26], radius=13, fill=hex_to_rgb(colors['accent']))
    draw.text((tag_x+12, tag_y+5), title, font=tag_font, fill='white')
    
    # 时间标签
    if time_label:
        draw_icon(draw, 'clock', 100, tag_y+9, 10)
        draw.text((115, tag_y+7), time_label, font=time_font, fill='#666666')
    
    return img, draw, colors

def draw_nutrition_section(draw, x, y, consumed, target, label, color, icon):
    """绘制营养素区块 - v2.2 手绘图标版"""
    font_bold = load_font(18)
    font_small = load_font(12)
    font_tiny = load_font(10)
    
    # 图标和标签
    draw_icon(draw, icon, x, y+2, 9, color)  # 图标调小
    draw.text((x+15, y), label, font=font_small, fill='#555555')
    
    # 数值显示
    consumed_text = f"{consumed:.0f}g"
    target_text = f"/ {target}g"
    draw.text((x, y+18), consumed_text, font=font_bold, fill=hex_to_rgb(color))
    
    # 获取文字宽度计算目标位置
    consumed_w = font_bold.getlength(consumed_text)
    draw.text((x+consumed_w+2, y+22), target_text, font=font_tiny, fill='#999999')
    
    # 进度条
    progress = consumed / target if target > 0 else 0
    bar_width = 180
    draw_progress_bar(draw, x, y+45, bar_width, 10, progress, color)
    
    # 百分比
    pct = min(progress * 100, 100)
    draw.text((x+bar_width+8, y+42), f"{pct:.0f}%", font=font_tiny, fill='#888888')
    
    return y + 65

def draw_food_items(draw, x, y, foods, font=None):
    """绘制食物列表 - v2.2 手绘图标版"""
    font_small = font if font else load_font(12)
    
    current_y = y
    icon_size = 10  # 图标调小
    
    for i, food in enumerate(foods):
        # 使用手绘食物图标
        icon_func = FOOD_ICONS[i % len(FOOD_ICONS)]
        icon_func(draw, x + icon_size, current_y + icon_size, icon_size)
        draw.text((x+25, current_y+1), food, font=font_small, fill='#333333')
        current_y += 20
    
    return current_y

def generate_recommendation_card():
    """生成推荐卡片"""
    img, draw, colors = create_base_card('summary', '智能推荐', '基于营养补位')
    
    font_title = load_font(22)
    font_text = load_font(14)
    font_small = load_font(12)
    
    # 主标题
    draw.text((25, 60), '智能推荐下一餐', font=font_title, fill=hex_to_rgb(colors['text']))
    
    # 推荐内容
    recommendations = [
        ('🥩', '蛋白质补位', '鸡胸肉/鸡蛋/豆腐', '缺口: 25g', '#1ABC9C'),
        ('🌾', '控制碳水', '替换为糙米/燕麦', '碳水超标', '#F39C12'),
        ('⏰', '最佳时间', '19:00前吃完晚餐', '轻断食窗口', '#9B59B6'),
    ]
    
    y = 95
    for icon, title, food, note, color in recommendations:
        # 推荐卡片
        draw.rounded_rectangle([25, y, CARD_WIDTH-25, y+55], radius=10, fill='white')
        draw.rounded_rectangle([25, y, 25+5, y+55], radius=3, fill=hex_to_rgb(color))
        
        draw.text((45, y+8), f"{icon} {title}", font=font_text, fill='#333333')
        draw.text((45, y+30), food, font=font_small, fill='#666666')
        draw.text((450, y+30), note, font=font_small, fill=hex_to_rgb(color))
        
        y += 65
    
    # 底部瑜伽暗纹
    
    return img

def generate_meal_card(card_type, title, time_label, foods, nutrition_data, kcal, recommendation):
    """生成餐食卡片 - 新布局：卡路里+营养在上，建议在中，食物在下"""
    img, draw, colors = create_base_card(card_type, title, time_label)
    
    font_kcal = load_font(24)  # 参考总结页28，稍小一点
    font_kcal_label = load_font(13)
    font_title = load_font(15)  # 标题稍微大点
    font_text = load_font(13)
    font_tip = load_font(13)  # 和运动页正文保持一致
    font_food = load_font(12)  # 最小字体12，和运动页保持一致
    
    y = 60
    
    # ===== 上面：热量大字（最左）=====
    draw_icon(draw, 'fire', 25, y+2, 10)
    draw.text((42, y), f"{kcal}", font=font_kcal, fill=hex_to_rgb(colors['accent']))
    draw.text((42 + font_kcal.getlength(str(kcal)), y+5), ' kcal', font=font_kcal_label, fill='#888888')
    y += 55
    
    # ===== 上面：营养素（治愈系命名） =====
    draw_icon(draw, 'chart', 25, y+2, 9)
    draw.text((42, y), '元气分析', font=font_title, fill='#666666')
    y += 30
    
    # 四项营养素 - 治愈系命名 + Emoji
    nutritions = [
        ('肌肉小马达', 'protein', '#1ABC9C'),
        ('快乐能量站', 'carb', '#F39C12'),
        ('温柔小油箱', 'fat', '#E74C3C'),
        ('清道夫', 'fiber', '#90EE90'),
    ]
    
    for label, key, color in nutritions:
        draw.rounded_rectangle([25, y, CARD_WIDTH-25, y+35], radius=8, fill='white')
        value = nutrition_data.get(key, 0)
        draw.text((40, y+8), f"{label}: {value}g", font=font_text, fill=hex_to_rgb(color))
        y += 42
    
    y += 5  # 增加间距
    
    # ===== 温暖陪伴语录 =====
    # 根据卡片类型选择语录
    quote_map = {
        'breakfast': '新的一天，从好好吃饭开始',
        'lunch': '午后的能量，是下午的底气',
        'dinner': '清淡的一餐，给身体放个假',
        'snack1': '小确幸，大快乐',
        'snack2': '甜蜜时刻，值得珍惜',
    }
    default_quotes = [
        '每一餐，都是对自己的温柔',
        '好好吃饭，就是好好生活',
        '食物的温暖，会传递到心里',
    ]
    quote = quote_map.get(card_type, default_quotes[0])
    
    draw.rounded_rectangle([25, y, CARD_WIDTH-25, y+45], radius=10, fill=(*hex_to_rgb(colors['accent']), 25))
    draw_sticker(draw, 'heart', 40, y+15, size=8)
    quote_width = font_tip.getlength(f"「{quote}」")
    quote_x = (CARD_WIDTH - quote_width) // 2
    draw.text((quote_x, y+13), f"「{quote}」", font=font_tip, fill=hex_to_rgb(colors['text']))
    y += 55
    
    # ===== 建议区块 =====
    draw.rounded_rectangle([25, y, CARD_WIDTH-25, y+45], radius=10, fill=(*hex_to_rgb(colors['accent']), 40))
    draw_icon(draw, 'bulb', 40, y+14, 9)
    draw.text((58, y+12), f"建议: {recommendation}", font=font_tip, fill=hex_to_rgb(colors['text']))
    y += 55
    
    # ===== 下面：食物清单 + 食物情绪标签（移到上面更显眼） =====
    # 先显示食物情绪标签
    if foods:
        mood_counts = {}
        for food in foods:
            food_name = food.get('name', '') if isinstance(food, dict) else str(food)
            mood_info = get_food_mood(food_name)
            mood_name = mood_info.get('name', '开心食物')
            mood_emoji = mood_info.get('emoji', '😊')
            mood_counts[mood_name] = mood_counts.get(mood_name, 0) + 1
        
        if mood_counts:
            main_mood = max(mood_counts.items(), key=lambda x: x[1])[0]
            mood_color_map = {
                '开心食物': ('#FFD700', 'star'),
                '治愈食物': ('#87CEEB', 'heart'),
                '力量食物': ('#4169E1', 'muscle'),
                '清爽食物': ('#90EE90', 'leaf'),
                '甜蜜食物': ('#FF69B4', 'flower'),
                '满足食物': ('#FFA500', 'star'),
            }
            color, icon_type = mood_color_map.get(main_mood, ('#FFD700', 'star'))
            
            draw.rounded_rectangle([25, y, CARD_WIDTH-25, y+40], radius=10, fill=(*hex_to_rgb(color), 30))
            # 调用手绘图标函数，零字体依赖
            draw_sticker(draw, icon_type, 40, y+18, size=10)
            draw.text((58, y+10), f"这顿饭是 {main_mood}", font=font_text, fill=hex_to_rgb(color))
            y += 50
    
    # 食物清单
    draw_icon(draw, 'list', 25, y+2, 9)
    draw.text((42, y), '食物清单', font=font_title, fill='#666666')
    y += 28
    y = draw_food_items(draw, 30, y, foods, font_food)
    
    # 餐食推荐
    if recommendation and '推荐' in recommendation:
        y += 65
        font_next_title = load_font(16)
        draw_icon(draw, 'clock', 25, y+3, 14)
        draw.text((45, y), '下一餐推荐', font=font_next_title, fill=hex_to_rgb(colors['text']))
        y += 30
        draw.rounded_rectangle([25, y, CARD_WIDTH-25, y+45], radius=10, fill='white')
        draw.text((40, y+13), recommendation, font=load_font(15), fill='#333333')
    
    # 右下角瑜伽暗纹
    
    # v2.5 调整：绘制用户贴纸（右上角，手绘彩色，避免遮挡底部文字）
    stickers = get_stickers(card_type)
    if stickers:
        sticker_x = CARD_WIDTH - 100  # 右上角，从右往左
        sticker_y = 45  # 顶部往下
        for sticker in stickers:
            draw_sticker(draw, sticker, sticker_x, sticker_y, size=10)
            sticker_x -= 28  # 从右往左排列
    
    # v2.3 新增：温馨提示（右下角，淡灰色）
    draw.text((CARD_WIDTH-165, CARD_HEIGHT-22), "数据仅供参考，好好吃饭最重要", 
             font=load_font(9), fill='#AAAAAA')
    
    return img

def generate_exercise_card(exercise_name='跑步', distance='5km', duration='30min', burned_kcal=350, time_label='16:30-17:00'):
    """生成运动卡片
    exercise_name: 运动名称（跑步/力量训练/瑜伽等）
    distance: 距离或时长描述
    duration: 时长（数字+min，如'30min'）
    burned_kcal: 消耗卡路里
    time_label: 时间标签
    """
    img, draw, colors = create_base_card('exercise', '运动', time_label)
    
    font_kcal = load_font(24)
    font_kcal_label = load_font(13)
    font_title = load_font(15)
    font_text = load_font(13)
    font_tip = load_font(12)
    font_star = load_font(16)
    
    # 解析运动时长（提取数字）
    import re
    duration_min = 30
    duration_match = re.search(r'(\d+)', str(duration))
    if duration_match:
        duration_min = int(duration_match.group(1))
    
    # 治愈系3档运动状态文案（基于WHO标准：每周150分钟中等强度）
    if duration_min < 30:
        # 探索中：循序渐进
        exercise_status = '探索中'
        exercise_tip = '运动是循序渐进的过程，慢慢来也很好'
    elif duration_min < 90:
        # 刚刚好：身体正在被温柔唤醒
        exercise_status = '刚刚好'
        exercise_tip = '身体正在被温柔唤醒，今天也很棒'
    else:
        # 很充实：运动过量时的温和提醒
        exercise_status = '很充实'
        exercise_tip = '今天很充实，给身体一些时间休息恢复吧'
    
    y = 60
    
    # ===== 上面：今日总消耗（最左）=====
    draw_icon(draw, 'fire', 25, y+2, 10)
    draw.text((42, y), f"{burned_kcal}", font=font_kcal, fill=hex_to_rgb(colors['accent']))
    draw.text((42 + font_kcal.getlength(str(burned_kcal)), y+5), ' kcal', font=font_kcal_label, fill='#888888')
    draw.text((42, y+30), '今日总消耗', font=font_tip, fill='#666666')
    y += 70
    
    # ===== 中间：运动类型列表 =====
    draw_icon(draw, 'run', 25, y+2, 9)
    draw.text((42, y), '运动记录', font=font_title, fill='#666666')
    y += 30
    
    # 根据运动名称选择图标
    icon_map = {
        '跑步': ('run', '#F39C12'),
        '慢跑': ('run', '#F39C12'),
        '力量训练': ('weight', '#9B59B6'),
        '健身': ('weight', '#9B59B6'),
        '瑜伽': ('yoga', '#1ABC9C'),
        '游泳': ('swim', '#3498DB'),
        '骑车': ('bike', '#27AE60'),
        '步行': ('walk', '#F39C12'),
    }
    icon, icon_color = icon_map.get(exercise_name, ('run', '#F39C12'))
    
    exercise_types = [
        (icon, exercise_name + ' ' + distance, duration, f'{burned_kcal}kcal', icon_color),
    ]
    
    for icon, name, dur, burned, color in exercise_types:
        draw.rounded_rectangle([25, y, CARD_WIDTH-25, y+42], radius=10, fill='white')
        draw_icon(draw, icon, 40, y+10, 9, color)
        draw.text((55, y+8), name, font=font_text, fill='#333333')
        draw.text((55, y+26), dur, font=font_tip, fill='#888888')
        draw.text((500, y+12), f"消耗 {burned}", font=font_text, fill=hex_to_rgb(colors['accent']))
        y += 50
    
    # ===== 运动状态（治愈系3档）=====
    draw.rounded_rectangle([25, y, CARD_WIDTH-25, y+42], radius=10, fill='white')
    draw.text((40, y+12), f'今日状态 · {exercise_status}', font=font_text, fill=hex_to_rgb(colors['accent']))
    y += 50
    
    # ===== 温暖陪伴语录 =====
    draw.rounded_rectangle([25, y, CARD_WIDTH-25, y+42], radius=10, fill=(*hex_to_rgb(colors['accent']), 25))
    draw_sticker(draw, 'heart', 40, y+15, size=8)
    quote = '流汗也是疗愈'
    quote_width = font_tip.getlength(f"「{quote}」")
    quote_x = (CARD_WIDTH - quote_width) // 2
    draw.text((quote_x, y+13), f"「{quote}」", font=font_tip, fill=hex_to_rgb(colors['text']))
    y += 52
    
    # ===== 下面：运动提醒（治愈系）=====
    draw.rounded_rectangle([25, y, CARD_WIDTH-25, y+42], radius=10, fill='white')
    draw_icon(draw, 'heart', 40, y+13, 9)
    draw.text((55, y+11), exercise_tip, font=font_tip, fill='#555555')
    
    # 瑜伽暗纹
    
    # v2.5 调整：绘制用户贴纸（右上角，手绘彩色，避免遮挡底部文字）
    stickers = get_stickers('exercise')
    if stickers:
        sticker_x = CARD_WIDTH - 100
        sticker_y = 45
        for sticker in stickers:
            draw_sticker(draw, sticker, sticker_x, sticker_y, size=10)
            sticker_x -= 28
    
    # v2.3 新增：温馨提示（右下角，淡灰色）
    draw.text((CARD_WIDTH-165, CARD_HEIGHT-22), "数据仅供参考，好好吃饭最重要", 
             font=load_font(9), fill='#AAAAAA')
    
    return img

def generate_consume_card(gender='男', height=175, weight=70, age=25):
    """生成基础消耗卡片
    gender: '男' or '女'
    height: 身高cm
    weight: 体重kg
    age: 年龄
    """
    img, draw, colors = create_base_card('consume', '基础代谢', '全天')
    
    font_kcal = load_font(24)
    font_kcal_label = load_font(13)
    font_title = load_font(15)
    font_text = load_font(13)
    font_tip = load_font(12)
    font_small = load_font(11)
    
    y = 60
    
    # ===== 用户信息 =====
    draw_icon(draw, 'user', 25, y+2, 10)
    draw.text((42, y), '用户信息', font=font_title, fill='#666666')
    y += 25
    draw.text((25, y), f"{gender} | 身高 {height}cm | 体重 {weight}kg | 年龄 {age}岁", 
             font=font_small, fill='#888888')
    y += 35
    
    # ===== 上面：基础代谢率（Mifflin-St Jeor公式）=====
    draw_icon(draw, 'dna', 25, y+2, 10)
    draw.text((42, y), '基础代谢率 (BMR)', font=font_title, fill='#666666')
    y += 40
    
    # Mifflin-St Jeor公式计算BMR
    if gender == '男':
        bmr = int(10 * weight + 6.25 * height - 5 * age + 5)
    else:
        bmr = int(10 * weight + 6.25 * height - 5 * age - 161)
    
    draw.text((25, y), f'{bmr:,}', font=font_kcal, fill=hex_to_rgb(colors['accent']))
    draw.text((25 + font_kcal.getlength(f'{bmr:,}'), y+5), ' kcal/天', font=font_kcal_label, fill='#888888')
    y += 65
    
    # ===== 下面：详细分解（手绘彩色圆点，不用Emoji）=====
    draw_icon(draw, 'chart', 25, y+2, 9)
    draw.text((42, y), '消耗明细', font=font_title, fill='#666666')
    y += 30
    
    # 根据BMR动态计算分解
    brain = int(bmr * 0.20)
    heart = int(bmr * 0.15)
    muscle = int(bmr * 0.25)
    cell = bmr - brain - heart - muscle
    
    items = [
        ('脑力消耗', f'{brain}kcal', '20%', '#FF6B6B'),
        ('心脏运转', f'{heart}kcal', '15%', '#FFD93D'),
        ('肌肉活动', f'{muscle}kcal', '25%', '#6BCB77'),
        ('细胞代谢', f'{cell}kcal', '40%', '#4D96FF'),
    ]
    
    for name, val, pct, color in items:
        draw.rounded_rectangle([25, y, CARD_WIDTH-25, y+36], radius=8, fill='white')
        draw.ellipse([40, y+11, 48, y+19], fill=hex_to_rgb(color))
        draw.text((56, y+9), f"{name}", font=font_text, fill='#333333')
        draw.text((450, y+9), f"{val} ({pct})", font=font_text, fill=hex_to_rgb(colors['text']))
        y += 43
    
    # ===== 温暖陪伴语录 =====
    draw.rounded_rectangle([25, y, CARD_WIDTH-25, y+40], radius=10, fill=(*hex_to_rgb(colors['accent']), 25))
    draw_sticker(draw, 'heart', 40, y+14, size=7)
    quote = '你的存在，本身就需要能量'
    quote_width = font_tip.getlength(f"「{quote}」")
    quote_x = (CARD_WIDTH - quote_width) // 2
    draw.text((quote_x, y+12), f"「{quote}」", font=font_tip, fill=hex_to_rgb(colors['text']))
    y += 50
    
    # 瑜伽暗纹
    
    # v2.5 调整：绘制用户贴纸（右上角，手绘彩色，避免遮挡底部文字）
    stickers = get_stickers('consume')
    if stickers:
        sticker_x = CARD_WIDTH - 100
        sticker_y = 45
        for sticker in stickers:
            draw_sticker(draw, sticker, sticker_x, sticker_y, size=10)
            sticker_x -= 28
    
    # v2.3 新增：温馨提示（右下角，淡灰色）
    draw.text((CARD_WIDTH-165, CARD_HEIGHT-22), "数据仅供参考，好好吃饭最重要", 
             font=load_font(9), fill='#AAAAAA')
    
    return img

def generate_summary_card(meal_data=None, weight=70, gender='male', fiber_target=30):
    """生成总结卡片
    meal_data: 今日所有餐食数据，用于动态计算情绪统计
    weight: 用户体重(kg)，用于动态计算营养目标
    gender: 性别('male'/'female')
    fiber_target: 纤维目标(g)，男性默认30g
    """
    img, draw, colors = create_base_card('summary', '今日总结', '')
    
    font_kcal = load_font(28)  # 从36改到28，避免溢出
    font_text = load_font(14)
    font_tip = load_font(12)
    font_bold = load_font(18)
    font_animal_name = load_font(16)
    font_animal_slogan = load_font(11)
    
    y = 55  # 从顶部开始
    
    # 首先根据真实餐食数据计算总营养
    if meal_data:
        total_protein = 0
        total_carb = 0
        total_fat = 0
        total_fiber = 0
        total_kcal = 0
        
        for meal in meal_data.values() if isinstance(meal_data, dict) else meal_data:
            if isinstance(meal, dict):
                # kcal在顶层，不在nutrition里面
                total_kcal += meal.get('kcal', meal.get('calories', 0))
                if 'nutrition' in meal:
                    nut = meal['nutrition']
                    total_protein += nut.get('protein', 0)
                    total_carb += nut.get('carb', 0)
                    total_fat += nut.get('fat', 0)
                    total_fiber += nut.get('fiber', 0)
    else:
        # 默认值
        total_protein = 72
        total_carb = 85
        total_fat = 45
        total_fiber = 0
        total_kcal = 1320
    
    # ===== 动态计算营养目标（基于中国营养学会权威指南）=====
    # 蛋白质：1.5g/kg 体重（权威推荐：普通成人1.0-1.2g/kg，健身人群1.2-1.6g/kg）
    target_protein = int(weight * 1.5)
    # 脂肪：1.0g/kg 体重（健康范围，占总能量20-30%）
    target_fat = int(weight * 1.0)
    # 碳水：剩余热量分配（BMR约1800kcal - 蛋白热量 - 脂肪热量）/ 4
    protein_kcal = target_protein * 4
    fat_kcal = target_fat * 9
    target_carb = int((1800 - protein_kcal - fat_kcal) / 4)
    
    # 基础代谢 + 活动消耗（估算）
    total_consume = 1823 + 350  # 用户真实数据
    
    # ===== 区块1：总摄入 vs 总消耗（手账风，对称布局）=====
    draw_icon(draw, 'lightning', 25, y+2, 12)
    draw.text((42, y), '今日元气值', font=font_text, fill='#666666')
    y += 25
    
    # 左右对称的两个卡片（宽度均为285px，间距20px）
    card_width = 285
    card_height = 58  # 压缩高度
    
    # 左侧：摄入
    draw.rounded_rectangle([25, y, 25+card_width, y+card_height], radius=12, fill='white')
    draw.text((40, y+5), '收集元气', font=font_tip, fill='#888888')
    kcal_str = f'{total_kcal:,}'
    draw.text((40, y+20), kcal_str, font=font_kcal, fill='#E74C3C')
    draw.text((40 + font_kcal.getlength(kcal_str), y+28), ' kcal', font=font_tip, fill='#888888')
    
    # 右侧：消耗
    draw.rounded_rectangle([CARD_WIDTH-25-card_width, y, CARD_WIDTH-25, y+card_height], radius=12, fill='white')
    right_x = CARD_WIDTH - 25 - card_width + 15
    draw.text((right_x, y+5), '消耗元气', font=font_tip, fill='#888888')
    consume_str = f'{total_consume:,}'
    draw.text((right_x, y+20), consume_str, font=font_kcal, fill='#27AE60')
    draw.text((right_x + font_kcal.getlength(consume_str), y+28), ' kcal', font=font_tip, fill='#888888')
    
    # ===== 区块2：今日陪伴语录（治愈系·无评判）=====
    y += card_height + 18  # 压缩间距
    
    # 治愈系陪伴语录（3档·完全无负面）
    target_kcal = 1800
    if total_kcal < target_kcal * 0.7:
        # 摄入较少：温柔提醒可以加餐
        advice_icon_type = "heart"
        advice_text = "今天吃得比较轻盈，可以考虑给自己加份小点心哦"
        advice_color = '#F39C12'  # 暖橙色
    elif total_kcal > target_kcal * 1.2:
        # 摄入较多：接纳和包容
        advice_icon_type = "star"
        advice_text = "今天吃得很满足，身体正在好好吸收这份能量"
        advice_color = '#1ABC9C'  # 柔和绿色
    else:
        # 正常范围：正向肯定
        advice_icon_type = "heart"
        advice_text = "今天的饮食节奏很舒服，身体正在被好好照顾"
        advice_color = '#4ECDC4'  # 清新青色
    
    draw.rounded_rectangle([25, y, CARD_WIDTH-25, y+45], radius=12, fill=(*hex_to_rgb(advice_color), 25))
    text_width = font_bold.getlength(f"  {advice_text}")
    text_start = CARD_WIDTH//2 - text_width//2
    draw_icon(draw, advice_icon_type, text_start - 18, y+15, 14, advice_color)
    draw.text((text_start, y+13), advice_text, font=font_bold, fill=advice_color)
    
    # ===== 区块3：营养素达标率（手账风）=====
    y += 55  # 压缩间距
    draw_icon(draw, 'sparkle', 25, y+2, 12)
    draw.text((42, y), '营养进度条', font=font_text, fill='#666666')
    y += 25
    
    # 手账风营养标签 + 趣味进度文案（动态目标基于体重）
    nutrients = [
        ('肌肉小马达', total_protein, target_protein, 'muscle', '#1ABC9C'),   # 蛋白质
        ('快乐能量站', total_carb, target_carb, 'brain', '#F39C12'),      # 碳水
        ('温柔小油箱', total_fat, target_fat, 'butter', '#E74C3C'),      # 脂肪
        ('肠道清道夫', total_fiber, fiber_target, 'leaf', '#90EE90'),   # 膳食纤维
    ]
    
    for name, consumed, target, _, color in nutrients:
        pct = consumed / target * 100
        # 去掉左边彩色图标，文字左移对齐
        draw.text((25, y), name, font=font_tip, fill='#666666')
        draw.text((115, y), f"{consumed}g/{target}g", font=font_tip, fill='#333333')
        draw_progress_bar(draw, 215, y+2, 200, 14, pct/100, color)
        
        # 进度趣味文案（根据完成度和营养素类型）
        # 治愈系3档状态文案（无评价·纯陪伴）
        is_protein = '蛋白质' in name or '蛋白' in name or '马达' in name
        is_fiber = '纤维' in name or '清道夫' in name
        
        if pct >= 120:
            # 超过目标：正向肯定
            status_icon = 'star'
            if is_protein or is_fiber:
                status_text = "很充足"
            else:
                status_text = "很满足"
        elif pct >= 70:
            # 接近目标：刚刚好
            status_icon = 'thumbsup'
            status_text = "刚刚好"
        else:
            # 还有空间：探索更多美味
            status_icon = 'leaf'
            status_text = "探索中"
        
        # 去掉百分比和图标，只显示状态文案
        status_x = 425  # 进度条左移，状态文案也左移
        draw.text((status_x, y), status_text, font=font_tip, fill=color)
        y += 28  # 压缩行间距
    
    # ===== 区块4：今日食物情绪盘点 =====
    y += 12  # 压缩区块间距
    draw_icon(draw, 'brain', 25, y+2, 12)
    draw.text((42, y), '食物情绪盘点', font=font_text, fill='#666666')
    y += 25
    
    # 动态计算情绪统计
    mood_counts = {}
    if meal_data:
        # 从所有餐食中收集所有食物
        all_foods = []
        for meal in meal_data.values() if isinstance(meal_data, dict) else meal_data:
            if isinstance(meal, dict) and 'foods' in meal:
                all_foods.extend(meal['foods'])
            elif isinstance(meal, list):
                all_foods.extend(meal)
        
        # 统计每种情绪出现的次数
        for food in all_foods:
            food_name = food if isinstance(food, str) else str(food)
            mood_info = get_food_mood(food_name)
            mood_name = mood_info.get('name', '开心食物')
            mood_counts[mood_name] = mood_counts.get(mood_name, 0) + 1
    
    # 如果没有数据，显示默认提示
    if not mood_counts:
        mood_font = load_font(13)
        draw.text((30, y), "记录食物后自动统计", font=mood_font, fill='#888888')
        y += 22
    else:
        # 情绪-颜色映射表（治愈系配色）
        mood_color_map = {
            '开心食物': ('star', '#FFD700', '#FFF9E6'),
            '治愈食物': ('heart', '#87CEEB', '#E6F3FF'),
            '力量食物': ('muscle', '#4169E1', '#E6EBFF'),
            '清爽食物': ('leaf', '#90EE90', '#E6FFE6'),
            '甜蜜食物': ('flower', '#FF69B4', '#FFE6F0'),
            '满足食物': ('star', '#FFA500', '#FFF0E6'),
        }
        # 按次数排序，显示所有分类（总结页需要完整汇总）
        sorted_moods = sorted(mood_counts.items(), key=lambda x: x[1], reverse=True)
        mood_font = load_font(11)
        count_font = load_font(16)
        
        # 根据分类数量动态调整卡片宽度
        num_moods = len(sorted_moods)
        if num_moods <= 3:
            card_width = 190
            card_spacing = 10
        elif num_moods <= 4:
            card_width = 140
            card_spacing = 8
        else:
            card_width = 110
            card_spacing = 6
        card_height = 55
        start_x = 25
        
        for i, (mood_name, count) in enumerate(sorted_moods):
            sticker_type, color, bg_color = mood_color_map.get(mood_name, ('star', '#FFD700', '#FFF9E6'))
            card_x = start_x + i * (card_width + card_spacing)
            
            # 情绪卡片背景
            draw.rounded_rectangle([card_x, y, card_x + card_width, y + card_height], 
                                    radius=12, fill=hex_to_rgb(bg_color))
            
            # 手绘图标
            draw_sticker(draw, sticker_type, card_x + 18, y + 20, size=9)
            
            # 计数（大字号）
            count_text = f"{count}种"
            count_width = count_font.getlength(count_text)
            count_x = card_x + card_width - count_width - 15
            draw.text((count_x, y + 8), count_text, font=count_font, fill=hex_to_rgb(color))
            
            # 情绪名称
            name_width = mood_font.getlength(mood_name)
            name_x = card_x + card_width - name_width - 15
            draw.text((name_x, y + 32), mood_name, font=mood_font, fill='#666666')
        
        y += card_height + 15
    
    y += 20  # 压缩区块间距
    
    # ===== 区块5：今日饮食小动物 =====
    # 根据真实餐食数据动态计算（如果有数据的话）
    if meal_data:
        total_protein = 0
        total_carb = 0
        total_fat = 0
        total_kcal = 0
        snack_count = 0
        
        for meal in meal_data.values() if isinstance(meal_data, dict) else meal_data:
            if isinstance(meal, dict):
                if 'nutrition' in meal:
                    nut = meal['nutrition']
                    total_protein += nut.get('protein', 0)
                    total_carb += nut.get('carb', 0)
                    total_fat += nut.get('fat', 0)
                    total_kcal += nut.get('kcal', nut.get('calories', 0))
                if 'foods' in meal and len(meal['foods']) <= 2:
                    snack_count += 1
    else:
        # 默认值
        total_protein = 72
        total_carb = 85
        total_fat = 45
        total_kcal = 1320
        snack_count = 2
    
    total_nutrient = total_protein + total_carb + total_fat
    protein_pct = (total_protein / total_nutrient * 100) if total_nutrient > 0 else 33
    carb_pct = (total_carb / total_nutrient * 100) if total_nutrient > 0 else 33
    fat_pct = (total_fat / total_nutrient * 100) if total_nutrient > 0 else 33
    kcal_pct = (total_kcal / 1500 * 100) if 1500 > 0 else 50
    
    # v2.5 修复：只返回名称和标语，不返回Emoji（纯代码手绘，零字体依赖）
    match_result = match_diet_animal(protein_pct, carb_pct, fat_pct, kcal_pct, snack_count)
    if len(match_result) == 3:
        animal_name, _, animal_slogan = match_result  # 忽略Emoji字段
    else:
        animal_name, animal_slogan = match_result
    
    draw.rounded_rectangle([25, y, CARD_WIDTH-25, y+65], radius=12, fill='white')
    
    animal_cx, animal_cy = 75, y+33
    draw_func = ANIMAL_DRAW_FUNCS.get(animal_name, draw_animal_cat)
    draw_func(draw, animal_cx, animal_cy, size=26)
    
    # 文字向右移，避免与动物图像重叠
    text_x = 150
    draw.text((text_x, y+8), f"今日饮食小动物", font=font_tip, fill='#999999')
    draw.text((text_x, y+24), animal_name, font=font_animal_name, fill=hex_to_rgb(colors['text']))
    draw.text((text_x, y+44), f"「{animal_slogan}」", font=font_animal_slogan, fill='#888888')
    y += 75
    
    # 底部治愈系陪伴语录
    quotes = [
        "「今天也在好好照顾自己呢 🌸」",
        "「好好吃饭，就是好好生活。」",
        "「每一餐，都是对自己的温柔。」",
        "「食物的温暖，会传递到心里。」",
        "「你值得被好好对待，从每一餐开始。」",
    ]
    import random
    quote = random.choice(quotes)
    quote_width = font_tip.getlength(quote)
    draw.text((CARD_WIDTH//2 - quote_width//2, CARD_HEIGHT-20), 
              quote, font=font_tip, fill='#888888')
    
    # 瑜伽暗纹
    
    # v2.5 调整：绘制用户贴纸（右上角，手绘彩色，避免遮挡底部文字）
    stickers = get_stickers('summary')
    if stickers:
        sticker_x = CARD_WIDTH - 100
        sticker_y = 45
        for sticker in stickers:
            draw_sticker(draw, sticker, sticker_x, sticker_y, size=10)
            sticker_x -= 28
    
    return img

# ==================== 主函数 ====================
def generate_all_cards(output_dir='cards', run_self_check=True):
    """生成所有7张demo卡片
    
    Args:
        output_dir: 输出目录
        run_self_check: 是否运行自检（默认True）
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # 准备示例数据（用于自检）
    breakfast_data = {
        'foods': ['水煮蛋 × 2', '全麦面包 × 2片', '牛奶 250ml'],
        'nutrition': {'protein': 26, 'carb': 35, 'fat': 12, 'fiber': 6},
        'kcal': 350,
        'recommendation': '午餐建议补充蔬菜和蛋白质!'
    }
    
    lunch_data = {
        'foods': ['糙米饭 150g', '鸡胸肉 120g', '西兰花 200g', '番茄炒蛋'],
        'nutrition': {'protein': 45, 'carb': 55, 'fat': 15, 'fiber': 8},
        'kcal': 580,
        'recommendation': '加餐可选蛋白质棒或坚果'
    }
    
    snack1_data = {
        'foods': ['酸奶 200g', '小番茄 100g'],
        'nutrition': {'protein': 10, 'carb': 20, 'fat': 5, 'fiber': 3},
        'kcal': 150,
        'recommendation': '下午茶优选!'
    }
    
    snack2_data = {
        'foods': ['坚果混合 30g', '黑咖啡'],
        'nutrition': {'protein': 5, 'carb': 8, 'fat': 18, 'fiber': 4},
        'kcal': 240,
        'recommendation': '控制每日坚果摄入量'
    }
    
    all_meals = {
        'breakfast': breakfast_data,
        'lunch': lunch_data,
        'snack1': snack1_data,
        'snack2': snack2_data
    }
    
    # v2.5：运行数据自检
    if run_self_check:
        check_success, check_report = self_checker.run_full_check(all_meals)
        # 保存自检报告到文件
        report_path = os.path.join(output_dir, 'SELF_CHECK_REPORT.txt')
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(check_report)
        print(f"📋 自检报告已保存: {report_path}")
    
    # v2.1：给每张卡片加一些可爱的手绘贴纸装饰
    from emoji_stickers import add_sticker, clear_stickers
    clear_stickers()
    add_sticker('breakfast', 'sun')    # 太阳
    add_sticker('breakfast', 'star')   # 星星
    add_sticker('lunch', 'leaf')       # 叶子
    add_sticker('lunch', 'star')       # 星星
    add_sticker('snack1', 'flower')    # 花朵
    add_sticker('snack2', 'heart')     # 爱心
    add_sticker('exercise', 'star')    # 星星
    add_sticker('consume', 'star')     # 星星
    add_sticker('summary', 'star')     # 星星
    add_sticker('summary', 'heart')    # 爱心
    
    # 生成卡片
    cards = [
        ('01_早餐.png', generate_meal_card('breakfast', '早餐', '07:30', 
             breakfast_data['foods'], breakfast_data['nutrition'], 
             breakfast_data['kcal'], breakfast_data['recommendation'])),
        ('02_午餐.png', generate_meal_card('lunch', '午餐', '12:00',
             lunch_data['foods'], lunch_data['nutrition'],
             lunch_data['kcal'], lunch_data['recommendation'])),
        ('03_加餐1.png', generate_meal_card('snack1', '加餐①', '15:30',
             snack1_data['foods'], snack1_data['nutrition'],
             snack1_data['kcal'], snack1_data['recommendation'])),
        ('04_加餐2.png', generate_meal_card('snack2', '加餐②', '17:30',
             snack2_data['foods'], snack2_data['nutrition'],
             snack2_data['kcal'], snack2_data['recommendation'])),
        ('05_运动.png', generate_exercise_card()),
        ('06_基础消耗.png', generate_consume_card()),
        ('07_总结.png', generate_summary_card(meal_data={
            'breakfast': breakfast_data,
            'lunch': lunch_data,
            'snack1': snack1_data,
            'snack2': snack2_data
        })),
    ]
    
    for filename, card in cards:
        filepath = os.path.join(output_dir, filename)
        card.save(filepath, 'PNG', quality=95)
        print(f"✅ 已生成: {filepath}")
    
    print(f"\n🎉 共生成 {len(cards)} 张卡片!")
    return [f[0] for f in cards]

if __name__ == '__main__':
    import sys
    out_dir = sys.argv[1] if len(sys.argv) > 1 else 'cards'
    generate_all_cards(out_dir)

