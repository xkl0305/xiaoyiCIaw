# -*- coding: utf-8 -*-
"""
v2.5 P2 新增：手绘贴纸系统
===========================
用户可参与的手绘贴纸生态系统

模块结构：
├── preset_stickers.py    # 18个预设贴纸的纯代码手绘函数
├── sticker_renderer.py   # 贴纸位置系统 + 贴纸渲染逻辑
├── sticker_library.py    # 贴纸库管理（JSON持久化）
└── sticker_parser.py     # 贴纸描述语言解析器

使用示例：
1. 在卡片上贴贴纸：
   renderer = StickerRenderer()
   renderer.add_sticker('右上角', 'heart')
   renderer.render(draw, card_x, card_y)

2. 手绘新贴纸：
   parser = get_sticker_parser()
   sticker_id, name, params = parser.render_and_save("红色圆形加绿色叶子")

3. 管理贴纸库：
   library = get_sticker_library()
   all_stickers = library.list_stickers()
"""

from .preset_stickers import (
    PRESET_STICKERS,
    get_preset_sticker,
    list_preset_stickers,
)

from .sticker_renderer import (
    StickerRenderer,
    STICKER_POSITIONS,
    POSITION_NAMES,
    get_position_help,
)

from .sticker_library import (
    StickerLibrary,
    get_sticker_library,
    STICKER_LIBRARY_PATH,
    MAX_USER_STICKERS,
)

from .sticker_parser import (
    StickerParser,
    get_sticker_parser,
    get_help_text as get_parser_help,
)

__all__ = [
    # 预设贴纸
    'PRESET_STICKERS',
    'get_preset_sticker',
    'list_preset_stickers',
    
    # 贴纸渲染
    'StickerRenderer',
    'STICKER_POSITIONS',
    'POSITION_NAMES',
    'get_position_help',
    
    # 贴纸库
    'StickerLibrary',
    'get_sticker_library',
    'STICKER_LIBRARY_PATH',
    'MAX_USER_STICKERS',
    
    # 贴纸描述解析
    'StickerParser',
    'get_sticker_parser',
    'get_parser_help',
]

__version__ = '1.0.0'
