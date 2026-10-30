# 编曲与风格工程（MuseAI）

负责歌曲的"声音"面：结构编排、风格定义、人声设计、乐器配置和迭代调优。歌词文本、和声词和中文咬字见 `references/lyrics.md`。

> **标注约定**：【实验性】= 社区验证、官方未文档化；【迷思】= 已证伪（见文末）。prompt 层规律多属社区经验，存争议处以实际生成返回为准。

## 起手式：标准动作（先读）

各流派现成 `--style` 配方、全部标签可靠性分级在两个 reference 里，主文档只给决策框架。**最常见质量损失点：凭通用乐理即兴拼 style/标签而不去翻配方**——现成配方按 MuseAI 实际行为校准，比即兴拼稳。流程：

1. **用户报出任何具体流派/子流派（drill、city pop、trap…）→ 第一步翻 `references/genres.md`**，取 `--style` 配方和结构模板作起点；无精确匹配就用最近的父/邻流派微调。
2. **要给某段选具名乐器、人声标签、音效或收尾方式 → 翻 `references/tags.md`**，查可靠性 Tier 与确切写法。
3. 写词和咬字见 `references/lyrics.md`；实际生成和取音频见 `references/runtime.md`。

各章节末的 references 指针标了翻阅时机，是工作流一步、非可选延伸。

### 成品自检：交付任何 style/结构前逐条核对（最高优先）

不加约束时 agent 几乎总产出"偷懒编曲"——全裸标签、从头唱到尾、无动态。三条**硬要求，不满足即未完成**：

1. **段落标签默认带修饰，禁交全裸标签。** `[Verse]`/`[Chorus]` 只是搭骨架的占位；成品里**每个有人声的段落都用合并/逗号/冒号语法**附人声/情绪/乐器，如 `[Anthemic Chorus]`、`[Verse 1, soft, acoustic guitar]`、`[Bridge: piano only, vulnerable vocals]`。通篇裸标签 = 未完成。
2. **至少一个器乐段。** 常规歌不会人声从头铺到尾——放一个器乐段（结构段 `[Instrumental Break]` 或具名独奏 `[Guitar Solo]`），内容不止单件 solo（满编/riff/氛围/breakdown 皆可）。**放哪是编曲决策非固定槽位**，随设计意图变、别每首钉同一处（位置选法见「结构模板」）。说唱/电子同样要。**唯一例外**：用户明确要一气呵成短 demo 可省并说明。
3. **能量有起伏且贴合流派。** 别每段同音量平铺。通用曲线：主歌收→导歌推→副歌放→桥段对比→末副歌最炸，用 `soft/intimate`↔`anthemic/explosive` 把曲线写进标签。流派曲线不同（民谣靠 dynamics、EDM 靠 build/drop、drill 全程保持气压）——**选结构前翻 genre-recipes**。**同名重复段（尤其 Verse 1 vs Verse 2）必须逐段差异化/加层**（`[Verse 2, fuller, add drums]`），Verse 1≈Verse 2 是"原地打转"头号成因。

## 字段架构与职能分工（最底层规则）

风格与人声控制分散在两个字段，职能不可互换；最常见错误是把结构标签塞进风格描述。映射 `muse song generate`：**Style 字段 ≈ `--style`（逗号分隔风格标签）；Lyrics 字段 ≈ `--description`（custom 模式 = 完整歌词，别名 `--lyrics`）**。

|控制层|放置位置|作用|优先级|
|--------|----------|------|--------|
|全曲风格/音色底色|**Style 字段**|流派、人声基调、制作质感|最高|
|分段结构/局部覆盖|**Lyrics 字段** `[方括号]`|特定段落覆盖默认风格|段落级|
|行级演唱/和声|**Lyrics 字段** `(圆括号)`|行级演唱、ad-lib、背景和声|行级|
|文本节奏微调|**Lyrics 字段**大小写/标点|换气、强调、音节延长|字符级|

- **结构标签只放 Lyrics 字段**，绝不混入 Style；**Style 字段只用逗号分隔标签**，不写方括号。
- 标签是"倾向引导"非强制——结果受歌词形状、Style、随机性共同影响。完整歌词+标记显著提升重现性，非 100% 保证。

## 字段与字符上限速查

- **Style（`--style`）** 1000 字符（超出静默截断、无警告）；**Lyrics（`--description`）** 约 5000（社区量级，CLI 只校验非空、不硬截断，详见 lyrics reference）；**Title（`--title`）** 100 字符（仅展示）；**首次生成时长** 8 分钟。
- **争议**：部分来源称 Style 实际约 200 字符即静默截断。**保守做法**：核心风格词放前 200 字符内，超出当"减弱权重的补充"。字符多 ≠ 效果好。

## 歌曲结构标记

方括号包裹，**单独占一行**，放段落歌词之前。大小写无关（`[VERSE]` = `[Verse]`）。

### 核心段落（高可靠）

|标记|用途|备注|
|------|------|------|
|`[Intro]`|开场，常无/稀疏人声||
|`[Verse]` / `[Verse 1]` / `[Verse 2]`|主歌叙事|编号变体提示不同旋律|
|`[Pre-Chorus]`|导歌，构建张力|缺它会让主歌到副歌过渡生硬|
|`[Chorus]`|副歌主钩子，最高能量|最核心|
|`[Post-Chorus]`|后副歌延伸|维持能量余韵|
|`[Bridge]`|桥段，对比/转折|适合情感转折|
|`[Outro]`|尾声收束|与 `[Fade Out]` 联用更佳|
|`[End]`|硬终止信号|**放歌词绝对最后一行，下方不留任何内容**|

### 动态/过渡段（仅在明确动态转折点用）

`[Build]`/`[Build-Up]`（张力递增）、`[Drop]`（冲击释放）、`[Breakdown]`（缩减编配）、`[Climax]`（最高强度）。
- `[Drop]` = **纯乐器**能量释放（无人声旋律）；`[Chorus]` = 有人声 hook 的高潮。
- `[Drop]` **仅用于电子/舞曲**（民谣/摇滚中会产生意外 dubstep 效果），非电子流派能量高潮用 `[Chorus]` + 有力人声。

### 乐器/独奏段

两类标签：**结构段落**——`[Instrumental]`/`[Instrumental Break]`（抑制人声最可靠）/`[Interlude]`（连接段）/`[Breakdown]`（缩编）；**具名独奏**——`[Guitar Solo]`/`[Saxophone Solo]` 等 `[乐器名 Solo]` 模式（**具名 > 泛 `[Solo]`**，须 `--style` 已铺垫该乐器才稳）。

器乐段内容开放、不止"某件乐器 solo"——满编/riff/氛围/breakdown 皆可，用冒号写清（`[Instrumental Break: full band, driving]`）。纯乐器段不写歌词（否则随机人声）。**它要承担能量职能**：作留白为副歌蓄力（`stripped down, building`），或作器乐亮点把具名乐器推前景（`[Guitar Solo: soaring]`）。连接过渡用 `[Interlude]`、独立器乐亮点用 `[Instrumental Break]`/具名 solo，别当同义词混用。

### 收尾控制（解决突然截断/无意义循环尾巴）

- `[Fade Out]`/`[Fade In]`；`[Cold Stop]`（峰值瞬切静音）、`[Abrupt Cut]`/`[Sudden Stop]`（硬切，punk/grindcore）、`[Final Chorus]`（最后一次副歌，要求更高能量而非单纯重复）。
- **防拖尾标准模板**：`[Final Chorus]` → `[Outro]` → `[End]`。约 90% 截断问题根因是缺 `[Outro]`+`[End]`。
- **末副歌要"更大"三种收法**（别只换 `explosive` 形容词）：① 分层抬升 `[Explosive Final Chorus, layered vocals, full band]`；② 呼应应答（主唱句 + `(背景应答)` + `[Harmonies]`）；③ 渐弱 `[Outro: fade out]`。炸感来自前后落差——前段先 strip 再炸。

### 节奏控制

- **有效**：`[Double Time]`（双倍速鼓点）、`[Half Time]`（半拍，hip-hop/trap），写 `[Chorus, Half Time]`。
- **无效**：`[Play faster]`（改用 `[Double Time]`）、BPM 放歌词字段（BPM 放 Style 写数字）。

**拿不准某结构/动态/收尾标签可不可靠或怎么写 → 查 [tags.md](tags.md) 完整分级，别凭印象。**

## 人声标记与可靠性分级

人声标记放段落开头，影响该段演唱。**关键：不同标记可靠性差异很大**，照搬"看起来合理"的标签常失败：

- **Tier 1（>80%，可单用）**：`[Whispered]`、`[Spoken Word]`、`[Rap]`、`[Belting]`、`[Male Vocal]`/`[Female Vocal]`
- **Tier 2（50-80%，需 Style 同时铺垫）**：`[Falsetto]`（Style 也写 `falsetto`）、`[Harmonies]`、`[Choir]`、`[Duet]`、`[Call and Response]`、`[Scream]`
- **Tier 3（30-50%，概率命中）**：`[Soprano]`/`[Alto]`/`[Tenor]`/`[Baritone]` 声部、`[Vocoder]`/`[AutoTune]`（需 Style 配合）
- **Tier 4（无效 placebo）**：任何**带冒号+百分比/参数**格式，如 `[Reverb: 30%]`、`[AutoTune: 60%]`。MuseAI 不解析参数，只响应描述性词语。

**人声/混音效果放 Style 字段用描述词**（`reverb-drenched`、`autotuned vocals, T-Pain style`、`dry close-mic vocals`），而非歌词里加效果标签。

**给某段选具名乐器/人声标签/音效前 → 查 [tags.md](tags.md) 确认 Tier 与写法，冷门乐器和效果标签尤其要查（凭印象写的常落在 Tier 3-4 失效区）。**

## Meta Tag 组合语法

控制单段"结构+人声+乐器+效果"有几种写法，按推荐度。**默认每段都该加修饰**——裸 `[Verse]`/`[Chorus]` 只是草稿占位，交付前用 ①②③ 之一补全：

**① 合并标签（最经济，默认首选）** — 演唱方式并入段落名，仍算 1 个标签：`[Anthemic Chorus]`、`[Whispered Verse]`、`[Explosive Final Chorus]`。
> **合并不凭空提升可靠性**——Tier 继承被并入的人声标签：whispered/spoken/belting 是 Tier 1 故稳；并入 Tier 2 词（`[Falsetto Chorus]`、`[Operatic Bridge]`）**仍须 Style 铺垫** `falsetto`/`operatic`，否则命中率掉一半。

**② 逗号组合（直观可靠）**：`[Chorus, Half Time]`、`[Verse, soft, intimate]`、`[Bridge, piano only]`。

**③ 冒号参数化（社区主推，【实验性】）** — 冒号后加描述性修饰词，做段落级局部控制而不改全局 Style：`[Verse: whispered vocals, acoustic guitar only]`、`[Chorus: full band, powerful vocals, energy lift]`。社区验证最广，官方未文档化，可用不保证 100% 稳定。

**④ 管道符 `|`（旧写法、稳定性低）**：`[Chorus | Powerful | bass drop]`。无官方说明、**不作首选**，仅兼容旧歌词。

每段 **2-4 个**组合元素（软性、非硬上限），优先级 段落 > 人声/情绪 > 乐器 > 效果；过载时靠后元素**被弱化**。冒号/逗号里每个逗号分隔的修饰词各计 1 个——`[Chorus: full band, powerful vocals, energy lift]` 是 4 个，非"冒号后随便堆"。

**圆括号 `( )`** 触发行级和声/ad-lib，**概率性、不保证**（约七成）。独占一行的 1-3 词倾向当演唱方向、不唱出（`(softly)`）；行内完整短句被唱作 ad-lib；绝对不想被唱的用独占行方括号或 `[Instrumental Break]`。**写什么词 → lyrics reference**。

> 花括号 `{ }` 伴唱指令是**迷思**（~50% 模糊合规、单源，已证伪）。和声改用 `[Harmonies]`/`[Backing Vocals]` + Style 描述词。

## 人声编排（男女声 / 对唱 / 合唱）

**核心机制：逐行标注说话者**——只在段顶标一次会导致声部漂移。

### 男女声切换 / 对唱

```
[Verse 1]
[Female] 独自走在深夜的街头
[Male] 霓虹灯映着我的影子
[Both] 而我们终将在副歌相遇
```
- **逐行标说话者**用 `[Male]`/`[Female]`/`[Both]`（即 Tier 1 `[Male Vocal]`/`[Female Vocal]` 的对唱简写、同属高可靠），不只段顶标一次；单段 **8-12 行以内**，过长会声部崩塌或性别随机互换；从 A/B 交替起步，再用 `[Both]` 共唱。
- **MuseAI 不支持真正对位双声部**（两条独立旋律会崩塌成单声部）。三种近似：**交替轮唱**（整行轮流）、**call-and-response**（一问一答）、**lead + ad-libs**（主唱整行 + 短促配唱，最稳）。

**lead + ad-libs 骨架**——主唱整行，行内用圆括号写 1-3 词回声/ad-lib（直接写要唱的词，别写 `echo`/`adlib` 标签词否则会被唱出）：
```
[Male] 我们说好不回头 (不回头)
[Male] 可路灯把影子拉得好长 (oh yeah)
```

### 合唱与呼应

- `[Choir]`（Tier 2，需 Style 铺垫）— 多人合唱，宜副歌高潮/尾声营造宏大感。
- **音域/合唱组合词放 Style 字段**比仅写 Tier 3 声部标签更锁人声底色：`soprano`/`alto`/`tenor`/`baritone`、`SATB choir`/`antiphonal`/`barbershop`。
- `[Call and Response]` — 一问一答，宜 gospel/soul/民谣。**逐行交替问/应、每行标说话者**（如 `[Female] 你还会回来吗` → `[Male] 等风停了就回`），别只当段顶标签；无需再写 `(回应)`（会被唱出）。Style 可加 `antiphonal vocals`。

### 段内声音变化

Bridge 收 → Chorus 放是最经典手法，对比越强冲击越大（`[Verse 1, soft, intimate]` → `[Anthemic Chorus]`）。

**对唱/合唱歌词文本怎么写好 → 配合 lyrics reference。声部崩塌时缩短段落行数后多生成几次选优。**

## Style Prompt 工程

`--style` 接受逗号分隔自由文本标签，决定全曲走向，最高优先级。

### 推荐排序公式

```
[流派+子流派], [情绪/能量], [BPM], [人声风格], [关键乐器], [制作风格/年代], [负面排除]
```
示例：`synth-pop, 80s-inspired, euphoric and nostalgic, 118 BPM, polished female vocals, analog synth pads, gated reverb drums, no autotune`

### 核心原则

- **流派放位置 1**：模型首读、定走向；子流派 > 父类（`80s-inspired dream pop` > `pop`）。
- **BPM 写数字**（`118 BPM` 非 `fast`），是范围引导非锁定，用区间思维（trap 138-142）别执着单点。
- **乐器具体**：`fingerpicked acoustic guitar` > `guitar`；列 2-3 种、超 3-4 种会乱；冷僻乐器具名（`guzheng`/`erhu`）。
- **明确人声性别**：不指定 → 随机（泛化首因）。CLI 用 `--voice male|female|random`；Style 叠加 `[性别]+[音色]+[唱法]+[处理]`（`raspy male baritone, intimate close-mic`）。
- **流派融合最多 2-3 种**、主流派前置；**年代锚定**（`1980s`/`90s grunge`）比形容词更锁制作惯例。
- **精简优于堆砌**：最优 **4-9 个**精准标签（软性非硬上限）。
- **全局能量弧线写进 Style**（`builds from quiet solitude to surging hope`）：段标签做局部、Style 弧线做全局，否则被流行引力拉回平均能量。实验融合可用非标准拍号（`5/4 time`）对抗 4/4 漂移。

### 其它要点

- **关键词权重**：靠前权重高方向真实，但"第 1 标签 2× 权重"等伪精确、已证伪，把最重要的词前置即可。
- **自然语言**：散文式 Style 也生效，但逗号标签最可控；标签为主、必要时一句散文补氛围。
- **负面排除**：内联进 `--style`（无独立排除字段）。可靠性递减 `no [X]` > `without [X]` > `exclude [X]` > `avoid [X]`；用具体名、别写口语整句（`no drums` 优于 `I don't want drums`，`avoid rock-like` 无效）。最多 2-3 个、同时给替代（`no electric guitar` + `acoustic guitar carries rhythm`）、放正面描述后。steering 非 hard ban，失败 3 次改更明确替代或多生成选优。
- **跑调常是流派美学冲突非缺陷**：indie/folk/lo-fi/punk 自带"真实感微偏音"；确需音准加 `pitch perfect, in tune vocals`、别盲目重刷。
- **人声被乐器盖住**：`--style` 加 `vocal-forward` + `spacious mix`、人声描述前移。
- **艺人名（政策）**：官方禁用艺人/乐队名（版权，触发 "Impersonation"/过滤）。替代用声学指纹（`atmospheric trap, moody R&B, melodic male vocals, 808 bass, 78 BPM` 代 `Drake style`）；时代/风格参照（`80s new wave`）安全。

**用户报出任何具体流派/子流派 → 写 `--style` 第一步翻 [genres.md](genres.md)** 取现成配方，无精确匹配用最近邻流派微调。即兴拼往往不如校准配方稳。

## 迭代 / 重生成

MuseAI 每次生成是**整曲、无状态**——改某段只能调该段标签后整曲重生成，段标签只是倾向引导。心法：

- **单次生成概率性**：同 `--style`/歌词不同次差异可能很大。「产 3-5 版选优」是**默认动作**非失败补救。音准/咬字/声部崩塌无内置校正，只能跨次重生成挑最好。
- **弱底稿不靠迭代救活**：第一版整体差（流派没锚、结构散）就先改 prompt/结构再生成，别在弱底稿上反复刷。
- **每次只改一个变量**，否则变好/变坏无法归因。
- **换风格/整体重做 → 重申完整 Style 锚点**：`--style` 把目标流派+BPM+人声+关键乐器写全，别只改一项依赖上一版"记忆"（无状态会漂移）；"重贴同一 tag 即可防漂移"未经验证，靠书面写全维度而非寄望模型记住上一版。
- **换某段编曲 → 最小改动、锁定其余**：只调该段标签修饰词（`[Verse 2]` → `[Verse 2: add drums and bass, building]`），其余不动，多版本选优，别因一段推翻整首。
- **让某段更炸 → 调段间落差非单段堆音量**：要更炸的段，前面先 strip/breakdown 留白；调的是段间对比。

## 关键避坑规则（快速自查）

必须含 `[Outro]`/`[End]`（`[End]` 在最后一行、下方空）否则截断/循环尾；副歌每次写全歌词（别 "repeat chorus"/"同上"）；`[Pre-Chorus]` 必须标否则过渡段错拍；`[Drop]` 仅电子/舞曲（区别见动态/过渡段）；纯乐器段（`[Instrumental]`/`[Solo]`/`[Drop]`）不写歌词否则随机人声；禁艺人名（用声学指纹）；禁参数百分比标签（`[Reverb: 30%]` placebo，效果放 Style）；别矛盾堆叠（`lo-fi + studio quality`、`minimal + orchestral` 会成"泥浆"）；标签 4-9 个、别超 9-10；过度演绎就简化 prompt、别堆标签。三大"偷懒编曲"（裸标签/无器乐段/平铺能量）见「成品自检」。

## 歌曲结构模板

硬约束只有"必须有一个器乐段"（见成品自检）；段序、间奏位置按这首歌的情绪/流派现想，别套固定槽位。**搭结构前 → 翻 [genres.md](genres.md)**：那里有流行默认结构模板、电子 Build→Drop 循环、间奏放置三法（中段喘息／低谷推高潮／段间连接），及各流派惯用结构——套现成模板比从头排稳。

## 纯器乐创作

tag-only：用标记搭骨架、不写歌词文本。
- **触发**：`muse song generate --mode instrumental`（`--description` 填自然语言场景/氛围），或 custom 模式歌词字段仅填 `[Instrumental]` 系列标签。**校验细节 → CLI reference。**
- **双保险**：`--mode instrumental` + `--style` 写 `instrumental, no vocals` + 歌词字段仅放结构标签。网传「`[Instrumental]` 须放末位」各源矛盾，靠双保险即可、位置不强求。每段用合并/逗号语法指定乐器和情绪（`[Intro: piano, lo-fi, warm]`）。
- **无人声主信息线，Style 不分配人声预算**——字符全投向 2-3 件核心乐器+音色、编曲动态、情绪/年代。范例：`cinematic post-rock, building intensity, fingerpicked clean guitar, swelling strings, melancholic to triumphant, no vocals`。
- **也要能量起伏**：intro 稀疏 → 主段铺满 → 对比段 stripped → 高潮，别一个密度平铺。

## 需废弃的迷思（高频）

证伪后别再用：管道符 `|`／花括号 `{ }`（不稳/证伪，改合并/逗号/冒号 + `[Harmonies]`）、`[Reverb: 30%]` 等参数标签（Tier 4 placebo，效果放 Style）、`[Key Change]` 触发转调（失败，Style 写 `in G minor` 或让 Bridge 自然转）、`[Explicit]` 解锁限制内容（无效）、`////***////` 防标签被唱（无效，正解是标签独占一行）、真正对位双声部（会崩塌，用交替/呼应/lead+adlib 近似）。

**拿不准某写法是不是已证伪的迷思 → 查 [tags.md](tags.md) 文末完整迷思清单**（含 Style 200 字符、BPM 精确锁定、`[Instrumental]` 末位、`[Beat Switch]`、首次时长等本表未列条目，是唯一权威全表）。
