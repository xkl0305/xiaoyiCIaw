# -*- coding: utf-8 -*-
"""
Open Food Facts API 集成 - V2 API
全球450万+食品数据库
支持中文搜索
"""
import requests
import json
from typing import Dict, Optional, List

class OpenFoodFactsAPI:
    """Open Food Facts API 客户端 - 使用稳定的 V2 API"""
    
    def __init__(self):
        self.base_url = "https://world.openfoodfacts.org"
        # 使用标准浏览器User-Agent，避免被反爬虫机制屏蔽
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        self.headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://world.openfoodfacts.org/"
        }
    
    def search_food(self, query: str, lang: str = "zh", limit: int = 5) -> List[Dict]:
        """
        搜索食物 (V2 API)
        
        Args:
            query: 搜索关键词
            lang: 语言代码 (zh, en, fr, etc.)
            limit: 返回结果数量
        
        Returns:
            搜索结果列表
        """
        try:
            url = f"{self.base_url}/api/v2/search"
            params = {
                "search_terms": query,
                "page_size": limit,
                "fields": "code,product_name,product_name_zh,brands,nutriments,"
                         "categories_zh,categories,image_url,nutriscore_grade"
            }
            
            response = requests.get(url, params=params, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            products = data.get("products", [])
            
            results = []
            for product in products:
                parsed = self._parse_product(product)
                if parsed:
                    results.append(parsed)
            
            return results
            
        except Exception as e:
            print(f"Open Food Facts API 搜索错误: {e}")
            return []
    
    def get_product_by_barcode(self, barcode: str) -> Optional[Dict]:
        """
        通过条形码获取产品信息
        
        Args:
            barcode: 条形码 (如 6908791888880)
        
        Returns:
            产品信息字典
        """
        try:
            url = f"{self.base_url}/api/v2/product/{barcode}"
            params = {
                "fields": "code,product_name,product_name_zh,brands,nutriments,"
                         "categories_zh,categories,image_url,nutriscore_grade"
            }
            response = requests.get(url, params=params, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            if data.get("status") == 1:
                return self._parse_product(data.get("product", {}))
            return None
            
        except Exception as e:
            print(f"Open Food Facts API 条形码查询错误: {e}")
            return None
    
    def _parse_product(self, product: Dict) -> Optional[Dict]:
        """
        解析产品数据
        
        Args:
            product: Open Food Facts 原始产品数据
        
        Returns:
            标准化的营养数据
        """
        try:
            # 尝试获取中文名称，优先中文
            name = (product.get("product_name_zh") or 
                   product.get("product_name") or 
                   product.get("product_name_en"))
            
            if not name:
                return None
            
            # 获取营养数据 (每100g)
            nutriments = product.get("nutriments", {})
            
            # 能量 (kcal) - 优先使用 kcal，否则转换
            calories = (nutriments.get("energy-kcal_100g") or 
                       nutriments.get("energy-kcal") or
                       (nutriments.get("energy_100g") or nutriments.get("energy", 0)) / 4.184)
            
            # 蛋白质
            protein = nutriments.get("proteins_100g") or nutriments.get("proteins", 0)
            
            # 脂肪
            fat = nutriments.get("fat_100g") or nutriments.get("fat", 0)
            
            # 碳水化合物
            carbs = nutriments.get("carbohydrates_100g") or nutriments.get("carbohydrates", 0)
            
            # 膳食纤维
            fiber = nutriments.get("fiber_100g") or nutriments.get("fiber", 0)
            
            # 糖
            sugar = nutriments.get("sugars_100g") or nutriments.get("sugars", 0)
            
            # 钠
            sodium = nutriments.get("sodium_100g") or nutriments.get("sodium", 0)
            
            # 品牌
            brand = product.get("brands", "")
            
            # 分类
            category = product.get("categories_zh") or product.get("categories", "")
            
            # 图片
            image_url = product.get("image_url", "")
            
            # Nutri-Score
            nutri_score = product.get("nutriscore_grade", "").upper()
            
            return {
                "name": str(name).strip(),
                "calories": round(float(calories), 1) if calories else 0,
                "protein": round(float(protein), 2) if protein else 0,
                "fat": round(float(fat), 2) if fat else 0,
                "carbs": round(float(carbs), 2) if carbs else 0,
                "fiber": round(float(fiber), 2) if fiber else 0,
                "sugar": round(float(sugar), 2) if sugar else 0,
                "sodium": round(float(sodium), 2) if sodium else 0,
                "brand": str(brand),
                "category": str(category),
                "image_url": str(image_url),
                "nutri_score": str(nutri_score),
                "barcode": str(product.get("code", "")),
                "source": "Open Food Facts"
            }
            
        except Exception as e:
            print(f"解析产品数据错误: {e}")
            return None
    
    def search_with_fallback(self, query: str) -> Optional[Dict]:
        """
        智能搜索：中文 → 英文 fallback，带相关性检查
        
        Args:
            query: 搜索关键词
        
        Returns:
            最佳匹配结果，未找到返回 None
        """
        query_lower = query.lower()
        
        # 首先尝试中文搜索
        results = self.search_food(query, lang="zh", limit=3)
        
        if results and len(results) > 0:
            best_match = results[0]
            # 相关性检查：确保产品名和查询有一定关联
            if self._is_relevant(query_lower, best_match):
                return best_match
        
        # 如果中文没结果，尝试英文（很多产品只有英文名）
        english_queries = self._translate_to_english(query)
        for en_query in english_queries:
            results = self.search_food(en_query, lang="en", limit=3)
            if results and len(results) > 0:
                best_match = results[0]
                if self._is_relevant(en_query.lower(), best_match):
                    return best_match
        
        # 所有搜索都失败或不相关，返回 None 让系统降级到估算模式
        return None
    
    def _is_relevant(self, query: str, product: Dict) -> bool:
        """
        检查产品是否与查询相关
        
        Args:
            query: 搜索关键词（小写）
            product: 产品数据
        
        Returns:
            是否相关
        """
        if not product:
            return False
        
        product_name = str(product.get("name", "")).lower()
        product_brand = str(product.get("brand", "")).lower()
        
        # 简单的相关性检查：产品名或品牌中包含查询词的某些部分
        query_words = set(query.split())
        name_words = set(product_name.split())
        
        # 如果有共同的词，认为相关
        if query_words & name_words:
            return True
        
        # 如果查询词是产品名的子串，认为相关
        if query in product_name or product_name in query:
            return True
        
        # 检查品牌
        if query in product_brand or product_brand in query:
            return True
        
        # 太短的查询（小于2个字）可能是不相关的
        if len(query) < 2:
            return False
        
        # 默认：API返回的结果可能是不相关的默认产品
        return False
    
    def _translate_to_english(self, chinese_query: str) -> List[str]:
        """
        简单的中文到英文常见食物翻译
        
        Args:
            chinese_query: 中文食物名
        
        Returns:
            可能的英文翻译列表
        """
        translations = {
            # 水果
            "牛油果": ["avocado"],
            "榴莲": ["durian"],
            "山竹": ["mangosteen"],
            "荔枝": ["lychee"],
            "龙眼": ["longan"],
            "芒果": ["mango"],
            "猕猴桃": ["kiwi", "kiwi fruit"],
            "草莓": ["strawberry"],
            "蓝莓": ["blueberry"],
            "樱桃": ["cherry"],
            "葡萄": ["grape"],
            "西瓜": ["watermelon"],
            "苹果": ["apple"],
            "香蕉": ["banana"],
            "橙子": ["orange"],
            
            # 快餐/品牌
            "麦当劳": ["mcdonald", "mcdonalds"],
            "肯德基": ["kfc", "kentucky"],
            "星巴克": ["starbucks"],
            "必胜客": ["pizza hut"],
            "汉堡王": ["burger king"],
            "赛百味": ["subway"],
            "德克士": ["dicos"],
            
            # 常见食品
            "巧克力": ["chocolate"],
            "咖啡": ["coffee"],
            "牛奶": ["milk"],
            "酸奶": ["yogurt", "yoghurt"],
            "奶酪": ["cheese"],
            "黄油": ["butter"],
            "面包": ["bread"],
            "披萨": ["pizza"],
            "汉堡": ["burger", "hamburger"],
            "薯片": ["chips", "potato chips", "crisps"],
            "可乐": ["cola", "coca cola", "coke"],
            "橙汁": ["orange juice"],
            "啤酒": ["beer"],
            "红酒": ["wine", "red wine"],
            "蛋糕": ["cake"],
            "饼干": ["biscuit", "cookie"],
            "冰淇淋": ["ice cream", "icecream"],
            
            # 中餐
            "饺子": ["dumpling", "jiaozi"],
            "包子": ["baozi", "steamed bun"],
            "面条": ["noodle", "noodles"],
            "米饭": ["rice"],
            "豆腐": ["tofu"],
            "酱油": ["soy sauce"],
            "绿茶": ["green tea"],
            "红茶": ["black tea"],
            
            # 零食
            "坚果": ["nuts"],
            "杏仁": ["almond"],
            "核桃": ["walnut"],
            "腰果": ["cashew"],
            "花生": ["peanut"],
        }
        
        results = [chinese_query]  # 先保留原查询
        
        for cn, en_list in translations.items():
            if cn in chinese_query:
                results.extend(en_list)
        
        return results


# 全局实例
off_api = OpenFoodFactsAPI()


def search_openfoodfacts(query: str) -> Optional[Dict]:
    """
    便捷函数：搜索 Open Food Facts
    
    Args:
        query: 食物名称
    
    Returns:
        匹配的食物数据，无匹配返回 None
    """
    return off_api.search_with_fallback(query)


if __name__ == "__main__":
    # 测试
    print("=" * 60)
    print("Open Food Facts API 测试 - V2")
    print("全球 4,500,000+ 食品数据库")
    print("=" * 60)
    
    test_queries = [
        "avocado",
        "starbucks",
        "nutella",
        "cola",
        "chocolate"
    ]
    
    for query in test_queries:
        print(f"\n搜索: {query}")
        result = search_openfoodfacts(query)
        if result:
            print(f"  ✅ 找到: {result['name']}")
            print(f"     热量: {result['calories']} kcal/100g")
            print(f"     蛋白质: {result['protein']}g | 脂肪: {result['fat']}g | 碳水: {result['carbs']}g")
            if result.get('brand'):
                print(f"     品牌: {result['brand']}")
            if result.get('nutri_score'):
                print(f"     Nutri-Score: {result['nutri_score']}")
        else:
            print(f"  ❌ 未找到")
