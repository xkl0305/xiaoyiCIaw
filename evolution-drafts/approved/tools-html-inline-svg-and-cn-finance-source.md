# Evolution Proposal: HTML图表用内联SVG + 国内财经数据源取数

- Created-At: 2026-09-18 19:48
- Target-File: TOOLS.md
- Trigger-Type: struggle

## Why This Matters
生成 HTML 报告/页面时，图表若引用外部 CDN 脚本（如 Chart.js bootcdn），在部分网络环境下加载不出导致图表空白（本次金价报告实际踩坑）；且沙箱网络对外网财经源不通、对国内源可达。固化这两条，避免重复踩坑。

## Evidence
- 金价报告首版用 Chart.js(bootcdn) 画折线图，用户反馈"走势总览那块什么也看不见"
- 改为内联 SVG 折线图后，零外部依赖，任何网络可稳定显示（修复成功）
- 沙箱 curl 测试：tradingeconomics/jinse 等外网源不通(000/ENOTFOUND)，baidu/eastmoney/sina/jin10 均可达(200)
- 实时金价：curl -H "Referer: https://finance.sina.com.cn" "https://hq.sinajs.cn/list=hf_XAU,hf_GC" 可拿到伦敦金/纽约金现价（返回GBK需iconv）
- 历史K线：东财 push2/push2his kline、新浪期货 getKLineData 在本环境返回空/报错，勿反复尝试

## Conflict Points
None

## Plan
1. 在 TOOLS.md 追加「HTML 图表渲染」规则：生成 HTML 报告/页面的图表一律用**内联 SVG/CSS 自绘**，禁止依赖外部 CDN 脚本（如 Chart.js），否则部分网络下图表空白。
2. 在 TOOLS.md 追加「沙箱网络与财经数据源」规则：
   - 外网财经源(tradingeconomics等)不可达，国内源(baidu/eastmoney/sina/jin10)可达
   - 实时金价用：`curl -H "Referer: https://finance.sina.com.cn" "https://hq.sinajs.cn/list=hf_XAU,hf_GC"`（GBK编码按需iconv）
   - 东财/新浪历史K线接口在本地不通，勿反复尝试；历史走势可用公开知识+实时价锚定
