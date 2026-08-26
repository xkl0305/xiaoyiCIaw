# Evolution Proposal: kdocs-cli 升级跨文件系统 rename 失败的处理

- Created-At: 2026-08-19 15:19
- Target-File: TOOLS.md
- Trigger-Type: struggle

## Why This Matters
- kdocs-cli / 类似下载到 /tmp 解压后再 install 的 CLI 工具，升级时 `rename` 常因跨文件系统（/tmp 挂载与 ~/.local/bin 不同设备）报 `invalid cross-device link` 而失败
- 第一次 `kdocs-cli upgrade -y` 就复现，属于通用、可复现、对未来工具排错有帮助的坑

## Evidence
- `kdocs-cli upgrade -y`（2.5.7→2.6.2）执行到替换二进制时报：`Replace failed: rename /tmp/.../kdocs-cli ...: invalid cross-device link`
- 版本号未变（仍是 2.5.7）
- 用 setup.sh 确认了真实下载 URL 构成：`${CDN_BASE}/v${version}/releases/kdocs-cli-${version}-${os}-${arch}.tar.gz`（CDN_BASE=`https://wpsai.wpscdn.cn/skillhub/pro`），带 checksums.txt 可校验
- 手动下载解压后 `cp -f <bin> ~/.local/bin/kdocs-cli` 替换成功，版本升级到 2.6.2，认证（加密 token）不受影响

## Conflict Points
- None（TOOLS.md 无 kdocs / CLI 升级相关经验，不冲突）

## Plan
1. 在 TOOLS.md 追加一条「CLI 工具升级 `invalid cross-device link` 处理」经验：
   - kdocs-cli 等安装器解压到 /tmp、目标在 ~/.local/bin，升级时 `rename` 跨设备会失败
   - 解法：手动下载最新版到本地 → 解压 → `cp -f` 替换目标二进制 → `chmod +x`
   - 真实下载 URL 格式：`${CDN_BASE}/v${version}/releases/<bin>-<version>-<os>-<arch>.tar.gz`
2. 追加到 TOOLS.md 末尾（追加文本如下），保持精简
