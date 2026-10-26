# Evolution Proposal: 火山引擎 ARK 直连两处 bug 修复

- Created-At: 2026-10-24 09:07
- Target-File: TOOLS.md

## Why This Matters

火山引擎(ARK)通道配置在、网络通、key 有效，但直连一直实际失效：两个代码 bug 让 ARK 直连从未真正在出图里用到。本次修复并实测跑通"带参考图的 ARK 直连出图"。

## Evidence

- 用户原话：「火山引擎」多次确认通道在不在 → 实测发现直连失效 → 确认修复
- Bug① URL 拼接重复：`SEEDREAM_API_URL`(`.xiaoyienv`)=`ark.cn-beijing.volces.com/api/v3` 已含 `/api/v3`，但 `seedream_provider.py` 里 `base + '/api/v3/images/generations'` 又拼一次 → 请求 `.../api/v3/api/v3/images/generations` 重复路径，`generate_image(channel='ark')` 报 `HTTP 0`(连接层失败)
- Bug② has_ark 判定缺陷：`cli_generate.py` 里 `has_ark` 检查 `provider_env().url`(即第一通道 huawei_sse 的 url)是否含 volces.com → 恒 False → ARK 分支永不触发、CLI 永远走 SSE
- 修复：① base 以 `/api/v3` 结尾或含 `/v1` 时直接拼 `/images/generations`;② `has_ark` 改用 `_load_all_channel_configs()` 查 `name=='ark'` 且 url 含 volces.com,并显式 `channel='ark'`
- 实测：`cli_generate --no-dry-run` → `generation_channel: ark_direct`、`channel_used: ark`、model `doubao-seedream-5-0-260128`、`image_generated: True`、无 provider_error;备份 `.bak-arkfix`

## Conflict Points

- TOOLS.md 已有 ARK 通道配置备份(382-415 行)+「人格视角出图·真出图 CLI 与 MAINCHAIN_PROOF_KEY」条目(664 行起,含"通道 fallback:无 ARK 直连环境自动走 SSE""参考图通道差异:必须走 ARK 才带参考图"),但**未记录** ARK 直连两个 bug 及"已修复可用"最新状态 → 同主题新增补充,不构成冲突

## Plan

在 TOOLS.md「人格视角出图·真出图 CLI 与 MAINCHAIN_PROOF_KEY」条目之后,新增独立小节「火山引擎 ARK 直连修复(2026-10-24)」:

```
### 火山引擎 ARK 直连修复(2026-10-24 固化)

**背景:** ARK 通道配置在、网络通、key 有效,但直连长时间实际失效——两个代码 bug 让 ARK 直连从未真正走到。已修复并实测跑通带参考图的 ARK 直连出图。

**两个 bug:**
1. **URL 拼接重复**(`seedream_provider.py`):`SEEDREAM_API_URL`=`ark.cn-beijing.volces.com/api/v3` 已含 `/api/v3`,代码又拼一次 → `.../api/v3/api/v3/images/generations` 重复路径,`generate_image(channel='ark')` 报 HTTP 0。修复:base 以 `/api/v3` 结尾或含 `/v1` 时直接拼 `/images/generations`。
2. **has_ark 判定缺陷**(`cli_generate.py`):原判断检查 `provider_env().url`(=第一通道 huawei_sse 的 url)是否含 volces.com → 恒 False、ARK 分支永不触发、CLI 永远走 SSE。修复:改用 `_load_all_channel_configs()` 查 `name=='ark'` 且 url 含 volces.com,并显式 `channel='ark'`。

**实测验证(2026-10-24):** `cli_generate --no-dry-run` → `generation_channel: ark_direct`、`channel_used: ark`、model `doubao-seedream-5-0-260128`、`image_generated: True`、无 provider_error,出图落 `.persona_visual/generated/seedream_ark_*.png`。

**注意:** 备份 `.bak-arkfix`。siliconflow 的 url 配置带完整 `/v1/images/gen` 路径,同样会拼出重复 `/images/generations`(原有问题,不在 ARK 本次范围)。
```
