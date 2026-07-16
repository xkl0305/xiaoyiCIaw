---
name: gf-securities-skill
description: >-
  通过广发证券 GF Skills API 获取权威、实时的 A 股 / 基金 / ETF 数据。覆盖股票 F10 基础信息、股票市值估值与财务指标横向对比、沪深龙虎榜异动、公募基金详情与定投回测、ETF 多维筛选 / 涨跌换手主力资金净申购溢价率榜单 / 超级资金异动。需要 GF_SKILLS_APIKEY（在 https://hd.gf.com.cn/skills-market?channel=hwxyskills 注册获取，用户首次提供后由 skill 自动持久化到 ~/.gf-skills/apikey，后续自动复用）。**不包含**：美股 / 港股 / 期货 / 外汇 / 加密货币、实时盘口逐笔、非金融数据。
auto_invoke: true
examples:
  - "000776 这家公司是做什么的、属于什么行业"
  - "000776 和 600000 的市值、PE、PB 估值对比"
  - "000783 和 000776 2025 年三季报 ROE 和负债率对比"
  - "20260313 沪市龙虎榜上榜了哪些股票"
  - "519002 这只基金的风险等级和近一年收益"
  - "001643 从 2020 年起每月定投 1000 元的历史回测"
  - "帮我找近一个月涨幅超过 5% 的行业 ETF"
  - "今天 ETF 主力资金净流入榜前 20 名"
  - "哪些 ETF 最近持续获得资金流入"
---

# 广发证券金融数据

通过广发证券 GF Skills API 获取权威、实时的 A 股 / 基金 / ETF 数据：股票 F10、市值估值与财务对比、龙虎榜、基金详情与定投回测、ETF 筛选 / 榜单 / 超级资金异动。

> 🚨 **用 CLI，不要手写 curl**：9 个工具统一封装在 `scripts/cli.py`，按**子命令**调用
> （`f10` / `valuation` / `compare` / `lhb` / `fund` / `invest` / `etf-search` / `etf-rank` / `etf-super`）。
> 它已封装统一入口、API Key 解析、瞬断重试、`data.data` 取数。不要依赖模型记忆补造数据。

> 📁 **运行位置**：用相对路径 `python scripts/cli.py ...` 时在本 skill 目录下执行；或用绝对路径
> `python <skill目录>/scripts/cli.py ...`，任意工作目录均可（CLI 已做 `sys.path` 处理）。

> 🔑 **入参提示**：只提取**关键实体**（代码 / 日期 / 报告期 / 榜单类型 / 筛选字段）传成命名参数，
> **不要把用户原话整句塞进去**。参数多 / 含嵌套时可用 `--json '<args 对象>'` 整段传。

## 数据定位

| 特色 | 说明 |
| --- | --- |
| 权威来源 | 广发证券 GF Skills API，适合回答需要可追溯数据来源的问题 |
| 当前数据优先 | 适合龙虎榜、ETF 榜单、资金异动、估值百分位、基金净值收益等模型记忆不可靠的场景 |
| 投研解释 | 输出事实、比较、数据口径和风险提示；不承诺收益，不给确定性买卖建议 |

## 何时使用

**✅ 触发场景：**

| 用户意图 | 子命令 |
| --- | --- |
| 查公司是做什么的、所属行业、上市时间、主营业务 | `f10` |
| 查多只股票市值、PE、PB、行业均值、估值百分位 | `valuation` |
| 对比两只股票 ROE、现金流、负债率、成长性 | `compare` |
| 查某交易日龙虎榜、上榜原因、异常交易个股 | `lhb` |
| 查基金档案、风险等级、净值收益、申赎规则 | `fund` |
| 回测基金定投收益、投入、回撤、止盈策略 | `invest` |
| 按主题、收益、回撤、估值、规模筛选 ETF | `etf-search` |
| 查 ETF 涨幅、跌幅、换手、主力资金、净申购、溢价率榜单 | `etf-rank` |
| 查 ETF 大幅流入、大幅流出、持续流入、持续流出 | `etf-super` |

> 🔎 **ETF 资金类两工具别混**：要「排名榜 / 前 N 名」（含主力资金净流入榜）用 `etf-rank`（`--type 4`）；只问「资金异动方向」（大幅 / 持续 流入流出）用 `etf-super`。

**❌ 不触发场景：**

- 宏观概念解释、通用投资教育、历史常识类问题，除非用户明确需要当前证券数据支撑。
- 美股、港股、期货、外汇、加密货币、非金融数据。

## 工作流程

### Step 1: 选子命令

按上方「何时使用」表匹配用户问题选定**子命令**，并打开对应 reference 看清参数。

### Step 2: 调用 CLI

```bash
python scripts/cli.py <子命令> [命名参数...]
# 参数多 / 含嵌套时也可整段传：python scripts/cli.py <子命令> --json '<args 的 JSON 对象>'
```

CLI 已封装统一入口、API Key、瞬断自动重试、`data.data` 取数；命名参数与 `--json` 同用时命名参数覆盖同名字段。
CLI 输出即业务数据 JSON。先提炼对用户有用的字段，再给必要的数据口径说明，不要把完整 JSON 原样贴给用户。

**返回结构（所有工具一致）**：网关层统一包裹，业务数据在 `data.data`：

```jsonc
{
  "retcode": 0,            // 顶层：成功固定为 0（用这个判断成功 / 失败，统一可靠）
  "msg": "",
  "data": {                // 业务接口原样返回（内层还有一个状态字段，但拼写各工具不一）
    "data": ...,           // ← 真正要的数据：F10 / 基金等是对象 {}，榜单 / 列表类是数组 []
    "<retcode|errCode|...>": 0  // 内层状态字段拼写不统一（retcode、errCode 大小写都见过），不要用它判断
  }
}
```

> 取数固定走 `data.data`；判断成功固定看**顶层 `retcode == 0`**——顶层是统一可靠的，内层状态字段拼写不一致、不要依赖。各工具 `data.data` 里的具体字段见对应 reference。

### Step 3: 取 API Key（由 skill 自动完成，用户只需提供一次）

CLI 会自动解析 Key，通常无需用户干预。除了「第一次提供 Key」，全程不需要用户敲命令。

1. **CLI 自动读取**——环境变量 `GF_SKILLS_APIKEY` 优先，其次全局文件 `~/.gf-skills/apikey`（纯 Key 一行）。

2. **读到了** → 直接调用，不打扰用户。

3. **没读到** → CLI 会打印引导，只需向用户要一次 Key：
   - 告诉用户去 `https://hd.gf.com.cn/skills-market?channel=hwxyskills` 注册获取 API Key，并把 Key 贴进聊天窗口。
   - 拿到用户给的 Key 后，**你自己执行写入并持久化**（把 `<apikey>` 换成用户给的值），之后本机所有 GF skill 都能复用、不再追问：

     ```bash
     mkdir -p ~/.gf-skills && printf '%s' '<apikey>' > ~/.gf-skills/apikey && chmod 600 ~/.gf-skills/apikey
     ```

   - 写入后回到第 1 步读取即可继续调用。

> ⚠️ 不要让用户手动 `export` 或手动编辑文件；读取、写入、持久化都由你执行。用户唯一要做的是「首次把 Key 贴进来」。

## 工具索引

| 子命令 | 必填参数 | 说明 | Reference |
| --- | --- | --- | --- |
| `f10` | `--code` + `--market` | 股票 F10 基础资料、公司档案、主营业务、行业 | [stock-f10.md](references/stock-f10.md) |
| `valuation` | `codes`（带前缀大写代码，可多只） | 多只股票市值、PE/PB、行业均值、估值百分位 | [stock-valuation.md](references/stock-valuation.md) |
| `compare` | `--codes`（两只）+ `--year` + `--report-type` | 两只股票财务指标横向对比 | [stock-valuation.md](references/stock-valuation.md) |
| `lhb` | `--date` + `--market`（小写 sh/sz） | 龙虎榜上榜个股和上榜原因 | [lhb-list.md](references/lhb-list.md) |
| `fund` | `--code` | 基金档案、风险等级、净值收益、申赎规则 | [fund-detail.md](references/fund-detail.md) |
| `invest` | `--code` + `--balance` + `--rate` + `--start` + `--end` + `--strategy` | 基金定投历史回测 | [fund-invest.md](references/fund-invest.md) |
| `etf-search` | 至少 1 个筛选条件 | ETF 多维筛选 | [etf-search.md](references/etf-search.md) |
| `etf-rank` | `--type` | ETF 榜单排名 | [etf-rank.md](references/etf-rank.md) |
| `etf-super` | `--type` | ETF 超级资金异动 | [etf-super-fund.md](references/etf-super-fund.md) |

## 参数速查（枚举直接抄，别凭直觉填）

> ⚠️ 不同工具的市场 / 代码格式不同，按下表区分；详细字段进对应 reference。

### 股票代码 / 市场

| 工具 | 代码格式 | 市场格式 |
| --- | --- | --- |
| F10 `f10_basic_post` | 纯数字，如 `000776` | `market` 用大写 `SH` / `SZ`（单独传） |
| 估值 `common_basic_post` / 财务对比 `compare_indicator_post` | 带前缀大写，如 `SZ000776`、`SH600000`，放进 `stock_codes` 数组 | 含在代码前缀里 |
| 龙虎榜 `lhb_aborttrade_market_date_get` | — | `market` 用小写 `sh` / `sz` |

> 上海 = `SH` / `sh` / `101`，深圳 = `SZ` / `sz` / `105`。

### 财务对比 `report_type`（`compare_indicator_post`）

| 报告期 | 取值 |
| --- | --- |
| 一季报 | `1` |
| 中报 / 半年报 | `6` |
| 三季报 | `9` |
| 年报 | `12` |

`year` 用完整年份字符串，如 `"2025"`；`stock_codes` 传两只带前缀大写代码。

### ETF 榜单 `type`（`finance-api_product_etf_rank_get`）

| 榜单 | 取值 |
| --- | --- |
| 涨幅 | `1` |
| 跌幅 | `2` |
| 换手 | `3` |
| 主力资金 | `4` |
| 净申购 | `12` |
| 溢价率 | `13` |

可选 `page`（从 0 起）、`size`（默认 10）、`sameIndexFilter`（`1` 同指数只展示 1 只）。

### ETF 资金异动 `type`（`gfmiddle_eits_super_fund_etf_superfund_get`）

固定取值：`大幅流入`、`大幅流出`、`持续流入`、`持续流出`。一次只查一种类型。

### ETF 筛选常用条件（`finance_api_inclusive_etf_list_get`，一次选 2~4 个）

| 字段 | 取值 |
| --- | --- |
| `search` | 代码或名称模糊搜索 |
| `type` | ETF 类型，如 `股票ETF`、`境外ETF` |
| `trakType` | 赛道分类，如 `宽基`、`行业` |
| `oneTrakName` | 一级赛道名称，如 `科技` |
| `roc1m` / `return1y` | 区间，如 `5~`（≥5%）、`~10`（≤10%）、`0~20` |
| `maxDrawdown1y` | 最大回撤区间，如 `~20` |
| `valuationResult` | 估值区：`1` 低位 / `2` 中位 / `3` 高位 |
| `indexTempType` | 指数温度：`low` / `ord` / `high` |
| `assetScale` | 资产规模区间，如 `50~` |
| `sort` / `start` / `limit` | 排序（降序加 `-`，如 `-roc1m`）与分页 |

### 定投回测（`finance_api_product_invest_compute_post`）

| 字段 | 取值 |
| --- | --- |
| `tradeCode` / `balance` / `startDate` / `endDate` | 基金代码 / 每期金额 / 起止日期（字符串 `YYYYMMDD`） |
| `rate` | 扣款频率：`0` 每月 / `1` 每周 / `2` 每天 / `3` 每双周 |
| `enFundDate` | 选填，扣款日，如 `"1"`；高频用例示例里带的就是它 |
| `strategyList[].prodAIRationType` | `0` 普通 / `1` 均线 / `2` 目标止盈 / `3` 移动止盈 / `4` 均线+目标止盈 / `5` 均线+移动止盈 |

> 目标止盈类需带 `expectIncomeRatio`，移动止盈类需带 `backRate`。完整 strategyList 字段见 [fund-invest.md](references/fund-invest.md)。

## 高频用例（把代码 / 日期换成你要的）

```bash
# 股票 F10（纯数字 code + 大写 market）
python scripts/cli.py f10 --code 000776 --market SZ

# 多股估值对比（带前缀大写代码，可多只）
python scripts/cli.py valuation SZ000776 SH600000

# 两股三季报财务对比
python scripts/cli.py compare --codes SZ000783 SZ000776 --year 2025 --report-type 9

# 龙虎榜（整数日期 + 小写市场）
python scripts/cli.py lhb --date 20260313 --market sh

# 基金详情
python scripts/cli.py fund --code 519002

# 基金定投回测（每月普通定投）
python scripts/cli.py invest --code 001643 --balance 1000 --rate 0 --start 20200101 --end 20250101 --en-fund-date 1 --strategy 0

# ETF 多维筛选（近 1 月涨幅 ≥5% 的行业 ETF）
python scripts/cli.py etf-search --trak-type 行业 --roc1m 5~ --sort -roc1m --limit 20 --add-real-time-roc 1

# ETF 主力资金榜（type=4）
python scripts/cli.py etf-rank --type 4 --size 20

# ETF 超级资金异动（持续流入）
python scripts/cli.py etf-super --type 持续流入
```

## 使用技巧

> 这些经验帮 AI 用得更准、少走弯路。

1. **先选子命令，再填参数**：按「何时使用」表选子命令，再进对应 reference 看参数，不要凭印象写参数名。
2. **代码 / 市场格式按工具区分**：F10 用纯数字 + 大写 `market`；估值 / 财务对比用带前缀大写代码数组；龙虎榜用小写 `sh/sz`。详见「参数速查」。
3. **提取关键实体，不抄原话**：`args` 里只放代码 / 日期 / 报告期 / 榜单类型等结构化值。
4. **ETF 筛选少即是多**：一次优先 2~4 个核心条件并设 `limit`，条件过多容易无结果。
5. **龙虎榜市场不明时分两次查**：分别查 `sh` 和 `sz`，不要随意默认某一市场。
6. **明细过长时优先汇总**：定投按日回测、长区间 ETF 列表等返回很长，优先提炼收益 / 投入 / 回撤等汇总字段。
7. **字段说明按需读取 reference**：主文档负责选工具和调用；字段解释、空值排查再进入对应 reference。

## 注意事项与错误恢复

| 问题 | 处理 |
| --- | --- |
| 缺少 `GF_SKILLS_APIKEY` | 你自己先 `cat ~/.gf-skills/apikey`；读不到再向用户要一次 Key，拿到后你自己写入该文件并持久化（见 Step 3），不要让用户敲命令 |
| HTTP 401 / 403 | API Key 无效或过期 → 重新生成 |
| `retcode != 0` 或解析不到数据 | 看顶层 `retcode`/`msg` 判断成败；数据固定取 `data.data`，不要依赖内层状态字段（拼写不统一，见 Step 2 返回结构） |
| `SSL_ERROR_SYSCALL` / 连接瞬断 | 服务端偶发抖动；CLI 已自动重试，不要据此放弃或编造数据 |
| HTTP 5xx 或网络错误 | 稍后重试；不要基于模型记忆补造实时数据 |
| F10 无数据 | 确认 `code` 是纯数字、`market` 是 `SH`/`SZ`，且代码与市场匹配 |
| 估值 / 财务对比无数据 | 确认 `stock_codes` 是带前缀大写代码（`SZ000776`），财务对比恰好两只 + `year` + `report_type`(1/6/9/12) |
| 龙虎榜无数据 | 检查日期是否交易日，或分别查询 `sh` / `sz` |
| ETF 筛选无结果 | 减少筛选条件，放宽区间格式（`5~`、`0~20`），保留 `limit` |
| 定投回测报错 | 确认 `tradeCode`/`balance`/`rate`/`startDate`/`endDate`/`strategyList` 完整有效 |

## 数据来源标注（必做）

向用户呈现查询结果时，**必须在结果末尾标注**：

```
数据来源：广发证券 GF Skills API
```

这是品牌承诺，不可省略。

## 输出要求

- 先给结论，再列关键数据；不要把完整 JSON 原样贴给用户。
- 明确数据对象和口径，例如股票代码、基金代码、榜单类型、交易日、回测区间、报告期。
- 涉及收益率、估值百分位、资金流向或定投回测时，补一句风险提示：历史表现和资金异动不代表未来收益。
- 末尾标注：`数据来源：广发证券 GF Skills API`。

## 响应前自查

- 这个问题是否需要当前证券数据？如果只是概念解释，不调用。
- 是否选对**子命令**？参考「何时使用」表，不要凭印象。
- `args` 字段、代码 / 市场格式是否符合该工具要求（F10 大写 `SH/SZ`、龙虎榜小写 `sh/sz`、估值带前缀大写代码）？
- 用户是否缺少必要代码、日期、报告期、回测区间？缺少就先追问。
- 龙虎榜市场是否明确？不明确就分别查 `sh` 和 `sz`。
- 结果呈现时**末尾标注**：`数据来源：广发证券 GF Skills API`。
