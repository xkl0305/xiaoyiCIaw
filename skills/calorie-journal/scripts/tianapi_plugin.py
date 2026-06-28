# -*- coding: utf-8 -*-
"""
TianAPI 食物营养查询插件 - 可插拔式
====================================
设计原则: 
1. 完全独立的模块，不修改原有代码
2. 通过配置开关控制是否启用
3. API失败时自动降级到原有搜索流程

使用方式:
1. 配置你的 API_KEY
2. 在 search_engine_v2 中启用此插件
3. 搜索失败自动回退到原有流程
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests
import urllib.parse
from typing import Dict, Optional

# ==================== 插件配置 ====================
# 开关：设置为False则完全不使用TianAPI，回退到原有搜索
TIANAPI_ENABLED = True

# 你的TianAPI密钥 - 在这里配置，或通过环境变量
# 也可以在运行时通过 set_api_key() 动态设置
TIANAPI_KEY = os.environ.get("TIANAPI_KEY", "")  # 优先从环境变量读取

# API超时设置（秒）
TIANAPI_TIMEOUT = 10
# =================================================


def set_api_key(api_key: str):
    """
    动态设置API密钥（方便运行时配置）
    
    Args:
        api_key: TianAPI的API Key
    """
    global TIANAPI_KEY
    TIANAPI_KEY = api_key


def set_enabled(enabled: bool):
    """
    动态启用/禁用TianAPI插件
    
    Args:
        enabled: True=启用，False=禁用
    """
    global TIANAPI_ENABLED
    TIANAPI_ENABLED = enabled


def is_available() -> bool:
    """
    检查TianAPI是否可用
    
    Returns:
        True=已启用且配置了API_KEY
    """
    return TIANAPI_ENABLED and bool(TIANAPI_KEY)


def search_tianapi(food_name: str) -> Optional[Dict]:
    """
    查询TianAPI获取食物营养数据
    
    Args:
        food_name: 食物名称（支持中文，如"黄焖鸡米饭"）
    
    Returns:
        结构化的营养数据字典，失败或未配置返回None
    """
    # 插件未启用或未配置Key，直接返回None（触发降级）
    if not is_available():
        return None
    
    try:
        # 构造请求
        encoded_food = urllib.parse.quote(food_name)
        url = f"http://api.tianapi.com/txapi/nutrient/index?key={TIANAPI_KEY}&word={encoded_food}"
        
        # 发送请求
        response = requests.get(url, timeout=TIANAPI_TIMEOUT)
        response.raise_for_status()
        
        # 解析响应
        result = response.json()
        
        # 检查API状态
        if result.get("code") != 200:
            return None  # API调用失败，降级
        
        # 提取数据
        news_list = result.get("newslist", [])
        if not news_list:
            return None  # 无数据，降级
        
        # 取第一个匹配结果
        food_data = news_list[0]
        
        # 数据校验：必须有热量数据
        if not food_data.get("heat"):
            return None
        
        # 标准化为统一格式（与现有引擎兼容）
        return {
            "name": food_name,
            "name_en": food_data.get("en_name", ""),
            "calories": float(food_data.get("heat", 0)),
            "protein": float(food_data.get("protein", 0)),
            "fat": float(food_data.get("fat", 0)),
            "carbs": max(0, float(food_data.get("carbohydrate", 0))),  # 确保不为负
            "fiber": float(food_data.get("fiber", 0)),
            "category": food_data.get("type", ""),
            "unit": "100g",
            "source": "天聚数行TianAPI"
        }
        
    except requests.exceptions.Timeout:
        return None  # 超时，降级
    except requests.exceptions.RequestException:
        return None  # 网络错误，降级
    except Exception:
        return None  # 其他错误，降级


# 如果直接运行此文件，做简单测试
if __name__ == "__main__":
    print("=" * 50)
    print("TianAPI 插件测试")
    print("=" * 50)
    
    # 检查配置状态
    if is_available():
        print("✅ TianAPI已配置并启用")
        # 测试查询
        result = search_tianapi("鸡蛋")
        if result:
            print("\n查询结果（鸡蛋）:")
            for k, v in result.items():
                print(f"  {k}: {v}")
        else:
            print("\n❌ 查询失败或无数据")
    else:
        print("⚠️  TianAPI未配置或未启用")
        print("   请设置 TIANAPI_KEY 后再测试")
        print("\n配置方式：")
        print("  1. 在代码中直接设置 TIANAPI_KEY")
        print("  2. 设置环境变量 export TIANAPI_KEY='你的密钥'")
        print("  3. 运行时调用 set_api_key('你的密钥')")
