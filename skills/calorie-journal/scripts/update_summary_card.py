# 在总结卡片中添加今日燃料类型统计

with open('text_handbook_generator.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 在总结的今日统计后添加燃料类型统计
old_summary_stats = """    # 汇总数据
    lines.append('├─────────────────────────────────────┤')
    lines.append('│  📊 今日汇总')
    lines.append(f'│      摄入能量: 约{total_cal} kcal')
    if exercise_kcal > 0:
        lines.append(f'│      运动消耗: 约{exercise_kcal} kcal')
    lines.append('│')
    lines.append(f'│      蛋白质总计: {total_protein}g')
    lines.append(f'│      碳水总计: {total_carbs}g')
    lines.append(f'│      脂肪总计: {total_fat}g')
    lines.append(f'│      膳食纤维总计: {total_fiber}g')"""

new_summary_stats = """    # 今日燃料类型统计
    fuel_counts = {}
    for meal in meals_data:
        fuel_type = get_fuel_type(meal['nutrition'], theme)
        fuel_counts[fuel_type] = fuel_counts.get(fuel_type, 0) + 1
    
    # 获取主题系统名称和分类
    t = THEMES[theme]
    if theme == 'space_explorer':
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
    for fuel_type, count in fuel_counts.items():
        label, icon = system['categories'].get(fuel_type, ('未知', '❓'))
        lines.append(f'│      {icon} {label}: {count}份')"""

content = content.replace(old_summary_stats, new_summary_stats)

with open('text_handbook_generator.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ 已为总结卡片添加燃料类型统计")
