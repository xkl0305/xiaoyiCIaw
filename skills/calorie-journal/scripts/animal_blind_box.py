# -*- coding: utf-8 -*-
"""
v2.1 优化：小动物盲盒系统
=========================
根据当日真实营养数据动态匹配专属小动物
每天都是惊喜！
"""

# ============== 7只可爱小动物 ==============
# 【重要】匹配顺序：越特殊的条件越靠前，越宽泛的条件越靠后
ANIMALS = [
    # (name, emoji, slogan, condition_function)
    
    # 🐿️ 小松鼠：加餐多（最特殊的条件，优先匹配）
    ('小松鼠', '🐿️', '东藏一口西囤一点，小嘴不停歇',
     lambda p, c, f, k, s: s >= 2),
    
    # 🐰 小兔子：吃得少/热量缺口大（特殊条件）
    ('小兔子', '🐰', '嚼嚼绿叶就满足，轻盈感满分',
     lambda p, c, f, k, s: k < 80),
    
    # 🐻 小熊：高脂肪高热量（特殊条件）
    ('小熊', '🐻', '吃得饱饱的，离冬眠又近一步',
     lambda p, c, f, k, s: f > 35 and k > 90),
    
    # 🐆 小猎豹：高蛋白低碳水（特殊条件）
    ('小猎豹', '🐆', '蛋白质是猎物，全速冲刺不手软',
     lambda p, c, f, k, s: p > 35 and c < 40),
    
    # 🐹 小仓鼠：高碳水（特殊条件）
    ('小仓鼠', '🐹', '腮帮子塞满碳水，圆滚滚好安心',
     lambda p, c, f, k, s: c > 55),
    
    # 🦊 小狐狸：饮食均衡（较宽泛条件）
    ('小狐狸', '🦊', '什么都吃一点，精明得很到位',
     lambda p, c, f, k, s: 15 <= p <= 40 and 35 <= c <= 60 and 15 <= f <= 35),
    
    # 🐱 小猫咪：兜底匹配（总是最后一个）
    ('小猫咪', '🐱', '不挑食不浪费，悠哉悠哉刚刚好',
     lambda p, c, f, k, s: True),  # 总是匹配
]


def match_diet_animal(protein_pct, carb_pct, fat_pct, kcal_pct, snack_count):
    """根据营养比例匹配饮食小动物
    
    Args:
        protein_pct: 蛋白质占比（%，比如 30 表示30%）
        carb_pct: 碳水占比（%）
        fat_pct: 脂肪占比（%）
        kcal_pct: 热量完成度（%，比如 85 表示完成85%目标）
        snack_count: 加餐次数
        
    Returns:
        tuple: (name, emoji, slogan)
    """
    for name, emoji, slogan, cond in ANIMALS:
        if cond(protein_pct, carb_pct, fat_pct, kcal_pct, snack_count):
            return name, emoji, slogan
    
    # 兜底（理论上不会走到这里，因为小猫咪总是匹配）
    return '小猫咪', '🐱', '不挑食不浪费，悠哉悠哉刚刚好'


def get_animal_info(animal_name):
    """获取小动物的详细信息
    
    Args:
        animal_name: 小动物名称
        
    Returns:
        dict: {name, emoji, slogan, description}
    """
    animal_descriptions = {
        '小猎豹': {
            'description': '你今天吃了好多蛋白质！肌肉正在悄悄生长，像小猎豹一样活力满满！',
            'tip': '记得多喝点水帮助蛋白质吸收哦~',
        },
        '小仓鼠': {
            'description': '碳水让你安全感满满，像小仓鼠抱着腮帮子一样满足！',
            'tip': '明天可以多加点蔬菜，营养更均衡呀~',
        },
        '小狐狸': {
            'description': '你的饮食超均衡！像小狐狸一样精明，什么营养都照顾到了！',
            'tip': '保持这个节奏，你就是最棒的！',
        },
        '小松鼠': {
            'description': '今天加餐不少呢，像小松鼠囤坚果一样，嘴巴根本停不下来~',
            'tip': '加餐可以选点健康的，比如水果或酸奶哦！',
        },
        '小兔子': {
            'description': '今天吃得很清淡，像小兔子一样轻盈，感觉身体都变轻松了！',
            'tip': '别饿到自己哦，适当加点优质蛋白质~',
        },
        '小熊': {
            'description': '今天吃得超满足，像小熊要冬眠一样，能量满满！',
            'tip': '偶尔放纵没关系，明天又是新的一天！',
        },
        '小猫咪': {
            'description': '今天吃得不紧不慢，像小猫咪一样悠哉悠哉~',
            'tip': '享受美食的感觉真好！',
        },
    }
    
    for name, emoji, slogan, _ in ANIMALS:
        if name == animal_name:
            info = animal_descriptions.get(name, {})
            return {
                'name': name,
                'emoji': emoji,
                'slogan': slogan,
                'description': info.get('description', ''),
                'tip': info.get('tip', ''),
            }
    
    return None


def format_animal_reveal(animal_info, is_first_time=False):
    """格式化小动物揭晓的惊喜提示
    
    Args:
        animal_info: 小动物信息字典
        is_first_time: 是否是第一次解锁
        
    Returns:
        str: 格式化的揭晓文案
    """
    lines = []
    
    if is_first_time:
        lines.append("🎉 恭喜你解锁了第一只食物小动物！")
    else:
        lines.append("🐾 今日专属食物小动物揭晓！")
    
    lines.append("")
    lines.append(f"   {animal_info['emoji']} {animal_info['name']}")
    lines.append(f"   「{animal_info['slogan']}」")
    lines.append("")
    lines.append(f"💡 {animal_info['description']}")
    lines.append(f"✨ {animal_info['tip']}")
    
    return "\n".join(lines)


if __name__ == "__main__":
    # 测试用例
    print("=" * 60)
    print("🐾 小动物盲盒系统 - 测试用例")
    print("=" * 60 + "\n")
    
    test_cases = [
        # (蛋白质%, 碳水%, 脂肪%, 热量完成度%, 加餐次数, 预期名称)
        (40, 30, 30, 100, 1, "小猎豹"),   # 高蛋白低碳水
        (15, 60, 25, 100, 1, "小仓鼠"),   # 高碳水
        (25, 45, 30, 100, 1, "小狐狸"),   # 均衡饮食
        (25, 45, 30, 100, 2, "小松鼠"),   # 加餐2次
        (25, 45, 30, 70, 1, "小兔子"),    # 吃得少
        (20, 30, 50, 95, 1, "小熊"),      # 高脂肪
        (20, 35, 45, 85, 1, "小猫咪"),    # 兜底
    ]
    
    print("🧪 匹配测试：")
    print("-" * 60)
    
    all_passed = True
    for p, c, f, k, s, expected in test_cases:
        name, emoji, slogan = match_diet_animal(p, c, f, k, s)
        status = "✅" if name == expected else f"❌ (预期:{expected})"
        if name != expected:
            all_passed = False
        print(f"{status} 蛋白{p}% 碳水{c}% 脂肪{f}% → {emoji} {name}")
    
    print("\n" + "-" * 60)
    
    # 测试小动物详情
    print("\n📋 小猎豹详情示例：")
    info = get_animal_info("小猎豹")
    print(format_animal_reveal(info, is_first_time=True))
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ 所有测试通过！")
    else:
        print("⚠️  部分测试未通过，请检查匹配逻辑")
    print("=" * 60)
