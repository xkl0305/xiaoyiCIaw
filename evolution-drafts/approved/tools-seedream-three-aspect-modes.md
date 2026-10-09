# 种子提案: seedream 横/竖/正方形三形态构图结论补充

- 日期: 2026-10-01
- 状态: approved
- 进化项: TOOLS.md「seedream 生图排错与 size 支持实测」段补充三形态构图结论
- 修改文件: TOOLS.md(376行结论段扩充)

## 经验规则
1. 横/竖/正方形三形态统一靠 prompt 构图词实现(2026-10-01 实测全通过):竖版写"竖长海报/竖版构图"、横版写"横向宽画幅横幅构图"、默认即方形。
2. 勿靠 --size 参数控比例:huawei_sse 上 4K 系(4K/4K-square/4K-wide/4K-portrait)全 no_image,只用 2K/3K。
3. max-images 多图组图场景同样适用该规则。

## 依据
- 横屏/竖屏/正方形三形态均用 prompt 构图词+默认尺寸实测成功;4K 系此前实测全 no_image。
