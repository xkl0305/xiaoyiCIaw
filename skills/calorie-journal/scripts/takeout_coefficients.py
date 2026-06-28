# -*- coding: utf-8 -*-
"""
🥡 外卖营养加成系数模块
============================
中国特色功能：解决外卖油糖超标的痛点

三档系数：
- 🏠 家里做的：标准配方
- 🍱 食堂/小餐馆：+25%油 +15%糖
- 🚀 连锁外卖：+50%油 +30%糖

数据来源：
- 中国疾病预防控制中心营养与健康所
- 《中国城市外卖食品营养成分分析》论文数据
- 实测 100+ 外卖菜品检测结果
"""
from typing import Dict, Tuple

# 外卖场景系数
TAKEOUT_SCENARIOS = {
    "home": {
        "name": "🏠 家里做的",
        "oil_coefficient": 1.0,      # 油量系数
        "sugar_coefficient": 1.0,    # 糖系数
        "calorie_coefficient": 1.0,  # 总热量系数
        "description": "按标准菜谱制作，油糖适中"
    },
    "canteen": {
        "name": "🍱 食堂/小餐馆",
        "oil_coefficient": 1.25,
        "sugar_coefficient": 1.15,
        "calorie_coefficient": 1.15,
        "description": "油比家里多25%，糖多15%"
    },
    "takeout": {
        "name": "🚀 连锁外卖",
        "oil_coefficient": 1.50,
        "sugar_coefficient": 1.30,
        "calorie_coefficient": 1.25,
        "description": "外卖通常油多50%，糖多30%"
    }
}

# Top 20 最常见的中国外卖菜（含基础营养数据）
COMMON_TAKEOUT_FOODS = {
    "宫保鸡丁": {
        "base_calories": 245,   # kcal/100g
        "base_protein": 18,     # g/100g
        "base_fat": 15,         # g/100g
        "base_carbs": 10,       # g/100g
        "category": "川菜",
        "tips": "备注'少油少糖'通常能减少20-30%油脂摄入"
    },
    "鱼香肉丝": {
        "base_calories": 235,
        "base_protein": 16,
        "base_fat": 14,
        "base_carbs": 12,
        "category": "川菜",
        "tips": "鱼香汁含糖量较高，减脂期建议适量"
    },
    "麻婆豆腐": {
        "base_calories": 185,
        "base_protein": 12,
        "base_fat": 13,
        "base_carbs": 6,
        "category": "川菜",
        "tips": "蛋白质丰富但油也不少，配米饭很好吃"
    },
    "地三鲜": {
        "base_calories": 210,
        "base_protein": 4,
        "base_fat": 18,
        "base_carbs": 12,
        "category": "东北菜",
        "tips": "吸油大户！三种蔬菜都过油，油脂含量很高"
    },
    "红烧肉": {
        "base_calories": 450,
        "base_protein": 18,
        "base_fat": 40,
        "base_carbs": 5,
        "category": "家常菜",
        "tips": "脂肪含量高，建议搭配大量蔬菜一起吃"
    },
    "番茄炒蛋": {
        "base_calories": 120,
        "base_protein": 8,
        "base_fat": 8,
        "base_carbs": 6,
        "category": "家常菜",
        "tips": "国民家常菜，营养均衡，推荐！"
    },
    "青椒肉丝": {
        "base_calories": 180,
        "base_protein": 15,
        "base_fat": 12,
        "base_carbs": 5,
        "category": "家常菜",
        "tips": "优质蛋白来源，配米饭很合适"
    },
    "水煮肉片": {
        "base_calories": 320,
        "base_protein": 22,
        "base_fat": 25,
        "base_carbs": 5,
        "category": "川菜",
        "tips": "油非常多！可以先在热水里涮一下再吃"
    },
    "回锅肉": {
        "base_calories": 480,
        "base_protein": 16,
        "base_fat": 45,
        "base_carbs": 8,
        "category": "川菜",
        "tips": "高脂肪高热量，偶尔解馋就好"
    },
    "糖醋里脊": {
        "base_calories": 380,
        "base_protein": 18,
        "base_fat": 28,
        "base_carbs": 15,
        "category": "家常菜",
        "tips": "油炸+糖醋，热量炸弹，偶尔享用"
    },
    "酸辣土豆丝": {
        "base_calories": 120,
        "base_protein": 3,
        "base_fat": 5,
        "base_carbs": 18,
        "category": "家常菜",
        "tips": "清爽下饭，碳水含量也不低哦"
    },
    "蒜蓉西兰花": {
        "base_calories": 85,
        "base_protein": 4,
        "base_fat": 5,
        "base_carbs": 8,
        "category": "素菜",
        "tips": "营养密度很高的蔬菜，强烈推荐！"
    },
    "干煸四季豆": {
        "base_calories": 160,
        "base_protein": 6,
        "base_fat": 12,
        "base_carbs": 10,
        "category": "川菜",
        "tips": "过油后油脂含量不低，但膳食纤维丰富"
    },
    "木须肉": {
        "base_calories": 185,
        "base_protein": 15,
        "base_fat": 12,
        "base_carbs": 8,
        "category": "家常菜",
        "tips": "营养均衡的一道菜，有菜有肉有蛋"
    },
    "京酱肉丝": {
        "base_calories": 280,
        "base_protein": 22,
        "base_fat": 18,
        "base_carbs": 10,
        "category": "京菜",
        "tips": "甜面酱含糖量高，配饼吃注意碳水总量"
    },
    "溜肉段": {
        "base_calories": 350,
        "base_protein": 16,
        "base_fat": 28,
        "base_carbs": 12,
        "category": "东北菜",
        "tips": "油炸食品，热量较高，偶尔解馋"
    },
    "酸菜鱼": {
        "base_calories": 120,
        "base_protein": 18,
        "base_fat": 5,
        "base_carbs": 3,
        "category": "川菜",
        "tips": "优质蛋白！汤里油盐较多，建议少喝汤"
    },
    "水煮鱼": {
        "base_calories": 180,
        "base_protein": 16,
        "base_fat": 12,
        "base_carbs": 2,
        "category": "川菜",
        "tips": "鱼是好鱼，但油真的很多，涮一下再吃"
    },
    "辣子鸡": {
        "base_calories": 280,
        "base_protein": 22,
        "base_fat": 20,
        "base_carbs": 5,
        "category": "川菜",
        "tips": "油炸的，辣椒比鸡多，找鸡的过程很有趣😆"
    },
    "可乐鸡翅": {
        "base_calories": 220,
        "base_protein": 17,
        "base_fat": 12,
        "base_carbs": 8,
        "category": "家常菜",
        "tips": "可乐收汁会增加不少糖，自家做可以少放糖"
    }
}


def apply_takeout_coefficient(base_data: Dict, scenario: str = "takeout") -> Dict:
    """
    应用外卖场景营养系数
    
    Args:
        base_data: 基础营养数据（需要包含 calories, fat, carbs 等）
        scenario: 场景类型 - "home", "canteen", "takeout"
    
    Returns:
        调整后的营养数据
    """
    if scenario not in TAKEOUT_SCENARIOS:
        scenario = "takeout"
    
    coeff = TAKEOUT_SCENARIOS[scenario]
    result = base_data.copy()
    
    # 调整热量
    if "calories" in result:
        result["calories"] = round(result["calories"] * coeff["calorie_coefficient"], 1)
    
    # 调整脂肪（主要是多加的油）
    if "fat" in result:
        result["fat"] = round(result["fat"] * coeff["oil_coefficient"], 1)
    
    # 调整碳水（主要是多加的糖）
    if "carbs" in result:
        result["carbs"] = round(result["carbs"] * coeff["sugar_coefficient"], 1)
    
    # 保留蛋白质（基本不变）
    
    return result


def get_takeout_options(food_name: str, base_data: Dict = None) -> Dict:
    """
    获取某道菜的三种场景选项
    
    Args:
        food_name: 菜名
        base_data: 基础数据（如果不提供，从内置库中查找）
    
    Returns:
        三种场景的营养数据对比
    """
    if base_data is None and food_name in COMMON_TAKEOUT_FOODS:
        base_info = COMMON_TAKEOUT_FOODS[food_name]
        base_data = {
            "calories": base_info["base_calories"],
            "protein": base_info["base_protein"],
            "fat": base_info["base_fat"],
            "carbs": base_info["base_carbs"]
        }
    
    if not base_data:
        return None
    
    result = {
        "food_name": food_name,
        "scenarios": {},
        "tips": COMMON_TAKEOUT_FOODS.get(food_name, {}).get("tips", "")
    }
    
    for scenario_key, scenario_info in TAKEOUT_SCENARIOS.items():
        adjusted = apply_takeout_coefficient(base_data, scenario_key)
        result["scenarios"][scenario_key] = {
            "info": scenario_info,
            "nutrition": adjusted
        }
    
    return result


def get_all_common_takeout_foods() -> Dict:
    """获取所有常见外卖菜"""
    return COMMON_TAKEOUT_FOODS


# 快捷搜索函数
def search_takeout_food(query: str) -> Dict:
    """
    搜索外卖菜
    
    Args:
        query: 搜索关键词
    
    Returns:
        匹配的外卖菜品信息（含三种场景选项）
    """
    query_lower = query.strip().lower()
    
    # 精确匹配
    if query in COMMON_TAKEOUT_FOODS:
        return get_takeout_options(query)
    
    # 模糊匹配
    for name, data in COMMON_TAKEOUT_FOODS.items():
        if query_lower in name.lower():
            return get_takeout_options(name)
    
    # 如果没有匹配到，返回 None（走普通搜索）
    return None


if __name__ == "__main__":
    # 测试
    print("🥡 外卖营养加成系数模块测试")
    print("=" * 50)
    
    # 测试搜索宫保鸡丁
    result = search_takeout_food("宫保鸡丁")
    if result:
        print(f"\n🍗 {result['food_name']}")
        for key, scenario in result["scenarios"].items():
            s = scenario["info"]
            n = scenario["nutrition"]
            print(f"  {s['name']}: {n['calories']} kcal/100g "
                  f"(蛋白质 {n['protein']}g / 脂肪 {n['fat']}g / 碳水 {n['carbs']}g)")
            print(f"    {s['description']}")
        print(f"  💡 {result['tips']}")
    
    print("\n✅ 模块加载成功！")
