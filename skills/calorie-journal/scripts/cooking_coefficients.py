# -*- coding: utf-8 -*-
"""
🍳 烹饪方式营养系数模块
============================
解决痛点：所有营养数据都是生的，但用户吃的是熟的！

数据来源：
- 中国食物成分表标准版（第6版）
- 《不同烹饪方式对食物营养成分影响的研究》论文
- 中国营养学会烹饪营养指南

设计原则：让用户知道"生鸡胸"和"煎鸡胸"营养完全不一样
"""
from typing import Dict, Optional

# 烹饪方式定义与营养系数
COOKING_METHODS = {
    "boil": {
        "name": "🍲 煮/焯水",
        "emoji": "🍲",
        "description": "水煮，少油少盐，最健康的烹饪方式",
        "moisture_change": 1.2,      # 吸水20%（重量增加）
        "protein_retention": 0.95,   # 蛋白质保留95%
        "fat_change": 1.0,           # 脂肪无变化（不吸油）
        "carbs_retention": 0.9,      # 碳水保留90%（部分溶于水）
        "vitamin_retention": 0.6,    # 维生素（B族/C）保留60%（溶于水流失）
        "oil_absorption": 0,         # 吸油量 g/100g
        "health_score": 5,            # 健康评分 1-5
        "tips": "最推荐的烹饪方式，营养保留率高，不额外增加油脂"
    },
    "steam": {
        "name": "🥘 蒸",
        "emoji": "🥘",
        "description": "隔水蒸，营养保留最好",
        "moisture_change": 1.1,      # 吸水10%
        "protein_retention": 0.98,   # 蛋白质保留98%
        "fat_change": 1.0,
        "carbs_retention": 0.95,
        "vitamin_retention": 0.8,    # 维生素保留80%（不直接接触水）
        "oil_absorption": 0,
        "health_score": 5,
        "tips": "营养保留率最高！几乎不流失水溶性维生素"
    },
    "stir_fry": {
        "name": "🥡 快炒",
        "emoji": "🥡",
        "description": "大火快炒，家常菜最常用",
        "moisture_change": 0.9,      # 失水10%
        "protein_retention": 0.95,
        "fat_change": 1.0,           # 本身脂肪不变
        "carbs_retention": 0.95,
        "vitamin_retention": 0.7,    # 维生素保留70%
        "oil_absorption": 10,        # 吸油约10g/100g生重
        "health_score": 4,
        "tips": "快炒比久炒好，减少加热时间能保留更多营养"
    },
    "deep_fry": {
        "name": "🍗 煎/炸",
        "emoji": "🍗",
        "description": "油炸或油煎，吸油量大",
        "moisture_change": 0.7,      # 失水30%
        "protein_retention": 0.9,    # 蛋白质变性但不流失
        "fat_change": 1.0,
        "carbs_retention": 0.95,
        "vitamin_retention": 0.4,    # 高温破坏严重
        "oil_absorption": 30,        # 吸油约30g/100g生重！
        "health_score": 2,
        "tips": "吸油量很大！偶尔解馋就好，建议用厨房纸吸一下油再吃"
    },
    "braise": {
        "name": "🍖 红烧/焖炖",
        "emoji": "🍖",
        "description": "加酱油糖红烧，油糖都不少",
        "moisture_change": 0.8,      # 失水20%
        "protein_retention": 0.95,
        "fat_change": 1.0,
        "carbs_retention": 0.9,
        "vitamin_retention": 0.5,    # 长时间加热流失多
        "oil_absorption": 20,        # 吸油约20g/100g
        "sugar_added": 15,           # 加糖约15g/100g
        "health_score": 2,
        "tips": "红烧很香但糖油都不少，建议配大量蔬菜一起吃"
    },
    "roast": {
        "name": "🍠 烤/烘",
        "emoji": "🍠",
        "description": "烤箱/空气炸锅烤",
        "moisture_change": 0.75,     # 失水25%
        "protein_retention": 0.95,
        "fat_change": 1.0,
        "carbs_retention": 0.98,     # 美拉德反应但碳水不流失
        "vitamin_retention": 0.65,
        "oil_absorption": 5,         # 空气炸锅吸油少，约5g/100g
        "health_score": 3,
        "tips": "空气炸锅比油炸健康多了！烤蔬菜烤红薯都很好"
    },
    "raw": {
        "name": "🥗 生食/凉拌",
        "emoji": "🥗",
        "description": "生吃或凉拌，维生素保留最完整",
        "moisture_change": 1.0,      # 水分不变
        "protein_retention": 1.0,
        "fat_change": 1.0,
        "carbs_retention": 1.0,
        "vitamin_retention": 1.0,    # 维生素100%保留
        "oil_absorption": 8,         # 凉拌酱汁约8g/100g
        "health_score": 5,
        "tips": "蔬菜能生吃尽量生吃！但肉类蛋类一定要煮熟"
    },
    "microwave": {
        "name": "⚡ 微波",
        "emoji": "⚡",
        "description": "微波炉加热，其实营养保留很好",
        "moisture_change": 0.95,
        "protein_retention": 0.98,
        "fat_change": 1.0,
        "carbs_retention": 0.98,
        "vitamin_retention": 0.85,   # 加热时间短，维生素保留率很高
        "oil_absorption": 0,
        "health_score": 4,
        "tips": "微波炉其实很健康！加热时间短，营养保留比水煮还好"
    }
}

# 常见食物生熟重量比（熟重/生重）
COOKED_WEIGHT_RATIO = {
    "鸡胸肉": 0.7,      # 煮后变轻
    "猪里脊": 0.75,
    "牛肉": 0.7,
    "三文鱼": 0.8,
    "虾仁": 0.85,
    "鸡蛋": 1.0,        # 熟蛋和生蛋差不多
    "米饭": 2.7,        # 生米煮成熟饭吸水膨胀
    "面条": 2.5,
    "土豆": 1.0,        # 烤后差不多
    "红薯": 0.9,
    "西兰花": 0.95,
    "胡萝卜": 0.95,
    "菠菜": 0.3,        # 菠菜炒完缩水严重
}


class CookingCoefficient:
    """烹饪方式营养计算器"""
    
    def __init__(self):
        self.methods = COOKING_METHODS
    
    def get_method_options(self) -> Dict:
        """获取所有烹饪方式选项"""
        return self.methods
    
    def apply_cooking(self, raw_nutrition: Dict, cooking_method: str, food_name: str = None) -> Dict:
        """
        应用烹饪方式营养变化
        
        Args:
            raw_nutrition: 生的营养数据 {calories, protein, fat, carbs} 单位/100g
            cooking_method: 烹饪方式 key
            food_name: 食物名称（用于生熟重量比调整）
        
        Returns:
            烹饪后的营养数据
        """
        if cooking_method not in self.methods:
            cooking_method = "stir_fry"  # 默认快炒
        
        method = self.methods[cooking_method]
        result = raw_nutrition.copy()
        
        # 1. 基础营养变化
        if "protein" in result:
            result["protein"] = round(result["protein"] * method["protein_retention"], 1)
        
        if "carbs" in result:
            result["carbs"] = round(result["carbs"] * method["carbs_retention"], 1)
        
        # 2. 吸油（增加脂肪）
        if "fat" in result and method["oil_absorption"] > 0:
            result["fat"] = round(result["fat"] + method["oil_absorption"], 1)
        
        # 3. 红烧额外加糖
        if cooking_method == "braise" and "carbs" in result:
            result["carbs"] = round(result["carbs"] + method["sugar_added"], 1)
        
        # 4. 重新计算热量（因为脂肪和碳水变了）
        # 热量公式: 蛋白质4 + 脂肪9 + 碳水4 (kcal/100g)
        if all(k in result for k in ["protein", "fat", "carbs"]):
            result["calories"] = round(
                result["protein"] * 4 + 
                result["fat"] * 9 + 
                result["carbs"] * 4, 
                1
            )
        
        # 5. 添加烹饪方式信息
        result["cooking_method"] = method["name"]
        result["cooking_tips"] = method["tips"]
        result["health_score"] = method["health_score"]
        
        # 6. 生熟重量比（如果有）
        if food_name and food_name in COOKED_WEIGHT_RATIO:
            result["cooked_weight_ratio"] = COOKED_WEIGHT_RATIO[food_name]
            result["weight_note"] = f"生熟比约 1:{result['cooked_weight_ratio']}（100g生的做熟约{int(result['cooked_weight_ratio']*100)}g）"
        
        return result
    
    def compare_methods(self, raw_nutrition: Dict, food_name: str = None) -> Dict:
        """
        对比同一种食物不同烹饪方式的营养差异
        
        Returns:
            各种烹饪方式的营养对比
        """
        result = {
            "food_name": food_name or "食物",
            "raw": raw_nutrition,
            "methods": {}
        }
        
        for method_key, method_info in self.methods.items():
            cooked = self.apply_cooking(raw_nutrition, method_key, food_name)
            result["methods"][method_key] = {
                "info": method_info,
                "nutrition": cooked
            }
        
        return result
    
    def get_health_recommendation(self, cooking_method: str) -> str:
        """获取某烹饪方式的健康建议"""
        if cooking_method in self.methods:
            return self.methods[cooking_method]["tips"]
        return "选择你喜欢的烹饪方式就好～"


# 全局单例
_cooking = CookingCoefficient()


def get_cooking_options() -> Dict:
    """快捷函数：获取所有烹饪方式选项"""
    return _cooking.get_method_options()


def apply_cooking_method(raw_nutrition: Dict, cooking_method: str, food_name: str = None) -> Dict:
    """快捷函数：应用烹饪方式营养变化"""
    return _cooking.apply_cooking(raw_nutrition, cooking_method, food_name)


def compare_cooking_methods(raw_nutrition: Dict, food_name: str = None) -> Dict:
    """快捷函数：对比不同烹饪方式的营养差异"""
    return _cooking.compare_methods(raw_nutrition, food_name)


if __name__ == "__main__":
    print("🍳 烹饪方式营养系数模块测试")
    print("=" * 50)
    
    # 测试鸡胸肉不同做法
    raw_chicken = {
        "calories": 165,
        "protein": 31,
        "fat": 3.6,
        "carbs": 0
    }
    
    print("\n🍗 鸡胸肉不同做法对比（每100g生重）:")
    print(f"  生鸡胸: {raw_chicken['calories']} kcal | 蛋白{raw_chicken['protein']}g | 脂肪{raw_chicken['fat']}g")
    
    for method in ["boil", "stir_fry", "deep_fry", "braise"]:
        cooked = apply_cooking_method(raw_chicken, method, "鸡胸肉")
        info = COOKING_METHODS[method]
        print(f"  {info['name']}: {cooked['calories']} kcal | 蛋白{cooked['protein']}g | 脂肪{cooked['fat']}g")
        print(f"    💡 {cooked['cooking_tips']}")
    
    print("\n✅ 模块加载成功！")
