# TokUI DSL Renderer 技能

## 简介

TokUI DSL 是小艺通道端侧（手机侧）的**原生 UI 渲染语言**。本技能提供完整的组件手册查询和 DSL 代码生成能力，使 AI 回复能以丰富 UI 组件呈现，而非纯文本。

**核心规则**：生成的 DSL 必须用 ` ```tokui ` 代码块包裹。

## 语法铁律（生成前必读）

1. **禁止发明组件类型** — 只能用下面穷举的组件列表
2. **禁止发明属性名** — 必须用简写（`l:` 非 `label:`、`tx:` 非 `text:`），全称无效
3. **禁止发明变体值** — `v:` 的值必须是变体白名单内的（见 §4）
4. **禁止发明布尔属性** — 只有指定 key 能裸写生效
5. **禁止编造图表类型** — 仅限 20 种
6. **禁止编造内置图标名** — 仅 View/Edit/Delete/Add/Copy/Download/Upload/Refresh/Check/Close/Search/Setting/Info/Lock/Unlock/More/Save/Warn/Export/Filter/Sort/Star/Link/Menu 共 24 个
7. **禁止编造颜色语义名** — 仅 primary/success/warning/danger/info/dark/light
8. **不确定就不写** — 宁可少写属性也不要猜测

## 语法基础

```
[type key:value key:value ... content]          ;; 自闭合
[type key:value]...[/type]                       ;; 容器（必须闭合）
```

- 第一个 token 是组件类型名
- 后续 `key:value` 为属性（key 为英文标识符）
- 最后剩余文本为裸内容（body text）
- 值含**空格**必须双引号：`ph:"请输入姓名"`
- 值含**逗号/竖线/分号**必须双引号：`d:"10,20,30"`

### 十条铁律

| # | 规则 | 错误示例 | 正确示例 |
|---|------|---------|---------|
| 1 | 属性间必须空格分隔（含 CJK 后） | `[item l:服务费（10%）tx:¥48]` | `[item l:服务费（10%） tx:¥48]` |
| 2 | tr 单元格之间用英文逗号分隔 | `2列：[tr 张三,25,北京,10,000]` | `[tr "张三,25,北京","10,000"]` |
| 3 | 变体必须带 `v:` 前缀 | `[p muted 文本]` | `[p v:muted 文本]` |
| 4 | card 有子元素时禁用`tx` | `[card tt:标题 tx:内容]...[/card]` | `[card tt:标题]...[/card]` |
| 5 | p 双模：有正文=自闭合 | — | `[p 文本]` 或 `[p][btn tx:点击][/p]` |
| 6 | 正文里别写 `英文:值` | `Q:什么是AI` | `Q：什么是AI`（全角冒号） |
| 7 | 正文含字面 `[` `]` 整段双引号包 | `[item arr[0]]` | `[item "arr[0]"]` |
| 8 | chart 属性顺序 | `[chart d:"..." t:bar]` | `[chart t:bar ... d:"..."]` |
| 9 | 组件名必须在手册清单内 | `[price-card]` | 不存在，用 `[card]` |
| 10 | 文本块用裸内容，非`tx` | `[p tx:文本]` | `[p 文本]` |

### 属性简写映射

| 简写 | 全称 | 说明 |
|------|------|------|
| `id` | element id | 元素 ID |
| `tt` | title | 标题 |
| `tx` | text | 文本内容（自闭合展示组件专用） |
| `l` | label | 表单标签 / desc 项标签 |
| `ph` | placeholder | 占位提示 |
| `u` | url | 链接地址 |
| `s` | src/source/size | 图片/视频/音频源或尺寸 |
| `n` | name | 表单字段名 |
| `v` | value/variant | 值或变体 |
| `t` | type | 子类型（按钮变体、图表类型等） |
| `clk` | onclick | 点击处理器 |
| `dis` | disabled | 禁用 |
| `ro` | readonly | 只读 |
| `req` | required | 必填 |
| `chk` | checked | 选中 |
| `w`/`h` | width/height | 宽/高 |
| `bg`/`fc` | background/font-color | 背景色/文字色 |
| `c` | color/colors | 颜色列表 |
| `icon` | icon | SVG 图标名 |
| `i` | emoji/char icon | emoji 或字符图标 |

### 值类型

| 类型 | 格式 | 示例 |
|------|------|------|
| 颜色 | 语义名或 6 位 hex 不带 # | `bg:primary` `bg:FF0000` |
| 数值 | 纯数字，禁止带单位 | `w:480` `h:300` |
| 布尔 | 只写 key | `stripe` `req` `dis` |
| 多选 | 逗号/竖线分隔，双引号包 | `d:"10,20\|30,40"` |

### 变体白名单

`v:` 后的值必须在此表中：

| 组件 | 允许的变体值 |
|------|-------------|
| `btn` | `primary` `danger` `success` `warning` `ghost` `sm` `lg` `pill` `square` `block` |
| `card` | `highlight` `flat` `bordered` `center` `right` |
| `table` | `bordered` `compact` |
| `h1`~`h6` | `left` `center` `right` `ribbon` `underline` `badge` `pill` |
| `p` | `left` `center` `right` `muted` `bold` `sm` `lg` |
| `a` | `muted` `danger` `success` `underline` |
| `img` | `avatar` `rounded` `bordered` |
| `input`/`pwd` | `error` `success` `sm` `lg` `underline` `pill` |
| `select`/`picker`/`cascader` | `error` `success` |
| `dv` | `dashed` `dotted` `sm` `md` `lg` `vert` `plain` |
| `drawer` | `left` `right` `top` `bottom` |
| `breadcrumb` | `arrow` |

### 内置图标名（24 个，穷举）

View, Edit, Delete, Add, Copy, Download, Upload, Refresh, Check, Close, Search, Setting, Info, Lock, Unlock, More, Save, Warn, Export, Filter, Sort, Star, Link, Menu

---

## 01 - 文本与基础组件

| 组件 | 类型 | 合法属性 | 说明 |
|------|------|---------|------|
| `h1`~`h6` | 自闭合 | 裸内容, `v`, `bg`, `fc` | 标题 |
| `p` | 双模 | 裸内容, `v` | 段落，可含内联子节点 |
| `a` | 自闭合 | `u`, `tx`/裸内容, `tt`, `target`, `dis`, `v` | 链接 |
| `img` | 自闭合 | `s`, `alt`, `w`, `h`, `tt`, `v` | 图片 |
| `hr` | 自闭合 | — | 分割线 |
| `dv` | 自闭合 | `tx`/裸内容, `v`, `vert`, `size`, `align`, `bg`, `th`, `plain` | 分割线 |
| `md` | 容器·原始 | — | Markdown 渲染 |
| `code` | 容器·原始 | `lang` | 语法高亮代码块 |
| `tag` | 自闭合 | `tx`, `t`, `s`, `bg`, `fc` | 标签 |
| `b`/`strong` | 自闭合 | 裸内容 | 加粗 |
| `em` | 自闭合 | 裸内容 | 斜体 |
| `mark` | 自闭合 | 裸内容 | 高亮 |
| `del` | 自闭合 | 裸内容 | 删除线 |
| `sub`/`sup` | 自闭合 | 裸内容 | 下标/上标 |

## 02 - 状态反馈与交互组件

| 组件 | 类型 | 关键属性 | 说明 |
|------|------|---------|------|
| `callout` | 自闭合/容器 | `t`, `tt`, `tx`/裸内容 | 警示框，t: info/success/warning/error/tip |
| `spin` | 自闭合 | `t`, `s`, `tx` | 加载指示器 |
| `skeleton` | 自闭合 | `t`, `rows`, `w`, `h` | 骨架屏 |
| `shimmer` | 自闭合 | `t`, `rows` | 闪光骨架 |
| `empty` | 自闭合 | `tx`, `icon`, `s` | 空状态 |
| `result` | 自闭合 | `t`, `tt`, `tx` | 结果页 |
| `barcode` | 自闭合 | `tx`, `l`, `s` | 条码 |
| `qrcode` | 自闭合 | `tx`, `l`, `s`, `ec` | 二维码 |
| `dot` | 自闭合 | `t`, `tx`, `s`, `pulse` | 状态点 |
| `badge` | 自闭合 | `count`, `overflow`, `dot`, `t`, `tx`, `pill` | 徽标 |
| `badge-box` | 容器 | `t`, `count`, `overflow`, `tx` | 角标包裹 |
| `toast` | 自闭合 | `t`, `tx`, `duration`, `pos` | 全局提示 |
| `notification` | 自闭合 | `t`, `tt`, `tx`, `duration`, `pos` | 全局通知 |
| `progress` | 自闭合 | `v`, `t`, `l`, `stripe`, `status` | 进度条 |
| `stat` | 自闭合 | `tt`, `v`, `pre`, `suf`, `trend`, `dec` | 统计数字 |
| `countdown` | 自闭合 | `target`/`dur`, `fmt`, `tx`, `l` | 倒计时 |
| `thumb` | 自闭合 | `t`, `v`, `clk` | 赞/踩 |
| `toggle` | 自闭合 | `tx`, `chk`, `clk`, `dis` | 切换按钮 |
| `copy` | 自闭合 | `tx`, `tt` | 复制按钮 |
| `upd` | 自闭合 | `id` + 更新键 | 动态更新 |
| `tooltip` | 自闭合 | `tt`, `pos`, `tx` | 文字提示 |
| `popconfirm` | 自闭合 | `tt`, `tx`, `clk`, `pos` | 确认气泡 |
| `popover` | 容器 | `tx`, `tt`, `pos`, `w`, `trig` | 气泡卡片 |
| `hover-card` | 容器 | `pos`, `w`, `delay` | 悬停卡片 |
| `dropdown` | 容器 | `tx`/`tt`, `v` | 下拉菜单 |
| `backtop` | 自闭合 | `t`, `v`, `tx`, `s` | 回到顶部 |
| `pagination` | 自闭合 | `page`, `total`, `count`, `clk`, `s` | 分页 |
| `breadcrumb` | 自闭合 | `items`, `sep`, `clk`, `v` | 面包屑 |
| `calendar` | 自闭合 | `month`, `v`, `marks`, `sel`, `range` | 日历 |
| `watermark` | 容器 | `tx`, `s`, `font`, `c`, `gap`, `ro` | 水印 |
| `avatar` | 自闭合 | `s`, `tx`, `size`, `bg`, `fc` | 头像 |
| `file` | 自闭合 | `n`, `s`, `t`, `u`, `tt` | 文件卡片 |
| `chat-input` | 容器 | `ph`, `clk`, `dis`, `max`, `auto`, `rows` | 对话输入框 |
| `msg-actions` | 容器 | `clk`, `copy`, `regenerate`, `like`, `delete`, `visible` | 消息操作栏 |

## 03 - 思考与计划组件

| 组件 | 类型 | 关键属性 | 说明 |
|------|------|---------|------|
| `think` | 容器 | `tt`, `open` | 思考块（折叠） |
| `think-chain` | 容器 | `tt`, `status`, `open` | 推理链 |
| `think-step` | 容器 | `status`, `tt`, `dur` | 推理步骤 |
| `plan` | 容器 | `tt` | 执行计划 |
| `plan-step` | 自闭合 | `status`, `tt`, `desc` | 计划步骤 |
| `agent` | 容器 | `name`, `status`, `action`, `duration` | 智能体状态 |

## 04 - AI / 对话组件

| 组件 | 类型 | 关键属性 | 说明 |
|------|------|---------|------|
| `bubble` | 容器 | `role`, `model`, `time` | 对话气泡，role: user/ai/system |
| `toolbar` | 容器 | `pos`, `align` | 工具栏 |
| `tool-call` | 容器 | `name`, `status`, `duration`, `id` | 工具调用 |
| `typing` | 自闭合 | `text`（用 text 非 tx） | 输入中指示 |
| `quick-reply` | 容器 | `items`, `clk` | 快捷回复 |
| `suggestions` | 容器 | `cols`, `clk`, `id` | 建议网格 |
| `suggestion` | 自闭合 | `tt`, `tx`, `clk`, `icon`, `dis` | 建议项 |
| `source` | 自闭合 | `n`, `tt`, `sn`, `u` | 引用源 |
| `diff` | 容器·原始 | `title`, `lang` | 代码差异 |
| `file-tree` | 容器 | — | 文件树 |
| `terminal` | 容器·原始 | `title`, `status` | 终端输出 |
| `sandbox` | 容器·原始 | `lang`, `title`, `height` | 代码沙箱 |
| `test-result` | 容器 | `pass`, `fail`, `skip`, `total`, `duration` | 测试结果 |
| `commit` | 自闭合 | `hash`, `msg`, `author`, `branch`, `time`, `additions`, `deletions` | Git 提交 |
| `quote` | 容器 | `role`, `tx`, `msgid` | 引用消息 |
| `latency` | 自闭合 | `v`, `t` | 延迟指标 |
| `video` | 自闭合 | `s`, `poster`, `ratio`, `w`, `h` | 视频 |
| `audio` | 自闭合 | `s`, `tt`, `duration`, `w` | 音频 |
| `welcome` | 容器 | `tt`, `st`, `bd`, `hd`, `ft` | 欢迎页 |
| `feature` | 自闭合 | `tt`, `tx`, `i`, `clk` | 特性卡片 |
| `artifact` | 容器 | `tt`, `lang`, `pos`, `w` | Artifact 预览 |
| `canvas` | 容器 | `tt`, `pos`, `w`, `open`, `closable` | 画布面板 |

## 05 - 布局容器组件

| 组件 | 类型 | 关键属性 | 说明 |
|------|------|---------|------|
| `card` | 容器 | `tt`, `tx`, `v`, `w`, `hc`, `ht` | 卡片 |
| `ft` | 容器 | `tx`/裸内容, `v` | 卡片页脚 |
| `row` | 容器 | `v` | 栅格行（12列 grid） |
| `col` | 容器 | `span` | 栅格列（1-12） |
| `list` | 容器 | `t`, `plain` | 列表 |
| `item` | 容器 | `tx`/裸内容, `l`, `span` | 列表项 |
| `tabs` | 容器 | — | 标签页 |
| `tab` | 容器 | `tt` | 标签项 |
| `accordion` | 容器 | — | 手风琴 |
| `collapse` | 容器 | `tt`, `open` | 折叠面板 |
| `dialog` | 容器 | `tt`, `id` | 对话框 |
| `drawer` | 容器 | `tt`, `pos`, `w`, `h` | 抽屉 |
| `imgs` | 容器 | `s` | 图片网格 |
| `timeline` | 容器 | `v` | 时间轴 |
| `ti` | 自闭合 | `tm`, `t`, `tt`, 裸内容 | 时间轴项 |
| `steps` | 容器 | `v`, `s`, `vd` | 步骤条 |
| `step` | 容器 | `tt`, `status`, 裸内容 | 步骤 |
| `desc` | 容器 | `cols`, `stripe`, `bordered`, `v`, `lw` | 描述列表 |
| `desc-item` | 自闭合 | `l`, `tx`, `span` | 描述项 |
| `carousel` | 容器 | `auto`, `thumb`, `w`, `h`, `ratio` | 轮播 |
| `tree` | 容器 | `id`, `l`, `clk`, `chk` | 树 |
| `tn` | 容器/自闭合 | `v`, `tx`, `open`, `leaf`, `chk` | 树节点 |
| `menu` | 容器 | `v`, `act`, `bg`, `fc` | 菜单 |
| `resizable` | 容器 | `dir`, `min`, `max`, `default` | 分割面板 |
| `scroll-area` | 容器 | `h`, `w` | 滚动区域 |
| `sidebar` | 容器 | `w`, `pos`, `collapsible`, `tt` | 侧边栏 |
| `print-area` | 容器 | `id`, `tt` | 打印区 |

## 06 - 表单组件

| 组件 | 类型 | 关键属性 | 说明 |
|------|------|---------|------|
| `form` | 容器 | `act`, `mtd`, `sub`, `clk`, `id` | 表单 |
| `input` | 自闭合 | `t`, `l`, `ph`, `id`, `n`, `val`, `req`, `dis`, `ro`, `v` | 输入框 |
| `pwd` | 自闭合 | 同 input + `toggle` | 密码框 |
| `textarea` | 容器 | `l`, `ph`, `rows`, `maxlen`, `req`, `dis` | 多行文本 |
| `select` | 容器 | `l`, `ph`, `multi`, `req`, `opt` | 下拉选择 |
| `radio` | 容器 | `l`, `n`, `v`, `opt` | 单选组 |
| `checkbox` | 自闭合/容器 | `l`, `chk`, `opt`, `multi` | 复选框 |
| `switch` | 自闭合 | `l`, `chk`, `dis` | 开关 |
| `slider` | 自闭合 | `l`, `min`, `max`, `step`, `v` | 滑块 |
| `rate` | 自闭合 | `l`, `v`, `max` | 评分 |
| `numinput` | 自闭合 | `l`, `v`, `min`, `max`, `step` | 数字输入 |
| `btn` | 自闭合 | `tx`, `t`, `sub`, `clk`, `dis`, `icon`, `i`, `form`, `reset`, `print` | 按钮 |
| `btngroup` | 容器 | `id`, `v` | 按钮组 |
| `picker` | 容器 | `l`, `ph`, `multi`, `dis`, `v` | 选择器 |
| `cascader` | 容器 | `l`, `ph`, `dis`, `v` | 级联选择 |
| `transfer` | 容器 | `l`, `tt`, `tt2`, `clk`, `dis`, `h`, `mh` | 穿梭框 |
| `upload` | 自闭合 | `l`, `ph`, `accept`, `multi`, `max` | 文件上传 |
| `datepicker` | 自闭合 | `l`, `ph`, `fmt`, `v` | 日期选择 |
| `timepicker` | 自闭合 | `l`, `ph`, `fmt`, `v` | 时间选择 |
| `datetimepicker` | 自闭合 | `l`, `ph`, `fmt`, `v` | 日期时间选择 |

### opt 简写语法
```
[radio n:gender l:性别 opt:"1:男;2:女"]
[select n:city l:城市 opt:"bj:北京;sh:上海"]
[checkbox n:brand l:品牌 opt:"1:篮球;2:足球;3:羽毛球"]
```

## 07 - 表格组件

| 组件 | 类型 | 合法属性 | 说明 |
|------|------|---------|------|
| `table` | 容器 | `stripe`, `cap`/`caption`, `v`, `id` | 表格 |
| `thead` | 容器/自闭合 | `cols` | 表头 |
| `tbody` | 容器 | — | 表体 |
| `tr` | 自闭合 | `v:total` | 行，逗号分隔单元格 |
| `tcol` | 自闭合 | `n` | 列占位 |

### 单元格特殊语法
- **序号列**：thead 写 `#`，tr 对应留空
- **勾选列**：thead 写 `chk`
- **标签**：`tag:VIP t:success`
- **操作按钮**：`btn:详情 clk:handler|btn:删除 v:danger clk:handler`（`|` 分隔）
- **内联组件**：`[badge count:5]`
- **横向合并**：`值=cN`（横跨 N 列）
- **纵向合并**：`值=rN`（纵跨 N 行）
- **对齐**：`/c` 居中 `/r` 居右 `/l` 居左
- **配色**：`/primary` `/success` `/warning` `/danger` `/info`
- **汇总行**：`tr v:total`

## 08 - 图表组件（20种）

### 通用属性
`t:`（必填）、`d:`、`l:`、`c:`（必须是#开头hex）、`title:`、`w:`（禁止带单位）、`h:`、`legend`、`animation`、`unit:`

| 图表 | t:值 | 数据格式 d: |
|------|------|------------|
| 折线图 | `line` | `v1,v2,v3`；多系列 `v1,v2\|v3,v4` |
| 柱状图 | `bar` | 同上 |
| 饼图 | `pie` | `v1,v2,v3` |
| 环形图 | `donut` | `v1,v2,v3`；多组 `v1,v2\|v3,v4` |
| 面积图 | `area` | 同 line |
| 雷达图 | `radar` | `v1,v2,v3` |
| 散点图 | `scatter` | `x1,y1;x2,y2` |
| 气泡图 | `bubble` | `x,y,s;x,y,s` |
| 嵌套环形图 | `doughnut` | 同 donut |
| 仪表盘 | `gauge` | 单个数值 |
| 进度环 | `progress` | 单个数值 |
| 漏斗图 | `funnel` | `v1,v2,v3` |
| 矩形树图 | `treemap` | `名称1:值1,名称2:值2` |
| 热力图 | `heatmap` | `v1,v2,...` + `cols:` |
| K线图 | `candlestick` | `o,h,l,c;o,h,l,c` |
| 箱线图 | `box` | `min,q1,med,q3,max;...` |
| 桑基图 | `sankey` | `nodes:` + `flows:` |
| 甘特图 | `gantt` | `tasks:` |
| 混合图 | `mix` | `bar:v1,v2\|line:v3,v4` |
| 矩阵图 | `matrix` | `v1,v2\|v3,v4` |

### 颜色要求
图表颜色 `c:` 必须带 `#` 前缀（如 `c:"#FF4D4F,#FAAD14"`），不能省略。

---

## 生成示例

### 卡片布局
```tokui
[card tt:项目概览 v:bordered]
[row]
[col span:6][stat tt:总用户 v:12,580 trend:up][/col]
[col span:6][stat tt:活跃用户 v:8,342 trend:up][/col]
[/row]
[progress v:75 l:完成度 stripe]
[/card]
```

### 对话回复
```tokui
[bubble role:ai model:GPT-4 time:10:30]
[think tt:分析过程][p 正在分析你的需求...][/think]
[card tt:推荐方案]
[p 基于你的需求，推荐以下方案]
[tag tx:推荐 t:success]
[/card]
[source n:1 tt:官方文档 u:https://example.com]
[/bubble]
```

### 表格 + 分页
```tokui
[table stripe v:compact]
[thead cols:"#,姓名,部门/c,状态,操作"]
[tbody]
[tr ,张三,技术部,tag:在职 t:success,btn:详情 clk:view]
[tr ,李四,产品部,tag:休假 t:warning,btn:编辑 clk:edit]
[/tbody]
[/table]
[pagination page:1 total:5 count:50 show-total clk:onPage /]
```

### 步骤条 + 时间轴
```tokui
[steps v:2]
[step tt:需求分析 status:done 已完成]
[step tt:方案设计 进行中]
[step tt:编码实现 待开始]
[/steps]
[timeline]
[ti tm:周一 tt:确定方案 确认技术方案]
[ti tm:周二 tt:开发 主力功能开发]
[/timeline]
```

## 参考资料

完整规范文档见 `references/` 目录（共 29 个 markdown 文件）：
- `00-公共规范.md` — 语法铁律、属性简写、变体白名单、内置图标、容器规则
- `01-文本与基础组件.md` ~ `08-图表组件.md` — 各分类组件完整字典
- `图表-*.md` — 20 种图表的独立详细文档
