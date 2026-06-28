# 在食物名称旁边添加燃料类型标签

with open('text_handbook_generator.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 修改单餐卡片的食物显示部分
old_food_display = """    # 食物
    for food in food_items:
        lines.append(f'│  {food}')
    lines.append('│')"""

new_food_display = """    # 食物 + 燃料类型标签
    fuel_type = get_fuel_type(nutrition_data, theme)
    fuel_label, fuel_icon = get_attribute_label(fuel_type, theme)
    
    for i, food in enumerate(food_items):
        if i == 0:
            # 第一个食物显示燃料标签
            lines.append(f'│  {food}  {fuel_icon}【{fuel_label}】')
        else:
            lines.append(f'│  {food}')
    lines.append('│')"""

content = content.replace(old_food_display, new_food_display)

with open('text_handbook_generator.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ 已为单餐卡片添加燃料类型标签")
