# 🎨 如何制作自己的主题包

## 什么是主题包？

主题包是一个完整的世界观套装，包含6个模块：
- 📝 命名系统（naming.json）
- 🎭 角色设定（character.json）
- 😊 情绪分类（emotion.json）
- 💬 话术系统（quotes.json）
- 🎨 视觉风格（style.json）
- 🎪 贴纸库（stickers.json）

## 快速开始

### 1. 复制默认主题包

```bash
cp -r default my_theme
cd my_theme
```

### 2. 修改每个JSON文件

按照下面的模板，修改每个模块的内容。

### 3. 测试你的主题包

```python
from theme_pack_loader import get_theme_loader

loader = get_theme_loader()
theme = loader.load_theme("my_theme")  # 你的主题包目录名
```

---

## 📝 命名系统（naming.json）

```json
{
  "theme_id": "my_theme",
  "theme_name": "我的主题",
  "version": "1.0",
  "author": "你的名字",
  
  "nutrition_names": {
    "calories": {
      "name": "热量的新名字",
      "icon": "🔥",
      "description": "一句话描述"
    },
    "protein": {},
    "carbs": {},
    "fat": {},
    "fiber": {}
  }
}
```

**营养字段说明：**
- `calories` - 热量
- `protein` - 蛋白质
- `carbs` - 碳水化合物
- `fat` - 脂肪
- `fiber` - 膳食纤维

---

## 🎭 角色设定（character.json）

```json
{
  "character_id": "my_character",
  "character_name": "我的角色",
  
  "personality": {
    "tone": "说话语气",
    "speech_style": "说话风格",
    "core_value": "核心价值观"
  },
  
  "greetings": [
    "问候语1",
    "问候语2"
  ],
  
  "signatures": [
    "签名1",
    "签名2"
  ]
}
```

---

## 😊 情绪分类（emotion.json）

```json
{
  "emotion_system_id": "my_emotion",
  "system_name": "我的情绪分类",
  
  "categories": {
    "category_id": {
      "name": "分类名称",
      "icon": "🌟",
      "description": "描述",
      "keywords": ["关键词1", "关键词2"]
    }
  },
  
  "default_category": {
    "name": "默认分类",
    "icon": "🍽️"
  }
}
```

---

## 💬 话术系统（quotes.json）

```json
{
  "quotes_system_id": "my_quotes",
  "system_name": "我的话术",
  
  "triggers": {
    "general": {
      "name": "通用",
      "quotes": ["语录1", "语录2", "语录3"]
    },
    "happy_food": {},
    "late_night": {},
    "high_protein": {},
    "light_meal": {}
  },
  
  "default_quote": "默认话术"
}
```

**触发类型说明：**
- `general` - 通用
- `happy_food` - 快乐食物（甜食、甜点）
- `late_night` - 深夜进食
- `high_protein` - 高蛋白食物
- `light_meal` - 轻食、健康食物

---

## 🎨 视觉风格（style.json）

```json
{
  "style_system_id": "my_style",
  "system_name": "我的风格",
  "default_style": "style1",
  
  "styles": {
    "style1": {
      "name": "风格名称",
      "background": "#f5f0e8",
      "card_bg": "#fff9f0",
      "text_color": "#5a4a3a",
      "accent_color": "#d4a574",
      "description": "风格描述"
    }
  }
}
```

---

## 🎪 贴纸库（stickers.json）

```json
{
  "sticker_system_id": "my_stickers",
  "system_name": "我的贴纸",
  
  "preset_stickers": {
    "sticker_id": {
      "name": "贴纸名称",
      "emoji": "🦊",
      "description": "描述",
      "rarity": "common",
      "positions": ["any"]
    }
  },
  
  "sticker_rules": {
    "max_per_card": 3,
    "rare_chance": 0.1,
    "epic_chance": 0.03,
    "legendary_chance": 0.01
  },
  
  "positions": [
    "top_left", "top_center", "top_right",
    "center",
    "bottom_left", "bottom_center", "bottom_right"
  ]
}
```

**稀有度说明：**
- `common` - 普通
- `uncommon` - 稀有
- `rare` - 珍贵
- `epic` - 史诗
- `legendary` - 传说

---

## 💡 创作灵感

### 科幻主题
- 命名：能量、护盾、燃料、储备、离子
- 角色：宇航员、AI助手、星际旅行者
- 话术：客观、理性、探索

### 魔法主题
- 命名：魔力、护盾、法力、精华、净化
- 角色：魔法师、精灵、魔女
- 话术：神秘、优雅、奇幻

### 校园主题
- 命名：学分、体力、脑力、活力、活力
- 角色：学长/学姐、班长、社团伙伴
- 话术：青春、活力、鼓励

---

## ✅ 检查清单

发布前检查：
- [ ] 所有JSON文件语法正确
- [ ] 所有字段都有值
- [ ] 话术积极向上，符合零焦虑原则
- [ ] 图标使用Emoji
- [ ] 颜色使用十六进制格式（#RRGGBB）

---

## 📤 分享你的主题包

把你的主题包目录打包成ZIP，分享给其他用户！

```bash
zip -r my_theme.zip my_theme/
```

---

## 🎉 示例主题包

查看 `default/` 目录下的完整示例，了解更多细节！
