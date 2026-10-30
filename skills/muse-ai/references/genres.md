# 流派配方与 Style Prompt（MuseAI）

为特定流派创作、组合 Style Prompt 时参考本文件。每个配方含：Style Prompt 范式（带 BPM 数字 + 年代锚定）+ 推荐结构 + 置信度 + 必需触发关键词。

> 语法说明：段落标记用**合并标签 / 逗号 / 冒号参数化**（如 `[Whispered Verse]`、`[Chorus, Half Time]`、`[Bridge: piano only]`），**不用管道符**。原因见 [arrangement.md「Meta Tag 组合语法」](arrangement.md#meta-tag-组合语法)。

## 目录

- [流派置信度总览](#流派置信度总览)
- [通用五层公式](#通用五层公式)
- [高置信度流派配方](#高置信度流派配方)
- [需触发关键词的流派（中置信度）](#需触发关键词的流派中置信度)
- [中文 / 国风配方](#中文--国风配方)
- [EDM Build & Drop 技巧](#edm-build--drop-技巧)
- [负面提示详解](#负面提示详解)
- [Style Prompt 常见错误](#style-prompt-常见错误)

---

## 流派置信度总览

- **高置信度（开箱即用）**：Pop, Synth-Pop/80s, Lo-fi Hip-Hop, Deep House, Indie Folk, Neo-Soul, Trap, Boom Bap, Cinematic, Indie/Alt Rock, City Pop, Country, Jazz, Pop Punk。
- **中置信度（必须写触发关键词）**：Drill, Dubstep, Liquid DnB, Trance, Reggaeton, Afrobeats, Shoegaze/Post-Punk, Heavy/Death Metal, Hyperpop。
- **低置信度（多次迭代或考虑其他工具）**：含微音程/非西方调性的传统地域音乐、Avant-Garde/实验、戏腔。

---

## 通用五层公式

```
[流派+子流派], [情绪/能量], [BPM 数字], [人声方向], [标志乐器], [制作风格/年代]
```

---

## 高置信度流派配方

### 流行 (Pop)
**Style**: `pop, bright and catchy, 120 BPM, polished female vocals, bright synths, punchy drums, radio-ready production`
```
[Intro]
[Verse 1, soft, acoustic guitar]
[Pre-Chorus, building]
[Anthemic Chorus]
[Verse 2, fuller, add drums]
[Pre-Chorus, building]
[Anthemic Chorus]
[Bridge: falsetto, piano only]
[Instrumental Break: synth lead]
[Explosive Final Chorus]
[Outro]
[End]
```

### Synth-Pop / 80s（极高）
**Style**: `synth-pop, 80s-inspired, euphoric and nostalgic, 118 BPM, polished female vocals, analog synth pads, gated reverb drums, Moog bass`

### Lo-fi Hip-Hop（极高）
**Style**: `lo-fi hip-hop, chill and nostalgic, 75 BPM, boom-bap drums, vinyl crackle, detuned jazz piano, Rhodes, tape saturation`（纯器乐可加 `instrumental`）

### Deep House（高）
**Style**: `deep house, groovy and hypnotic, 122 BPM, filtered vocal chops, warm bass synth, crisp hi-hats, shuffled beat, Rhodes stabs, minimal`

### 抒情民谣 / Indie Folk（高）
**Style**: `indie folk, warm and intimate, 92 BPM, soft breathy male vocals, fingerpicked acoustic guitar, upright bass, brushed snare, harmonica, singer-songwriter`
```
[Intro: acoustic guitar]
[Whispered Verse]
[Verse 2, breathy]
[Chorus, soulful, harmonies]
[Verse 3, fuller]
[Chorus, soulful, harmonies]
[Bridge: soft, piano only]
[Final Chorus, powerful]
[Outro: fade out]
[End]
```

### Neo-Soul / R&B（高）
**Style**: `neo-soul, smooth and intimate, 78 BPM, silky female vocals with runs, Rhodes electric piano, warm sub bass, brushed drums, layered harmonies`

### Trap（高）
**Style**: `trap, dark and aggressive, 140 BPM, melodic rap delivery, heavy 808 sub-bass, hi-hat rolls, atmospheric pads`
```
[Intro: 808s, dark]
[Verse 1, rap]
[Chorus, autotuned, harmonies]
[Verse 2, rap, aggressive]
[Chorus, autotuned, harmonies]
[Bridge, soft, melodic]
[Instrumental Break: 808 rolls, atmospheric pads]
[Verse 3, rap, high energy]
[Final Chorus]
[Outro]
[End]
```

### Drill（中置信度，Trap 子流派）
**Style**: `drill, UK drill, dark and menacing, 142 BPM, aggressive male rap, sliding 808 bass, skittering hi-hat rolls, ominous minor piano loop, gritty street production, no melodic singing`
```
[Intro: dark piano loop, 808 slides, ominous]
[Verse 1, rap, aggressive]
[Hook, braggadocious, gang vocals]
[Verse 2, rap, high energy]
[Hook, braggadocious, gang vocals]
[Instrumental Break: 808 slides, skittering hi-hats]
[Verse 3, rap, relentless]
[Final Hook, explosive, gang vocals]
[Outro: 808 slides, fade out]
[End]
```
> **与 Trap 的差异点**（drill 是 trap 子流派，但别只写 `trap`——会偏 Atlanta trap，必须 `drill, UK drill` 才能锚住节奏惯例）：① 用**滑音 808**（`sliding 808 bass`）而非持续低频；② **半拍感节奏**（BPM 约 140-142，范围引导非精确锁定；与 trap 的区别在律动与滑音而非具体 BPM 数字）；③ 暗黑钢琴 loop + 密集 triplet hi-hat；④ 高潮用 `[Hook]` 喊麦、可叠 `gang vocals`，**不柔化**——去掉 Trap 模板里的 `[Bridge, soft, melodic]`，换成保持气压的 `[Instrumental Break]`。
> **中英混 / 中文说唱**：Style 里写 `code-switching English and Mandarin Chinese bars` 显式声明语言（防英文化漂移），配 `--voice male`；句内怎么切语言、咬字押韵交给 lyrics reference。

### Boom Bap（高）
**Style**: `boom bap, 1990s East Coast hip-hop, 90 BPM, confident rap delivery, dusty sampled drums, vinyl crackle, jazz horn stabs`

### 影视配乐 / Cinematic（高）
**Style**: `cinematic orchestral, epic and triumphant, 85 BPM, soaring strings, French horns, choir, thunderous percussion, film score quality`（纯器乐加 `instrumental`）

### 摇滚 / Indie-Alt Rock（高）
**Style**: `alternative rock, raw and emotional, 135 BPM, raspy male vocals, distorted guitar wall, explosive drums, quiet-to-loud dynamic, 90s grunge production`
```
[Intro: distorted guitar, driving]
[Verse 1, raspy]
[Pre-Chorus, building]
[Anthemic Chorus]
[Verse 2, raspy]
[Pre-Chorus, building]
[Anthemic Chorus]
[Bridge: soft, acoustic guitar]
[Guitar Solo]
[Explosive Final Chorus]
[Outro: distorted guitar]
[End]
```

### City Pop（高）
**Style**: `city pop, 1980s Japanese funk, 105 BPM, smooth warm vocals, chorus-effect guitar, slap bass, shimmering synths, yacht rock`

### 乡村 (Country)（高）
**Style**: `country, heartfelt Americana, 100 BPM, warm baritone vocals, acoustic guitar, pedal steel, brushed drums`

### 爵士 (Jazz)（高）
**Style**: `smooth jazz, warm and intimate, 95 BPM, crooning vocals, saxophone, upright bass, brush drums, Rhodes`

### 朋克摇滚 (Pop Punk)（高）
**Style**: `pop punk, youthful and raw, 165 BPM, raspy male vocals, distorted power chords, fast drums, crowd-style gang vocals`

---

## 需触发关键词的流派（中置信度）

不写触发词会退化成通用输出。

| 流派 | 必需触发词 | Style 范式 |
|------|-----------|-----------|
| **Dubstep** | `half-time drums`, `wobble bass` | `dubstep, aggressive, 140 BPM (half-time feel), wobble bass, screeching synths, massive drop` |
| **Liquid DnB** | `breakbeat` / `chopped breakbeats` | `liquid drum and bass, euphoric, 174 BPM, chopped breakbeats, lush pads, rolling sub bass` |
| **Trance** | `building energy`, `arpeggio synths` | `uplifting trance, euphoric, 138 BPM, building energy, arpeggio synths, supersaw leads, breakdown` |
| **Reggaeton** | `dembow beat` | `reggaeton, sensual, 95 BPM, dembow beat, melodic male vocals, latin percussion, synth bass` |
| **Afrobeats** | `log drum, shaker, call-and-response percussion` | `afrobeats, groovy and warm, 105 BPM, log drum, shaker, melodic vocals, syncopated percussion` |
| **Shoegaze** | 用描述词替代风格名 | `dreamy, female vocals buried in reverb, wall of distorted guitar, hazy, 120 BPM` |
| **Heavy/Death Metal** | `[Scream]` 标签 + 多次迭代 | `death metal, brutal, 180 BPM, growled vocals, blast beats, double bass drums, downtuned guitar` |
| **Hyperpop** | 需多次迭代 | `hyperpop, chaotic and euphoric, 160 BPM, pitched-up vocals, distorted 808s, glitchy synths, maximalist` |

---

## 中文 / 国风配方

> 中文歌词的**咬字、多音字、汉字优先、行长**等文本技巧 → 配合 lyrics reference。本节是 Style/编曲侧。

### 华语流行抒情 (Mandopop Ballad)（中-高）
**Style**: `Mandopop ballad, emotional and tender, 72 BPM, male vocals singing in Mandarin Chinese, piano, strings, soft drums, cinematic build`
- 必须显式写 `singing in Mandarin Chinese`，否则可能英文化或中英混唱。
- 防漂移：加 `All lyrics in Mandarin Chinese, no English`。

### 国风 / 古风 (Guofeng)（中）
**Style**: `guofeng, ethereal and poetic, 80 BPM, female vocals singing in Mandarin Chinese, guzheng, erhu, dizi, pentatonic scale, traditional Chinese fusion with modern production`
```
[Intro: guzheng, atmospheric]
[Verse 1: female vocal, gentle]
[Pre-Chorus, building]
[Chorus: ethereal, layered harmonies]
[Verse 2: fuller, layered]
[Chorus: ethereal, layered harmonies]
[Bridge: erhu solo]
[Final Chorus: powerful]
[Outro: dizi, fade out]
[End]
```
- 民乐**具名**（`guzheng, erhu, pipa, dizi`）优于泛 `Chinese traditional instruments`。
- 五声音阶写 `pentatonic scale`。

### 中文说唱 (Mandarin Hip-Hop)（中）
**Style**: `mandarin hip-hop, confident, 90 BPM, male rap delivery in Mandarin Chinese, boom-bap drums, jazzy sample, 808 bass`
- 用汉字写词，控制 flow 密度与押韵 → 配合 lyrics reference。

---

## EDM Build & Drop 技巧

`[Build]` 和 `[Drop]` 是电子音乐核心动态标签，**仅用于电子/舞曲流派**。

- **`[Build]`**：张力递增（riser、鼓 roll、滤波扫频）。歌词保持短促重复或留空。可在 Build 前加 `[Breakdown]` 制造能量落差。
- **`[Drop]`**：全面释放——**仅乐器爆发，无人声旋律**。`[Chorus]` = 有人声 hook 的高潮；`[Drop]` = 纯乐器释放。在非电子流派用 `[Drop]` 会产生意外 dubstep 效果。
- 推荐 Style 关键词：`festival edm, big room, massive kick, driving bass, bright synth lead, uplifting breakdown`。

### 电子/舞曲结构模板
```
[Intro: atmospheric, building]
[Build-Up: riser, filter sweep]
[Drop: instrumental, massive]
[Verse: vocal chops, groove]
[Build-Up: rising tension]
[Drop: instrumental, massive]
[Breakdown: stripped, emotional]
[Build-Up: rising tension]
[Drop: instrumental, final, biggest]
[Outro: fade out]
[End]
```
- Build→Drop 是核心循环，`[Breakdown]` 在二段后做能量落差、再 Build 回最大 Drop。
- `[Drop]` 段不写歌词（纯乐器释放）；人声/vocal chops 放 `[Verse]`。
- 子流派微调：Dubstep 用 half-time drop、Trance 把 `[Breakdown]` 拉长做情绪铺垫、Big Room 强调 massive kick。

---

## 通用结构模板与间奏放置

### 流行歌默认结构
**示范、非填空公式**——展示成品该有的样子（组合标签 + 器乐段 + 能量曲线），但段序、间奏位置按这首歌的情绪/流派现想，别照搬：
```
[Intro: bright synths, building]
[Verse 1, soft, acoustic guitar]
[Pre-Chorus, building]
[Anthemic Chorus]
[Verse 2, fuller, add drums]
[Pre-Chorus, building]
[Anthemic Chorus]
[Instrumental Break: synth lead]
[Bridge: stripped down, piano only, vulnerable vocals]
[Explosive Final Chorus]
[Outro: fade out]
[End]
```
能量：主歌 soft → 副歌 anthemic → 桥段 stripped → 末副歌 explosive，逐级对比，不是一个音量到底。

### 间奏放哪（由职能决定，非固定槽位）
硬约束只有"必须有一个器乐段"；放在哪由它要承担的职能决定：
- **中段喘息 + 器乐亮点（最经典，上面模板用此）**：第二段副歌后，人声唱满两轮再进 Bridge/Final Chorus。
- **把能量从低谷推回高潮**：Bridge 后、Final Chorus 前做推进坡道（特定设计、别默认套，否则间奏永远贴结尾）。
- **段间短连接**：Verse 之间做 turnaround，是过渡非亮点 solo。

先问"这首器乐段要干什么"再决定放哪，别照模板填槽。电子/舞曲结构见上「EDM Build & Drop 技巧」节。

---

## 负面提示详解

负面提示的**通用规则**（`no [X]` 递减序列、2-3 项上限、排除时给替代方案、steering 非 hard ban）见 [arrangement.md「Style Prompt 工程」](arrangement.md#style-prompt-工程) 的「负面排除」条——此处只列流派相关的去泛化手段，不重复通用规则：

- 对抗"流行引力"（输出过于泛化）的去泛化排除：`no four-on-the-floor kick`、`no busy arrangement`、`no over-mastered sound`；可配非标准拍号（`5/4 time`、`7/8 groove`）正向锁定特色。

---

## Style Prompt 常见错误

| 错误 | 问题 | 正确做法 |
|------|------|----------|
| 堆 15+ 个标签 | 注意力退化、互相打架 | 4-9 个精准标签，核心前置 |
| `summer vibes` | 太模糊 | `upbeat, bright synths, beach energy, 110 BPM, female vocals` |
| `fast` / `upbeat` 代替 BPM | 不精确 | 写数字 `128 BPM` |
| `calm aggressive` | 矛盾 | `melancholic but hopeful`（可共存的情绪）|
| 不指定性别 | 随机性别 | 始终明确 `male/female vocals` |
| 单独形容词 | 太模糊 | 流派 + 年代组合 `90s R&B`、`80s synths` |
| 用艺人名 `Drake style` | 触发过滤 | 声学指纹替代（BPM+人声+制作） |
| `Chinese music` | 可能生成中国元素的英文歌 | `singing in Mandarin Chinese` + 具名民乐 |
