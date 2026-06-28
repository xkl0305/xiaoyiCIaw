# 调整更合理的燃料类型推断规则

with open('text_handbook_generator.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_rules = '''def get_fuel_type(nutrition_data, theme='healing_forest'):
    """
    基于营养数据智能推断食物属性（燃料类型/情绪类型）
    
    规则：
    - 🔥 高燃燃料/happy：热量 > 400 kcal 或 碳水 > 50g
    - 🚀 星际补给/supply：蛋白质 > 20g
    - 🌟 稳定能量/stable：脂肪 < 10g 且 纤维 > 5g
    - 🌙 轻型燃料/light：其他情况
    """
    cal = nutrition_data.get('calories', 0)
    protein = nutrition_data.get('protein', 0)
    carbs = nutrition_data.get('carbs', 0)
    fat = nutrition_data.get('fat', 0)
    fiber = nutrition_data.get('fiber', 0)
    
    if cal > 400 or carbs > 50:
        return 'high_energy' if theme == 'space_explorer' else 'happy'
    elif protein > 20:
        return 'supply' if theme == 'space_explorer' else 'energy'
    elif fat < 10 and fiber > 5:
        return 'stable' if theme == 'space_explorer' else 'healing'
    else:
        return 'light' if theme == 'space_explorer' else 'comfort'
'''

new_rules = '''def get_fuel_type(nutrition_data, theme='healing_forest'):
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
    
    if theme == 'space_explorer':
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
'''

content = content.replace(old_rules, new_rules)

with open('text_handbook_generator.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ 已更新为更合理的分类规则")
