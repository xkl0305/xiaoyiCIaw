# 种子提案: 通用补丁器支持 env_restore 型,纳入 seedream 通道配置补回

- **日期**: 2026-09-26
- **状态**: approved
- **进化项**: 通用补丁器(patch_autoheal)新增 env_restore 目标类型,守护 seedream 通道配置补回
- **修改文件**: scripts/patch_autoheal.py + scripts/patch_autoheal_config.json

## 变更内容
1. patch_autoheal.py 新增 `env_restore` 类型:检查目标 env 文件必需 key 是否齐全,缺则从 sourceFile(TOOLS.md 备份)正则提取补写,补写前自动备份(`.bak-envrestore-`)。
2. config 追加 `seedream-channel-env-restore` 目标:守护 `.xiaoyienv` 的 SEEDREAM_API_URL/KEY/ENDPOINT_ID + SILICONFLOW_API_URL/KEY 五键。
3. daemon 每次 subprocess 调脚本时重读 config,新目标自动生效,无需重启 daemon。

## 测试结论
- 语法 py_compile 通过;完整运行 3 目标全"齐全"退出码 0。
- env_restore 逻辑:check 正确报缺失 → patch 从 TOOLS.md 提取补写 → 再跑报"齐全",保留无关 key。
- 备份:patch_autoheal.py.bak-envrestore-20260926-130135 / config.bak-envrestore-20260926-130135。

## 背景
.xiaoyienv 通道 key 曾全空→seedream 退化单通道→huawei_sse 生图全失败。纳入守护后,daemon 每小时自检能自动补回,防止再次裸奔无兜底。
