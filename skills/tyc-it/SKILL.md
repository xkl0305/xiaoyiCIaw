---
name: tianyancha
description: 使用本地 `tyc` 命令查询天眼查企业数据。适用于企业主体核验、合作方/客户/供应商风险评估、股东和实控人分析、受益所有人、关联关系路径、司法诉讼、执行失信、行政处罚、经营真实性、招投标、资质许可、知识产权、董监高、历史沿革、行业企业发现等商业及企业信用场景。
version: 1.0.0
env:
 - 118104171_login_token: API调用凭证token，仅当实际调用 API 执行时才需要此凭证，仅介绍/说明 skill 时无需凭证，凭证获取方式："从 /home/sandbox/.openclaw/.xiaoyienv 文件中读取账号凭证；若为空，或当前时间大于 ${118104171_login_token_expire_time} 的取值（即凭证已过期），调用一次 huawei_id_tool工具（工具参数：clientId=117660163，skillName=tyc-it）刷新凭证；刷新成功后重新读取账号凭证，继续执行后续业务逻辑"
 - 118104171_login_token_expire_time: "账号凭证过期时间；当前时间大于该值时需先刷新凭证再继续调用"
---

# 天眼一下

本 Skill 聚合天眼查企业数据查询能力，运行时根据用户问题自动选择合适维度进行调用。华为侧账号接入使用小艺账号绑定服务获取 `loginToken`；该 `loginToken` 等价于 `tyc` OAuth 短期 access token，CLI 调用时写入 `Authorization: Bearer <loginToken>`。不要发起 OAuth Device Flow，也不要要求用户粘贴 API Key。

## 能力概览

| 能力模块  | 适用场景                  | 代理命令                                   |
| ----- | --------------------- | -------------------------------------- |
| 主体画像  | 查询企业登记、规模、联系方式、基础画像   | `tyc company ...`                      |
| 风险合规  | 查询司法、执行、失信、处罚、经营异常    | `tyc risk ...`                         |
| 股东与实控 | 查询股东、实控人、受益所有人、股权路径   | `tyc company ...`                      |
| 经营真实性 | 查询招投标、资质、许可、招聘、产品、上下游 | `tyc operation ...`                    |
| 知识产权  | 查询专利、商标、软著、创新力评分      | `tyc intellectual_property ...`        |
| 人员与历史 | 查询董监高、人员风险、历史沿革、历史股东  | `tyc executive ...`; `tyc history ...` |

## 安装与鉴权

安装：

```bash
npm install -g tyc-cli
```

## 凭据说明

- 凭证授权前，先检查tyc-cli是否安装完成，如果未安装，需要先等待安装完成后再进行凭证授权。
- 统一使用 `.xiaoyienv` 文件中的 `118104171_login_token` 和 `118104171_login_token_expire_time`。
- 若 `118104171_login_token` 为空，或当前时间大于 `118104171_login_token_expire_time`，调用一次 `huawei_id_tool` 工具（工具参数：`clientId=118104171`，`skillName=tyc-it`）刷新凭证（升级小艺APP和小艺Claw到最新版本后支持）。
- 刷新成功后重新读取 `.xiaoyienv` 文件，再继续后续业务逻辑。
- 禁止要求用户粘贴 API Key；禁止执行 `tyc login`、OAuth Device Flow 或 `tyc init --authorization`。
- 用户未授权或授权过期时，由小艺授权卡或小艺 Claw 账号管理页完成账号绑定/续期。

查询前，使用华为 `loginToken` 写入 CLI 鉴权请求头：

```bash
tyc init --url https://mcp.tianyancha.com/mcp --header "Authorization=Bearer <loginToken>"
```

其中 `<loginToken>` 必须替换为 `.xiaoyienv` 中 `118104171_login_token` 的当前值。凭证刷新后，重新执行一次上述 `tyc init`，确保后续 `tyc` 查询携带最新 `Authorization`。不要只写 `login-token` 自定义头；`tyc` CLI 会要求配置 `Authorization`。

确认 CLI 可用：

```bash
tyc --version
tyc company companies "百度" --pageNum 1 --pageSize 3 --md
```

如果查询提示未登录、凭证缺失或凭证过期，先按本节凭据规则调用一次 `huawei_id_tool` 刷新凭证，重新写入 `Authorization` 后再重试一次；仍失败时，说明账号绑定未完成或服务端凭据异常，应提示用户在小艺授权卡或账号管理页完成绑定。

## 🔑 强制前置流程：每次查询前的凭证检查

**在任何 `tyc` 命令执行之前，必须严格按以下步骤检查凭证有效性。**

### 步骤 1：读取凭证文件

```bash
grep -E "118104171_login_token|118104171_login_token_expire_time" /home/sandbox/.openclaw/.xiaoyienv 2>/dev/null
```

### 步骤 2：判断凭证状态

| 情况                                                     | 处理方式            |
| ------------------------------------------------------ | --------------- |
| `118104171_login_token` **不存在或为空**                     | → 走授权（步骤 3）     |
| `118104171_login_token_expire_time` **不存在**            | → 走授权（步骤 3）     |
| 当前时间 **大于** `118104171_login_token_expire_time`（凭证已过期） | → 走授权（步骤 3）     |
| token 存在且未过期                                           | → 跳过授权，直接跳到步骤 5 |

### 步骤 3：发起授权

调用 `huawei_id_tool` 刷新凭证：

```
huawei_id_tool(clientId="118104171", skillName="tyc-it")
```

- 若返回**失败**，说明当前环境无授权通道（如 `.xiaoyienv` 被重置、会话过期），**不要重复重试**，直接告知用户授权失败，建议稍后重试或重启会话。
- 若返回**成功**，继续步骤 4。

### 步骤 4：重新读取并写入凭证

再次读取 `.xiaoyienv` 文件获取新 token：

```bash
grep -E "118104171_login_token" /home/sandbox/.openclaw/.xiaoyienv 2>/dev/null
```

然后用新 token 初始化 tyc CLI：

```bash
tyc init --url https://mcp.tianyancha.com/mcp --header "Authorization=Bearer <loginToken>"
```

### 步骤 5：执行业务查询

此时凭证已确保有效，继续执行具体的 `tyc` 查询命令。

### ⚠️ 关键强制规则

> **任何时候都必须先执行步骤 1（检查凭证文件），确认 token 确实存在且未过期，再走查询。**
> 
> 禁止出现以下情况：
> 
> - 凭"刚才查过"的记忆跳过步骤 1
> - 认为"最近成功查询过"就假设 token 仍然有效，不做检查
> - 两次查询之间不重复执行完整流程

### 要点

- **每次用户发起查询请求时，都必须完整走一遍上述流程**。不能假设上次授权的 token 仍然有效——环境重置、文件覆盖等都可能导致 token 丢失。
- 步骤 2 的判断逻辑**必须执行**（哪怕刚授权过），因为 `.xiaoyienv` 文件可能被外部重置。
- `huawei_id_tool` 调用**最多重试一次**。第二次仍失败，停止并告知用户。

## 命令规则

- 使用 `tyc` 命令，不使用 `tyc-cli` 命令。
- 所有查询必须通过 `Authorization: Bearer <loginToken>` 完成鉴权；这里的 `loginToken` 是从 `.xiaoyienv` 文件中读取的 `118104171_login_token` 值，不是用户手动复制的 API Key。
- 不确定参数时，先运行 `tyc <category> --help` 或 `tyc <category> <method> --help`。
- 分析时优先使用默认 JSON 输出；需要给用户展示候选表或简短结果时使用 `--md`。
- 列表查询默认加 `--pageNum 1 --pageSize 10`，除非用户要求更多。
- 大结果使用 `--head`、`--threshold` 或 `--output-file` 控制输出，不把长原始数据直接塞进最终答复。
- 空结果只表示当前命令未返回数据；不要写成“绝对没有风险”。

## 查询流程

1. 从用户问题提取主体、意图、深度和决策场景。
2. 除非用户给出完整企业名或 18 位统一社会信用代码，否则先锚定主体。
3. 先调用一到两个总览命令。
4. 只下钻回答问题必需的维度。
5. 重要判断尽量用两个以上维度交叉验证。
6. 输出时先给结论，再给证据、限制和下一步建议。

## 主体锚定

简称、品牌、曾用名、模糊名称或不确定主体，先用企业搜索：

```bash
tyc company companies "<query>" --pageNum 1 --pageSize 5 --md
```

优先选择经营状态正常、名称匹配语境，并且法定代表人、地区、行业或 USCC 与用户线索一致的候选。

只有一个明确候选时，可继续使用官方名称或 USCC 查询。多个候选都可能匹配时，先让用户确认：

```markdown
你说的「<query>」匹配到多家企业，请确认是哪一家：

| # | 企业名称 | USCC | 状态 | 法定代表人 | 注册地 |
|---|---|---|---|---|---|
| 1 | ... | ... | ... | ... | ... |
| 2 | ... | ... | ... | ... | ... |

回复编号继续，或回复“都不是”重新输入。
```

多主体关系问题必须分别锚定每个主体，再判断关系。

## 常用命令

| 意图      | 命令                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| ------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 主体画像    | `tyc company registration-info "<company>"`; `tyc company profile "<company>"`; `tyc company scale "<company>"`; `tyc company contact-info "<company>" --pageNum 1 --pageSize 10`                                                                                                                                                                                                                                                                  |
| 合作风险    | `tyc risk overview "<company>"`; `tyc risk business-exception "<company>" --pageNum 1 --pageSize 10`; `tyc risk administrative-penalty "<company>" --pageNum 1 --pageSize 10`; `tyc risk judgment-debtor-info "<company>" --pageNum 1 --pageSize 10`; `tyc risk dishonest-info "<company>" --pageNum 1 --pageSize 10`                                                                                                                              |
| 司法与执行   | `tyc risk judicial-case "<company>" --pageNum 1 --pageSize 10`; `tyc risk judicial-documents "<company>" --pageNum 1 --pageSize 10`; `tyc risk case-filing-info "<company>" --pageNum 1 --pageSize 10`; `tyc risk high-consumption-restriction "<company>" --pageNum 1 --pageSize 10`                                                                                                                                                              |
| 行政与合规   | `tyc risk administrative-penalty "<company>" --pageNum 1 --pageSize 10`; `tyc risk serious-violation "<company>" --pageNum 1 --pageSize 10`; `tyc risk environmental-penalty "<company>" --pageNum 1 --pageSize 10`; `tyc risk tax-violation "<company>" --pageNum 1 --pageSize 10`; `tyc risk tax-arrears-notice "<company>" --pageNum 1 --pageSize 10`                                                                                           |
| 股东与实控   | `tyc company shareholder-info "<company>" --pageNum 1 --pageSize 10`; `tyc company actual-controller "<company>"`; `tyc company beneficial-owners "<company>" --pageNum 1 --pageSize 10`; `tyc company equity-tree "<company>"`; `tyc company equity-ratio "<company>"`                                                                                                                                                                            |
| 关联关系    | `tyc company relation-path "<companyA>" --searchKey2 "<companyB>"`; `tyc company relation-graph "<company>"`; `tyc company group-info "<company>"`                                                                                                                                                                                                                                                                                                 |
| 经营真实性   | `tyc operation bidding-info "<company>" --pageNum 1 --pageSize 10`; `tyc operation qualifications "<company>" --pageNum 1 --pageSize 10`; `tyc operation administrative-license "<company>" --pageNum 1 --pageSize 10`; `tyc operation recruitment-info "<company>" --pageNum 1 --pageSize 10`; `tyc operation products-info "<company>" --pageNum 1 --pageSize 10`; `tyc operation suppliers-and-customers "<company>" --pageNum 1 --pageSize 10` |
| 知识产权与品牌 | `tyc intellectual_property ipr-score "<company>"`; `tyc intellectual_property patent-info "<company>" --pageNum 1 --pageSize 10`; `tyc intellectual_property trademark-info "<company>" --pageNum 1 --pageSize 10`; `tyc intellectual_property software-copyright-info "<company>" --pageNum 1 --pageSize 10`                                                                                                                                      |
| 董监高和人员  | `tyc company key-personnel "<company>" --pageNum 1 --pageSize 10`; `tyc executive person-profile "<company>" --humanName "<name>"`; `tyc executive person-risk-overview "<company>" --humanName "<name>"`; `tyc executive personnel-positions "<company>" --humanName "<name>"`; `tyc executive personnel-related-companies "<company>" --humanName "<name>"`                                                                                      |
| 历史沿革    | `tyc history historical-overview "<company>"`; `tyc history historical-registration "<company>"`; `tyc history historical-shareholders "<company>" --pageNum 1 --pageSize 10`; `tyc history historical-investments "<company>" --pageNum 1 --pageSize 10`; `tyc company change-records "<company>" --pageNum 1 --pageSize 10`; `tyc company history-names "<company>"`                                                                             |
| 企业发现    | `tyc company companies-by-industry-region "<keyword>" --industry "<code>" --region "<code>" --pageNum 1 --pageSize 10`; `tyc company companies-by-tag "<tag>" --pageNum 1 --pageSize 10`; `tyc company companies-by-ranking "<company>" --pageNum 1 --pageSize 10`; `tyc company park-companies "<park>" --pageNum 1 --pageSize 10`                                                                                                                |
| 关键词搜索   | `tyc operation bids "<keyword>" --pageNum 1 --pageSize 10`; `tyc intellectual_property patents "<keyword>" --pageNum 1 --pageSize 10`; `tyc intellectual_property trademarks "<keyword>" --pageNum 1 --pageSize 10`                                                                                                                                                                                                                                |
| 上市与财务   | `tyc company financial-summary "<company>"`; `tyc company financial-data "<company>"`; `tyc company listing-info "<company>"`; `tyc company income-statement "<company>"`; `tyc company balance-sheet "<company>"`; `tyc company cash-flow-statement "<company>"`; `tyc company stock-shareholders "<company>" --pageNum 1 --pageSize 10`                                                                                                          |

## 意图捷径

- 用户只说“查一下这家公司”时，默认查主体画像、风险总览、经营真实性和实控摘要。
- 用户问“能不能合作/供应商准入/客户风险”时，优先查登记状态、风险总览、行政处罚、执行失信、经营异常、经营信号和资质。
- 用户问“背后是谁/实际控制人/受益人”时，优先查股东、实际控制人、受益所有人、股权树和集团信息。
- 用户问“两家公司有没有关系”时，先锚定双方，再查关联路径和关键中间节点。
- 用户问“真实经营吗”时，结合登记信息、规模、招投标、资质、许可、产品、招聘、客户供应商和必要的舆情信息。
- 用户问“商标/专利/技术实力”时，结合创新力评分、专利、商标和软著明细。
- 用户问“高管/法人背景”时，先查主要人员，再带 `--humanName` 查询人员画像和人员风险。

## 判断规则

- 区分“查到风险记录”“已查询但未返回记录”“未查询该维度”。
- 不替用户做法律、投资、授信或采购最终决策；给数据驱动建议，并列出需要人工复核的材料。
- 重大风险结论必须说明依据的业务记录或数据维度，不向用户展示内部 `tyc` 命令。
- 优先使用具体记录和近期记录，不只看总数。总览和明细冲突时，直接说明冲突。
- 集团、实控和关联关系判断以路径、持股、任职、集团信息为依据，不以名称相似为依据。

## 输出格式

默认使用简体中文，结论先行。

```markdown
# 商查摘要：<company>

## 结论
<1-3 句话直接回答用户问题>

## 关键信号
| 维度 | 发现 | 判断 |
|---|---|---|
| 主体 | ... | 通过/关注/异常 |
| 风险 | ... | 低/中/高 |
| 经营 | ... | 强/一般/弱 |
| 股权/关系 | ... | 清晰/需复核 |

## 依据与限制
- <关键业务记录或数据维度>
- <需要人工复核的点>

## 下一步动作
- <下一步动作>
```
