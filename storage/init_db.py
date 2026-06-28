"""数据库初始化入口。首次使用时调用。"""
from .db import init

init()
print('✅ storage database initialized')
