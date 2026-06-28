---
name: xiaoyi-vlog-gen
description: 一键成片、vlog制作，支持批量导入多张图片，智能画面编排、自动匹配氛围感BGM、添加流畅转场与创意特效，一键渲染生成精美vlog短片。触发词：一键成片、vlog、照片剪辑、多图成片、图库生成视频。
---

# 小艺一键成片

传入一组图片，按序执行 **初始化检查 → 图像理解 → BGM生成 → 智能编排 → 项目准备 → 渲染输出 → 发送给用户**，不得跳过任何步骤，每步汇报进度。

---

## 一键成片完整流程

### 第0步：初始化检查

每次生成视频前，先检查初始化状态：

```bash
bash ~/.openclaw/workspace/skills/xiaoyi-vlog-gen/scripts/check-init.sh
```

- 退出码 0 → 已初始化，继续下一步
- 退出码 1 → 执行 [docs/setup.md](docs/setup.md) 重新初始化

### 第1步：图像理解

使用当前环境中已安装的**图像理解技能**分析理解图片内容。

**要点：**
- ⚡ **多张图片可并行理解，显著缩短分析耗时**
- 对每张图片都要调用，收集完整的视觉信息
- prompt 应引导模型输出适合视频脚本创作的描述：场景、人物、物体、情绪、色彩、构图、光线
- 特别关注图片间的**关联性**（同一场景？时间顺序？主题递进？），为后续编排提供依据
- 将所有图片的理解结果汇总，作为脚本创作的素材

### 第2步：BGM 生成

使用当前环境中已安装的**音乐生成技能**（minimax-music-gen）根据视频风格生成背景音乐。

**BGM 来源：**
- 用户提供 → 直接使用
- 重排/重渲染 → 复用已有 BGM
- 全新视频 → 生成新 BGM（约5分钟，exec timeout 设 600 秒）
- 用户不要音乐 → 跳过


**BGM 风格参考：**

| 视频风格 | BGM 描述示例 |
|----------|-------------|
| 旅行 vlog | 轻快吉他、民谣风、公路旅行感 |
| 浪漫/婚礼 | 钢琴、弦乐、温柔抒情 |
| 复古/胶片 | Lo-fi、爵士、怀旧黑胶感 |
| 都市/街拍 | 电子节拍、Hip-hop、都市氛围 |
| 自然/风景 | 环境音乐、空灵钢琴、自然音效 |
| 美食/生活 | 轻快爵士、法式手风琴、温馨感 |
| 运动/冒险 | 摇滚、电子、节奏感强 |

### 第3步：智能编排

根据图像理解结果，决定图片的展示顺序、动画、转场、特效和每张图片的展示时长。**核心原则：根据内容动态匹配，不要固定套路。**

**编排策略：**
- **叙事逻辑**：按时间线、因果关系或故事弧线排列
- **情绪曲线**：起→承→转→合，制造情绪起伏
- **视觉节奏**：冷暖色调交替、远近景切换、动静搭配
- **主题聚类**：相同主题的图片归组，组间用转场分隔

**动画选择逻辑（根据图片内容匹配）：**

| 效果 | 适用场景 | 选择依据 |
|------|----------|----------|
| `zoom-in` | 突出细节、营造聚焦感 | 图片有明确视觉焦点（人物、物体、花朵等） |
| `zoom-out` | 展示全貌、揭示环境 | 图片从局部到整体的叙事需要 |
| `pan-left` | 向左平移、回顾 | 水平构图、全景、城市天际线 |
| `pan-right` | 向右平移、推进 | 水平构图、全景、城市天际线 |
| `tilt-up` | 展示建筑、树木等纵向主体 | 纵向构图、高楼、瀑布、大树 |
| `tilt-down` | 俯瞰、降落感 | 俯视构图、从天空到地面 |
| `rotate-cw` | 顺时针旋转、活力感 | 动态场景、运动、舞蹈、旋转物体 |
| `rotate-ccw` | 逆时针旋转、梦幻感 | 梦幻、超现实、艺术感场景 |
| `3d-tilt-left` | 3D透视左倾、空间感 | 科技感、产品展示、立体构图 |
| `3d-tilt-right` | 3D透视右倾、空间感 | 科技感、产品展示、立体构图 |
| `static` | 人像特写、文字画面 | 人脸特写、已有强视觉冲击的图片 |

**转场选择逻辑（根据前后场景关系匹配）：**

| 转场 | 适用场景 | 选择依据 | 可用 transitionProps |
|------|----------|----------|---------------------|
| `fade` | 通用过渡 | 默认选择，情绪平稳过渡 | `shouldFadeOutExitingScene: true`（退出场景也淡出，更丝滑，**默认开启**） |
| `dissolve` | 梦幻、回忆、情绪过渡 | 前后场景情绪连贯、柔和（带微缩放，区别于fade） | — |
| `slide-left` | 时间推进、场景变换 | 前后场景空间/时间相邻 | `slideEnterStyle`/`slideExitStyle`（可加旋转/缩放让滑入更酷） |
| `slide-right` | 回忆、倒叙 | 回溯之前的场景 | 同上 |
| `slide-up` | 上升、揭示、新篇章 | 从下往上揭示新内容、情绪上升 | 同上 |
| `slide-down` | 下沉、结束、沉淀 | 情绪回落、段落结束 | 同上 |
| `wipe` | 信息更新、对比、时间流逝 | 前后场景有对比关系（新旧、昼夜）或时间跨度 | `wipeDirection`：8方向（见下表） |
| `flip` | 对比、转折 | 情绪转折点、主题切换 | `flipDirection`：4方向 + `flipPerspective`（默认1000，越小透视越强） |
| `zoom` | 聚焦、冲击、强调 | 需要视觉冲击力、从远到近或近到远 | `zoomDirection`：`'in'`（默认）| `'out'` |
| `rotate` | 活力、动感、风格切换 | 运动场景、风格突变、节奏段落 | `rotateDirection`：`'cw'`（默认）| `'ccw'` |
| `blur` | 梦幻、朦胧、记忆 | 回忆、梦境、情绪过渡、柔焦效果 | `blurAmount`：模糊像素，默认30 |
| `glitch` | 科技、故障风、快节奏 | 赛博朋克、数字感、快节奏剪辑 | — |
| `clock-wipe` | 时间流逝、揭示、仪式感 | 时钟式擦除，适合时间推进、重要场景揭示 | — |
| `iris` | 聚焦、经典电影感 | 圆形展开/收缩，复古电影、聚焦人物 | — |
| `none` | 节奏快、新闻感 | 快节奏段落、连续动作 | — |

**transitionProps 详解：**

| 字段 | 适用转场 | 类型 | 默认值 | 说明 |
|------|----------|------|--------|------|
| `wipeDirection` | wipe | string | `'from-left'` | 8方向：`from-left` `from-top-left` `from-top` `from-top-right` `from-right` `from-bottom-right` `from-bottom` `from-bottom-left` |
| `flipDirection` | flip | string | `'from-left'` | 4方向：`from-left` `from-right` `from-top` `from-bottom` |
| `flipPerspective` | flip | number | `1000` | 透视距离，越小3D感越强（推荐 600-1200） |
| `shouldFadeOutExitingScene` | fade | boolean | `true` | 退出场景是否也淡出（默认开启，转场更丝滑） |
| `slideEnterStyle` | slide-* | CSS | — | 进入场景自定义样式，如 `{"transform":"scale(0.9) rotate(-3deg)"}` |
| `slideExitStyle` | slide-* | CSS | — | 退出场景自定义样式，如 `{"transform":"scale(1.1) rotate(3deg)"}` |
| `zoomDirection` | zoom | string | `'in'` | `'in'`：从小到大 | `'out'`：从大到小 |
| `rotateDirection` | rotate | string | `'cw'` | `'cw'`：顺时针 | `'ccw'`：逆时针 |
| `blurAmount` | blur | number | `30` | 模糊像素值，越大越模糊 |

**编排建议：**
- `wipe` 根据画面主体位置选方向：主体在右侧用 `from-left`，主体在左下用 `from-top-right`，对角线擦除更有动感
- `flip` 配合 `flipPerspective: 800` 透视更强烈，适合情绪转折
- `slide-*` 加 `slideEnterStyle` 旋转/缩放可让普通滑入变酷，如旋转 ±3° + 缩放 0.9→1
- `fade` 默认已开启 `shouldFadeOutExitingScene`，无需手动设置

**特效选择逻辑（根据视频风格按需添加）：**

| 特效 | 配置方式 | 适用场景 |
|------|-------------------|----------|
| 运动模糊 | `scene.effect: 'motion-blur'` | 增强动感 |
| 字幕叠加 | `scene.caption: '文字'` | TikTok风格文字、地点名、歌词 |
| 几何图形装饰 | `scene.decorations: [{shape, position, color, size, opacity?}]` | 角落装饰、信息点缀。shape 取值：`circle` `star` `heart` `polygon` `arrow`；position 取值：`top-left` `top-right` `bottom-left` `bottom-right` `center` |
| SVG描边动画 | 顶层 `titleStroke: true` | 标题文字描边揭示效果 |

**时长编排要点：**
- **图片展示时长由内容决定**，不是由 BGM 时长决定。通常 3-8 秒/张
  - 风景、全景类：5-8 秒（需要时间感受氛围）
  - 人物特写、情绪类：4-6 秒
  - 快节奏段落（运动、街拍）：2-4 秒
- 视频总时长 = 所有图片展示时长之和 - 转场重叠时长
- BGM 截断到视频总时长 + 1 秒淡出缓冲，不需要用完整个 BGM
  - Remotion 中通过 `<Audio>` 组件的 `trimAfter` prop 控制（已内置在 MainComposition 中）
  - BGM 末尾 1 秒自动淡出（已内置）
- 情绪高潮处图片停留稍长，过渡段可快速切换
- `calculateMetadata` 自动计算总帧数和转场重叠，agent 只需提供 `sceneDurations`，不需要手动扣除转场重叠

**编排原则：**

**⛔ 硬性约束（违反即不合格）：**
1. **禁止连续相同转场** — 相邻两个场景的 transition 必须不同，fade→dissolve 也算同类软转场，禁止连续出现
2. **转场种类 ≥ ⌈N/3⌉** — 12 张图至少 4 种不同转场，6 张图至少 2 种
3. **动画种类 ≥ ⌈N/3⌉** — 12 张图至少 4 种不同动画，同一种动画最多出现 ⌈N/2⌉ 次
4. **transitionProps 使用率 ≥ 30%** — 至少三成的转场必须搭配 transitionProps 增强参数，不能只填转场名称
5. **字幕克制** — 非必要不加 caption

**✅ 编排策略（让视频更好看）：**
1. **转场强度匹配情绪** — 平稳过渡用弱转场（fade/dissolve/blur），情绪转折/场景突变用强转场（flip/wipe/clock-wipe/iris），视觉冲击用 zoom/rotate
2. **转场方向匹配画面** — 主体在右侧→wipe from-left，主体在左下→wipe from-top-right；情绪上升→slide-up，回忆倒叙→slide-right
3. **动画匹配内容** — 有焦点的图→zoom-in，全景→pan，纵向主体→tilt，动态场景→rotate，人像特写→static
4. **节奏有快有慢** — 不是所有图都 5 秒，高潮场景 6-8 秒，过渡场景 3-4 秒，快节奏段落 2-3 秒
5. **图片多则缩短单张时长** — 图片超过10张适当降低每张时长，总时长控制在 30-100 秒
6. **特效点缀不堆砌** — 运动感→1-2 个 motion-blur，不要每张都加

**主题配色（theme 字段，根据内容自选或自定义，下表仅供参考）：**

| 预设名 | bgColor | textColor | accentColor | 适用风格 |
|--------|---------|-----------|-------------|----------|
| 暗金（默认） | `#1a1a2e` | `#e8d5b7` | `#a89070` | 复古、经典、婚礼 |
| 纯白 | `#ffffff` | `#1a1a2e` | `#666666` | 简约、商务、产品 |
| 暖橙 | `#2d1b0e` | `#ff9f43` | `#c4762c` | 旅行、美食、生活 |
| 冷蓝 | `#0a1628` | `#74b9ff` | `#4a8bc2` | 科技、城市、夜景 |
| 莫兰迪 | `#3c3c3c` | `#d4c5b9` | `#9e8e7e` | 文艺、胶片、安静 |
| 森绿 | `#0d2818` | `#a8e6cf` | `#6bae8f` | 自然、风景、户外 |
| 粉红 | `#2d0a1e` | `#ffb6c1` | `#c97b8b` | 浪漫、可爱、少女 |
| 赛博 | `#0a0a0a` | `#00ff88` | `#00cc6a` | 赛博朋克、电子、潮流 |

**输出 script.json：**

编排完成后直接生成 `script.json`，作为 `--props` 传给 Remotion：

```json
{
  "title": "视频标题",
  "subtitle": "副标题",
  "endText": "片尾文字",
  "bgmSrc": "<实际生成的音乐文件名>",
  "titleStroke": true,
  "theme": {
    "bgColor": "#1a1a2e",
    "textColor": "#e8d5b7",
    "accentColor": "#a89070"
  },
  "sceneDurations": [135, 120, 96],
  "scenes": [
    {
      "image": "photo1.jpg",
      "animation": "zoom-in",
      "transition": "wipe",
      "transitionDuration": 24,
      "transitionProps": {"wipeDirection": "from-bottom-right"},
      "narration": "场景描述（仅用于 agent 记录，不渲染）",
      "effect": "motion-blur",
      "caption": "地点名或描述文字",
      "decorations": [{"shape": "star", "position": "top-right", "color": "#FFD700", "size": 40, "opacity": 0.5}]
    },
    {
      "image": "photo2.jpg",
      "animation": "pan-right",
      "transition": "flip",
      "transitionDuration": 24,
      "transitionProps": {"flipDirection": "from-right", "flipPerspective": 800}
    },
    {
      "image": "photo3.jpg",
      "animation": "tilt-up",
      "transition": "slide-left",
      "transitionProps": {"slideEnterStyle": {"transform": "scale(0.9) rotate(-3deg)"}, "slideExitStyle": {"transform": "scale(1.1) rotate(3deg)"}}
    }
  ]
}
```

**字段说明：**
- `bgmSrc`：**顶层字段**，BGM 文件名（放在 `audio/` 目录下，文件名需与实际文件一致）。不要放在 scene 级别
- `titleStroke`：**可选**，true 时标题文字用描边揭示动画
- `theme`：**可选**，标题/片尾颜色主题，不设则用默认暗金主题
  - `bgColor`：标题/片尾背景色，默认 `#1a1a2e`（深蓝紫）
  - `textColor`：主文字色（标题、片尾），默认 `#e8d5b7`（暖金）
  - `accentColor`：副标题色，默认 `#a89070`（暗金）
- `sceneDurations`：**帧数数组**，长度必须与 scenes 一致。每张图 3-8 秒 × 24fps
- `scene.narration`：场景描述文字，仅用于 agent 记录，组件不渲染
- `scene.image`：图片文件名（放在 `images/` 目录下）
- `scene.animation`：动画类型（11 种，见上方动画表）
- `scene.transition`：转场类型（15 种含 none，见上方转场表），kebab-case 格式
- `scene.transitionDuration`：**可选**，转场帧数，默认 18（0.75秒），情绪转折处可加长（24-36帧），快节奏可缩短（8-12帧）
- `scene.transitionProps`：**可选**，转场增强参数对象，根据转场类型选择（见上方 transitionProps 详解表）。常用示例：
  - wipe 加方向：`{"wipeDirection": "from-bottom-right"}`
  - flip 加透视：`{"flipDirection": "from-right", "flipPerspective": 800}`
  - slide 加旋转：`{"slideEnterStyle": {"transform": "scale(0.9) rotate(-3deg)"}, "slideExitStyle": {"transform": "scale(1.1) rotate(3deg)"}}`
- `scene.effect`：**可选**，视觉特效 `'motion-blur'` | `'none'`
- `scene.caption`：**可选**，底部文字叠加。
- `scene.decorations`：**可选**，几何装饰数组，每项 {shape, position, color, size, opacity?}

### 第4步：项目准备

准备渲染环境，将 script.json 和素材部署到模板项目。

#### 4.1 创建输出目录、拷贝素材、写入 script.json

```bash
OUTPUT=~/.openclaw/workspace/generated-vlog/YYYYMMDD_HHMMSS

# 创建输出目录
mkdir -p $OUTPUT/images $OUTPUT/audio $OUTPUT/out

# 按 script.json 中的文件名拷贝图片和BGM
cp <用户图片> $OUTPUT/images/<scene.image中的文件名>
cp <BGM音频> $OUTPUT/audio/<bgmSrc中的文件名>
```

将第3步编排的 script.json 写入 `$OUTPUT/script.json`。

#### 4.2 调用脚本部署到模板

```bash
PROJECT=~/.openclaw/workspace/generated-vlog/template
SCRIPT=~/.openclaw/workspace/skills/xiaoyi-vlog-gen/scripts/prepare-project.sh

bash $SCRIPT $OUTPUT $PROJECT
```

### 第5步：渲染输出

调用脚本完成预览帧检查和渲染：

```bash
OUTPUT=~/.openclaw/workspace/generated-vlog/YYYYMMDD_HHMMSS
SCRIPT=~/.openclaw/workspace/skills/xiaoyi-vlog-gen/scripts/render-video.sh

bash $SCRIPT $OUTPUT <内容缩写> [--timeout 1800]
```

`<内容缩写>` 为视频文件名（不含 .mp4），根据图片内容提取 2-4 个关键词，短横线连接，全小写。示例：猫咪日常 → `cats-daily`，旅行风景 → `travel-landscape`。

渲染耗时较长，exec timeout 建议设 20 分钟以上。

### 第6步：发送视频给用户

渲染完成后，将生成的视频文件通过 `MEDIA:` 指令发送给用户：

```
MEDIA:~/.openclaw/workspace/generated-vlog/YYYYMMDD_HHMMSS/out/<内容缩写>.mp4
```