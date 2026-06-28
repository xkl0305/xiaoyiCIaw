# -*- coding: utf-8 -*-
"""
v2.5 新增：正念话术库
=====================
基于场景匹配的温暖话术系统
遵循三大铁律：不评判、不制造焦虑、不否定用户
"""

import random
from datetime import datetime
from collections import Counter


# ============== 1. 通用治愈语录（兜底） ==============
GENERAL_QUOTES = [
    "每一口食物，都是身体在说'谢谢'。享受这份滋养，你值得被温柔对待。",
    "吃饭不是任务，是和自己相处的时光。慢下来，感受每一种味道。",
    "今天的你，辛苦了。这顿饭，是对自己最好的犒赏。",
    "食物没有好坏，只有喜欢和不喜欢。吃你想吃的，开心最重要。",
    "肚子饱饱的，心里暖暖的，这就是最简单的幸福呀～",
    "不用计算每一口，相信你的身体知道它需要什么。",
    "好好吃饭，就是爱自己最具体的方式。",
    "每一餐，都是一次小小的庆祝。庆祝我们还活着，还能感受美味。",
    "吃了就吃了，不要愧疚。身体知道怎么处理它收到的礼物。",
    "你不是在'吃热量'，你是在吃营养，在吃快乐，在吃生活的味道。",
]


# ============== 2. 按食物情绪标签分类话术 ==============
MOOD_QUOTES = {
    # 😊 开心食物：富含色氨酸（牛奶、香蕉、坚果）
    'happy': [
        "开心食物会让大脑分泌快乐因子，今天也要开开心心～",
        "这些食物是身体的小确幸，一口一口把幸福吃进去～",
        "吃点开心的，今天的烦恼就不算数啦～",
        "原来你也需要被甜蜜治愈，没关系，我都懂～",
        "快乐是可以吃出来的，不信你再吃一口？",
    ],
    
    # 💪 力量食物：优质蛋白质（鸡蛋、鸡胸肉、鱼、豆腐）
    'power': [
        "蛋白质拉满！今天的你超有行动力～",
        "力量食物正在为你的身体充电，继续加油呀！",
        "你对自己的身体很负责，这是很棒的事～",
        "每一口蛋白质，都在帮你变成更好的自己～",
        "有力量的食物，给有力量的你～",
    ],
    
    # 🧸 治愈食物：碳水化合物为主（米饭、面包、面条、红薯）
    'comfort': [
        "碳水是身体的拥抱，你值得这份温暖和安全～",
        "今天需要很多安全感对不对？没关系，碳水会抱住你～",
        "治愈系食物的魔法，就是把疲惫变成踏实～",
        "吃碳水不是罪，是身体在说'我需要被照顾'～",
        "踏踏实实的一餐，就像踏踏实实的生活，很好～",
    ],
    
    # 🍃 清爽食物：高纤维低热量（蔬菜、水果、沙拉）
    'fresh': [
        "清清爽爽的一餐，身体也跟着轻起来～",
        "吃点清爽的，给身体做个深呼吸～",
        "你在很用心地照顾自己，这样真的很好～",
        "新鲜的食物，给你新鲜的好心情～",
        "轻盈不是目的，舒服才是～",
    ],
    
    # 🍬 甜蜜食物：含糖食物（蛋糕、奶茶、巧克力、糖）
    'sweet': [
        "甜的东西会直达心底，今天辛苦了对不对？",
        "吃点甜的，生活就不苦啦～",
        "甜蜜食物是生活的小糖片，偶尔吃一颗，心情就亮了～",
        "想吃甜的不是你的错，是生活需要加点糖～",
        "甜食是大脑的拥抱，今天就好好享受吧～",
    ],
    
    # 🧈 满足食物：高脂肪食物（油炸、火锅、牛油果、五花肉）
    'satisfied': [
        "想吃就吃是身体在说话，这份满足感本身就是治愈～",
        "满足感是很重要的情绪营养，今天你补充够了吗？",
        "好好犒劳自己了！身体和心情都满足了吗？",
        "丰盛的一餐，配得上丰盛的你～",
        "偶尔的满足，是为了更好地继续前行～",
    ],
}


# ============== 3. 按小动物匹配专属话术 ==============
ANIMAL_QUOTES = {
    '小猎豹': [
        "蛋白质是你的猎物，全速冲刺不手软！今天的你超有力量～",
        "小猎豹的能量条已充满，准备好出击了吗？",
        "高效、精准、有力量，这就是今天的你呀～",
    ],
    
    '小仓鼠': [
        "腮帮子塞满碳水的感觉，是不是超安心～",
        "囤满能量的小仓鼠，今天可以安心过冬啦～",
        "踏踏实实的小确幸，就像小仓鼠囤粮一样幸福～",
    ],
    
    '小狐狸': [
        "什么都吃一点，精明的小狐狸最会照顾自己～",
        "营养均衡的一餐，果然只有聪明的小狐狸才懂～",
        "小狐狸的智慧：不极端、不纠结，好好吃饭～",
    ],
    
    '小松鼠': [
        "东一口西一口，每一口都是小确幸～",
        "小嘴不停的小松鼠，今天囤了多少快乐呀？",
        "零食不是洪水猛兽，是小松鼠的快乐宝藏～",
    ],
    
    '小兔子': [
        "蹦蹦跳跳的小兔子，吃得清清爽爽也超开心～",
        "轻盈不是目的，像小兔子一样快乐才是～",
        "简简单单的一餐，就像小兔子的心情一样纯净～",
    ],
    
    '小熊': [
        "吃得饱饱的小熊，离冬眠的幸福又近一步～",
        "小熊的人生哲学：想吃就吃，开心最重要～",
        "丰盛又满足，小熊的快乐就是这么简单～",
    ],
}


# ============== 4. 特殊场景话术 ==============
SPECIAL_SCENES_QUOTES = {
    # 检测到负罪感：用户说"又吃了"、"忍不住"、"本来不想"等
    'guilt': [
        "没有'又'，只有'此刻我选择了'～选择本身就值得被尊重。",
        "忍不住不是缺点，是身体真的需要呀。听见它的声音就好～",
        "本来不想吃，但吃了就吃了。不责怪自己，也是一种成长～",
        "愧疚感是最没营养的东西，把它和食物一起消化掉吧～",
        "食物是用来享受的，不是用来评判自己的。你很好，真的。",
    ],
    
    # 深夜记录：22:00 - 04:00
    'late_night': [
        "深夜的食物是白天没说出口的话，慢慢吃，我陪着你～",
        "深夜吃东西不是错，是灵魂需要一点温暖的安慰～",
        "全世界都睡了，只有你和你的食物在说悄悄话。真好～",
        "深夜的胃需要被填满，深夜的心也需要被温柔对待～",
        "不管多晚，好好吃饭的人，都值得被好好对待～",
    ],
}


# ============== 负罪感关键词检测 ==============
GUILT_KEYWORDS = [
    '又吃', '又买', '又点',
    '忍不住', '没忍住', '控制不住',
    '本来不想', '本来不打算',
    '罪恶感', '好罪恶', '愧疚',
    '不应该', '不该吃',
    '完蛋了', '废了', '破戒',
]


def detect_guilt(text):
    """检测文本中是否包含负罪感关键词"""
    if not text:
        return False
    text = text.lower()
    return any(keyword in text for keyword in GUILT_KEYWORDS)


def detect_late_night():
    """检测是否是深夜（22:00 - 04:00）"""
    hour = datetime.now().hour
    return hour >= 22 or hour <= 4


def get_dominant_mood(all_meals):
    """获取占主导的食物情绪标签"""
    from food_mood_analyzer import get_food_mood
    
    mood_counter = Counter()
    total_foods = 0
    
    for meal_type, foods in all_meals.items():
        for food in foods:
            mood_info = get_food_mood(food.get('name', ''))
            mood = mood_info.get('mood', 'happy')
            mood_counter[mood] += 1
            total_foods += 1
    
    if total_foods == 0:
        return None
    
    # 某类情绪占比超过50%则认为是主导
    dominant_mood, count = mood_counter.most_common(1)[0]
    if count / total_foods >= 0.5:
        return dominant_mood
    
    return None


# ============== 话术匹配主函数 ==============
def get_mindful_quote(all_meals=None, matched_animal=None, user_text=None):
    """获取匹配的正念话术
    
    Args:
        all_meals: 所有餐次数据，用于检测主导情绪标签
        matched_animal: 匹配到的小动物名称
        user_text: 用户输入的文本，用于检测负罪感
        
    Returns:
        str: 匹配到的正念话术
    """
    
    # 优先级1：检测负罪感（最高优先级）
    if user_text and detect_guilt(user_text):
        return random.choice(SPECIAL_SCENES_QUOTES['guilt'])
    
    # 优先级2：检测深夜记录
    if detect_late_night():
        return random.choice(SPECIAL_SCENES_QUOTES['late_night'])
    
    # 优先级3：匹配小动物专属话术
    if matched_animal and matched_animal in ANIMAL_QUOTES:
        return random.choice(ANIMAL_QUOTES[matched_animal])
    
    # 优先级4：某类食物情绪标签占主导
    if all_meals:
        dominant_mood = get_dominant_mood(all_meals)
        if dominant_mood and dominant_mood in MOOD_QUOTES:
            return random.choice(MOOD_QUOTES[dominant_mood])
    
    # 优先级5：通用治愈语录（兜底）
    return random.choice(GENERAL_QUOTES)


# ============== 快捷测试 ==============
if __name__ == '__main__':
    print("=" * 50)
    print("🧘 正念话术库测试")
    print("=" * 50)
    print()
    
    print("📝 通用语录:")
    for i in range(3):
        print(f"  {i+1}. {get_mindful_quote()}")
    print()
    
    print("🐾 小动物专属语录:")
    for animal in ['小猎豹', '小仓鼠', '小狐狸']:
        print(f"  {animal}: {get_mindful_quote(matched_animal=animal)}")
    print()
    
    print("😔 负罪感场景:")
    print(f"  {get_mindful_quote(user_text='我又忍不住吃了蛋糕...')}")
    print(f"  {get_mindful_quote(user_text='本来不想吃的，结果还是吃了')}")
    print()
    
    print("=" * 50)
    print("✅ 正念话术库加载完成！")
    print("=" * 50)
