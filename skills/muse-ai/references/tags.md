# 标签库与可靠性分级（MuseAI）

歌词字段内用方括号 `[Tag]` 嵌入的标签，控制该段落的乐器编排、情绪、人声、音效。这些标签与 Style 字段互补——Style 影响全曲，段落标签控制局部。**核心认知：标签可靠性差异很大**，本文用 Tier 1-4 标注哪些稳定、哪些是 placebo。

## 目录

- [字段归属提醒](#字段归属提醒)
- [人声标签可靠性分级](#人声标签可靠性分级)
- [乐器标签](#乐器标签)
- [情绪与能量标签](#情绪与能量标签)
- [节奏控制标签](#节奏控制标签)
- [收尾控制标签](#收尾控制标签)
- [音效标签](#音效标签)
- [音质与制作质感标签](#音质与制作质感标签)
- [人声/混音效果应放 Style 字段](#人声混音效果应放-style-字段)
- [需废弃的迷思清单](#需废弃的迷思清单)

---

## 字段归属提醒

- **结构/人声/乐器标签** → 放 Lyrics 字段（方括号，独占一行）。
- **全曲风格、人声音色、混音效果** → 放 Style 字段（逗号分隔的描述词）。
- **任何"标签:数值%"格式** → 无效，见文末迷思清单。

---

## 人声标签可靠性分级

控制演唱方式的方括号标签，按单独使用时的成功率分级。Tier 2 及以下需在 Style 字段写对应描述词"双重强化"才稳。

### Tier 1（>80%，可单独放歌词行）

`[Whispered]`、`[Spoken Word]` / `[Spoken]`、`[Rap]` / `[Rap Verse]`、`[Belting]`、`[Male Vocal]`、`[Female Vocal]`

> 对唱逐行标说话者时用简写 `[Male]` / `[Female]` / `[Both]`（`[Both]` = 共唱），与 `[Male Vocal]`/`[Female Vocal]` 同属 Tier 1 高可靠。

### Tier 2（50-80%，需 Style 字段同时铺垫）

`[Falsetto]`（须 Style 也写 `natural falsetto, airy high register`）、`[Harmonies]`、`[Choir]`、`[Duet]`、`[Call and Response]`、`[Scream]`、`[Growl]`、`[Operatic]`、合并标签如 `[Whispered Verse]`

### Tier 3（30-50%，概率命中）

`[Soprano]` / `[Alto]` / `[Tenor]` / `[Baritone]` 声部、`[Vocoder]` / `[AutoTune]`（歌词内，需 Style 配合）、`[Breathy]`、`[Raspy]`、`[Soulful]`、`[Crooning]`

### Tier 4（无效 placebo，不要用）

任何**带冒号+百分比/参数**的格式：`[Reverb: 30%]`、`[Bass: 80%]`、`[AutoTune: 60%]`、`[Stereo Width: Wide]`、`[Compression: Medium]`。MuseAI 不解析参数语法，只响应描述性词语。

### 音域 / 合唱组合词（放 Style 字段，不是歌词标签）

设定整曲人声底色时，把音域与组合词写进 Style 比在歌词写 Tier 3 声部标签更可靠：

- **音域**：女声 `soprano` / `mezzo-soprano` / `alto`，男声 `tenor` / `baritone` / `basso`。
- **质地**（与音域叠用）：`raspy` / `breathy` / `silky` / `operatic`，如 `raspy male baritone`、`silky mezzo-soprano`。
- **合唱组合**：`SATB choir`（混声四部）/ `antiphonal`（呼应式）/ `barbershop`（理发店四重唱）/ `androgynous`（中性嗓）——比单写"男声/女声"精细。

歌词内 `[Soprano]` / `[Baritone]` 仍是 Tier 3 概率命中；要锁定整曲音色底色，优先用 Style 字段的上述词。

> **合并写法更经济**：`[Anthemic Chorus]`、`[Whispered Verse]`、`[Spoken Word Bridge]` 比拆成两个标签更省配额、语义更清晰，仍算 1 个标签。**但合并不提升可靠性**——Tier 继承被并入的人声词（`[Falsetto Chorus]` 仍是 Tier 2，须 Style 双写）。

---

## 乐器标签

放在段落标记后，指示该段主要乐器。**具体名 > 泛称**（`fingerpicked acoustic guitar` > `guitar`）。

### 键盘类
`[Piano]`, `[Electric Piano]`, `[Rhodes]`, `[Wurlitzer]`, `[Organ]`, `[Hammond Organ]`, `[Synth]`, `[Analog Synth]`, `[Moog Synth]`, `[Synth Pad]`, `[Harpsichord]`, `[Clavinet]`

### 弦乐类
`[Acoustic Guitar]`, `[Electric Guitar]`, `[Distorted Guitar]`, `[Guitar Solo]`, `[Bass Guitar]`, `[Slap Bass]`, `[Upright Bass]`, `[Violin]`, `[Strings]`, `[String Quartet]`, `[Cello]`, `[Harp]`, `[Ukulele]`, `[Banjo]`, `[Mandolin]`, `[Sitar]`

### 打击类
`[Drums]`, `[Acoustic Drums]`, `[Electronic Drums]`, `[808s]`, `[808 Bass]`, `[Drum Machine]`, `[TR-909]`, `[Breakbeat]`, `[Brush Drums]`, `[Percussion]`, `[Taiko Drums]`, `[Congas]`, `[Bongos]`, `[Tambourine]`, `[Handclaps]`

### 管乐与铜管
`[Saxophone]`, `[Tenor Sax]`, `[Alto Sax]`, `[Trumpet]`, `[Trombone]`, `[French Horn]`, `[Brass Section]`, `[Flute]`, `[Clarinet]`, `[Harmonica]`, `[Accordion]`

### 电子与合成器
`[Synth Bass]`, `[Arpeggiated Synth]`, `[Lead Synth]`, `[Synth Stabs]`, `[Pad]`, `[Pluck Synth]`, `[Acid Bass]`, `[Supersaw]`, `[Wobbly Bass]`, `[Glitch]`

### 管弦与影视
`[Orchestra]`, `[Full Orchestra]`, `[Chamber Orchestra]`, `[Orchestral Strings]`, `[Brass Stabs]`, `[Timpani]`, `[Choir Vocals]`, `[Cinematic Percussion]`

### 中国传统乐器（具名优于泛称）
`[Guzheng]`（古筝）, `[Erhu]`（二胡）, `[Pipa]`（琵琶）, `[Dizi]`（笛子）, `[Guqin]`（古琴）, `[Suona]`（唢呐）, `[Yangqin]`（扬琴）。配合 Style 写 `Pentatonic Scale`、`Chinese folk` 更准。

---

## 情绪与能量标签

### 情绪
`[Uplifting]`, `[Melancholic]`, `[Haunting]`, `[Dark]`, `[Joyful]`, `[Nostalgic]`, `[Somber]`, `[Romantic]`, `[Intense]`, `[Dreamy]`, `[Peaceful]`, `[Anxious]`, `[Euphoric]`, `[Mysterious]`, `[Aggressive]`, `[Playful]`, `[Epic]`, `[Intimate]`, `[Bittersweet]`, `[Triumphant]`

### 能量级别
`[High Energy]`, `[Medium Energy]`, `[Low Energy]`, `[Chill]`, `[Driving]`, `[Explosive]`, `[Building]`, `[Relaxed]`, `[Frantic]`, `[Steady]`

> 情绪词 2-3 个为宜，超过会互相打架。抽象词（`beautiful`/`amazing`）无法转化为音乐决策，换成声学属性。

---

## 节奏控制标签

| 标签 | 有效性 | 说明 |
|------|--------|------|
| `[Double Time]` | ✅ 有效 | 双倍速鼓点感 |
| `[Half Time]` | ✅ 有效 | 半拍，hip-hop/trap；写 `[Chorus, Half Time]` |
| `[Play faster]` | ❌ 无效 | 改用 `[Double Time]` |
| `[120 BPM]`（放歌词字段） | ❌ 无效 | BPM 写数字放 Style 字段 |

---

## 收尾控制标签

解决"突然截断 / 无意义循环尾巴"。约 90% 截断问题根因是缺 `[Outro]` + `[End]`。

| 标签 | 用途 |
|------|------|
| `[Final Chorus]` | 最后一次副歌，要求更高能量/编配而非单纯重复 |
| `[Outro]` | 尾声收束，与 `[Fade Out]` 联用更佳 |
| `[Fade Out]` / `[Fade In]` | 渐弱 / 渐入 |
| `[Cold Stop]` | 峰值瞬切静音 |
| `[Abrupt Cut]` / `[Sudden Stop]` | 硬切，适合 punk/grindcore |
| `[End]` | 硬终止信号，**放歌词绝对最后一行，下方不留任何内容（含空格）** |

**标准收尾模板**：`[Final Chorus]` → `[Outro]` → `[End]`

---

## 音效标签

适合 Intro/Outro/Interlude 等非人声段落。

### 环境音
`[Birds Chirping]`, `[Rain]`, `[Thunder]`, `[Wind]`, `[Ocean Waves]`, `[City Ambience]`, `[Forest]`, `[Fire Crackling]`

### 人声音效
`[Applause]`, `[Cheering]`, `[Clapping]`, `[Chuckles]`, `[Giggles]`, `[Sighs]`, `[Whispers]`, `[Whistling]`, `[Screams]`

### 机械与电子音效
`[Phone Ringing]`, `[Beeping]`, `[Bell Dings]`, `[Static]`, `[Record Scratch]`

---

## 音质与制作质感标签

`[Lo-fi]`, `[Gritty]`, `[Clean]`, `[Raw]`, `[Lush]`, `[Sparse]`, `[Tape-Saturated]`, `[Vinyl Hiss]`, `[Atmospheric]`, `[Punchy]`, `[Warm]`, `[Bright]`, `[Polished]`

---

## 人声/混音效果应放 Style 字段

效果不要在歌词里加参数标签，应在 Style 字段用描述词。对照：

| 效果 | Style 字段（有效） | 歌词字段 |
|------|------|------|
| Autotune | `autotuned vocals, T-Pain style` | `[AutoTune: 60%]` ❌ placebo |
| Vocoder | `robotic vocal, vocoder-like` | `[Vocoder]`（Tier 3） |
| Reverb | `reverb-drenched, cathedral reverb` | `[Reverb: 30%]` ❌ placebo |
| 干声 | `dry vocals, close-mic` | — |
| 去 autotune | `no autotune`（放 Style 末尾，有效） | — |
| Megaphone | `megaphone effect, lo-fi distorted vocal` | `[Megaphone]` 证据不足 |

---

## 使用说明

- 可与结构标记组合：`[Bridge, piano, melancholic]` 或 `[Bridge: piano only, melancholic]`（推荐冒号/逗号，避免管道符）。
- 建议每段 2-4 个标签，过多稀释。
- 音效标签适合 Intro/Outro/Interlude 等非人声段落。
- 乐器标签在 `[Instrumental]` 和 `[Solo]` 段落效果最佳；`[Guitar Solo]` 这类具名独奏 > 泛 `[Solo]`。

---

## 需废弃的迷思清单

| 迷思 | 真相 |
|------|------|
| **管道符 `\|` 是标准 meta tag 堆叠语法** | 无官方说明、社区报告结果不稳定、不推荐。改用合并标签 / 逗号 / 冒号参数化语法 |
| **花括号 `{ }` 有"强调/重复/伴唱"功能** | ~50% 模糊合规率，单一/同源来源，官方与多数指南只认方括号。和声用 `[Harmonies]` / `[Backing Vocals]` + Style 描述 |
| **`[Reverb: 30%]` 等参数/百分比标签有效** | Tier 4 placebo，MuseAI 不解析参数语法。用描述词 `reverb-drenched` |
| **Style 上限 200 字符 / "15-30 词为佳"** | 旧规格。现为 1000 字符；最优 4-9 个精准标签（部分来源仍称约 200，争议见 [arrangement.md](arrangement.md#字段与字符上限速查)） |
| **Lyrics 上限固定 3000 / 5000 字符** | 均为社区参考值、非官方硬阈值；CLI 只校验非空、不按字数截断，以实际返回为准 |
| **`[Key Change]` 标签触发转调** | 失败标签。转调在 Style 描述（`in G minor`）或自然发生在 Bridge |
| **第 1 标签 2× 权重、第 6 位降至 15%** | 伪精确数字。位置效应方向真实，量化无据 |
| **BPM 被"精确锁定"** | 近似引导，可能输出非整数/微观波动 |
| **首次生成上限 4 分钟** | 旧规格，现 up to 8 分钟 |
| **`[Explicit]` 标签解锁成人内容** | 内容过滤依然有效，该标签基本无效 |
| **真正对位双声部可实现** | 架构边界，会崩塌为单声部。用交替/呼应/lead+adlib 近似 |
| **`[Beat Switch]` / `[Accelerando]` / `[Big Finish]` 确认有效** | 单一来源，【存疑】实验性，勿在生产流程依赖 |
| **`////*****////` 分隔符防标签被唱** | 无可验证来源，迷思。正解：标签独占一行 |
| **`[Instrumental]` 须放歌词最末位才生效** | 各源矛盾、不可靠的位置规则。靠 `--mode instrumental` + `no vocals` 双保险，位置不强求 |
