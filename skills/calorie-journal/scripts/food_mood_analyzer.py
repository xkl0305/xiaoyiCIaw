# -*- coding: utf-8 -*-
"""
v2.1 新增：食物情绪占星师
=========================
基于营养学权威依据给食物贴情绪标签
3层匹配机制：硬编码精确匹配 → 关键词模糊匹配 → 默认值
"""

# ============== 第1层：硬编码精确匹配 ==============
FOOD_MOOD_TAGS = {
    # 😊 开心食物：富含色氨酸（血清素前体）
    "鸡蛋": {"mood": "happy", "emoji": "😊", "name": "开心食物"},
    "牛奶": {"mood": "happy", "emoji": "😊", "name": "开心食物"},
    "全脂牛奶": {"mood": "happy", "emoji": "😊", "name": "开心食物"},
    "脱脂牛奶": {"mood": "happy", "emoji": "😊", "name": "开心食物"},
    "香蕉": {"mood": "happy", "emoji": "😊", "name": "开心食物"},
    "奶酪": {"mood": "happy", "emoji": "😊", "name": "开心食物"},
    "芝士": {"mood": "happy", "emoji": "😊", "name": "开心食物"},
    "坚果": {"mood": "happy", "emoji": "😊", "name": "开心食物"},
    
    # 🧸 治愈食物：碳水化合物为主
    "米饭": {"mood": "comfort", "emoji": "🧸", "name": "治愈食物"},
    "糙米饭": {"mood": "comfort", "emoji": "🧸", "name": "治愈食物"},
    "白面包": {"mood": "comfort", "emoji": "🧸", "name": "治愈食物"},
    "全麦面包": {"mood": "comfort", "emoji": "🧸", "name": "治愈食物"},
    "馒头": {"mood": "comfort", "emoji": "🧸", "name": "治愈食物"},
    "面条": {"mood": "comfort", "emoji": "🧸", "name": "治愈食物"},
    "红薯": {"mood": "comfort", "emoji": "🧸", "name": "治愈食物"},
    "土豆": {"mood": "comfort", "emoji": "🧸", "name": "治愈食物"},
    "包子": {"mood": "comfort", "emoji": "🧸", "name": "治愈食物"},
    "饺子": {"mood": "comfort", "emoji": "🧸", "name": "治愈食物"},
    
    # 💪 力量食物：优质蛋白质为主
    "鸡胸肉": {"mood": "power", "emoji": "💪", "name": "力量食物"},
    "鸡腿": {"mood": "power", "emoji": "💪", "name": "力量食物"},
    "牛肉": {"mood": "power", "emoji": "💪", "name": "力量食物"},
    "猪瘦肉": {"mood": "power", "emoji": "💪", "name": "力量食物"},
    "三文鱼": {"mood": "power", "emoji": "💪", "name": "力量食物"},
    "鲈鱼": {"mood": "power", "emoji": "💪", "name": "力量食物"},
    "虾": {"mood": "power", "emoji": "💪", "name": "力量食物"},
    "豆腐": {"mood": "power", "emoji": "💪", "name": "力量食物"},
    "豆浆": {"mood": "power", "emoji": "💪", "name": "力量食物"},
    "希腊酸奶": {"mood": "power", "emoji": "💪", "name": "力量食物"},
    
    # 🍃 清爽食物：高纤维低热量
    "西兰花": {"mood": "fresh", "emoji": "🍃", "name": "清爽食物"},
    "菠菜": {"mood": "fresh", "emoji": "🍃", "name": "清爽食物"},
    "生菜": {"mood": "fresh", "emoji": "🍃", "name": "清爽食物"},
    "白菜": {"mood": "fresh", "emoji": "🍃", "name": "清爽食物"},
    "番茄": {"mood": "fresh", "emoji": "🍃", "name": "清爽食物"},
    "黄瓜": {"mood": "fresh", "emoji": "🍃", "name": "清爽食物"},
    "胡萝卜": {"mood": "fresh", "emoji": "🍃", "name": "清爽食物"},
    "苹果": {"mood": "fresh", "emoji": "🍃", "name": "清爽食物"},
    "橙子": {"mood": "fresh", "emoji": "🍃", "name": "清爽食物"},
    "草莓": {"mood": "fresh", "emoji": "🍃", "name": "清爽食物"},
    "蓝莓": {"mood": "fresh", "emoji": "🍃", "name": "清爽食物"},
    
    # 🍬 甜蜜食物：含糖食物
    "燕麦片": {"mood": "sweet", "emoji": "🍬", "name": "甜蜜食物"},
    "酸奶": {"mood": "sweet", "emoji": "🍬", "name": "甜蜜食物"},
    "奶茶": {"mood": "sweet", "emoji": "🍬", "name": "甜蜜食物"},
    "蛋糕": {"mood": "sweet", "emoji": "🍬", "name": "甜蜜食物"},
    "糖果": {"mood": "sweet", "emoji": "🍬", "name": "甜蜜食物"},
    "巧克力": {"mood": "sweet", "emoji": "🍬", "name": "甜蜜食物"},
    
    # 🧈 满足食物：高脂肪食物
    "猪五花肉": {"mood": "satisfied", "emoji": "🧈", "name": "满足食物"},
    "牛油果": {"mood": "satisfied", "emoji": "🧈", "name": "满足食物"},
    "炸鸡": {"mood": "satisfied", "emoji": "🧈", "name": "满足食物"},
    "汉堡": {"mood": "satisfied", "emoji": "🧈", "name": "满足食物"},
    "薯条": {"mood": "satisfied", "emoji": "🧈", "name": "满足食物"},
}

# ============== 第2层：关键词模糊匹配 ==============
MOOD_KEYWORDS = [
    # （优先级按顺序排列，越靠前权重越高）
    ("satisfied", ["火锅", "油炸", "炸", "油", "脂", "肥肉", "汉堡", "薯条", "麻辣", "牛油"], {"mood": "satisfied", "emoji": "🧈", "name": "满足食物"}),
    ("sweet", ["糖", "甜", "蜜", "奶茶", "巧克力", "蛋糕", "可乐", "饮料"], {"mood": "sweet", "emoji": "🍬", "name": "甜蜜食物"}),
    ("power", ["肉", "鸡", "牛", "鱼", "虾", "豆", "蛋", "宫保", "鸡丁"], {"mood": "power", "emoji": "💪", "name": "力量食物"}),
    ("fresh", ["菜", "果", "瓜", "蓝", "橙", "柠", "蔬", "沙拉", "青"], {"mood": "fresh", "emoji": "🍃", "name": "清爽食物"}),
    ("comfort", ["饭", "面", "包", "馒头", "薯", "饼", "米", "盖饭"], {"mood": "comfort", "emoji": "🧸", "name": "治愈食物"}),
    ("happy", ["奶", "香蕉", "坚果", "芝士", "酸奶"], {"mood": "happy", "emoji": "😊", "name": "开心食物"}),
]

# 默认值（兜底）
DEFAULT_MOOD = {"mood": "happy", "emoji": "😊", "name": "开心食物"}


def get_food_mood(food_name):
    """获取食物的情绪标签（3层匹配机制）
    
    Args:
        food_name: 食物名称
        
    Returns:
        dict: {mood, emoji, name}
    """
    food_name = food_name.strip()
    
    # 第1层：精确匹配
    if food_name in FOOD_MOOD_TAGS:
        return FOOD_MOOD_TAGS[food_name].copy()
    
    # 第2层：关键词模糊匹配（按优先级顺序）
    for mood_name, keywords, mood_info in MOOD_KEYWORDS:
        for kw in keywords:
            if kw in food_name:
                return mood_info.copy()
    
    # 第3层：默认值（乐观原则）
    return DEFAULT_MOOD.copy()


def calculate_daily_mood_summary(food_list):
    """计算今日情绪盘点
    
    Args:
        food_list: 食物名称列表
        
    Returns:
        dict: {情绪名称: 数量}
    """
    mood_counts = {
        "开心食物": 0,
        "治愈食物": 0,
        "力量食物": 0,
        "清爽食物": 0,
        "甜蜜食物": 0,
        "满足食物": 0,
    }
    
    for food in food_list:
        food_name = food.get("name", "") if isinstance(food, dict) else str(food)
        mood_info = get_food_mood(food_name)
        mood_name = mood_info.get("name")
        if mood_name in mood_counts:
            mood_counts[mood_name] += 1
    
    return mood_counts


def format_mood_summary(mood_counts):
    """格式化情绪盘点输出
    
    Args:
        mood_counts: 情绪统计字典
        
    Returns:
        str: 格式化后的情绪盘点
    """
    lines = ["🧠 今日食物情绪盘点"]
    total = sum(mood_counts.values())
    
    for mood_name, count in mood_counts.items():
        if count > 0:
            # 找对应的emoji
            emoji = "😊"
            for _, _, mood_info in MOOD_KEYWORDS:
                if mood_info["name"] == mood_name:
                    emoji = mood_info["emoji"]
                    break
            
            percentage = int(count / total * 100) if total > 0 else 0
            lines.append(f"  {emoji} {mood_name}: {count} 种 ({percentage}%)")
    
    # 找占比最高的情绪
    if total > 0:
        max_mood = max(mood_counts.items(), key=lambda x: x[1])
        for _, _, mood_info in MOOD_KEYWORDS:
            if mood_info["name"] == max_mood[0]:
                emoji = mood_info["emoji"]
                lines.append(f"\n✨ 今日主情绪：{emoji} {max_mood[0]}")
                break
    
    return "\n".join(lines)


if __name__ == "__main__":
    # 测试用例
    test_foods = [
        "鸡蛋", "米饭", "鸡胸肉", "西兰花", "奶茶", "炸鸡",  # 精确匹配
        "宫保鸡丁盖饭", "重庆火锅", "珍珠奶茶", "麦辣鸡腿堡", "蔬菜沙拉",  # 关键词匹配
        "不知道什么菜", "用户随便说的菜名",  # 兜底匹配
    ]
    
    print("=" * 50)
    print("🧠 食物情绪占星师 - 测试用例")
    print("=" * 50 + "\n")
    
    for food in test_foods:
        mood = get_food_mood(food)
        print(f"🍽️ {food:20s} → {mood['emoji']} {mood['name']}")
    
    print("\n" + "=" * 50)
    print("📊 今日情绪盘点示例")
    print("=" * 50 + "\n")
    
    today_meals = ["鸡蛋", "包子", "牛奶", "宫保鸡丁盖饭", "米饭", "炸鸡", "奶茶", "苹果"]
    mood_counts = calculate_daily_mood_summary(today_meals)
    print(format_mood_summary(mood_counts))

# ============== 新增：营养密度评分 ==============
# 基于 USDA 营养密度评分公式（NRF9.3）
# 计算每100kcal食物的营养质量评分

def calculate_nutrient_density(nutrition):
    """
    计算营养密度评分（NRF9.3算法简化版）
    返回: (星级1-5, 描述)
    """
    # 提取关键营养
    protein = nutrition.get("protein", 0)
    fiber = nutrition.get("fiber", 0)
    calories = nutrition.get("calories", 100)
    
    if calories <= 0:
        calories = 1
    
    # 简化版：基于蛋白质和纤维密度
    protein_per_100kcal = (protein / calories) * 100
    fiber_per_100kcal = (fiber / calories) * 100
    
    # 综合评分
    score = protein_per_100kcal * 2 + fiber_per_100kcal * 3
    
    # 星级转换
    if score >= 15:
        return 5, "⭐⭐⭐⭐⭐ 营养超丰富"
    elif score >= 10:
        return 4, "⭐⭐⭐⭐ 营养很丰富"
    elif score >= 6:
        return 3, "⭐⭐⭐ 营养均衡"
    elif score >= 3:
        return 2, "⭐⭐ 营养一般"
    else:
        return 1, "⭐ 能量为主"

def get_nutrition_highlights(nutrition, food_name=""):
    """
    获取食物营养亮点（正面描述）
    """
    highlights = []
    protein = nutrition.get("protein", 0)
    fiber = nutrition.get("fiber", 0)
    carbs = nutrition.get("carbs", 0)
    fat = nutrition.get("fat", 0)
    
    if protein >= 10:
        highlights.append("💪 高蛋白")
    if fiber >= 3:
        highlights.append("🌾 高纤维")
    if carbs >= 30 and protein < 5:
        highlights.append("⚡ 快速供能")
    if fat >= 8 and protein >= 8:
        highlights.append("🥑 优质脂肪")
    
    # 添加营养密度星级
    stars, star_desc = calculate_nutrient_density(nutrition)
    highlights.append(star_desc)
    
    return highlights
