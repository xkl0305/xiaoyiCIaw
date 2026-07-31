---
name: imo-solver
description: 
  小艺数学解题技能，支持各类数学问题和IMO题目，主要是求解和证明类数学问题，当用户提出**纯数学学科性**问题（解方程、求积分/导数/极限、化简表达式、几何证明、数列求和、线性代数运算、概率统计推导等）时使用，涉及生活实务计算（运费、折扣、账单、单位换算）不触发。
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

## 会话初始化（环境检查完成后立即执行）

```bash
export IMO_SESSION_ID="${IMO_SESSION_ID:-$(uuidgen 2>/dev/null || $PYTHON_CMD -c 'import uuid; print(uuid.uuid4())')}"
export IMO_SESSION_DIR="/tmp/imo/$IMO_SESSION_ID"
mkdir -p "$IMO_SESSION_DIR"
echo "会话 ID：$IMO_SESSION_ID"
echo "会话目录：$IMO_SESSION_DIR"
```

| 变量 | 路径 |
|------|------|
| `~/.openclaw/workspace/skills/imo-solver` | 本 skill 根目录（由运行环境注入） |
| `~/.openclaw/workspace/skills/imo-solver/scripts/` | 脚本目录 |
| `$IMO_SESSION_DIR` | `/tmp/imo/$IMO_SESSION_ID/` |
| `/tmp/imo/$IMO_SESSION_ID/generate.log` | 运行日志 |

**会话初始化无需向用户汇报。**

---

## 触发条件

**精确触发**：以下场景应当触发Skill：

- 用户提出明确的**纯数学学科性**问题：解方程、求积分、求导数、求极限、化简表达式、几何证明、数列求和、概率计算、线性代数运算等
- 用户说"帮我算一下"、"解一下"、""求解"、"计算"、"推导"、"证明"、"求证"等后面跟数学内容
- 用户给出数学表达式、公式、方程要求解答或计算

**不触发**（以下情况应视为不相关，返回通用能力，无需执行流程调用IMOAgent）：
- 非数学类的通用问答、编程、写作等
- 虽然包含数字但非数学解题场景，如生活实务计算（运费、折扣、账单、单位换算）（"帮我算3个盒子的运费"）

---

## 执行流程

1. **分析数学问题**：理解用户提出的数学问题类型（代数、几何、微积分、概率统计等），确认问题完整、可解。

2. **调用IMOAgent求解**：
   - 将用户的数学问题完整组装到 `query` 参数中
   - 调用方式：
     ```bash
     echo "$IMO_SESSION_ID"
     echo "$IMO_SESSION_DIR"
     IMO_SESSION_ID="$IMO_SESSION_ID"
     IMO_SESSION_DIR="/tmp/imo/$IMO_SESSION_ID"
     IMO_SESSION_ID="$IMO_SESSION_ID" \
       $PYTHON_CMD ~/.openclaw/workspace/skills/imo-solver/scripts/imo_agent_invoke.py \
       "<完整的数学问题描述>" \
       --log-dir "$IMO_SESSION_DIR" \
       > /dev/null 2>&1 &
     
     IMO_PID=$!
     echo "IMO 解题任务已启动"
     echo "PID：$IMO_PID"
     echo "日志：/tmp/imo/$IMO_SESSION_ID/generate.log"
     ```

   **关于命令末尾的 `> /dev/null 2>&1 &`**：
   - `> /dev/null` 丢弃 stdout，`2>&1` 把 stderr 也合并到 stdout（一并丢弃），`&` 让任务进入后台并把 PID 写入 `$!`
   - **不通过 exec 的 stdout 监控脚本进度**：Python 脚本内部已将结构化进度写入 `$IMO_SESSION_DIR/generate.log`，监控逻辑统一从该日志文件读取
   - 这样做避免后台进程被未读取的 stdout 缓冲区阻塞、防止脚本内部输出污染对话上下文

   **完成汇报**：
   ```
   ✅ 数学解题任务已启动，开始监控进度...
   ```

3. **监控进度**：

   **目标**：每 15 秒读取一次日志文件，向用户持续汇报解题进展。

   > **监控原则**：**仅通过 `tail` 读取 `generate.log` 判断进度和完成状态**，不使用 `kill -0`、`process poll` 等进程探测方式。脚本会在日志中写入进度标记，监控逻辑通过识别这些标记决定是否退出循环。

   ### 3.1 监控循环（每 15 秒执行一次，最多 80 次）

   初始化计数器后开始轮询：

   ```bash
   IMO_POLL_COUNT=0
   IMO_POLL_MAX=80
   ```

   每轮执行：

   ```bash
   IMO_POLL_COUNT=$((IMO_POLL_COUNT + 1))
   # 读取最新5行了解当前进度
   tail -5 "$IMO_SESSION_DIR/generate.log"

   # 用 grep 搜索整个日志判断终止条件（因为解题结果可能很长，tail 可能看不到标记）
   if grep -q "✅ 解题完成" "$IMO_SESSION_DIR/generate.log" 2>/dev/null; then
     echo "解题完成！"
     break
   fi

   if grep -qE "\[ERROR\]|服务端错误" "$IMO_SESSION_DIR/generate.log" 2>/dev/null; then
     echo "检测到错误，停止监控。"
     break
   fi
   ```

   **终止条件**（通过 `grep` 搜索整个日志文件判断）：

   1. 日志中出现 `✅ 解题完成` 标记 → 结束监控，进入步骤四
   2. 日志中出现 `[ERROR]` 或 `服务端错误` → 结束监控，向用户报告失败并附上日志路径
   3. 否则等待 15 秒后进入下一轮

   **当 `IMO_POLL_COUNT` 达到 `IMO_POLL_MAX`（80 次，约 20 分钟）时**，即使日志未出现完成/失败标记，也停止轮询，向用户报告超时，并告知日志路径供手动查看。

   ### 3.2 日志解读与汇报

   根据日志内容，向用户汇报当前阶段：

   | 日志包含 | 向用户汇报 |
   |---------|-----------|
   | `[进度]` | 显示解题推理中间过程 |
   | `[等待中]` | 「IMOAgent仍在处理中...」 |
   | `✅ 解题完成` | 「解题完成，停止监控，进入步骤四...」 |
   | `[ERROR]` 或 `服务端错误` | 向用户报告错误信息 |

   ### 3.3 终止条件判断

   | 状态                              | 处理方式                                                 |
   |---------------------------------|------------------------------------------------------|
   | 进程运行中，且未超时                      | 继续等待 15 秒，再次检查                                       |
   | 进程已退出 + 日志含 `✅ 解题完成`            | **停止轮询，进入步骤四**                                       |
   | 进程已退出 + 日志含 `[ERROR]` 或 `服务端错误` | 向用户报告错误信息，停止                                         |
   | 进程已退出 + 无任何终止标记                 | 向用户报告异常崩溃，询问是否重试                                     |
   | 轮询次数达到 80 次（约 20 分钟）            | 停止轮询，向用户报告超时，并告知日志路径：`$IMO_SESSION_DIR/generate.log` |

   **必须遵守⚠️⚠️⚠️：generate.log未输出ERROR错误则保持输出，即使监控超时也不要由模型推理回答，后续根据generate.log结果回答，无需模型推理回答！！！**

4. **返回结果**：

   **目标**：从 `generate.log` 中提取解题结果，以清晰、易于理解的方式呈现给用户。

   ```bash
   cat "$IMO_SESSION_DIR/generate.log"
   ```

   从日志中提取 `完整解题结果` 相关行之后的 `Solution` 内容，将解答结果呈现给用户。如果返回中包含逐步推导过程，保持步骤完整呈现。
   **必须遵守⚠️⚠️⚠️：generate.log未输出ERROR错误则保持输出，即使监控超时也不要由模型推理回答，后续根据generate.log结果回答，无需模型推理回答！！！**

5. **错误处理**：
   - 如果脚本返回 `error` 对象或退出码非 0，向用户说明求解失败
   - 脚本遇到ERROR错误，最多重试一次，仍失败则由模型自身推理回答。
   - **generate.log未输出ERROR错误则保持输出，即使监控超时也不要由模型推理回答，后续根据generate.log结果回答，无需模型推理回答！！**
   - 如果用户的问题不完整或存在歧义，先向用户确认补充后再调用

**必须遵守⚠️⚠️⚠️：generate.log未输出ERROR错误则保持输出，即使监控超时也不要由模型推理回答，后续根据generate.log结果回答，无需模型推理回答！！！**

## 处理要点
- **必须通过 ~/.openclaw/workspace/skills/imo-solver/scripts/imo_agent_invoke.py 脚本调用IMOAgent服务求解，禁止凭自身知识直接给出数学解答或推导过程**；即使答案显然，也必须以脚本运行的generate.log结果为准。
- **禁止凭自身知识直接给出数学解答或推导过程；即使答案显然，也必须以脚本运行的generate.log结果为准。**
- **参数完整性**：`query` 为必填参数，必须为非空且语义完整的数学问题。`requestId` 由脚本内部自动生成，无需传入。
- **超时控制**：监控循环最多 120 次（约 20 分钟）。
- **重试策略**：脚本遇到ERROR错误最多重试一次，仍失败则由模型自身推理回答。**generate.log未输出ERROR错误则保持输出，不要由模型推理回答，后续根据generate.log结果回答，无需模型推理回答！！**
- **数学格式**：如果结果中包含数学公式，保持其原有格式（LaTeX 等）以便用户阅读。
- **日志监控**：脚本后台运行，所有进度和结果写入 `$IMO_SESSION_DIR/generate.log`，通过 `tail` 读取日志监控进度和获取结果。