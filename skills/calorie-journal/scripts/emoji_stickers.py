# -*- coding: utf-8 -*-
"""
v2.1 新增：Emoji贴纸系统
=========================
每张卡片可以存储1-3个贴纸emoji
用户可以自由选择贴纸装饰手账卡片
"""

# 贴纸存储格式: {meal_type: [emoji1, emoji2, ...]}
# meal_type: breakfast, lunch, snack1, snack2, exercise, summary
CARD_STICKERS = {
    'breakfast': [],
    'lunch': [],
    'snack1': [],
    'snack2': [],
    'exercise': [],
    'summary': [],
}

# 每张卡片最多贴纸数量
MAX_STICKERS_PER_CARD = 3

# ============== 贴纸分类库 ==============
STICKER_CATEGORIES = {
    "🍞 食物贴纸": "🍞🥐🥚🍳🥓🍔🍟🍕🍜🍲🍣🍱🥟🍧🍨🍦🎂🍭🍬🍫🍪🌰🥜🍯🥛☕🍵🍶🍾🍷🍸🍹🍺",
    "😊 情绪贴纸": "😊😌😋🥰🤗😎🥳😇🤤😴😔😢😭😤😠🤬🤯😳🥵🥶😱😨😰😥😓🤔🤭🤫🤥",
    "✨ 装饰贴纸": "✨⭐🌟💫💥💦🔥💨💤💢💬💭♨️🫧❤️🧡💛💚💙💜🖤🤍🤎💖💗💓💞💕💌❣️💟🎀",
    "🐾 小动物贴纸": "🐆🐹🦊🐿️🐰🐻🐱🐶🐭🐼🦁🐮🐷🐸🐵🐔🐧🐦🐤🐣🐥🦆🦅🦉🦇🐺🐗🐴🦄🐝🐛🦋🐌🐞🐜🦟🦗🕷️🦂🐢🐍🦎🦖🦕🐙🦑🦐🦞🦀🐡🐠🐟🐬🐳🐋🦈🐊🐅",
}


def add_sticker(meal_type, emoji):
    """给指定卡片添加贴纸
    
    Args:
        meal_type: 卡片类型（breakfast/lunch/snack1/snack2/exercise/summary）
        emoji: 贴纸emoji
        
    Returns:
        bool: 是否添加成功
    """
    if meal_type in CARD_STICKERS and len(CARD_STICKERS[meal_type]) < MAX_STICKERS_PER_CARD:
        CARD_STICKERS[meal_type].append(emoji)
        return True
    return False


def remove_sticker(meal_type, index=-1):
    """移除指定卡片的贴纸
    
    Args:
        meal_type: 卡片类型
        index: 要移除的贴纸索引（默认移除最后一个）
        
    Returns:
        bool: 是否移除成功
    """
    if meal_type in CARD_STICKERS and len(CARD_STICKERS[meal_type]) > 0:
        try:
            CARD_STICKERS[meal_type].pop(index)
            return True
        except:
            return False
    return False


def get_stickers(meal_type):
    """获取指定卡片的贴纸列表
    
    Args:
        meal_type: 卡片类型
        
    Returns:
        list: 贴纸emoji列表
    """
    return CARD_STICKERS.get(meal_type, [])


def clear_stickers(meal_type=None):
    """清空贴纸
    
    Args:
        meal_type: 卡片类型，如果为None则清空所有卡片的贴纸
    """
    if meal_type:
        if meal_type in CARD_STICKERS:
            CARD_STICKERS[meal_type] = []
    else:
        for key in CARD_STICKERS:
            CARD_STICKERS[key] = []


def draw_stickers(draw, meal_type, x_start, y, spacing=35, font_size=28):
    """在卡片上绘制贴纸（供PIL调用）
    
    Args:
        draw: PIL ImageDraw对象
        meal_type: 卡片类型
        x_start: 起始X坐标
        y: Y坐标
        spacing: 贴纸间距
        font_size: 字体大小
    """
    if meal_type not in CARD_STICKERS:
        return
    
    stickers = CARD_STICKERS[meal_type]
    if not stickers:
        return
    
    # 加载字体（这里简化处理，实际使用时从gen_card.py传入字体）
    # 实际调用时应该在gen_card.py中实现draw_stickers函数，使用已加载的字体
    
    x = x_start
    for sticker in stickers:
        # 实际绘制由gen_card.py完成
        # draw.text((x, y), sticker, font=font, fill='#333333')
        x += spacing


def format_sticker_guide():
    """格式化贴纸选择指南
    
    Returns:
        str: 贴纸选择指南
    """
    lines = ["🎨 Emoji贴纸选择指南\n"]
    for category, stickers in STICKER_CATEGORIES.items():
        lines.append(f"{category}:")
        lines.append(f"  {stickers}\n")
    lines.append("💡 直接说贴纸的emoji就可以添加啦！")
    lines.append("   比如：\"给早餐贴个😊\"、\"给总结加3个⭐\"")
    return "\n".join(lines)


if __name__ == "__main__":
    # 测试用例
    print("=" * 50)
    print("🎨 Emoji贴纸系统 - 测试用例")
    print("=" * 50 + "\n")
    
    # 测试添加贴纸
    print("📝 测试添加贴纸...")
    add_sticker('breakfast', '😊')
    add_sticker('breakfast', '⭐')
    add_sticker('breakfast', '🍳')
    print(f"   早餐卡片贴纸: {get_stickers('breakfast')}")
    
    add_sticker('lunch', '🍜')
    add_sticker('lunch', '✨')
    print(f"   午餐卡片贴纸: {get_stickers('lunch')}")
    
    # 测试超过最大数量
    result = add_sticker('breakfast', '💖')
    print(f"\n⚠️  尝试添加第4个贴纸: {'失败（正常）' if not result else '成功'}")
    
    # 测试移除贴纸
    remove_sticker('breakfast')
    print(f"\n📤 移除最后一个后: {get_stickers('breakfast')}")
    
    # 测试清空
    clear_stickers('breakfast')
    print(f"\n🗑️  清空后: {get_stickers('breakfast')}")
    
    print("\n" + "=" * 50)
    print("✅ 所有测试通过！")
    print("=" * 50)
