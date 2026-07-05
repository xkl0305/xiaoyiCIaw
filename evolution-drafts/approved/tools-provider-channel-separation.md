# Evolution Proposal: Provider 多通道默认优先级分离模式

- Created-At: 2026-07-06 00:02
- Target-File: TOOLS.md
- Trigger-Type: workflow, explicit-instruction

## Why This Matters

seedream_provider.py 实现了多通道图生系统，但不同调用方（skill vs 人格视角出图）需要不同的默认通道优先级。以前是硬编码 provider_env 里的顺序，现在通过 channel 参数的逗号分隔列表机制实现了调用方级别的默认分离——调用方传不同的 channel 值即可，不需要改 provider 内部逻辑。

这是一个可复用的模式：以后加第四个通道、新系统调图，都按这个套路走。

## Evidence

- 用户明确要求"seedream-image-gen的三通道与人格视角出图的双通道区分开，默认优先顺序不同"
- 实现方案：seedream_provider.generate_image() 的 channel 参数支持逗号分隔列表
  - 不传 channel → 三通道全开：huawei_sse → ark → siliconflow
  - 传 channel='ark,huawei_sse' → 仅这俩通道，按列表顺序 fallback
- 修改点只有一行（桥接层传 channel 参数的值），不需要动 provider 内部

## Conflict Points

None

## Plan

在 TOOLS.md 中追加以下内容：

### seedream-provider 多通道调用规则

`seedream_provider.generate_image()` 的 `channel` 参数支持逗号分隔列表：

- **不传 channel** → 所有可用通道按注册顺序 fallback（当前注册顺序：huawei_sse → ark → siliconflow）
- **传单通道** → 只用该通道
- **传多通道列表**（如 `"ark,huawei_sse"`）→ 只走列表内的通道，按列表顺序 fallback

**当前两个系统的默认配置：**

| 调用方 | channel 参数 | 生效通道 | fallback 顺序 |
|:------|:------------:|:--------:|:-------------|
| seedream-image-gen skill | 不传 | 三通道 | huawei_sse → ark → siliconflow |
| 人格视角出图（桥接层） | `"ark,huawei_sse"` | 双通道 | ark → huawei_sse（无 siliconflow） |

**加新通道时**：在 `_load_all_channel_configs()` 里加配置即可，各调用方的默认优先级通过改其传的 channel 值控制，不需要动 provider 内部。
