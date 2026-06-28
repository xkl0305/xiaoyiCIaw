# -*- coding: utf-8 -*-
"""
v2.5 P2 新增：预设贴纸库
=========================
18个纯代码手绘贴纸，28x28像素大小
纯PIL绘制，零外部依赖，跨平台一致
"""


# ============== 食物类贴纸（8个） ==============

def draw_bread(draw, x, y, size=28):
    """手绘面包贴纸"""
    s = size // 2
    # 面包主体（椭圆）
    draw.ellipse([x-s, y-s//2, x+s, y+s//2], fill='#F5DEB3', outline='#DEB887', width=2)
    # 面包纹路
    draw.arc([x-s//2, y-s//4, x+s//2, y+s//4], start=0, end=180, fill='#D2B48C', width=1)


def draw_egg(draw, x, y, size=28):
    """手绘鸡蛋贴纸"""
    s = size // 2
    # 蛋白（椭圆形）
    draw.ellipse([x-s, y-s*1.2, x+s, y+s*1.2], fill='white', outline='#F0F0F0', width=1)
    # 蛋黄
    draw.ellipse([x-s//2, y-s//2, x+s//2, y+s//2], fill='#FFD700', outline='#FFA500', width=1)


def draw_milk(draw, x, y, size=28):
    """手绘牛奶贴纸"""
    s = size // 2
    # 牛奶盒主体
    draw.rectangle([x-s, y-s, x+s, y+s], fill='white', outline='#E0E0E0', width=1)
    # 标签
    draw.rectangle([x-s//2, y-s//2, x+s//2, y+s//2], fill='#87CEEB', outline='#4682B4', width=1)
    # 字母M
    draw.text((x-4, y-4), 'M', fill='white')


def draw_apple(draw, x, y, size=28):
    """手绘苹果贴纸"""
    s = size // 2
    # 苹果主体
    draw.ellipse([x-s, y-s, x+s, y+s], fill='#FF6B6B', outline='#E55555', width=2)
    # 叶子
    draw.ellipse([x-2, y-s-4, x+6, y-s], fill='#4CAF50')
    # 苹果柄
    draw.line([x, y-s+2, x, y-s-2], fill='#8B4513', width=2)


def draw_avocado(draw, x, y, size=28):
    """手绘牛油果贴纸"""
    s = size // 2
    # 牛油果主体（椭圆）
    draw.ellipse([x-s, y-s*1.1, x+s, y+s*1.1], fill='#7CB342', outline='#558B2F', width=2)
    # 果核
    draw.ellipse([x-s//3, y-s//3, x+s//3, y+s//3], fill='#8D6E63')


def draw_cake(draw, x, y, size=28):
    """手绘蛋糕贴纸"""
    s = size // 2
    # 蛋糕底座
    draw.rectangle([x-s, y, x+s, y+s], fill='#FFB6C1', outline='#FF69B4', width=1)
    # 蛋糕顶部（奶油）
    draw.ellipse([x-s, y-s//2, x+s, y+s//2], fill='white', outline='#FFF0F5', width=1)
    # 小樱桃
    draw.ellipse([x-3, y-s//2-3, x+3, y-s//2+3], fill='#FF0000')


def draw_salad(draw, x, y, size=28):
    """手绘沙拉贴纸"""
    s = size // 2
    # 碗
    draw.arc([x-s, y, x+s, y+s], start=0, end=180, fill='#87CEEB', width=3)
    # 生菜叶子
    draw.ellipse([x-s//2, y-s//2, x, y], fill='#90EE90')
    draw.ellipse([x, y-s//2, x+s//2, y], fill='#98FB98')
    draw.ellipse([x-s//3, y-s, x+s//3, y-s//2], fill='#90EE90')


def draw_chicken(draw, x, y, size=28):
    """手绘鸡腿贴纸"""
    s = size // 2
    # 鸡腿主体
    draw.ellipse([x-s, y-s//2, x+s//2, y+s//2], fill='#F5DEB3', outline='#DEB887', width=2)
    # 骨头
    draw.rectangle([x+s//2-2, y-3, x+s, y+3], fill='white', outline='#E0E0E0', width=1)
    # 骨头两端
    draw.ellipse([x+s-4, y-5, x+s+2, y-1], fill='white')
    draw.ellipse([x+s-4, y+1, x+s+2, y+5], fill='white')


# ============== 心情类贴纸（5个） ==============

def draw_heart(draw, x, y, size=28):
    """手绘爱心贴纸"""
    s = size // 2
    # 左半心
    draw.ellipse([x-s, y-s, x, y], fill='#FF69B4', outline='#FF1493', width=1)
    # 右半心
    draw.ellipse([x, y-s, x+s, y], fill='#FF69B4', outline='#FF1493', width=1)
    # 下三角
    draw.polygon([(x-s, y-2), (x+s, y-2), (x, y+s)], fill='#FF69B4', outline='#FF1493')


def draw_star(draw, x, y, size=28):
    """手绘星星贴纸"""
    s = size // 2
    # 五角星（用多边形近似）
    points = [
        (x, y-s),
        (x+s//3, y-s//3),
        (x+s, y-s//2),
        (x+s//2, y),
        (x+s//2, y+s),
        (x, y+s//2),
        (x-s//2, y+s),
        (x-s//2, y),
        (x-s, y-s//2),
        (x-s//3, y-s//3),
    ]
    draw.polygon(points, fill='#FFD700', outline='#FFA500', width=1)


def draw_sparkle(draw, x, y, size=28):
    """手绘闪光贴纸"""
    s = size // 2
    # 十字闪光
    draw.line([x-s//2, y, x+s//2, y], fill='#FFD700', width=3)
    draw.line([x, y-s//2, x, y+s//2], fill='#FFD700', width=3)
    # 四个小点点
    for dx, dy in [(-s, 0), (s, 0), (0, -s), (0, s)]:
        draw.ellipse([x+dx-2, y+dy-2, x+dx+2, y+dy+2], fill='#FFD700')


def draw_drop(draw, x, y, size=28):
    """手绘水滴贴纸"""
    s = size // 2
    # 水滴形状（椭圆+尖角）
    draw.ellipse([x-s, y-s//2, x+s, y+s//2], fill='#87CEEB', outline='#4682B4', width=1)
    draw.polygon([(x-s, y), (x+s, y), (x, y-s)], fill='#87CEEB', outline='#4682B4')


def draw_moon(draw, x, y, size=28):
    """手绘月亮贴纸"""
    s = size // 2
    # 月牙形（两个圆的差）
    draw.ellipse([x-s, y-s, x+s, y+s], fill='#FFE4B5', outline='#FFDAB9', width=1)
    # 用一个稍小的圆挖掉一部分
    draw.ellipse([x-s//2-2, y-s, x+s*1.2, y+s], fill='white', outline='white')


# ============== 装饰类贴纸（5个） ==============

def draw_bow(draw, x, y, size=28):
    """手绘蝴蝶结贴纸"""
    s = size // 2
    # 左环
    draw.ellipse([x-s, y-s//2, x, y+s//2], fill='#FF69B4', outline='#FF1493', width=1)
    # 右环
    draw.ellipse([x, y-s//2, x+s, y+s//2], fill='#FF69B4', outline='#FF1493', width=1)
    # 中心结
    draw.ellipse([x-s//3, y-s//4, x+s//3, y+s//4], fill='#FF1493')
    # 飘带
    draw.polygon([(x-s//2, y+s//2), (x, y+s//2-2), (x-s//2, y+s)], fill='#FF69B4')
    draw.polygon([(x+s//2, y+s//2), (x, y+s//2-2), (x+s//2, y+s)], fill='#FF69B4')


def draw_flower(draw, x, y, size=28):
    """手绘小花贴纸"""
    s = size // 2
    # 五个花瓣
    for i in range(5):
        import math
        angle = i * math.pi * 2 / 5 - math.pi / 2
        px = x + math.cos(angle) * s // 2
        py = y + math.sin(angle) * s // 2
        draw.ellipse([px-4, py-4, px+4, py+4], fill='#FFB6C1', outline='#FF69B4', width=1)
    # 花心
    draw.ellipse([x-3, y-3, x+3, y+3], fill='#FFD700')


def draw_dot(draw, x, y, size=28):
    """手绘圆点贴纸"""
    s = size // 2
    # 大圆点
    draw.ellipse([x-s//2, y-s//2, x+s//2, y+s//2], fill='#E91E63', outline='#C2185B', width=2)


def draw_diamond(draw, x, y, size=28):
    """手绘钻石贴纸"""
    s = size // 2
    # 菱形
    draw.polygon([
        (x, y-s),
        (x+s, y),
        (x, y+s),
        (x-s, y),
    ], fill='#00BCD4', outline='#0097A7', width=1)
    # 反光
    draw.polygon([(x-s//2, y-s//2), (x, y-s), (x, y), (x-s, y)], fill='#4DD0E1')


def draw_music(draw, x, y, size=28):
    """手绘音符贴纸"""
    s = size // 2
    # 符头
    draw.ellipse([x-s//2, y, x, y+s//2], fill='#9C27B0')
    draw.ellipse([x+2, y+s//4, x+s//2+2, y+s*3//4], fill='#9C27B0')
    # 符干
    draw.line([x, y-s//2, x, y], fill='#9C27B0', width=2)
    draw.line([x+s//2+2, y-s//4, x+s//2+2, y+s//4], fill='#9C27B0', width=2)
    # 符尾连接
    draw.line([x, y-s//2, x+s//2+2, y-s//4], fill='#9C27B0', width=2)


# ============== 贴纸库索引 ==============

PRESET_STICKERS = {
    # 食物类
    'bread': (draw_bread, '面包', 'food'),
    'egg': (draw_egg, '鸡蛋', 'food'),
    'milk': (draw_milk, '牛奶', 'food'),
    'apple': (draw_apple, '苹果', 'food'),
    'avocado': (draw_avocado, '牛油果', 'food'),
    'cake': (draw_cake, '蛋糕', 'food'),
    'salad': (draw_salad, '沙拉', 'food'),
    'chicken': (draw_chicken, '鸡腿', 'food'),
    
    # 心情类
    'heart': (draw_heart, '爱心', 'mood'),
    'star': (draw_star, '星星', 'mood'),
    'sparkle': (draw_sparkle, '闪光', 'mood'),
    'drop': (draw_drop, '水滴', 'mood'),
    'moon': (draw_moon, '月亮', 'mood'),
    
    # 装饰类
    'bow': (draw_bow, '蝴蝶结', 'deco'),
    'flower': (draw_flower, '小花', 'deco'),
    'dot': (draw_dot, '圆点', 'deco'),
    'diamond': (draw_diamond, '钻石', 'deco'),
    'music': (draw_music, '音符', 'deco'),
}


def get_preset_sticker(sticker_id):
    """获取预设贴纸的绘制函数
    
    Args:
        sticker_id: 贴纸ID（如'bread'、'heart'）
        
    Returns:
        (draw_func, name, category) 或 None
    """
    return PRESET_STICKERS.get(sticker_id)


def list_preset_stickers(category=None):
    """列出所有预设贴纸
    
    Args:
        category: 可选分类（food/mood/deco）
        
    Returns:
        [(sticker_id, name, category), ...]
    """
    result = []
    for sticker_id, (func, name, cat) in PRESET_STICKERS.items():
        if category is None or cat == category:
            result.append((sticker_id, name, cat))
    return result
