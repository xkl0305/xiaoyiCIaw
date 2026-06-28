---
name: salary-tax-calculator
description: >-
  薪酬个税计算器与异常检测 — 内置最新各地社保/公积金比例及个税算法，
  支持联网搜索和知识库搜索。输入工资数据自动计算应发/实发；
  支持上传上月与本月工资表，自动比对差异，标记异常波动。
  适用场景：HR核算工资、薪酬专员核对个税、财务审计工资异常、
  个人计算税后收入、社保公积金测算。
trigger_keywords:
  - 工资计算、个税计算、社保计算、公积金计算、五险一金
  - 税后工资、税前工资、实发工资、应发工资
  - 工资异常、工资差异、工资对比、薪酬审计
  - 专项附加扣除、个税专项、个税抵扣
  - 社保基数、公积金基数、社保比例
  - 薪酬、算薪、发薪、工资条
  - salary、tax、payroll、social insurance
agent_created: true
---

# 薪酬个税计算器与异常检测

## 概述

本技能是 HR 薪酬核算与审计的智能工具箱，核心能力：
1. **工资计算**：输入税前工资/社保公积金基数，自动计算五险一金、个税、实发工资
2. **异常检测**：上传两期工资表，自动对比差异，标记异常波动
3. **联网查询**：支持联网搜索最新社保基数、公积金比例等政策
4. **报告生成**：可视化 HTML 报告，含工资构成饼图、个税阶梯图、异常波动仪表盘

## 适用场景

| 场景 | 触发示例 | 处理方式 |
|------|---------|---------|
| 单人工资计算 | "北京月薪25000，社保基数按实际，帮我算税后多少" | `tax_calculator.py` 直接计算 |
| 批量工资计算 | "帮我算这个Excel里所有人的实发工资" | `salary_parser.py` 解析 → `tax_calculator.py` 批量计算 |
| 月度差异对比 | "这是上个月和这个月的工资表，看看谁的变化比较大" | `salary_parser.py` 解析 → `anomaly_detector.py` 对比 |
| 政策查询 | "2026年北京社保基数上下限是多少" | 联网搜索 / 知识库检索 |
| 报告输出 | "生成这份工资的详细报告" | `report_generator.py` 生成 HTML |

## AI 工作流

### 场景 1：单人/批量工资计算

```
1. 确认城市和社保公积金基数（基数默认按实际工资，有上下限）
2. 确认专项附加扣除项目（如用户未提供，默认 0）
3. 调用 tax_calculator.py --city <城市> --gross <税前工资> [--base <社保基数>] [--deductions <专项扣除>]
4. 解析 JSON 结果，展示：
   - 税前工资
   - 社保个人部分（养老/医疗/失业）
   - 公积金个人部分
   - 应纳税所得额
   - 个税金额
   - 实发工资
5. 如用户要求报告，调用 report_generator.py 生成 HTML
```

### 场景 2：月度工资差异比对与异常检测

```
1. 确认两个工资表文件路径（上月/本月）
2. 调用 salary_parser.py 解析两个文件
3. 调用 anomaly_detector.py --prev <上月JSON> --curr <本月JSON> --output <结果JSON>
4. 解析异常结果，分类展示：
   - 🔴 严重异常（≥3σ偏离）
   - 🟡 注意（2-3σ偏离）
   - 🟢 正常
5. 调用 report_generator.py --anomaly <异常JSON> 生成可视化报告
```

### 场景 3：政策查询

```
1. 识别查询意图（社保基数/公积金比例/个税政策/专项扣除标准）
2. 优先查本地 references/ 知识库
3. 如需最新数据，发起联网搜索
4. 以表格形式展示结果，标注数据来源和更新时间
```

## 脚本说明

| 脚本 | 功能 | 输入 | 输出 |
|------|------|------|------|
| `scripts/tax_calculator.py` | 核心计算引擎 | 城市/税前工资/基数/专项扣除 | JSON：工资构成明细 |
| `scripts/salary_parser.py` | 工资表解析 | Excel/CSV 文件路径 | JSON：标准化工资数据 |
| `scripts/anomaly_detector.py` | 异常检测 | 两期工资 JSON | JSON：差异分析+异常标记 |
| `scripts/report_generator.py` | 报告生成 | 计算结果/异常数据 JSON | HTML 可视化报告 |

## 参考数据

| 文件 | 内容 |
|------|------|
| `references/city_rates.json` | 各城市五险一金个人/单位比例及基数上下限 |
| `references/tax_brackets.json` | 综合所得个税累进税率表（含速算扣除数） |
| `references/deduction_rules.json` | 7项专项附加扣除标准 |
| `references/policy_links.json` | 各地人社局/税务局官网链接 |

## 依赖

- Python 3.8+
- openpyxl（Excel 解析）
- pandas（数据处理）
- 无需 GPU，纯 CPU 计算

安装：`pip install openpyxl pandas`
