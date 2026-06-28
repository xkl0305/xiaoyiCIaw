#!/usr/bin/env python3
"""
工资异常检测引擎
上传上月与本月工资表 → 自动比对差异 → 标记异常波动
"""

import json
import argparse
import sys
import math
from pathlib import Path
from datetime import datetime

SKILL_DIR = Path(__file__).resolve().parent.parent

# 检测字段及中文名
COMPARE_FIELDS = [
    ("gross", "税前工资"),
    ("net_pay", "实发工资"),
    ("tax_amount", "个税"),
    ("si_personal", "社保个人"),
    ("fund_personal", "公积金个人"),
    ("si_company", "社保公司"),
    ("fund_company", "公积金公司"),
    ("company_cost", "公司总成本"),
]

# 异常阈值配置
DEFAULT_CONFIG = {
    "zscore_threshold": 2.0,        # Z-Score ≥ 2.0 → 注意
    "zscore_high_threshold": 3.0,   # Z-Score ≥ 3.0 → 严重异常
    "abs_change_threshold": 5000,   # 绝对变化 ≥ 5000 → 至少注意
    "pct_change_threshold": 0.30,   # 百分比变化 ≥ 30% → 至少注意
    "pct_change_high": 0.50,        # 百分比变化 ≥ 50% → 严重异常
    "min_employees_for_stats": 3,   # 至少3人才做统计分析
}


def calc_mean_std(values):
    """计算均值和标准差"""
    n = len(values)
    if n == 0:
        return 0, 0
    mean_val = sum(values) / n
    if n == 1:
        return mean_val, 0
    variance = sum((x - mean_val) ** 2 for x in values) / (n - 1)
    return mean_val, math.sqrt(variance)


def calc_zscore(value, mean_val, std_val):
    """计算Z-Score"""
    if std_val == 0:
        return 0
    return (value - mean_val) / std_val


def detect_anomalies(prev_data, curr_data, config=None):
    """
    异常检测主函数

    参数:
        prev_data: 上月工资数据（来自 tax_calculator.py 输出或 salary_parser.py 输出）
        curr_data: 本月工资数据
        config: 阈值配置

    返回: 检测结果 JSON
    """
    if config is None:
        config = DEFAULT_CONFIG

    # 统一数据格式
    prev_employees = extract_employees(prev_data)
    curr_employees = extract_employees(curr_data)

    # 建立员工索引
    prev_map = build_employee_map(prev_employees)
    curr_map = build_employee_map(curr_employees)

    all_names = set(prev_map.keys()) | set(curr_map.keys())

    # 收集各字段的变化（用于统计分析）
    field_changes = {f: [] for f, _ in COMPARE_FIELDS}

    # 逐人对比
    comparisons = []
    for name in sorted(all_names):
        prev = prev_map.get(name)
        curr = curr_map.get(name)

        if prev and curr:
            # 两期都在 → 对比
            comp = compare_employee(name, prev, curr, field_changes)
            comparisons.append(comp)
            comp["status"] = "existing"
        elif prev and not curr:
            comparisons.append({
                "name": name,
                "status": "departed",
                "prev": prev,
                "curr": None,
                "warning": f"⚠️ {name} 本月不在工资表中（可能离职）"
            })
        else:
            comparisons.append({
                "name": name,
                "status": "new",
                "prev": None,
                "curr": curr,
                "info": f"🆕 {name} 为本月新增员工"
            })

    # 统计分析：计算每个字段的均值和标准差
    stats = {}
    for field, changes in field_changes.items():
        if len(changes) >= config["min_employees_for_stats"]:
            mean_val, std_val = calc_mean_std(changes)
            stats[field] = {"mean": mean_val, "std": std_val, "count": len(changes)}
        else:
            stats[field] = {"mean": 0, "std": 0, "count": len(changes), "insufficient_data": True}

    # 基于统计标记异常等级
    anomalies = []
    for comp in comparisons:
        if comp["status"] != "existing":
            if comp["status"] == "departed":
                anomalies.append({"name": comp["name"], "level": "warning", "type": "人员变动",
                                  "detail": comp["warning"]})
            else:
                anomalies.append({"name": comp["name"], "level": "info", "type": "人员变动",
                                  "detail": comp["info"]})
            continue

        # 检查各字段
        person_anomalies = []
        for field, label in COMPARE_FIELDS:
            change = comp.get(f"change_{field}")
            if change is None:
                continue

            abs_change = abs(change)
            pct_change = abs(change / comp[f"prev_{field}"]) if comp[f"prev_{field}"] != 0 else float("inf")

            level = "normal"
            reasons = []

            # Z-Score 检查
            if field in stats and not stats[field].get("insufficient_data"):
                zscore = abs(calc_zscore(change, stats[field]["mean"], stats[field]["std"]))
                if zscore >= config["zscore_high_threshold"]:
                    level = "critical"
                    reasons.append(f"Z-Score={zscore:.1f}（≥{config['zscore_high_threshold']}）")
                elif zscore >= config["zscore_threshold"]:
                    if level != "critical":
                        level = "warning"
                    reasons.append(f"Z-Score={zscore:.1f}（≥{config['zscore_threshold']}）")

            # 绝对变化
            if abs_change >= config["abs_change_threshold"]:
                if level == "normal":
                    level = "warning"
                reasons.append(f"绝对变化 ¥{abs_change:,.0f}（≥¥{config['abs_change_threshold']:,}）")

            # 百分比变化
            if pct_change >= config["pct_change_high"]:
                level = "critical"
                reasons.append(f"变化 {pct_change:.0%}（≥{config['pct_change_high']:.0%}）")
            elif pct_change >= config["pct_change_threshold"]:
                if level == "normal":
                    level = "warning"
                reasons.append(f"变化 {pct_change:.0%}（≥{config['pct_change_threshold']:.0%}）")

            if level != "normal":
                direction = "↑" if change > 0 else "↓"
                person_anomalies.append({
                    "field": field,
                    "label": label,
                    "level": level,
                    "direction": direction,
                    "prev_value": comp[f"prev_{field}"],
                    "curr_value": comp[f"curr_{field}"],
                    "change": change,
                    "change_pct": pct_change if pct_change != float("inf") else None,
                    "reasons": reasons
                })

        if person_anomalies:
            # 取最高等级
            max_level = "normal"
            level_order = {"normal": 0, "info": 1, "warning": 2, "critical": 3}
            for a in person_anomalies:
                if level_order.get(a["level"], 0) > level_order.get(max_level, 0):
                    max_level = a["level"]

            comp_name = comp["name"]
            anomalies.append({
                "name": comp_name,
                "level": max_level,
                "type": "工资异常",
                "fields": person_anomalies,
                "summary": f"{comp_name}: " + "; ".join(
                    f"{a['label']} {a['direction']}¥{a['change']:+,.2f}" for a in person_anomalies[:3]
                )
            })

    # 汇总统计
    total_employees = len(comparisons)
    new_count = sum(1 for c in comparisons if c["status"] == "new")
    departed_count = sum(1 for c in comparisons if c["status"] == "departed")
    existing_count = total_employees - new_count - departed_count

    critical_count = sum(1 for a in anomalies if a["level"] == "critical")
    warning_count = sum(1 for a in anomalies if a["level"] == "warning")
    info_count = sum(1 for a in anomalies if a["level"] == "info")

    return {
        "metadata": {
            "detection_time": datetime.now().isoformat(),
            "config": config,
            "prev_count": len(prev_map),
            "curr_count": len(curr_map)
        },
        "summary": {
            "total_employees": total_employees,
            "existing": existing_count,
            "new": new_count,
            "departed": departed_count,
            "anomalies_critical": critical_count,
            "anomalies_warning": warning_count,
            "anomalies_info": info_count,
            "anomalies_total": critical_count + warning_count
        },
        "statistics": stats,
        "comparisons": comparisons,
        "anomalies": anomalies
    }


def extract_employees(data):
    """从不同格式数据中提取员工列表"""
    if isinstance(data, list):
        return data
    if "employees" in data:
        return data["employees"]
    if "result" in data:
        return [data]
    return [data]


def build_employee_map(employees):
    """建立员工名→数据的映射"""
    emp_map = {}
    for e in employees:
        name = e.get("name", "")
        if name:
            emp_map[name] = e
    return emp_map


def compare_employee(name, prev, curr, field_changes):
    """对比单个员工的工资变化"""
    comp = {"name": name}

    # 基本信息
    for field in ["gross", "net_pay", "tax_amount", "si_personal", "fund_personal",
                  "si_company", "fund_company", "company_cost"]:
        prev_val = prev.get(field, 0)
        curr_val = curr.get(field, 0)
        change = curr_val - prev_val

        comp[f"prev_{field}"] = prev_val
        comp[f"curr_{field}"] = curr_val
        comp[f"change_{field}"] = change

        # 收集到字段变化列表
        for fname, _ in COMPARE_FIELDS:
            if fname == field:
                field_changes[fname].append(change)

    return comp


def main():
    parser = argparse.ArgumentParser(description="工资异常检测引擎")
    parser.add_argument("--prev", required=True, help="上月工资数据 JSON 文件")
    parser.add_argument("--curr", required=True, help="本月工资数据 JSON 文件")
    parser.add_argument("--config", help="自定义阈值配置 JSON")
    parser.add_argument("--output", "-o", help="输出 JSON 文件路径")

    args = parser.parse_args()

    with open(args.prev, "r", encoding="utf-8") as f:
        prev_data = json.load(f)

    with open(args.curr, "r", encoding="utf-8") as f:
        curr_data = json.load(f)

    config = None
    if args.config:
        with open(args.config, "r", encoding="utf-8") as f:
            config = json.load(f)

    result = detect_anomalies(prev_data, curr_data, config)

    output = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output:
        output_path = Path(args.output)
        if not output_path.is_absolute():
            output_path = SKILL_DIR / "data" / output_path
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"检测结果已保存至: {output_path}")
    else:
        print(output)


if __name__ == "__main__":
    main()
