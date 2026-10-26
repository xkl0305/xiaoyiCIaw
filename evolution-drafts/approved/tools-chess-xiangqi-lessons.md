# 进化提案：中国象棋开发三大坑 + 交叉点落子几何（TOOLS.md 补 r / s）

日期：2026-10-26
状态：✅ 已确认落盘（俞哥确认）
落盘文件：TOOLS.md canvas 棋盘游戏经验区

## 背景
大师级人机中国象棋开发中暴露多类可复用坑。用户反馈"棋子都在表格里不在线上"直接点出最典型的一类几何错误。

## 补 r) 走子类棋盘游戏三大坑（伪走法解构 / AI undo 索引 / 回调传参）
1. 伪走法解构错：`for(const[t]of pseudo(r,c))` 解构出 `t=tr(数字)`，pseudo 返回 `[tr,tc]`，导致 `t[0]` undefined，走法静默丢失 → 应 `for(const[tr,tc]of ...)`
2. AI 搜索 undo 索引错位：move=`[fr,fc,tr,tc]`，undo 必须 `board[m[0]][m[1]]=board[m[2]][m[3]]`，写成 `m[1][m[2]]/m[3][m[4]]`（m[4] undefined）污染棋盘
3. 事件回调传参不匹配：`commit(sel[0],sel[1],r,cc)` 而非 `commit(sel,r,cc)`

## 补 s) 象棋类交叉点落子几何
- 标准象棋棋子圆心在**交叉点** `(pad+cc*cell,pad+r*cell)`，不是格子中心 `(+cell/2)`
- 几何：cell=w/8、margin≥半径(取cell/2)、画布高=2margin+9cell
- 验证：canvas 像素校验「交叉点有棋+格中央为空」

## 验证
- 补 r：修复后 AI 走子不污染棋盘（前后指纹一致）、AI 走法在 genLegal 内
- 补 s：v2 32 子交叉点全有棋、格中心 6/6 空、image_reading 确认交叉点落子
