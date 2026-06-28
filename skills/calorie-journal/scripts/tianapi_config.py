# -*- coding: utf-8 -*-
"""
TianAPI 配置文件
================
集中管理TianAPI相关配置，方便统一修改

使用说明:
1. 复制此文件，改名为 tianapi_config_local.py（可选）
2. 在 local 文件中填写你的API_KEY
3. 不要把真实的API_KEY提交到版本控制
"""

# TianAPI开关
# 设置为False，则完全不使用TianAPI，完全回退到原版搜索
TIANAPI_ENABLED = True

# API密钥配置
# 方式一：直接在这里配置（不推荐提交到版本控制）
# TIANAPI_KEY = "你的API_KEY"

# 方式二：从环境变量读取（推荐）
import os
TIANAPI_KEY = os.environ.get("TIANAPI_KEY", "")

# 方式三：从本地配置文件读取（推荐，本地文件不提交）
# try:
#     from tianapi_config_local import TIANAPI_KEY
# except ImportError:
#     TIANAPI_KEY = ""


# API调用超时（秒）
TIANAPI_TIMEOUT = 10

# 是否在日志中输出调试信息
TIANAPI_DEBUG = False


# ========== 使用示例 ==========
"""
# 在业务代码中这样用：

from tianapi_config import TIANAPI_KEY, TIANAPI_ENABLED
from search_engine_v2 import FoodSearchEngineV2

engine = FoodSearchEngineV2()

if TIANAPI_ENABLED and TIANAPI_KEY:
    engine.set_tianapi_key(TIANAPI_KEY)
    print("✅ TianAPI已启用")
else:
    print("⚠️  TianAPI未配置，将使用原版搜索")

# 搜索，接口完全不变
result, source, icon = engine.search("黄焖鸡米饭")
"""
