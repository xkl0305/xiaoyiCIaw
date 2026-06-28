# -*- coding: utf-8 -*-
"""
v2.5 新增：文字版手账系统
=========================
在对话窗口直接生成可查看的文字和字符画手账
零图片依赖，纯文本渲染，风格与PIL卡片保持一致
"""

import random
import sys
from datetime import datetime

# 导入食物情绪分析模块（v2.1+ 已有功能）
sys.path.insert(0, '.')
try:
    from food_mood_analyzer import get_food_mood
    HAS_MOOD_ANALYZER = True
except ImportError:
    HAS_MOOD_ANALYZER = False
    def get_food_mood(name):
        return {"mood": "happy", "emoji": "😊", "name": "开心食物"}

# 导入正念话术库（v2.5 P1新增）
try:
    from mindful_quotes import get_mindful_quote as get_smart_quote
    HAS_MINDFUL_QUOTES = True
except ImportError:
    HAS_MINDFUL_QUOTES = False
    def get_smart_quote(all_meals=None, matched_animal=None, user_text=None):
        return "好好吃饭，就是爱自己最具体的方式。"


# ==================== ASCII 小动物字符画 ====================
# 注意：所有字符画保持4-6行，居中对齐
ASCII_ANIMALS = {
    '小猎豹': r"""
       ,--.       
      ( oo )  喵~ 
       >°<     
      /    \  
     ||      || 
    """,
    
    '小仓鼠': r"""
      (•̀ᴗ•́)و  
     ╭───────╮  
     │ 🥕 🍞 │  囤货中
     ╰───────╯  
    """,
    
    '小狐狸': r"""
       /\_/\  
      ( o.o )  精明如我
       > ^ <  
      /     \ 
    """,
    
    '小松鼠': r"""
       (\-/)  
      ( 'x' )  坚果储备
     / >🍪🍪< \
       ￣￣￣  
    """,
    
    '小兔子': r"""
       (•ө•)  
      / )  ) 
     (  🥕  )  蹦蹦跳跳
      ︶︶︶  
    """,
    
    '小熊': r"""
       ʕ•ᴥ•ʔ  
      ʕ つ🍯  准备冬眠
       づ   づ 
    """,
}


def get_ascii_animal(animal_name):
    """获取对应小动物的ASCII字符画"""
    return ASCII_ANIMALS.get(animal_name, ASCII_ANIMALS['小狐狸'])


# ==================== 营养比例文字条形图 ====================
def draw_text_bar(value, max_value=100, width=20):
    """文字版进度条"""
    filled = int(width * min(value, max_value) / max_value)
    bar = '█' * filled + '░' * (width - filled)
    return f"[{bar}] {value:.0f}%"


# ==================== 文字版手账生成 ====================
def render_meal_card(meal_type, foods, nutrition=None):
    """渲染单餐的文字版卡片
    
    Args:
        meal_type: 餐次类型 (breakfast/lunch/dinner/snack1/snack2)
        foods: 食物列表，每个食物是 dict {name, amount, kcal, protein, carb, fat}
        nutrition: 营养汇总，可选 {kcal, protein, carb, fat, kcal_target}
        
    Returns:
        str: 渲染好的文字版卡片
    """
    
    meal_names = {
        'breakfast': '🍞 早餐',
        'lunch': '☀️ 午餐',
        'dinner': '🌙 晚餐',
        'snack1': '🍪 加餐',
        'snack2': '🍬 小食',
        'summary': '📊 今日汇总'
    }
    
    meal_name = meal_names.get(meal_type, meal_type)
    date_str = datetime.now().strftime('%Y-%m-%d')
    
    # 卡片头部
    lines = []
    lines.append(f"\n{meal_name} · {date_str}")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    # 食物列表
    total_kcal = 0
    total_protein = 0
    total_carb = 0
    total_fat = 0
    
    # 先计算最长的食物名称+份量，用于对齐
    max_name_len = 0
    food_lines = []
    for food in foods:
        name = food.get('name', '未知食物')
        amount = food.get('amount', '')
        name_amount = f"{name} {amount}" if amount else name
        max_name_len = max(max_name_len, len(name_amount))
    
    for food in foods:
        name = food.get('name', '未知食物')
        amount = food.get('amount', '')
        kcal = food.get('kcal', 0)
        protein = food.get('protein', 0)
        carb = food.get('carb', 0)
        fat = food.get('fat', 0)
        
        total_kcal += kcal
        total_protein += protein
        total_carb += carb
        total_fat += fat
        
        # 获取食物情绪标签（v2.1的温馨命名系统）
        mood_info = get_food_mood(name)
        mood_emoji = mood_info.get("emoji", "😊")
        mood_name = mood_info.get("name", "开心食物")
        
        name_amount = f"{name} {amount}" if amount else name
        padded_name = name_amount.ljust(max_name_len)
        kcal_str = f"{kcal:>5} 元气" if kcal > 0 else ""
        
        # 显示：情绪图标 + 食物名称 + 热量 + 【情绪标签
        line = f"  {mood_emoji} {padded_name}  {kcal_str}  【{mood_name}】"
        lines.append(line)
    
    # 营养汇总
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    if nutrition:
        # 使用传入的汇总数据
        kcal_pct = nutrition.get('kcal_pct', 0)
        protein_pct = nutrition.get('protein_pct', 0)
        carb_pct = nutrition.get('carb_pct', 0)
        fat_pct = nutrition.get('fat_pct', 0)
        snack_count = nutrition.get('snack_count', 0)
        
        lines.append(f"  ✨ 今日元气: {nutrition.get('kcal', 0):.0f} / {nutrition.get('kcal_target', 1800):.0f}")
        lines.append(f"  {draw_text_bar(kcal_pct, 100, 24)}")
        lines.append("")
        lines.append(f"  💪 肌肉小马达: {protein_pct:.0f}%  |  🌾 快乐能量站: {carb_pct:.0f}%  |  🧈 温柔小油箱: {fat_pct:.0f}%")
    else:
        # 单餐汇总（温馨命名版）
        lines.append(f"  ✨ 本餐元气: {total_kcal:.0f}")
        if total_protein + total_carb + total_fat > 0:
            lines.append(f"  💪 肌肉小马达 {total_protein:.0f}g  |  🌾 快乐能量站 {total_carb:.0f}g  |  🧈 温柔小油箱 {total_fat:.0f}g")
    
    return "\n".join(lines)


def render_daily_summary(nutrition, matched_animal=None, all_meals=None, user_text=None):
    """渲染每日总结的文字版
    
    Args:
        nutrition: 营养数据 {kcal, protein, carb, fat, kcal_target, kcal_pct, ...}
        matched_animal: 匹配到的小动物名称
        all_meals: 所有餐次数据，用于智能语录匹配
        user_text: 用户输入的文本，用于检测负罪感
        
    Returns:
        str: 渲染好的每日总结
    """
    
    lines = []
    lines.append("\n" + "=" * 36)
    lines.append("       📊 今日饮食总结")
    lines.append("=" * 36)
    lines.append("")
    
    # 元气进度
    kcal_pct = nutrition.get('kcal_pct', 0)
    lines.append(f"  ✨ 今日元气收集: {nutrition.get('kcal', 0):.0f} / {nutrition.get('kcal_target', 1800):.0f}")
    lines.append(f"  {draw_text_bar(kcal_pct, 100, 28)}")
    lines.append("")
    
    # 三大营养素（温馨命名版）
    protein_pct = nutrition.get('protein_pct', 0)
    carb_pct = nutrition.get('carb_pct', 0)
    fat_pct = nutrition.get('fat_pct', 0)
    
    lines.append("  💪 肌肉小马达 " + draw_text_bar(protein_pct, 100, 15) + f"  {nutrition.get('protein', 0):.0f}g")
    lines.append("  🌾 快乐能量站 " + draw_text_bar(carb_pct, 100, 15) + f"  {nutrition.get('carb', 0):.0f}g")
    lines.append("  🧈 温柔小油箱 " + draw_text_bar(fat_pct, 100, 15) + f"  {nutrition.get('fat', 0):.0f}g")
    lines.append("")
    
    # 今日小动物
    if matched_animal:
        lines.append("  " + "🎭 今日饮食小动物")
        lines.append("  " + "─" * 32)
        ascii_art = get_ascii_animal(matched_animal)
        # 缩进每一行，小动物字符画本身已经带了缩进
        for line in ascii_art.strip().split('\n'):
            lines.append(f"    {line}")
        lines.append("")
    
    # 正念语录（智能匹配版）
    lines.append("  " + "🤍 今日陪伴语录")
    lines.append("  " + "─" * 32)
    quote = get_smart_quote(all_meals=all_meals, matched_animal=matched_animal, user_text=user_text)
    # 自动换行
    import textwrap
    wrapped = textwrap.wrap(quote, width=32)
    for line in wrapped:
        lines.append(f"  {line}")
    lines.append("")
    lines.append("=" * 36)
    
    return "\n".join(lines)


def _count_mood_tags(all_meals):
    """统计所有食物的情绪标签数量"""
    from collections import Counter
    mood_counter = Counter()
    
    for meal_type, foods in all_meals.items():
        for food in foods:
            mood_info = get_food_mood(food.get('name', ''))
            mood_name = mood_info.get('name', '开心食物')
            mood_emoji = mood_info.get('emoji', '😊')
            mood_counter[(mood_emoji, mood_name)] += 1
    
    return mood_counter


def render_full_day_summary(all_meals, nutrition, matched_animal=None, user_text=None):
    """渲染完整的一日手账（所有餐次+总结）
    
    Args:
        all_meals: 所有餐次数据 {meal_type: [foods]}
        nutrition: 营养汇总
        matched_animal: 匹配到的小动物
        user_text: 用户输入的文本，用于检测负罪感
        
    Returns:
        str: 完整的文字版手账
    """
    
    lines = []
    
    # 渲染每个餐次
    meal_order = ['breakfast', 'lunch', 'dinner', 'snack1', 'snack2']
    for meal_type in meal_order:
        if meal_type in all_meals and all_meals[meal_type]:
            lines.append(render_meal_card(meal_type, all_meals[meal_type]))
            lines.append("")
    
    # 食物情绪汇总
    mood_counter = _count_mood_tags(all_meals)
    if mood_counter:
        lines.append("  " + "💫 今日食物情绪汇总")
        lines.append("  " + "─" * 32)
        mood_summary = []
        for (emoji, name), count in sorted(mood_counter.items(), key=lambda x: -x[1]):
            mood_summary.append(f"{emoji}{name}×{count}")
        lines.append("  " + "  ".join(mood_summary))
        lines.append("")
    
    # 渲染每日总结（传递智能语录所需参数）
    lines.append(render_daily_summary(nutrition, matched_animal, all_meals=all_meals, user_text=user_text))
    
    return "\n".join(lines)


# ==================== 快捷测试函数 ====================
def demo():
    """演示文字版手账效果"""
    
    # 模拟数据
    demo_meals = {
        'breakfast': [
            {'name': '水煮蛋', 'amount': 'x 2', 'kcal': 140, 'protein': 12, 'carb': 2, 'fat': 10},
            {'name': '牛奶', 'amount': '200ml', 'kcal': 100, 'protein': 6, 'carb': 10, 'fat': 6},
            {'name': '全麦面包', 'amount': '1片', 'kcal': 80, 'protein': 4, 'carb': 15, 'fat': 1},
        ],
        'lunch': [
            {'name': '鸡胸肉沙拉', 'amount': '200g', 'kcal': 250, 'protein': 30, 'carb': 10, 'fat': 8},
            {'name': '糙米饭', 'amount': '100g', 'kcal': 116, 'protein': 2.6, 'carb': 25, 'fat': 0.3},
        ],
    }
    
    demo_nutrition = {
        'kcal': 686,
        'kcal_target': 1800,
        'kcal_pct': 38,
        'protein': 54.6,
        'protein_pct': 32,
        'carb': 62,
        'carb_pct': 36,
        'fat': 25.3,
        'fat_pct': 32,
        'snack_count': 0,
    }
    
    print(render_full_day_summary(demo_meals, demo_nutrition, '小狐狸'))


if __name__ == '__main__':
    demo()
