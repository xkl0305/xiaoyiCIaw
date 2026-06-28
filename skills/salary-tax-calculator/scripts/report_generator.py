#!/usr/bin/env python3
"""
薪酬个税可视化报告生成器
输出：自包含 HTML 文件（深色专业主题，内嵌 SVG 图表）
"""

import json
import argparse
import sys
import math
import os
from pathlib import Path
from datetime import datetime

SKILL_DIR = Path(__file__).resolve().parent.parent


def generate_salary_report(salary_data, output_path=None):
    """生成单人/批量工资计算报告"""
    if isinstance(salary_data, dict) and "result" in salary_data:
        employees = [salary_data]
    elif isinstance(salary_data, list):
        employees = salary_data
    else:
        raise ValueError("无效的工资数据格式")

    html = build_html(employees, report_type="salary")
    return save_or_print(html, output_path, "salary_report")


def generate_anomaly_report(anomaly_data, output_path=None):
    """生成异常检测报告"""
    html = build_anomaly_html(anomaly_data)
    return save_or_print(html, output_path, "anomaly_report")


def save_or_print(html, output_path, default_name):
    if output_path:
        if not os.path.isabs(output_path):
            output_path = str(SKILL_DIR / "data" / output_path)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"报告已生成: {output_path}")
        return output_path
    else:
        output_path = str(SKILL_DIR / "data" / f"{default_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"报告已生成: {output_path}")
        return output_path


def build_html(employees, report_type="salary"):
    """构建完整 HTML"""
    # 通用样式
    css = get_css()

    sections = []
    for i, emp in enumerate(employees):
        name = emp.get("name", f"员工{i+1}")
        result = emp.get("result", emp)
        deductions = emp.get("deductions", {})
        inp = emp.get("input", {})

        sections.append(build_employee_card(name, result, deductions, inp))

        if report_type == "salary" and len(employees) == 1:
            sections.append(build_pie_chart_svg(result))
            sections.append(build_tax_breakdown(result, emp.get("tax", {})))

    # 如果有多个员工，生成汇总表
    if len(employees) > 1:
        sections.append(build_summary_table(employees))

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>薪酬个税计算报告</title>
<style>{css}</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>💰 薪酬个税计算报告</h1>
        <div class="subtitle">生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 共 {len(employees)} 人</div>
    </div>
    {''.join(sections)}
    <div class="footer">
        <p>薪酬个税计算器 · 数据仅供参考，以实际发放为准 · 生成于 {datetime.now().strftime('%Y-%m-%d')}</p>
    </div>
</div>
</body>
</html>"""


def build_anomaly_html(anomaly_data):
    """构建异常检测报告 HTML"""
    css = get_css()
    summary = anomaly_data.get("summary", {})
    anomalies = anomaly_data.get("anomalies", [])
    comparisons = anomaly_data.get("comparisons", [])

    sections = []

    # 概览卡片
    sections.append(f"""
    <div class="summary-row">
        <div class="summary-card">
            <div class="card-number">{summary.get('total_employees', 0)}</div>
            <div class="card-label">总人数</div>
        </div>
        <div class="summary-card critical">
            <div class="card-number">{summary.get('anomalies_critical', 0)}</div>
            <div class="card-label">🔴 严重异常</div>
        </div>
        <div class="summary-card warning">
            <div class="card-number">{summary.get('anomalies_warning', 0)}</div>
            <div class="card-label">🟡 需注意</div>
        </div>
        <div class="summary-card info">
            <div class="card-number">{summary.get('anomalies_info', 0) + summary.get('new', 0) + summary.get('departed', 0)}</div>
            <div class="card-label">🟢 人员变动</div>
        </div>
    </div>""")

    # 异常详情
    if anomalies:
        sections.append('<div class="section"><h2>⚠️ 异常详情</h2>')
        for a in anomalies:
            level_class = f"anomaly-{a['level']}"
            level_emoji = {"critical": "🔴", "warning": "🟡", "info": "🟢", "normal": "✅"}.get(a["level"], "")
            sections.append(f"""
            <div class="anomaly-card {level_class}">
                <div class="anomaly-header">
                    <span class="anomaly-name">{level_emoji} {a['name']}</span>
                    <span class="anomaly-type">{a.get('type', '')}</span>
                </div>
                <div class="anomaly-detail">{a.get('summary', a.get('detail', ''))}</div>""")

            if "fields" in a:
                sections.append('<div class="anomaly-fields">')
                for f in a["fields"]:
                    sections.append(f"""
                    <div class="anomaly-field">
                        <span class="field-label">{f['label']}</span>
                        <span class="field-values">¥{f['prev_value']:,.2f} → ¥{f['curr_value']:,.2f}</span>
                        <span class="field-change {f['level']}">{f['direction']} ¥{abs(f['change']):,.2f} ({f.get('change_pct', 0):.1%})</span>
                    </div>""")
                sections.append('</div>')

            sections.append('</div>')
        sections.append('</div>')

    # 对比表
    if comparisons:
        sections.append('<div class="section"><h2>📊 全员对比数据</h2>')
        sections.append('<div class="table-wrapper"><table><thead><tr>')
        headers = ["姓名", "状态", "上月税前", "本月税前", "差异", "上月实发", "本月实发", "差异"]
        for h in headers:
            sections.append(f"<th>{h}</th>")
        sections.append('</tr></thead><tbody>')

        for c in comparisons:
            status_emoji = {"existing": "✅", "new": "🆕", "departed": "⚠️"}.get(c["status"], "")
            if c["status"] == "existing":
                gross_change = c.get("change_gross", 0)
                net_change = c.get("change_net_pay", 0)
                gross_cls = "positive" if gross_change > 0 else "negative" if gross_change < 0 else ""
                net_cls = "positive" if net_change > 0 else "negative" if net_change < 0 else ""
                sections.append(f"""
                <tr>
                    <td>{c['name']}</td>
                    <td>{status_emoji} 在职</td>
                    <td>¥{c['prev_gross']:,.2f}</td>
                    <td>¥{c['curr_gross']:,.2f}</td>
                    <td class="{gross_cls}">{gross_change:+,.2f}</td>
                    <td>¥{c['prev_net_pay']:,.2f}</td>
                    <td>¥{c['curr_net_pay']:,.2f}</td>
                    <td class="{net_cls}">{net_change:+,.2f}</td>
                </tr>""")
            else:
                sections.append(f"""
                <tr>
                    <td>{c['name']}</td>
                    <td>{status_emoji} {'新增' if c['status'] == 'new' else '离职'}</td>
                    <td colspan="6">{"本月新增" if c['status'] == 'new' else "上月离职"}</td>
                </tr>""")

        sections.append('</tbody></table></div></div>')

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>工资异常检测报告</title>
<style>{css}</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>🔍 工资异常检测报告</h1>
        <div class="subtitle">生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
    </div>
    {''.join(sections)}
    <div class="footer">
        <p>薪酬个税计算器 · 异常检测引擎 · 生成于 {datetime.now().strftime('%Y-%m-%d')}</p>
    </div>
</div>
</body>
</html>"""


def build_employee_card(name, result, deductions, inp):
    """构建员工工资卡片"""
    gross = result.get("gross_pay", 0)
    si = result.get("si_personal", 0)
    fund = result.get("fund_personal", 0)
    tax = result.get("tax_amount", 0)
    net = result.get("net_pay", 0)
    company = result.get("company_cost", 0)
    taxable = result.get("taxable_income", 0)

    return f"""
    <div class="section">
        <h2>👤 {name} 工资明细</h2>
        <div class="salary-flow">
            <div class="flow-item gross">
                <div class="flow-amount">¥{gross:,.2f}</div>
                <div class="flow-label">税前工资</div>
            </div>
            <div class="flow-arrow">→</div>
            <div class="flow-deductions">
                <div class="flow-detail">
                    <span>社保</span><span class="deduct">-¥{si:,.2f}</span>
                </div>
                <div class="flow-detail">
                    <span>公积金</span><span class="deduct">-¥{fund:,.2f}</span>
                </div>
                <div class="flow-detail">
                    <span>个税</span><span class="deduct">-¥{tax:,.2f}</span>
                </div>
                <div class="flow-total-deduct">合计扣款 ¥{si + fund + tax:,.2f}</div>
            </div>
            <div class="flow-arrow">→</div>
            <div class="flow-item net">
                <div class="flow-amount">¥{net:,.2f}</div>
                <div class="flow-label">实发工资</div>
            </div>
        </div>
        <div class="detail-grid">
            <div class="detail-item">
                <span class="detail-label">应纳税所得额</span>
                <span class="detail-value">¥{taxable:,.2f}</span>
            </div>
            <div class="detail-item">
                <span class="detail-label">社保（个人）</span>
                <span class="detail-value">¥{si:,.2f}</span>
            </div>
            <div class="detail-item">
                <span class="detail-label">公积金（个人）</span>
                <span class="detail-value">¥{fund:,.2f}</span>
            </div>
            <div class="detail-item">
                <span class="detail-label">公司总成本</span>
                <span class="detail-value highlight">¥{company:,.2f}</span>
            </div>
        </div>
    </div>"""


def build_pie_chart_svg(result):
    """构建工资构成饼图 SVG"""
    gross = result.get("gross_pay", 1)
    si = result.get("si_personal", 0)
    fund = result.get("fund_personal", 0)
    tax = result.get("tax_amount", 0)
    net = result.get("net_pay", 0)

    items = [
        ("实发工资", net, "#00d4aa"),
        ("社保个人", si, "#ff6b6b"),
        ("公积金", fund, "#ffa502"),
        ("个税", tax, "#ff4757"),
    ]

    total = gross
    if total == 0:
        return ""

    # SVG 饼图参数
    cx, cy, r = 140, 140, 100
    current_angle = -90

    paths = []
    labels = []

    for label, value, color in items:
        if value <= 0:
            continue
        angle = (value / total) * 360
        start_angle = current_angle
        end_angle = current_angle + angle

        # 弧度
        start_rad = math.radians(start_angle)
        end_rad = math.radians(end_angle)

        x1 = cx + r * math.cos(start_rad)
        y1 = cy + r * math.sin(start_rad)
        x2 = cx + r * math.cos(end_rad)
        y2 = cy + r * math.sin(end_rad)

        large_arc = 1 if angle > 180 else 0

        path = f'<path d="M{cx},{cy} L{x1:.1f},{y1:.1f} A{r},{r} 0 {large_arc},1 {x2:.1f},{y2:.1f} Z" fill="{color}" stroke="#1a1a2e" stroke-width="2"/>'
        paths.append(path)

        # 标签位置
        mid_angle = math.radians(start_angle + angle / 2)
        label_x = cx + (r + 35) * math.cos(mid_angle)
        label_y = cy + (r + 35) * math.sin(mid_angle)
        pct = (value / total) * 100

        labels.append(f'<text x="{label_x:.1f}" y="{label_y:.1f}" text-anchor="middle" fill="#aaa" font-size="12">{label} {pct:.1f}%</text>')

        current_angle = end_angle

    return f"""
    <div class="section">
        <h2>📈 工资构成</h2>
        <div class="chart-container">
            <svg viewBox="0 0 380 300" xmlns="http://www.w3.org/2000/svg">
                <text x="140" y="22" text-anchor="middle" fill="#ccc" font-size="14" font-weight="bold">税前 ¥{gross:,.2f}</text>
                {''.join(paths)}
                {''.join(labels)}
            </svg>
        </div>
    </div>"""


def build_tax_breakdown(result, tax_info):
    """构建个税阶梯说明"""
    taxable = result.get("taxable_income", 0)
    tax = result.get("tax_amount", 0)

    if isinstance(tax_info, dict):
        # 处理 detailed 模式
        monthly = tax_info.get("monthly_prepaid", tax_info)
        rate = monthly.get("rate", 0) * 100 if isinstance(monthly, dict) else 0
    else:
        rate = 0

    return f"""
    <div class="section">
        <h2>📋 个税计算说明</h2>
        <div class="tax-formula">
            <div class="formula-line">
                <span class="formula-label">应纳税所得额</span>
                <span class="formula-value">= 税前工资 - 社保 - 公积金 - 起征点(5000) - 专项扣除</span>
            </div>
            <div class="formula-line result">
                <span class="formula-label">=</span>
                <span class="formula-value">¥{taxable:,.2f}</span>
            </div>
            <div class="formula-line">
                <span class="formula-label">适用税率</span>
                <span class="formula-value">{rate:.1f}%</span>
            </div>
            <div class="formula-line result">
                <span class="formula-label">本月个税</span>
                <span class="formula-value highlight">¥{tax:,.2f}</span>
            </div>
        </div>
    </div>"""


def build_summary_table(employees):
    """构建多员工汇总表"""
    rows = []
    for e in employees:
        name = e.get("name", "—")
        r = e.get("result", e)
        rows.append(f"""
        <tr>
            <td>{name}</td>
            <td>¥{r.get('gross_pay', 0):,.2f}</td>
            <td>¥{r.get('si_personal', 0):,.2f}</td>
            <td>¥{r.get('fund_personal', 0):,.2f}</td>
            <td>¥{r.get('tax_amount', 0):,.2f}</td>
            <td class="net-highlight">¥{r.get('net_pay', 0):,.2f}</td>
            <td>¥{r.get('company_cost', 0):,.2f}</td>
        </tr>""")

    return f"""
    <div class="section">
        <h2>📊 全员汇总</h2>
        <div class="table-wrapper">
            <table>
                <thead>
                    <tr>
                        <th>姓名</th><th>税前工资</th><th>社保</th><th>公积金</th><th>个税</th><th>实发工资</th><th>公司成本</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows)}
                </tbody>
            </table>
        </div>
    </div>"""


def get_css():
    """统一的 CSS 样式 — 专业深色主题"""
    return """
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
    background: #0d1117;
    color: #c9d1d9;
    line-height: 1.6;
}
.container { max-width: 960px; margin: 0 auto; padding: 20px; }
.header {
    text-align: center; padding: 40px 20px;
    background: linear-gradient(135deg, #161b22 0%, #0d1117 100%);
    border: 1px solid #30363d; border-radius: 12px; margin-bottom: 24px;
}
.header h1 { font-size: 28px; color: #f0f6fc; margin-bottom: 8px; }
.subtitle { color: #8b949e; font-size: 13px; }
.section {
    background: #161b22; border: 1px solid #30363d; border-radius: 12px;
    padding: 24px; margin-bottom: 20px;
}
.section h2 { font-size: 18px; color: #f0f6fc; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid #21262d; }

/* 工资流转 */
.salary-flow { display: flex; align-items: center; justify-content: center; gap: 16px; flex-wrap: wrap; margin-bottom: 20px; }
.flow-item { text-align: center; padding: 16px 24px; border-radius: 10px; min-width: 140px; }
.flow-item.gross { background: #1a2332; border: 1px solid #58a6ff; }
.flow-item.net { background: #1a2e1a; border: 1px solid #3fb950; }
.flow-amount { font-size: 24px; font-weight: bold; color: #f0f6fc; }
.flow-label { font-size: 12px; color: #8b949e; margin-top: 4px; }
.flow-arrow { font-size: 24px; color: #484f58; }
.flow-deductions { text-align: left; padding: 12px 16px; background: #1a161b; border: 1px solid #30363d; border-radius: 8px; min-width: 180px; }
.flow-detail { display: flex; justify-content: space-between; padding: 3px 0; font-size: 13px; }
.deduct { color: #ff7b72; }
.flow-total-deduct { border-top: 1px solid #21262d; margin-top: 8px; padding-top: 6px; font-weight: bold; font-size: 13px; color: #ff7b72; }

/* 明细网格 */
.detail-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; }
.detail-item { background: #0d1117; border: 1px solid #21262d; border-radius: 8px; padding: 14px; display: flex; justify-content: space-between; align-items: center; }
.detail-label { color: #8b949e; font-size: 13px; }
.detail-value { color: #f0f6fc; font-weight: bold; font-size: 16px; }
.detail-value.highlight { color: #d2a8ff; }

/* 图表 */
.chart-container { text-align: center; padding: 10px; }
.chart-container svg { max-width: 100%; }

/* 个税公式 */
.tax-formula { background: #0d1117; border: 1px solid #21262d; border-radius: 8px; padding: 16px; }
.formula-line { display: flex; justify-content: space-between; padding: 6px 0; font-size: 14px; }
.formula-line.result { border-top: 1px solid #30363d; margin-top: 8px; padding-top: 10px; font-weight: bold; }
.formula-label { color: #8b949e; }
.formula-value { color: #c9d1d9; }
.formula-value.highlight { color: #3fb950; font-size: 18px; }

/* 汇总卡片 */
.summary-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 20px; }
.summary-card { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 20px; text-align: center; }
.summary-card.critical { border-color: #da3633; background: #1a0f0f; }
.summary-card.warning { border-color: #d2991d; background: #1a160f; }
.summary-card.info { border-color: #58a6ff; }
.card-number { font-size: 36px; font-weight: bold; color: #f0f6fc; }
.summary-card.critical .card-number { color: #ff7b72; }
.summary-card.warning .card-number { color: #d2991d; }
.card-label { font-size: 13px; color: #8b949e; margin-top: 6px; }

/* 异常卡片 */
.anomaly-card { border-radius: 10px; padding: 16px; margin-bottom: 12px; border: 1px solid #30363d; }
.anomaly-critical { border-color: #da3633; background: #1a0f0f; }
.anomaly-warning { border-color: #d2991d; background: #1a160f; }
.anomaly-info { border-color: #58a6ff; }
.anomaly-header { display: flex; justify-content: space-between; margin-bottom: 8px; }
.anomaly-name { font-weight: bold; font-size: 16px; color: #f0f6fc; }
.anomaly-type { font-size: 12px; color: #8b949e; padding: 2px 8px; background: #21262d; border-radius: 4px; }
.anomaly-detail { font-size: 14px; color: #c9d1d9; margin-bottom: 10px; }
.anomaly-fields { display: flex; flex-direction: column; gap: 6px; }
.anomaly-field { display: flex; justify-content: space-between; align-items: center; font-size: 13px; padding: 6px 0; border-bottom: 1px solid #21262d; }
.field-label { color: #8b949e; min-width: 80px; }
.field-values { color: #c9d1d9; }
.field-change { font-weight: bold; }
.field-change.critical { color: #ff7b72; }
.field-change.warning { color: #d2991d; }

/* 表格 */
.table-wrapper { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { background: #0d1117; color: #8b949e; font-weight: 600; padding: 12px 14px; text-align: left; border-bottom: 2px solid #30363d; }
td { padding: 10px 14px; border-bottom: 1px solid #21262d; }
tr:hover td { background: #1c2128; }
.positive { color: #3fb950; }
.negative { color: #ff7b72; }
.net-highlight { color: #3fb950; font-weight: bold; }

/* 页脚 */
.footer { text-align: center; padding: 20px; color: #484f58; font-size: 12px; border-top: 1px solid #21262d; margin-top: 10px; }
"""


def main():
    parser = argparse.ArgumentParser(description="薪酬个税可视化报告生成器")
    parser.add_argument("--type", choices=["salary", "anomaly"], default="salary", help="报告类型")
    parser.add_argument("--data", required=True, help="输入数据 JSON 文件")
    parser.add_argument("--output", "-o", help="输出 HTML 文件路径")
    parser.add_argument("--open", action="store_true", help="生成后打开报告")

    args = parser.parse_args()

    with open(args.data, "r", encoding="utf-8") as f:
        data = json.load(f)

    if args.type == "anomaly":
        output_path = generate_anomaly_report(data, args.output)
    else:
        output_path = generate_salary_report(data, args.output)

    if args.open:
        import webbrowser
        webbrowser.open(f"file://{os.path.abspath(output_path)}")


if __name__ == "__main__":
    main()
