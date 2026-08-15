# 错误处理指南

麦当劳 MCP 服务的错误处理规范，所有业务域通用。调用方式与 Token 配置见 [tool-calling-strategy.md](tool-calling-strategy.md)（文首「标准工作流程」）。

## HTTP 错误

| HTTP 状态码 | 含义 | 处理方式 |
|------------|------|---------|
| 401 | Token 无效或已过期 | 调用 `HuaweiIDTool("mcd-skills", "117797261")` 刷新 Token |
| 429 | 请求过于频繁（限 600 次/分钟） | 稍后重试 |
| 5xx | 服务端异常 | 提示用户稍后重试 |

## 业务错误码

| 错误码 | 含义 | 用户友好提示 |
|--------|------|-------------|
| `510001` | 积分不足 | 建议点餐攒积分 |
| `5100003` | 库存不足 | 建议换个商品 |
| `5100011` | 触发限购 | 建议换个商品 |
| `56300002` | 卡券兑换失败 | 建议稍后重试或换商品 |

## 处理原则

- 错误码不直接暴露给用户，优先展示接口返回的友好文案（如 `message`）
- 当 `data` 为 `null` 时，通常表示操作未成功，需结合 `message` 给出可执行建议（重试、换商品、检查 Token 等）
- 部分成功场景（如批量领券部分失败），需分别汇总成功与失败项，避免只报一半结果

## JSON-RPC / MCP 调用异常（脚本或网关）

- 若返回体不是预期 JSON 或缺少 `result`，先检查网络、URL、`Authorization` 是否与 [tool-calling-strategy.md](tool-calling-strategy.md) 一致
- `tools/call` 返回的 `error` 对象：将可读信息转述给用户，技术细节不展开

## 管道过滤异常（`call_tool_for_genui.sh --filter_mode`）

当 `call_tool_for_genui.sh --extract` 的输出通过管道传给 `call_tool_for_genui.sh --filter_mode meals` 时，可能出现以下异常：

| 异常场景 | 原因 | 处理方式 |
|----------|------|----------|
| `错误: 未收到数据` | 上游命令无 stdout 输出（如网络超时） | 重试一次；仍失败则提示用户稍后再试 |
| `错误: 上游返回非 JSON 数据` | `--extract` 检测到 `success: false`，输出了 markdown 格式的错误文本 | 检查 stderr 中的关键行，修正参数后重试 |
| `接口错误: {message} (code=xxx)` | 上游返回了 JSON 但 `success: false` | 根据 code 对照上方业务错误码表处理 |

**处理原则**：

1. `call_tool_for_genui.sh --filter_mode` 的错误输出到 stderr，调用时用 `2>&1` 合并才能在对话上下文中看到
2. 遇到参数错误（如 `检查必填参数`）时，运行 `bash scripts/discover_tools.sh --json` 实时查询工具 schema，确认必填字段，修正后重试
3. 不要将 filter 的 stderr 错误信息暴露给用户，转述为友好提示即可
