#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v2.5 完整字符手账生成系统
支持治愈森林/星际探索双主题
动态卡片数量，有什么数据生成什么卡片
"""

# ==================== 主题包配置 ====================
THEMES = {
    'healing_forest': {
        'name': '治愈森林',
        'role': '小狐狸',
        'role_icon': '🦊',
        # 食物情绪系统
        'mood_system': {
            'name': '食物情绪',
            'categories': {
                'happy': ('开心食物', '😊'),
                'healing': ('治愈食物', '🌸'),
                'energy': ('能量食物', '⚡'),
                'comfort': ('安慰食物', '🍫'),
            },
            'summary_text': '今日食物情绪统计',
        },
        # 通用燃料类型系统（兼容
        'fuel_system': {
            'name': '燃料类型',
            'categories': {
                'high_energy': ('高燃燃料', '🔥'),
                'supply': ('星际补给', '🚀'),
                'stable': ('稳定能量', '🌟'),
                'light': ('轻型燃料', '🌙'),
            },
            'summary_text': '今日燃料类型统计',
        },
        'meal_titles': {
            'breakfast': '清晨能量',
            'lunch': '午后活力',
            'dinner': '星夜温柔',
            'snack': '小确幸',
            'exercise': '轻盈律动',
            'basal': '基础能量',
            'summary': '每日陪伴'
        },
        'nutrition_names': {
            'calories': ('元气值', '🔥'),
            'protein': ('肌肉力', '💪'),
            'carbs': ('快乐源', '✨'),
            'fat': ('能量储备', '💡'),
            'fiber': ('清道夫', '🌱')
        },
        'quotes': {
            'breakfast': '新的一天，从好好吃饭开始',
            'lunch': '午后的能量，是下午的底气',
            'dinner': '清淡的一餐，给身体放个假',
            'snack': '小确幸，大快乐',
            'exercise': '流汗也是疗愈',
            'basal': '你的存在，本身就需要能量',
            'summary': '今天也在好好照顾自己呢 🌸',
            'late_night': '吃东西不是罪恶，是照顾自己'
        },
        'stickers': ['⭐', '❤️', '🍃', '🌸', '☀️'],
        'companion_text': '今日森林伙伴'
    },
    
    'space_explorer': {
        'name': '星际探索',
        'role': '舰长',
        'role_icon': '👨‍🚀',
        # 燃料类型系统
        'fuel_system': {
            'name': '燃料类型',
            'categories': {
                'high_energy': ('高燃燃料', '🔥'),
                'supply': ('星际补给', '🚀'),
                'stable': ('稳定能量', '🌟'),
                'light': ('轻型燃料', '🌙'),
            },
            'summary_text': '今日燃料类型统计',
        },
        # 治愈森林的食物情绪系统
        'mood_system': {
            'name': '食物情绪',
            'categories': {
                'happy': ('开心食物', '😊'),
                'healing': ('治愈食物', '🌸'),
                'energy': ('能量食物', '⚡'),
                'comfort': ('安慰食物', '🍫'),
            },
            'summary_text': '今日食物情绪统计',
        },
        'meal_titles': {
            'breakfast': '发射准备',
            'lunch': '轨道补给',
            'dinner': '星际晚餐',
            'snack': '能量注入',
            'exercise': '太空训练',
            'basal': '基础能耗',
            'summary': '航行日志'
        },
        'nutrition_names': {
            'calories': ('星能值', '🔥'),
            'protein': ('护盾值', '💪'),
            'carbs': ('推进力', '✨'),
            'fat': ('储备舱', '💡'),
            'fiber': ('净化器', '🌱')
        },
        'quotes': {
            'breakfast': '能量注入，准备起飞',
            'lunch': '补给完成，续航+1',
            'dinner': '夜间补给完成',
            'snack': '能量+1',
            'exercise': '体能训练完成',
            'basal': '基础能耗正常运行',
            'summary': '今日航行任务圆满完成',
            'late_night': '宇宙不打烊，你的能量也一样'
        },
        'stickers': ['⭐', '🚀', '🌙', '🌟', '✨'],
        'companion_text': '今日领航员'
    },

    'dragon_new_year': {
        'name': '龙年新春',
        'role': '小龙人',
        'role_icon': '🐉',
        'meal_titles': {
            'breakfast': '晨开运',
            'lunch': '午纳福',
            'dinner': '夜团圆',
            'snack': '小年味',
            'exercise': '跃龙门',
            'basal': '根基气',
            'summary': '岁末吉'
        },
        'nutrition_names': {
            'calories': ('福气值', '🧧'),
            'protein': ('龙气力', '💪'),
            'carbs': ('喜庆源', '🏮'),
            'fat': ('富足感', '✨'),
            'fiber': ('清道夫', '🌱')
        },
        'food_attribute_system': {
            'name': '年味类型',
            'categories': {
                'lucky': ('开运美食', '🧧'),
                'auspicious': ('吉祥佳肴', '🎊'),
                'blessing': ('福气点心', '🏮'),
                'reunion': ('团圆盛宴', '🥢'),
            },
            'summary_text': '今日年味统计',
        },
        'quotes': {
            'breakfast': '龙年大吉，吃好喝好',
            'lunch': '新春快乐，元气满满',
            'dinner': '团圆是福，好好吃饭',
            'snack': '小小年味，大大幸福',
            'exercise': '跃龙门，身体棒',
            'basal': '你的存在，本身就是最大的福气',
            'summary': '龙年吉祥，岁岁平安',
            'late_night': '年夜加餐，福气加倍'
        },
        'stickers': ['🧧', '🎆', '🏮', '🧨', '🎊'],
        'companion_text': '今日新春使者'
    }
}

# ==================== 建议文案库 ====================
SUGGESTIONS = {
    'breakfast': '💡 建议：早餐加份水果，开启活力一天',
    'lunch': '💡 建议：餐后散步10分钟，帮助消化',
    'dinner': '💡 建议：晚餐清淡为主，给肠胃休息时间',
    'snack': '💡 建议：选择坚果或酸奶，健康又满足',
    'exercise': '💡 建议：运动后记得补充水分和蛋白质',
}



# ==================== 食物属性推断函数 ====================
def get_attribute_type(nutrition_data, theme='healing_forest'):
    """
    基于营养数据智能推断食物属性（燃料类型/情绪类型）
    
    【星际探索 - 燃料类型】：
    - 🔥 高燃燃料：热量 > 550 kcal 或 脂肪 > 25g（真正的高能量密度
    - 🚀 星际补给：蛋白质 > 25g（高蛋白修复型
    - 🌟 稳定能量：纤维 > 6g 且 碳水 > 30g 且 脂肪 < 15g（缓释型复合碳水
    - 🌙 轻型燃料：其他情况（轻食、零食、低卡
    
    【治愈森林 - 食物情绪】：
    - 😊 开心食物：碳水 > 40g（碳水带来愉悦感
    - ⚡ 能量食物：蛋白质 > 20g
    - 🌸 治愈食物：纤维 > 5g 且 脂肪 < 12g
    - 🍫 安慰食物：其他情况
    """
    cal = nutrition_data.get('calories', 0)
    protein = nutrition_data.get('protein', 0)
    carbs = nutrition_data.get('carbs', 0)
    fat = nutrition_data.get('fat', 0)
    fiber = nutrition_data.get('fiber', 0)
    
    if theme == 'dragon_new_year':
        # 龙年新春主题：年味类型
        if cal > 550 or fat > 20:
            return 'lucky'
        elif protein > 25:
            return 'auspicious'
        elif carbs > 60:
            return 'blessing'
        else:
            return 'reunion'
    elif theme == 'space_explorer':
        # 星际探索主题：燃料类型
        if cal > 550 or fat > 25:
            return 'high_energy'
        elif protein > 25:
            return 'supply'
        elif fiber > 6 and carbs > 30 and fat < 15:
            return 'stable'
        else:
            return 'light'
    else:
        # 治愈森林主题：食物情绪
        if carbs > 40:
            return 'happy'
        elif protein > 20:
            return 'energy'
        elif fiber > 5 and fat < 12:
            return 'healing'
        else:
            return 'comfort'


def get_attribute_label(attr_type, theme='healing_forest'):
    """获取属性标签和图标"""
    t = THEMES[theme]
    
    
    # 根据主题选择对应的属性系统
    if theme == 'dragon_new_year':
        system = t['food_attribute_system']
    elif theme == 'space_explorer':
        system = t['fuel_system']
    else:
        system = t['mood_system']
    
    return system['categories'].get(attr_type, ('未知', '❓'))


# ==================== 卡片生成函数 ====================

    
    return system['categories'].get(attr_type, ('未知', '❓'))


# ==================== 卡片生成函数 ====================

def generate_meal_card(meal_type, food_items, nutrition_data, 
                        time=None, theme='healing_forest', is_late_night=False):
    """
    生成单餐字符手账卡片
    """
    t = THEMES[theme]
    title = t['meal_titles'][meal_type]
    names = t['nutrition_names']
    stickers = t['stickers']
    names = t['nutrition_names']
    
    # 选择话术
    if is_late_night:
        quote = t['quotes']['late_night']
    else:
        quote = t['quotes'].get(meal_type, t['quotes']['breakfast'])
    
    lines = []
    lines.append('┌─────────────────────────────────────┐')
    lines.append(f'│  {title:22s}          {t["role_icon"]} {t["role"]}')
    lines.append('├─────────────────────────────────────┤')
    
    # 时间
    if time:
        lines.append(f'│  🕐 {time}')
    else:
        lines.append('│  🕐 --:--')
    lines.append('│')
    
    # 食物列表
    for food in food_items:
        lines.append(f'│  {food}')
    lines.append('│')
    
    # 本餐燃料类型（单独一行，清晰可见
    attr_type = get_attribute_type(nutrition_data, theme)
    attr_label, attr_icon = get_attribute_label(attr_type, theme)
    lines.append(f'│  {attr_icon} 本餐类型：{attr_label}')
    lines.append('│')
    
    # 原始数据
    lines.append('├─────────────────────────────────────┤')
    lines.append('│  📊 原始数据')
    lines.append(f'│      热量(kcal): 约{nutrition_data["calories"]}')
    lines.append(f'│      蛋白质(g): 约{nutrition_data["protein"]}')
    lines.append(f'│      碳水(g): 约{nutrition_data["carbs"]}')
    lines.append(f'│      脂肪(g): 约{nutrition_data["fat"]}')
    lines.append(f'│      纤维(g): 约{nutrition_data["fiber"]}')
    
    # 主题数据
    lines.append('├─────────────────────────────────────┤')
    lines.append('│  ✨ 主题数据')
    lines.append(f'│      {names["calories"][1]} {names["calories"][0]}: {nutrition_data["calories"]}')
    lines.append(f'│      {names["protein"][1]} {names["protein"][0]}: {nutrition_data["protein"]}g')
    lines.append(f'│      {names["carbs"][1]} {names["carbs"][0]}: {nutrition_data["carbs"]}g')
    lines.append(f'│      {names["fat"][1]} {names["fat"][0]}: {nutrition_data["fat"]}g')
    lines.append(f'│      {names["fiber"][1]} {names["fiber"][0]}: {nutrition_data["fiber"]}g')
    
    # 陪伴语录
    lines.append('├─────────────────────────────────────┤')
    lines.append('│  💬 陪伴语录')
    lines.append(f'│     「{quote}」')
    
    # 建议区域
    if meal_type in SUGGESTIONS:
        lines.append('├─────────────────────────────────────┤')
        lines.append('│  ' + SUGGESTIONS[meal_type])
    
    # 底部贴纸
    lines.append('│                                     ' + '  '.join(stickers[:3]))
    lines.append('└─────────────────────────────────────┘')
    
    return '\n'.join(lines)


def generate_exercise_card(exercise_type, consume_kcal, theme='healing_forest'):
    """生成运动卡片"""
    t = THEMES[theme]
    title = t['meal_titles']['exercise']
    stickers = t['stickers']
    names = t['nutrition_names']
    quote = t['quotes']['exercise']
    
    lines = []
    lines.append('┌─────────────────────────────────────┐')
    lines.append(f'│  {title:22s}          {t["role_icon"]} {t["role"]}')
    lines.append('├─────────────────────────────────────┤')
    
    # 运动类型
    lines.append(f'│  🏃 {exercise_type}')
    lines.append('│')
    
    # 消耗数据
    lines.append('├─────────────────────────────────────┤')
    lines.append('│  📊 消耗数据')
    lines.append(f'│      消耗能量: 约{consume_kcal} kcal')
    
    # 主题数据
    lines.append('├─────────────────────────────────────┤')
    lines.append('│  ✨ 主题数据')
    lines.append(f'│      🔥 {names["calories"][0]}消耗: {consume_kcal}')
    lines.append('│      💨 轻盈指数: ⭐⭐⭐⭐⭐')
    lines.append('│      🎯 今日目标: 已达成')
    
    # 语录
    lines.append('├─────────────────────────────────────┤')
    lines.append(f'│  💬 「{quote}」')
    
    # 建议区域
    lines.append('├─────────────────────────────────────┤')
    lines.append('│  ' + SUGGESTIONS['exercise'])
    
    # 底部贴纸
    lines.append('│                                     ' + '  '.join(stickers[:3]))
    lines.append('└─────────────────────────────────────┘')
    
    return '\n'.join(lines)


def generate_basal_card(gender, height, weight, age=None, theme='healing_forest'):
    """生成基础代谢卡片"""
    t = THEMES[theme]
    title = t['meal_titles']['basal']
    names = t['nutrition_names']
    stickers = t['stickers']
    names = t['nutrition_names']
    quote = t['quotes']['basal']
    
    # Mifflin-St Jeor公式
    if gender == '男':
        bmr = 10 * weight + 6.25 * height - 5 * (age or 25) + 5
    else:
        bmr = 10 * weight + 6.25 * height - 5 * (age or 25) - 161
    
    bmr = int(bmr)
    daily_reference = int(bmr * 1.3)
    
    lines = []
    lines.append('┌─────────────────────────────────────┐')
    lines.append(f'│  {title:22s}          {t["role_icon"]} {t["role"]}')
    lines.append('├─────────────────────────────────────┤')
    
    # 用户信息
    lines.append('│  👤 用户信息')
    lines.append(f'│      性别: {gender}')
    lines.append(f'│      身高: {height} cm')
    lines.append(f'│      体重: {weight} kg')
    if age:
        lines.append(f'│      年龄: {age}岁')
    else:
        lines.append(f'│      年龄: 未填写（按默认25岁计算）')
    lines.append('│')
    
    # 基础数据
    lines.append('├─────────────────────────────────────┤')
    lines.append('│  📊 身体基础数据')
    lines.append(f'│      每日基础能量: 约{bmr} kcal')
    lines.append('│      日常活动水平: 轻度')
    lines.append(f'│      每日参考能量: 约{daily_reference} kcal')
    
    # 主题数据
    lines.append('├─────────────────────────────────────┤')
    lines.append('│  ✨ 主题数据')
    lines.append(f'│      {names["calories"][1]} 每日基础{names["calories"][0]}: {bmr}')
    lines.append(f'│      🌟 今日参考{names["calories"][0]}: {daily_reference}')
    lines.append('│      💡 数值仅供参考，请听从身体感受')
    
    # 语录
    lines.append('├─────────────────────────────────────┤')
    lines.append(f'│  💬 「{quote}」')
    
    # 建议区域
    lines.append('├─────────────────────────────────────┤')
    lines.append('│  💡 建议：配合体脂率和肌肉量数据更准确')
    
    # 底部贴纸
    lines.append('│                                     ' + '  '.join(stickers[:3]))
    lines.append('└─────────────────────────────────────┘')
    
    return '\n'.join(lines)


def generate_summary_card(meals_data, exercise_data=None, 
                          basal_data=None, theme='healing_forest'):
    """生成每日总结卡片"""
    t = THEMES[theme]
    title = t['meal_titles']['summary']
    names = t['nutrition_names']
    
    # 汇总数据
    total_cal = sum(m['nutrition']['calories'] for m in meals_data)
    total_protein = sum(m['nutrition']['protein'] for m in meals_data)
    total_carbs = sum(m['nutrition']['carbs'] for m in meals_data)
    total_fat = sum(m['nutrition']['fat'] for m in meals_data)
    total_fiber = sum(m['nutrition']['fiber'] for m in meals_data)
    
    exercise_kcal = exercise_data['consume'] if exercise_data else 0
    meal_count = len(meals_data)  # ✅ 修复：只统计用餐次数
    
    lines = []
    lines.append('┌─────────────────────────────────────┐')
    lines.append(f'│  {title:22s}          {t["role_icon"]} {t["role"]}')
    lines.append('├─────────────────────────────────────┤')
    lines.append('│  📅 今日统计')
    lines.append('│')
    lines.append(f'│      用餐次数: {meal_count}次记录')
    lines.append('│')
    
    # 今日燃料类型统计
    attr_counts = {}
    for meal in meals_data:
        attr_type = get_attribute_type(meal['nutrition'], theme)
        attr_counts[attr_type] = attr_counts.get(attr_type, 0) + 1
    
    # 获取主题系统名称和分类
    
    # 获取主题系统名称和分类
    t = THEMES[theme]
    if theme == 'dragon_new_year':
        system = t['food_attribute_system']
    elif theme == 'space_explorer':
        system = t['fuel_system']
    else:
        system = t['mood_system']
    
    
    # 汇总数据
    lines.append('├─────────────────────────────────────┤')
    lines.append('│  📊 今日汇总')
    lines.append(f'│      摄入能量: 约{total_cal} kcal')
    if exercise_kcal > 0:
        lines.append(f'│      运动消耗: 约{exercise_kcal} kcal')
    lines.append('│')
    lines.append(f'│      蛋白质总计: {total_protein}g')
    lines.append(f'│      碳水总计: {total_carbs}g')
    lines.append(f'│      脂肪总计: {total_fat}g')
    lines.append(f'│      膳食纤维总计: {total_fiber}g')
    
    # 添加燃料/情绪统计
    lines.append('├─────────────────────────────────────┤')
    lines.append(f'│  📊 {system["summary_text"]}')
    for attr_type, count in attr_counts.items():
        label, icon = system['categories'].get(attr_type, ('未知', '❓'))
        lines.append(f'│      {icon} {label}: {count}份')
    lines.append('│      💡 基于营养数据自动分类')
    
    # 主题汇总
    lines.append('├─────────────────────────────────────┤')
    lines.append('│  ✨ 主题汇总')
    lines.append(f'│      {names["calories"][1]} 今日{names["calories"][0]}: {total_cal}')
    lines.append(f'│      {names["protein"][1]} 肌肉补给: {total_protein}g 充足')
    lines.append(f'│      {names["carbs"][1]} 快乐指数: {total_carbs}g 充足')
    lines.append(f'│      {names["fat"][1]} 能量储备: {total_fat}g 充足')
    lines.append(f'│      {names["fiber"][1]} 总计: {total_fiber}g 良好')
    
    # 语录
    lines.append('├─────────────────────────────────────┤')
    lines.append('│  💬 「' + t['quotes']['summary'] + '」')
    lines.append('│')
    
    # ✅ 修复：根据主题显示不同陪伴文案
    lines.append(f'│  {t["role_icon"]} {t["companion_text"]}: {t["role"]}')
    lines.append('│                                     ' + '  '.join(t['stickers'][:3]))
    lines.append('└─────────────────────────────────────┘')
    
    return '\n'.join(lines)


def generate_daily_handbook(user_data, theme='healing_forest'):
    """
    生成完整的每日字符手账（动态卡片数量）
    
    user_data 格式:
    {
        'meals': [
            {'type': 'breakfast', 'foods': ['...'], 'nutrition': {...}, 'time': '07:30'},
        ],
        'exercise': {'type': '步行12000步', 'consume': 360},
        'basal': {'gender': '男', 'height': 175, 'weight': 68, 'age': 25}
    }
    """
    t = THEMES[theme]
    all_cards = []
    
    print('=' * 70)
    print(f'  {t["role_icon"]} {t["name"]}手账 · 完整一天')
    print('=' * 70)
    print()
    
    # 1. 生成各餐卡片
    for i, meal in enumerate(user_data['meals'], 1):
        print(f'📋 {i:02d}_{meal["type"]}卡片')
        print('-' * 50)
        card = generate_meal_card(
            meal['type'], meal['foods'], meal['nutrition'],
            meal.get('time'), theme=theme,
            is_late_night=meal.get('is_late_night', False)
        )
        print(card)
        print()
        all_cards.append(card)
    
    # 2. 生成运动卡片
    if 'exercise' in user_data and user_data['exercise']:
        print(f'📋 {len(all_cards)+1:02d}_运动卡片')
        print('-' * 50)
        ex = user_data['exercise']
        card = generate_exercise_card(ex['type'], ex['consume'], theme=theme)
        print(card)
        print()
        all_cards.append(card)
    
    # 3. 生成基础代谢卡片
    if 'basal' in user_data and user_data['basal']:
        print(f'📋 {len(all_cards)+1:02d}_基础代谢卡片')
        print('-' * 50)
        b = user_data['basal']
        card = generate_basal_card(b['gender'], b['height'], b['weight'], b.get('age'), theme=theme)
        print(card)
        print()
        all_cards.append(card)
    
    # 4. 生成总结卡片（如果记录>=2项）
    if len(all_cards) >= 2:
        print(f'📋 {len(all_cards)+1:02d}_总结卡片')
        print('-' * 50)
        card = generate_summary_card(
            user_data['meals'], 
            user_data.get('exercise'),
            user_data.get('basal'),
            theme=theme
        )
        print(card)
        print()
        all_cards.append(card)
    
    print('=' * 70)
    print(f'✅ 共生成 {len(all_cards)} 张卡片')
    print(f'🎨 主题: {t["name"]}')
    print(f'💡 所有数值均为估算值，仅供参考')
    print('=' * 70)
    
    return all_cards


# ==================== 测试用例 ====================
if __name__ == '__main__':
    
    # 测试用户数据
    test_user = {
        'meals': [
            {
                'type': 'breakfast',
                'foods': ['🥚 两个鸡蛋', '🍖 一个肉包子'],
                'nutrition': {'calories': 380, 'protein': 22, 'carbs': 35, 'fat': 16, 'fiber': 4},
                'time': '07:30'
            },
            {
                'type': 'lunch',
                'foods': ['🍜 一碗牛肉面', '      （牛肉 + 面条 + 蔬菜）'],
                'nutrition': {'calories': 620, 'protein': 32, 'carbs': 75, 'fat': 20, 'fiber': 6},
                'time': '12:30'
            },
            {
                'type': 'dinner',
                'foods': ['🍅 西红柿一个', '🐟 蒸三文鱼一份'],
                'nutrition': {'calories': 340, 'protein': 40, 'carbs': 8, 'fat': 18, 'fiber': 3},
                'time': '18:30'
            },
            {
                'type': 'snack',
                'foods': ['🍞 一份烤冷面', '      （面饼 + 鸡蛋 + 酱料）'],
                'nutrition': {'calories': 420, 'protein': 12, 'carbs': 55, 'fat': 18, 'fiber': 5},
                'time': '15:00'
            }
        ],
        'exercise': {
            'type': '步行 12000 步',
            'consume': 360
        },
        'basal': {
            'gender': '男',
            'height': 175,
            'weight': 68
            # age不填，测试默认值
        }
    }
    
    # 生成治愈森林主题
    print()
    print('🦊' * 35)
    print()
    generate_daily_handbook(test_user, theme='healing_forest')
    print()
    
    # 也可以生成星际探索主题
    # generate_daily_handbook(test_user, theme='space_explorer')
