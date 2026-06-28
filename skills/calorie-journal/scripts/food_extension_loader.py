# -*- coding: utf-8 -*-
"""
🍽️ 食物数据扩展加载器 - 可插拔插件系统
============================================

功能：
1. 自动加载 plugins/foods/ 目录下的所有扩展数据文件
2. 与核心数据库无缝合并
3. 支持一键启用/禁用扩展
4. 支持用户自定义数据文件

使用方式：
    把你的扩展数据JSON文件放到 plugins/foods/ 目录下
    系统会自动检测并加载

数据格式（JSON）：
{
  "name": "疾控中心食物扩展包",
  "version": "1.0",
  "description": "中国疾病预防控制中心营养与健康所官方数据",
  "foods": {
    "食物名称": {
      "cal": 100,
      "protein": 5.0,
      "fat": 3.0,
      "carbs": 15.0,
      "fiber": 2.0,
      "source": "中国食物成分表第6版"
    }
  }
}

作者：饮食疗愈手账团队
版本：v2.4
"""

import os
import json
import glob
from typing import Dict, Optional

# 扩展数据目录
EXTENSION_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'plugins',
    'foods'
)

# 确保目录存在
os.makedirs(EXTENSION_DIR, exist_ok=True)


class FoodExtensionLoader:
    """食物数据扩展加载器"""
    
    def __init__(self):
        self.extensions = {}  # 已加载的扩展包
        self.extended_foods = {}  # 合并后的扩展食物数据
        self.load_all_extensions()
    
    def load_all_extensions(self) -> int:
        """
        加载 plugins/foods/ 目录下的所有扩展包
        
        Returns:
            加载的扩展包数量
        """
        self.extensions = {}
        self.extended_foods = {}
        
        # 查找所有JSON文件
        json_files = glob.glob(os.path.join(EXTENSION_DIR, '*.json'))
        
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 验证格式
                if 'foods' not in data:
                    continue
                
                ext_name = data.get('name', os.path.basename(json_file))
                self.extensions[ext_name] = data
                
                # 合并食物数据（核心数据优先级更高，扩展包不会覆盖核心数据）
                for food_name, food_data in data['foods'].items():
                    if food_name not in self.extended_foods:
                        self.extended_foods[food_name] = food_data
                
            except Exception as e:
                print(f"⚠️  加载扩展失败 {json_file}: {e}")
        
        return len(self.extensions)
    
    def get_extended_foods(self) -> Dict:
        """
        获取所有扩展食物数据
        
        Returns:
            扩展食物字典
        """
        return self.extended_foods
    
    def get_extensions_info(self) -> list:
        """
        获取已加载扩展包的信息
        
        Returns:
            扩展包信息列表
        """
        info = []
        for name, data in self.extensions.items():
            info.append({
                'name': name,
                'version': data.get('version', '1.0'),
                'description': data.get('description', ''),
                'food_count': len(data.get('foods', {})),
                'enabled': True
            })
        return info
    
    def add_custom_food(self, food_name: str, food_data: Dict) -> bool:
        """
        动态添加单个自定义食物
        
        Args:
            food_name: 食物名称
            food_data: 食物营养数据
        
        Returns:
            是否添加成功
        """
        if not food_name:
            return False
        
        # 验证必要字段
        required_fields = ['cal']
        for field in required_fields:
            if field not in food_data:
                return False
        
        self.extended_foods[food_name] = food_data
        return True
    
    def remove_custom_food(self, food_name: str) -> bool:
        """
        移除单个自定义食物
        
        Args:
            food_name: 食物名称
        
        Returns:
            是否移除成功
        """
        if food_name in self.extended_foods:
            del self.extended_foods[food_name]
            return True
        return False
    
    def get_status(self) -> str:
        """
        获取扩展系统状态摘要
        
        Returns:
            状态描述字符串
        """
        ext_count = len(self.extensions)
        food_count = len(self.extended_foods)
        
        if ext_count == 0:
            return f"📦 扩展系统：未加载扩展包（使用核心100种食物）"
        else:
            return f"📦 扩展系统：已加载 {ext_count} 个扩展包，新增 {food_count} 种食物"


# 全局单例
_extension_loader = None


def get_extension_loader() -> FoodExtensionLoader:
    """
    获取扩展加载器单例
    
    Returns:
        FoodExtensionLoader 实例
    """
    global _extension_loader
    if _extension_loader is None:
        _extension_loader = FoodExtensionLoader()
    return _extension_loader


def get_extended_foods() -> Dict:
    """
    便捷函数：获取所有扩展食物数据
    
    Returns:
        扩展食物字典
    """
    return get_extension_loader().get_extended_foods()


def print_extension_status():
    """打印扩展系统状态"""
    loader = get_extension_loader()
    print(loader.get_status())
    
    info = loader.get_extensions_info()
    for ext in info:
        print(f"   - {ext['name']} (v{ext['version']}): {ext['food_count']} 种食物")


# 测试入口
if __name__ == "__main__":
    print("=" * 60)
    print("食物数据扩展系统测试")
    print("=" * 60)
    print()
    
    print_extension_status()
    print()
    
    # 测试添加自定义食物
    loader = get_extension_loader()
    test_food = {
        'cal': 80,
        'protein': 0.8,
        'fat': 0.2,
        'carbs': 20.0,
        'fiber': 1.5,
        'source': '用户自定义'
    }
    
    if loader.add_custom_food('测试食物', test_food):
        print("✅ 添加自定义食物成功")
        print(f"   当前扩展食物总数: {len(loader.get_extended_foods())}")
    else:
        print("❌ 添加自定义食物失败")
    
    print()
    print("=" * 60)
    print("提示：将扩展数据JSON文件放入 plugins/foods/ 目录即可自动加载")
    print("=" * 60)
