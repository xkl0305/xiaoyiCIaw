# 种子提案: seedream 生图排错与 size 支持实测

- **日期**: 2026-09-26
- **状态**: approved
- **进化项**: 固化 huawei_sse 通道 size 支持边界与生图排错流程到 TOOLS.md
- **修改文件**: TOOLS.md(新增「seedream 生图排错与 size 支持实测」段)

## 经验规则
1. huawei_sse 通道仅支持 2K/3K;4K / 4K-square / 4K-wide / 4K-portrait 全不支持,报 provider_returned_no_image。
2. .xiaoyienv 各通道 API key 可能全空 → 退化成单通道,用「Seedream 通道配置备份」补回 ARK/SILICONFLOW。
3. 排错顺序:查通道数 → 排除 size(不带 size 单测) → 确认 size 在目标通道支持范围 → 带完整 prompt。
4. 逐个变量隔离(通道/size/negative/prompt),勿叠加下结论、勿盲目重试。
5. 竖版海报用 2K/3K + prompt 强调"竖版构图",勿传 4K-portrait。

## 依据
- 实测矩阵:2K/3K generated;4K 系全 no_image(同 prompt 唯一变量 size)。
- 对比测试:同 huawei_sse + 同 prompt,无 size 成功、带 4K-portrait 失败,多次复现。
