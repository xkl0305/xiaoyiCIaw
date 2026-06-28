# -*- coding: utf-8 -*-
"""
智能食物搜索引擎 v2.4 - 终极增强版
======================================
完全兼容原有代码，零侵入，可随时开关

新增特性 v2.4:
1. ✅ TianAPI作为第2级数据源（国内API，中文家常菜支持好）
2. ✅ 可插拔食物扩展系统 - 支持用户自行添加疾控中心完整数据
3. ✅ 七级搜索架构，逐级降级
4. ✅ 运行时可动态配置开关和API_KEY
5. ✅ 完全向后兼容，原有代码不做任何修改

架构升级：
  第1级：内置100种常见食物 → 毫秒级响应
  第2级：用户扩展食物数据 → 插件式加载
  第3级：TianAPI → 国内家常菜/外卖
  第4级：Open Food Facts API → 全球食品
  第5级：烹饪方式系数修正
  第6级：外卖加成系数
  第7级：智能估算兜底

使用方式:
    # 新版引擎（带TianAPI支持+扩展系统）
    from search_engine_v2 import FoodSearchEngineV2
    
    # 配置API Key（可选）
    engine = FoodSearchEngineV2()
    engine.set_tianapi_key("你的API_KEY")
    
    # 搜索（与原版API完全一致）
    result, source, icon = engine.search("黄焖鸡米饭")
    
    # 也可以继续使用原版引擎，完全兼容
    from food_search_engine import FoodSearchEngine
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from typing import Dict, Optional, Tuple

# 导入原版引擎（保证完全兼容）
from food_search_engine import FoodSearchEngine, COMMON_FOODS, FOOD_CATEGORY_ESTIMATES

# 导入TianAPI插件
try:
    from tianapi_plugin import (
        search_tianapi, 
        set_api_key, 
        set_enabled, 
        is_available
    )
    TIANAPI_PLUGIN_AVAILABLE = True
except ImportError:
    TIANAPI_PLUGIN_AVAILABLE = False

# 导入食物扩展系统（可选，不影响核心功能）
try:
    from food_extension_loader import get_extended_foods, get_extension_loader
    EXTENSION_SYSTEM_AVAILABLE = True
except ImportError:
    EXTENSION_SYSTEM_AVAILABLE = False
    get_extended_foods = lambda: {}
    get_extension_loader = lambda: None


class FoodSearchEngineV2(FoodSearchEngine):
    """
    食物搜索引擎 v2.4 - 增强版
    
    完全继承原版引擎，新增两大功能：
    1. TianAPI 国内数据源支持
    2. 可插拔食物扩展系统（支持用户导入疾控中心全量数据）
    
    七级搜索架构:
    1. 内置100种常见食物 - 毫秒级响应
    2. 用户扩展食物数据 - 插件式加载
    3. 天聚数行TianAPI - 国内家常菜/外卖
    4. Open Food Facts API - 全球食品
    5. 烹饪方式系数修正
    6. 外卖加成系数
    7. 智能估算兜底
    """
    
    def __init__(self):
        # 先调用父类初始化，保证完全兼容
        super().__init__()
        
        # 记录插件状态
        self.tianapi_available = TIANAPI_PLUGIN_AVAILABLE
        self.extension_available = EXTENSION_SYSTEM_AVAILABLE
        
        # 重建数据源列表，插入新的层级
        original_sources = list(self.sources)
        new_sources = []
        
        # 第1级：内置常用食物（保留原有）
        new_sources.append(original_sources[0])
        
        # 第2级：新增 - 用户扩展食物数据
        if self.extension_available:
            new_sources.append(("扩展食物数据", self._search_extension, "📦"))
        
        # 第3级：新增 - TianAPI
        if self.tianapi_available:
            new_sources.append(("天聚数行TianAPI", self._search_tianapi, "🇨🇳"))
        
        # 第4级：原有 Open Food Facts
        if len(original_sources) > 1:
            new_sources.append(original_sources[1])
        
        # 更新数据源列表
        self.sources = new_sources
    
    # ==================== TianAPI 相关方法 ====================
    
    def set_tianapi_key(self, api_key: str):
        """
        动态设置TianAPI的API Key
        
        Args:
            api_key: 你的TianAPI密钥
        """
        if self.tianapi_available:
            set_api_key(api_key)
    
    def set_tianapi_enabled(self, enabled: bool):
        """
        动态启用/禁用TianAPI
        
        Args:
            enabled: True=启用，False=禁用
        """
        if self.tianapi_available:
            set_enabled(enabled)
    
    def is_tianapi_available(self) -> bool:
        """
        检查TianAPI是否配置好并可用
        
        Returns:
            True=可用
        """
        if not self.tianapi_available:
            return False
        return is_available()
    
    def _search_tianapi(self, query: str) -> Optional[Dict]:
        """
        第3级：搜索 TianAPI
        
        Args:
            query: 食物名称
        
        Returns:
            营养数据，失败返回None（自动降级到下一级）
        """
        if not self.tianapi_available:
            return None
        
        try:
            result = search_tianapi(query)
            if result and result.get("calories", 0) > 0:
                return {
                    "name": result.get("name", query),
                    "cal": result.get("calories", 0),
                    "protein": result.get("protein", 0),
                    "fat": result.get("fat", 0),
                    "carbs": result.get("carbs", 0),
                    "fiber": result.get("fiber", 0),
                    "source": result.get("source", "TianAPI")
                }
        except Exception:
            pass
        
        return None
    
    # ==================== 食物扩展系统相关方法 ====================
    
    def _search_extension(self, query: str) -> Optional[Dict]:
        """
        第2级：搜索用户扩展食物数据
        
        Args:
            query: 食物名称
        
        Returns:
            营养数据，失败返回None（自动降级到下一级）
        """
        if not self.extension_available:
            return None
        
        try:
            extended_foods = get_extended_foods()
            query_lower = query.lower().strip()
            
            # 精确匹配
            if query in extended_foods:
                food_data = extended_foods[query]
                return {
                    "name": query,
                    "cal": food_data.get("cal", 0),
                    "protein": food_data.get("protein", 0),
                    "fat": food_data.get("fat", 0),
                    "carbs": food_data.get("carbs", 0),
                    "fiber": food_data.get("fiber", 0),
                    "source": food_data.get("source", "用户扩展数据")
                }
            
            # 模糊匹配
            for food_name, food_data in extended_foods.items():
                if food_name in query or query in food_name:
                    return {
                        "name": food_name,
                        "cal": food_data.get("cal", 0),
                        "protein": food_data.get("protein", 0),
                        "fat": food_data.get("fat", 0),
                        "carbs": food_data.get("carbs", 0),
                        "fiber": food_data.get("fiber", 0),
                        "source": food_data.get("source", "用户扩展数据")
                    }
            
        except Exception:
            pass
        
        return None
    
    def get_extension_status(self) -> dict:
        """
        获取扩展系统状态
        
        Returns:
            扩展系统状态信息
        """
        if not self.extension_available:
            return {"enabled": False, "message": "扩展系统未启用"}
        
        loader = get_extension_loader()
        if loader:
            return {
                "enabled": True,
                "extensions": loader.get_extensions_info(),
                "total_foods": len(loader.get_extended_foods()),
                "status": loader.get_status()
            }
        
        return {"enabled": False, "message": "扩展加载器未初始化"}
    
    # ==================== 状态信息 ====================
    
    def get_search_levels_info(self) -> str:
        """
        获取当前搜索引擎的层级信息（用于调试/展示）
        
        Returns:
            层级说明字符串
        """
        lines = []
        for i, (name, _, icon) in enumerate(self.sources, 1):
            if name == "天聚数行TianAPI":
                status = "✅ 已配置" if self.is_tianapi_available() else "⚠️  未配置"
            elif name == "扩展食物数据":
                ext_count = len(get_extended_foods()) if self.extension_available else 0
                status = f"✅ {ext_count} 种食物" if ext_count > 0 else "⚠️  无扩展数据"
            else:
                status = "✅"
            lines.append(f"{i}. {icon} {name} {status}")
        
        lines.append(f"{len(self.sources) + 1}. 📊 智能估算")
        
        return "\n".join(lines)


# 兼容性：导出一个默认实例，方便使用
_default_engine_v2 = None


def get_engine_v2(tianapi_key: str = None) -> FoodSearchEngineV2:
    """
    获取v2版搜索引擎实例（单例）
    
    Args:
        tianapi_key: 可选，传入则自动配置TianAPI
    
    Returns:
        FoodSearchEngineV2 实例
    """
    global _default_engine_v2
    
    if _default_engine_v2 is None:
        _default_engine_v2 = FoodSearchEngineV2()
    
    if tianapi_key:
        _default_engine_v2.set_tianapi_key(tianapi_key)
    
    return _default_engine_v2


# ==================== 测试代码 ====================

if __name__ == "__main__":
    print("=" * 60)
    print("食物搜索引擎 v2.4 - 终极增强版 测试")
    print("=" * 60)
    
    engine = FoodSearchEngineV2()
    
    print("\n当前搜索层级:")
    print(engine.get_search_levels_info())
    
    # 测试扩展系统状态
    print("\n扩展系统状态:")
    ext_status = engine.get_extension_status()
    if ext_status["enabled"]:
        print(f"  ✅ 扩展系统已启用")
        print(f"  📦 扩展食物数量: {ext_status['total_foods']}")
        for ext in ext_status["extensions"]:
            print(f"  - {ext['name']}: {ext['food_count']} 种食物")
    else:
        print("  ⚠️  扩展系统未启用")
    
    # 测试搜索
    test_foods = ["鸡蛋", "米饭", "苹果"]
    
    print("\n" + "=" * 60)
    print("搜索测试（不配置TianAPI，行为同原版）")
    print("=" * 60)
    
    for food in test_foods:
        result, source, icon = engine.search(food)
        if result:
            cal = result.get("cal") or result.get("calories")
            print(f"\n{icon} {food}: {cal} kcal/100g")
            print(f"   数据源: {source}")
        else:
            print(f"\n❌ {food}: 未找到")
    
    print("\n" + "=" * 60)
    print("✅ v2.4 测试完成！")
    print("=" * 60)
    print("\n使用提示:")
    print("1. 配置API Key: engine.set_tianapi_key('你的密钥')")
    print("2. 添加扩展数据: 将JSON文件放入 plugins/foods/ 目录")
    print("3. 随时降级: 改回原版 import 即可，无需修改业务代码")
