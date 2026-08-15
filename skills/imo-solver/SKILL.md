---
name: imo-solver
description: 
  小艺竞赛解题技能，支持各类IMO和数学题目，主要是求解和证明类数学问题，当用户提出**纯数学学科性**问题（解方程、求积分/导数/极限、化简表达式、几何证明、数列求和、线性代数运算、概率统计推导等）时使用，涉及生活实务计算（运费、折扣、账单、单位换算）不触发。
  适用情形：
  1. 求解类：包括解方程、求积分、求导数、化简表达式、数列求和、极限计算、线性代数、概率统计等数学问题
  2. 证明类：几何、积分、导数、线性代数、概率统计、数学等各类证明
  3. 各类数学问题和IMO题目
  只要用户意图涉及“解答数学问题”、“解答IMO题目”、“推导解答数学问题”或“推导IMO题目”时必须触发。用户提出**纯数学学科性**问题，如公式推导、证明、计算求解、解题等场景必须触发，涉及生活实务计算（运费、折扣、账单、单位换算）不触发。
  
metadata:
  openclaw:
    requires:
      bins:
        - python3
---

# IMO 数学解题 Skill

以数学解题专家的身份，使用 IMOAgent 工具解决用户的数学问题。

---

## 环境初始化（始终最先执行此步骤）

**此技能需要 Python 3 (>=3.8)。在运行任何脚本之前，执行以下命令定位有效的 Python 可执行文件并安装依赖。**

```bash
PYTHON_CMD=""
for cmd in python3 python python3.13 python3.12 python3.11 python3.10 python3.9 python3.8; do
  if command -v "$cmd" &>/dev/null && "$cmd" -c "import sys; exit(0 if sys.version_info >= (3,8) else 1)" 2>/dev/null; then
    PYTHON_CMD="$cmd"
    break
  fi
done

if [ -z "$PYTHON_CMD" ]; then
  echo "错误：未找到 Python 3.8+"
  exit 1
fi

echo "已找到 Python：$PYTHON_CMD ($($PYTHON_CMD --version))"

$PYTHON_CMD -m pip install -q --break-system-packages requests
echo "依赖已就绪。"
```

> 检查完成后，在后续所有命令中使用发现的 `$PYTHON_CMD` 替代 `python`。

---

## 触发条件

**精确触发**：以下场景应当触发本 Skill：

- 用户提出明确的**纯数学学科性**问题：解方程、求积分、求导数、求极限、化简表达式、几何证明、数列求和、概率计算、线性代数运算等
- 用户说"帮我算一下"、"解一下"、"求解"、"计算"、"推导"、"证明"、"求证"等后面跟数学内容
- 用户给出数学表达式、公式、方程要求解答或计算

**不触发**（以下情况应视为不相关，返回通用能力，无需执行流程调用IMOAgent）：

- 非数学类的通用问答、编程、写作等
- 虽然包含数字但非数学解题场景，如生活实务计算（运费、折扣、账单、单位换算）（"帮我算3个盒子的运费"）

---

## 执行流程

1. **分析数学问题并分类**：

   理解用户提出的数学问题类型（代数、几何、微积分、概率统计等），确认问题完整、可解。根据难度分为两类，决定后续轮询的 sleep 间隔：

   | 分类 | 判断依据 | sleep 间隔  | 说明           |
   |------|---------|-----------|--------------|
   | **简单题目** | 解方程、求导数、求积分、化简表达式、求极限、数列求和、矩阵运算、概率计算等计算求解类问题 | **30 秒**  | 通常几分钟内完成     |
   | **IMO 题目** | 竞赛级证明题、IMO 题目、需要多步引理推导的复杂证明 | **120 秒** | 通常需要几十分钟深度推理 |

   > 分类由模型根据题目内容自行判断。如果难以确定，按 IMO 题目处理（sleep 120）。

2. **调用 imo_agent_invoke.py 求解**：

   - 将用户的数学问题完整组装到 `query` 参数中
   - 调用方式：

     ```bash
     timeout 3600 $PYTHON_CMD ~/.openclaw/workspace/skills/imo-solver/scripts/imo_agent_invoke.py "<完整的数学问题描述>"
     ```

   - **exec 工具参数**：`yieldMs` 设为 `120000`（120 秒后 yield 返回 running），`timeout` 必须设为 `3600`（与 bash timeout 一致，60 分钟）。**不要把 exec 的 timeout 设为 120**，否则进程会在 120 秒后被 SIGTERM 杀死。

   - 脚本通过 OSMS SSE 接口（`/celia-claw/v1/sse-api/skill/execute`）发起请求，循环读取 SSE 流，直到收到 `streamType: final` 的最终结果后返回完整 JSON
   - 脚本前台同步执行，进度和结果都输出到 stdout：
     - 心跳行：`=== HEARTBEAT === elapsed=<秒>`（每 30 秒输出一次，携带已耗时秒数，**供判超时使用**）
     - 进度行：`=== PROGRESS === <内容>`（解题过程中的中间状态，如 "Parsing the question..."、"Solving the problem..."、"Verifying the solution..."）
     - 结果行：`=== RESULT ===` 后紧跟完整 JSON
   - 脚本会自动从 `~/.openclaw/.xiaoyienv`（或 `ACP2SERVICE_ENV` 指定路径）加载 `SERVICE_URL`、`PERSONAL_UID`、`PERSONAL_API_KEY` 等认证配置
   - 整体超时由 `timeout 3600`（60 分钟）控制，含连接建立与等待 `final` 响应

   **完成汇报**：

   ~~~
    ✅ 数学解题任务已启动，正在解题中...
   ~~~

3. **等待结果（poll + sleep 循环）**：

   **关键环境事实**：exec 工具最多等待 **120 秒**就会 yield，返回 `"Command still running"`，命令转入后台。`yieldMs` 参数上限为 120 秒，设更大的值无效。yield 后必须通过 `process poll` + `sleep` 循环等待脚本完成。

   **sleep 间隔由步骤1的分类决定**：简单题目用 `sleep 30`，IMO 题目用 `sleep 120`。下文用 `<SLEEP_SEC>` 表示选定的秒数。

   **循环规则**（严格按此顺序执行，不要跳步）：

   **动作 A — poll 检查进程状态**：

   ```
   tool: process
   action: poll
   sessionId: <exec yield 返回的 sessionId>
   ```

   根据 poll 返回内容判断：

    | poll 返回内容 | 含义 | 下一步 |
    |--------------|------|--------|
    | 包含 `=== RESULT ===` | 脚本已完成，JSON 在下一行 | **将结果转述给用户，退出循环，进入步骤四** |
    | 包含 `=== HEARTBEAT ===` | 脚本运行中，附带真实已耗时 `elapsed=<秒>` | **读取 `elapsed` 判断是否超时（见下方）；不转述给用户、不输出任何内容**，继续动作 B |
    | 包含 `=== PROGRESS ===` | 脚本运行中，有新进度 | **将进度简短转述给用户**（如"正在求解中..."、"正在验证解法..."），继续动作 B |
    | 返回 `"Process still running"` 或 `"(no new output)"` | 脚本运行中，无新输出 | 继续动作 B |

   **动作 B — sleep 等待**：

   ```
   tool: exec
   command: sleep <SLEEP_SEC>
   yieldMs: 120000
   ```

   - **`<SLEEP_SEC>` 取值**：简单题目为 `30`，IMO 题目为 `120`
   - **`yieldMs` 固定为 `120000`**（环境上限），无论 sleep 多久都传此值
   - 简单题（sleep 30）：sleep 会在 30 秒后正常返回，随后继续 poll
   - IMO 题（sleep 120）：sleep 刚好在 120 秒时被 exec yield 返回（yieldMs 上限），一轮完整等待 2 分钟，随后继续 poll
   - sleep 返回后直接回到动作 A，继续 poll

   **沉默约束⚠️**：
   - ❌ 不要调用 `tail`、`grep`、`cat` 日志等任何其他命令
   - ❌ 不要思考"是不是该汇报进度"、"看看日志怎么样了"
   - ✅ poll 返回 `=== PROGRESS ===` 时，**简短转述进度给用户**（一句话即可，如"正在求解中..."、"正在验证解法..."）
   - ✅ poll 返回 `"Process still running"` 时，**不输出任何内容**，直接进入动作 B
    - ✅ poll 返回 `=== RESULT ===` 时，**将完整结果转述给用户**，进入步骤四
    - ✅ **累计等待时间只能来自 `=== HEARTBEAT ===` 的 `elapsed` 值，禁止凭感觉或轮数估算"已过几分钟"**
    - ✅ **唯一允许的循环动作：poll → sleep → poll → sleep → ... 直到拿到结果**

    **超时判断（以 `=== HEARTBEAT ===` 行的 `elapsed=<秒>` 为唯一依据，禁止自行估算累计时间）**：
    - 简单题目：`elapsed` 超过 `1200`（20 分钟）仍未完成，停止循环，向用户报告超时
    - IMO 题目：`elapsed` 超过 `3600`（60 分钟）仍未完成，停止循环，向用户报告超时
    - ⚠️ 严禁凭"轮询轮数 × sleep 间隔"或主观感觉估算"已过几分钟"——该方式与真实墙钟严重不符。唯一可信来源是心跳行的 `elapsed` 数值。

4. **解析结果**：

   - 从 poll 返回中找到 `=== RESULT ===` 标记后的 JSON
   - 正常返回格式：`{"streamInfo": {"streamContent": "...", "streamType": "final", ...}}`
   - 错误返回格式：`{"error": {"code": "TIMEOUT"|"NETWORK_ERROR"|"CONFIG_ERROR"|"NO_FINAL_RESULT"|"EMPTY_FINAL_RESULT"|"<errorCode>", "message": "..."}}`
   - 脚本退出码：成功为 0，失败为 1

5. **返回结果**：将脚本返回的 `streamInfo.streamContent` 中的解答结果以清晰、易于理解的方式呈现给用户。如果返回中包含逐步推导过程，保持步骤完整呈现。

6. **错误处理**：

   - 如果脚本返回 `error` 对象或退出码非 0，向用户说明求解失败
   - 退出码非 0 时（含 `TIMEOUT`、`NETWORK_ERROR`、`NO_FINAL_RESULT`、`EMPTY_FINAL_RESULT` 等所有错误码），最多重试一次，仍失败则由模型自身推理回答
   - `CONFIG_ERROR` 不重试，直接向用户报告配置缺失
   - 如果用户的问题不完整或存在歧义，先向用户确认补充后再调用

## 处理要点

- **必须通过 ~/.openclaw/workspace/skills/imo-solver/scripts/imo_agent_invoke.py 脚本调用 IMOAgent 服务求解，禁止凭自身知识直接给出数学解答或推导过程**；即使答案显然，也必须以脚本返回结果为准。
- **参数完整性**：`query` 为必填参数，必须为非空且语义完整的数学问题。`requestId`、`sessionId` 由脚本内部自动生成，无需传入。
- **题目分类**：根据难度分为简单题目（解方程、求导、积分等）和 IMO 题目（竞赛证明题），分别用 `sleep 30` 和 `sleep 120` 轮询。难以判断时按 IMO 处理。
- **超时控制**：脚本整体超时由 `timeout 3600`（60 分钟）控制。简单题目轮询超时 20 分钟，IMO 题目轮询超时 60 分钟。
- **stdout 格式**：脚本运行中输出三类行（均 flush 实时刷新）：`=== HEARTBEAT === <时间戳> elapsed=<秒>`（每 30 秒，供判超时）、`=== PROGRESS === <内容>`（解题中间状态）、结束时 `=== RESULT ===` 后紧跟完整 JSON。poll 返回中按这三个标记区分心跳、进度和最终结果。
- **轮询纪律**：poll 返回 `=== RESULT ===` 时转述完整结果；返回 `=== PROGRESS ===` 时简短转述进度给用户；返回 `=== HEARTBEAT ===` 时读取 `elapsed` 判超时但不输出给用户；返回 running 时保持沉默。累计等待时间以心跳 `elapsed` 为准，禁止主观估算。不读日志、不调用其他工具，只做 `poll → sleep` 循环。
- **重试策略**：脚本退出码非 0（含 `TIMEOUT`/`NETWORK_ERROR`/`NO_FINAL_RESULT`/`EMPTY_FINAL_RESULT` 等所有错误码）最多重试一次，仍失败则由模型自身推理回答。`CONFIG_ERROR` 属配置问题不重试。
- **数学格式**：如果结果中包含数学公式，保持其原有格式（LaTeX 等）以便用户阅读。
- **日志排查**：脚本运行日志写入 `~/.openclaw/workspace/skills/imo-solver/scripts/logs/imo_agent_invoke.log`，仅供异常排查使用，无需在对话中读取或轮询。