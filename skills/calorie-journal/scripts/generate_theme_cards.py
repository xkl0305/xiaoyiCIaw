#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v2.5 主题包系统 - 集成到原有卡片结构
保留原有7张卡片结构，只改变主题（命名/风格/话术）
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gen_card import (
    generate_meal_card, generate_exercise_card,
    generate_consume_card, generate_summary_card,
    draw_sticker_star, draw_sticker_heart, draw_sticker_leaf,
    draw_sticker_sun, draw_sticker_flower
)

# ==================== 主题包配置 ====================
THEME_PACKS = {
    'healing_forest': {
        'name': '治愈森林',
        'card_titles': {
            'breakfast': '清晨能量',
            'lunch': '午后活力',
            'snack1': '小确幸',
            'snack2': '暖心时光',
            'exercise': '轻盈律动',
            'consume': '基础能量',
            'summary': '每日陪伴'
        },
        'nutrition_names': {
            'kcal': '元气值',
            'protein': '肌肉力',
            'carb': '快乐源',
            'fat': '保护层'
        },
        'stickers': {
            'breakfast': ['sun', 'star'],
            'lunch': ['leaf', 'star'],
            'snack1': ['flower'],
            'snack2': ['heart'],
            'exercise': ['star', 'star'],
            'consume': ['star'],
            'summary': ['star', 'heart']
        },
        'quotes': {
            'breakfast': '新的一天，从好好吃饭开始',
            'lunch': '午后的能量，是下午的底气',
            'snack1': '小确幸，大快乐',
            'snack2': '每一口，都是对自己的温柔',
            'exercise': '流汗也是疗愈',
            'consume': '你的存在，本身就需要能量',
            'summary': '今天也在好好照顾自己呢'
        },
        'default_style': 'paper'
    },
    
    'space_explorer': {
        'name': '星际探索',
        'card_titles': {
            'breakfast': '发射准备',
            'lunch': '轨道补给',
            'snack1': '能量注入',
            'snack2': '星际下午茶',
            'exercise': '太空训练',
            'consume': '基础能耗',
            'summary': '航行日志'
        },
        'nutrition_names': {
            'kcal': '星能值',
            'protein': '护盾值',
            'carb': '推进力',
            'fat': '储备舱'
        },
        'stickers': {
            'breakfast': ['star', 'star'],
            'lunch': ['star', 'star'],
            'snack1': ['star'],
            'snack2': ['star'],
            'exercise': ['star', 'star'],
            'consume': ['star'],
            'summary': ['star', 'star']
        },
        'quotes': {
            'breakfast': '能量注入，准备起飞',
            'lunch': '补给完成，续航+1',
            'snack1': '能量+1',
            'snack2': '星际航行，能量补充',
            'exercise': '体能训练完成',
            'consume': '基础能耗正常',
            'summary': '今日航行任务完成'
        },
        'default_style': 'dark_night'
    }
}

# 贴纸绘制函数映射
STICKER_FUNCS = {
    'star': draw_sticker_star,
    'heart': draw_sticker_heart,
    'leaf': draw_sticker_leaf,
    'sun': draw_sticker_sun,
    'flower': draw_sticker_flower
}


def generate_theme_pack(theme_id: str, output_dir: str = None):
    """
    生成一个完整主题包的7张卡片
    
    Args:
        theme_id: 'healing_forest' 或 'space_explorer'
        output_dir: 输出目录
    """
    theme = THEME_PACKS[theme_id]
    
    if output_dir is None:
        output_dir = f'theme_{theme_id}'
    
    os.makedirs(output_dir, exist_ok=True)
    
    print(f'🎨 生成主题包：{theme["name"]}')
    print(f'📁 输出目录：{output_dir}')
    print()
    
    # ==================== 示例数据 ====================
    breakfast_data = {
        'foods': ['水煮蛋 × 2', '全麦面包 × 2片', '牛奶 250ml'],
        'nutrition': {'protein': 26, 'carb': 35, 'fat': 12},
        'kcal': 350,
        'recommendation': theme['quotes']['breakfast']
    }
    
    lunch_data = {
        'foods': ['糙米饭 150g', '鸡胸肉 120g', '西兰花 200g', '番茄炒蛋'],
        'nutrition': {'protein': 45, 'carb': 55, 'fat': 15},
        'kcal': 580,
        'recommendation': theme['quotes']['lunch']
    }
    
    snack1_data = {
        'foods': ['酸奶 200g', '小番茄 100g'],
        'nutrition': {'protein': 10, 'carb': 20, 'fat': 5},
        'kcal': 150,
        'recommendation': theme['quotes']['snack1']
    }
    
    snack2_data = {
        'foods': ['坚果混合 30g', '黑咖啡'],
        'nutrition': {'protein': 5, 'carb': 8, 'fat': 18},
        'kcal': 240,
        'recommendation': theme['quotes']['snack2']
    }
    
    exercise_data = {
        'exercise': '慢跑 30分钟',
        'consume': 250,
        'time': '18:00',
        'recommendation': theme['quotes']['exercise']
    }
    
    daily_kcal = breakfast_data['kcal'] + lunch_data['kcal'] + snack1_data['kcal'] + snack2_data['kcal']
    
    # ==================== 生成7张卡片 ====================
    
    # 1. 早餐
    print('1️⃣  早餐卡片')
    generate_meal_card(
        'breakfast',
        theme['card_titles']['breakfast'],
        '07:30',
        breakfast_data['foods'],
        breakfast_data['nutrition'],
        breakfast_data['kcal'],
        breakfast_data['recommendation'],
        style=theme['default_style']
    ).save(f'{output_dir}/01_{theme_id}_早餐.png')
    
    # 2. 午餐
    print('2️⃣  午餐卡片')
    generate_meal_card(
        'lunch',
        theme['card_titles']['lunch'],
        '12:30',
        lunch_data['foods'],
        lunch_data['nutrition'],
        lunch_data['kcal'],
        lunch_data['recommendation'],
        style=theme['default_style']
    ).save(f'{output_dir}/02_{theme_id}_午餐.png')
    
    # 3. 加餐1
    print('3️⃣  加餐1卡片')
    generate_meal_card(
        'snack1',
        theme['card_titles']['snack1'],
        '10:00',
        snack1_data['foods'],
        snack1_data['nutrition'],
        snack1_data['kcal'],
        snack1_data['recommendation'],
        style=theme['default_style']
    ).save(f'{output_dir}/03_{theme_id}_加餐1.png')
    
    # 4. 加餐2
    print('4️⃣  加餐2卡片')
    generate_meal_card(
        'snack2',
        theme['card_titles']['snack2'],
        '15:30',
        snack2_data['foods'],
        snack2_data['nutrition'],
        snack2_data['kcal'],
        snack2_data['recommendation'],
        style=theme['default_style']
    ).save(f'{output_dir}/04_{theme_id}_加餐2.png')
    
    # 5. 运动
    print('5️⃣  运动卡片')
    generate_exercise_card(
        exercise_data['exercise'],
        exercise_data['consume'],
        exercise_data['time'],
        exercise_data['recommendation'],
        style=theme['default_style']
    ).save(f'{output_dir}/05_{theme_id}_运动.png')
    
    # 6. 基础消耗
    print('6️⃣  基础消耗卡片')
    generate_consume_card(
        base_kcal=1400,
        activity_kcal=daily_kcal - 1400,
        total_kcal=daily_kcal,
        recommendation=theme['quotes']['consume'],
        style=theme['default_style']
    ).save(f'{output_dir}/06_{theme_id}_基础消耗.png')
    
    # 7. 总结
    print('7️⃣  总结卡片')
    generate_summary_card(
        breakfast_data['nutrition'],
        lunch_data['nutrition'],
        snack1_data['nutrition'],
        snack2_data['nutrition'],
        daily_kcal,
        theme['quotes']['summary'],
        style=theme['default_style']
    ).save(f'{output_dir}/07_{theme_id}_总结.png')
    
    print()
    print('=' * 50)
    print(f'✅ {theme["name"]} 主题包7张卡片生成完成！')
    print(f'📊 营养命名：{list(theme["nutrition_names"].values())}')
    print('=' * 50)
    
    # 列出文件
    print()
    print('文件列表：')
    total_size = 0
    for f in sorted(os.listdir(output_dir)):
        size = os.path.getsize(f'{output_dir}/{f}') // 1024
        total_size += size
        print(f'  🖼️  {f} ({size} KB)')
    print(f'\n  总计：{total_size} KB')


if __name__ == '__main__':
    # 生成治愈森林主题包
    print('=' * 60)
    generate_theme_pack('healing_forest', 'output_theme_healing')
    print()
    print()
    
    # 生成星际探索主题包
    print('=' * 60)
    generate_theme_pack('space_explorer', 'output_theme_space')
