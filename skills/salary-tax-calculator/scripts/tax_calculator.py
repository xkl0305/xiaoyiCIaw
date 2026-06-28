#!/usr/bin/env python3
"""
薪酬个税计算核心引擎
支持：五险一金计算 / 个税计算（月度预扣+年度汇算）/ 专项附加扣除 / 全年一次性奖金
"""

import json
import argparse
import sys
import os
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
REF_DIR = SKILL_DIR / "references"


def load_json(filename):
    with open(REF_DIR / filename, "r", encoding="utf-8") as f:
        return json.load(f)


def clamp(value, lo, hi):
    """将值限制在 [lo, hi] 区间"""
    return max(lo, min(value, hi))


def get_city_config(city_name):
    """获取城市五险一金配置，找不到则返回默认值"""
    data = load_json("city_rates.json")
    if city_name in data["cities"]:
        return data["cities"][city_name]
    # 返回默认配置
    return {
        "social_insurance": data["default_social_insurance"],
        "housing_fund": {
            "personal_min": 0.07, "personal_max": 0.07,
            "company_min": 0.07, "company_max": 0.07,
            "base_min": 3000, "base_max": 30000
        }
    }


def calc_social_insurance(gross, city_config, custom_base=None):
    """
    计算五险个人部分
    返回: {pension, medical, unemployment, injury, maternity, total, detail}
    """
    si = city_config["social_insurance"]
    result = {}
    total = 0.0
    detail = {}

    for item in ["pension", "medical", "unemployment", "injury", "maternity"]:
        rate = si[item]["personal"]
        if custom_base is not None:
            base = custom_base
        else:
            base_min = si[item].get("base_min", 0)
            base_max = si[item].get("base_max", float("inf"))
            base = clamp(gross, base_min, base_max)

        amount = round(base * rate, 2)
        detail[item] = {
            "rate": rate,
            "base": base,
            "amount": amount
        }
        result[item] = amount
        total += amount

    result["total"] = round(total, 2)
    result["detail"] = detail
    return result


def calc_housing_fund(gross, city_config, custom_rate=None, custom_base=None):
    """
    计算公积金个人部分
    返回: {personal, company, base, rate, amount}
    """
    hf = city_config["housing_fund"]

    if custom_rate is not None:
        rate = min(custom_rate, hf["personal_max"])
        rate = max(rate, hf["personal_min"])
    else:
        rate = hf.get("personal_min", 0.07)

    if custom_base is not None:
        base = custom_base
    else:
        base_min = hf.get("base_min", 0)
        base_max = hf.get("base_max", float("inf"))
        base = clamp(gross, base_min, base_max)

    amount = round(base * rate, 2)
    company_amount = round(base * rate, 2)

    return {
        "personal": amount,
        "company": company_amount,
        "base": base,
        "rate": rate,
        "amount": amount
    }


def calc_monthly_tax(taxable_income):
    """
    月度个税计算（预扣预缴法）
    按月税率表计算
    """
    if taxable_income <= 0:
        return {"tax": 0.0, "rate": 0.0, "bracket": 0, "quick_deduction": 0, "taxable_income": taxable_income}

    data = load_json("tax_brackets.json")
    brackets = data["monthly"]["brackets"]

    for b in brackets:
        limit = b["taxable_max"]
        if limit is None or taxable_income <= limit:
            tax = round(taxable_income * b["rate"] - b["quick_deduction"], 2)
            return {
                "tax": max(tax, 0),
                "rate": b["rate"],
                "bracket": b["level"],
                "quick_deduction": b["quick_deduction"],
                "taxable_income": taxable_income
            }

    # fallback - should not reach
    return {"tax": 0.0, "rate": 0.0, "bracket": 0, "quick_deduction": 0, "taxable_income": taxable_income}


def calc_annual_tax(cumulative_taxable_income, cumulative_tax_paid=0, month=1):
    """
    年度累计预扣法（居民个人综合所得）
    cumulative_taxable_income: 累计应纳税所得额（从1月到当前月）
    cumulative_tax_paid: 已预扣预缴税额
    month: 当前月份（1-12）
    """
    if cumulative_taxable_income <= 0:
        return {"monthly_tax": 0.0, "cumulative_tax": 0.0, "taxable_income": cumulative_taxable_income}

    data = load_json("tax_brackets.json")
    brackets = data["annual"]["brackets"]

    # 按年累计额查找税率
    for b in brackets:
        limit = b["taxable_max"]
        if limit is None or cumulative_taxable_income <= limit:
            cumulative_tax = round(cumulative_taxable_income * b["rate"] - b["quick_deduction"], 2)
            monthly_tax = round(cumulative_tax - cumulative_tax_paid, 2)
            return {
                "monthly_tax": max(monthly_tax, 0),
                "cumulative_tax": max(cumulative_tax, 0),
                "rate": b["rate"],
                "bracket": b["level"],
                "taxable_income": cumulative_taxable_income,
                "month": month
            }

    return {"monthly_tax": 0, "cumulative_tax": 0, "taxable_income": cumulative_taxable_income}


def calc_year_end_bonus_tax(bonus_amount):
    """
    全年一次性奖金单独计税（2027年底前有效）
    bonus_amount / 12 → 找月度税率 → bonus * rate - quick_deduction
    """
    if bonus_amount <= 0:
        return {"tax": 0.0, "rate": 0.0, "bracket": 0}

    monthly_equivalent = bonus_amount / 12
    data = load_json("tax_brackets.json")

    for b in data["monthly"]["brackets"]:
        limit = b["taxable_max"]
        if limit is None or monthly_equivalent <= limit:
            tax = round(bonus_amount * b["rate"] - b["quick_deduction"], 2)
            return {
                "tax": max(tax, 0),
                "rate": b["rate"],
                "bracket": b["level"],
                "quick_deduction": b["quick_deduction"]
            }

    return {"tax": 0.0, "rate": 0.0, "bracket": 0}


def calc_salary(gross, city, si_base=None, fund_rate=None, fund_base=None,
                special_deductions=0, method="monthly", cumulative_tax_paid=0, month=1):
    """
    完整工资计算

    参数:
        gross: 税前工资（应发工资）
        city: 城市名称
        si_base: 社保基数（None=按实际工资）
        fund_rate: 公积金比例（None=使用默认）
        fund_base: 公积金基数（None=按实际工资）
        special_deductions: 专项附加扣除（月）
        method: "monthly" | "annual" | "detailed"
        cumulative_tax_paid: 累计已预扣税额（用于annual法）
        month: 当前月份（1-12）

    返回: 完整工资构成JSON
    """
    city_config = get_city_config(city)

    # 1. 五险个人部分
    si_result = calc_social_insurance(gross, city_config, si_base)

    # 2. 公积金个人部分
    fund_result = calc_housing_fund(gross, city_config, fund_rate, fund_base)

    # 3. 应纳税所得额 = 税前 - 五险一金 - 起征点(5000) - 专项附加扣除
    standard_deduction = 5000.0
    taxable_income = round(gross - si_result["total"] - fund_result["amount"] - standard_deduction - special_deductions, 2)

    # 4. 个税计算
    if method == "detailed":
        # 详细模式：同时计算月度预扣 + 年度累计
        monthly_tax_result = calc_monthly_tax(taxable_income)
        annual_tax_result = calc_annual_tax(taxable_income, cumulative_tax_paid, month)
        tax_result = {
            "monthly_prepaid": monthly_tax_result,
            "annual_cumulative": annual_tax_result
        }
        tax_amount = monthly_tax_result["tax"]
    elif method == "annual":
        tax_result = calc_annual_tax(taxable_income, cumulative_tax_paid, month)
        tax_amount = tax_result["monthly_tax"]
    else:
        tax_result = calc_monthly_tax(taxable_income)
        tax_amount = tax_result["tax"]

    # 5. 实发工资
    net_pay = round(gross - si_result["total"] - fund_result["amount"] - tax_amount, 2)

    # 6. 公司成本
    si_company_total = 0.0
    for item in ["pension", "medical", "unemployment", "injury", "maternity"]:
        rate = city_config["social_insurance"][item]["company"]
        if si_base is not None:
            base = si_base
        else:
            base_min = city_config["social_insurance"][item].get("base_min", 0)
            base_max = city_config["social_insurance"][item].get("base_max", float("inf"))
            base = clamp(gross, base_min, base_max)
        si_company_total += round(base * rate, 2)

    company_cost = round(gross + si_company_total + fund_result["company"], 2)

    return {
        "input": {
            "gross_pay": gross,
            "city": city,
            "method": method,
            "si_base": si_base if si_base else gross,
            "fund_base": fund_base if fund_base else gross,
            "fund_rate": fund_result["rate"],
            "special_deductions": special_deductions,
            "standard_deduction": standard_deduction,
            "month": month
        },
        "deductions": {
            "social_insurance": si_result,
            "housing_fund": fund_result,
            "total_deductions": round(si_result["total"] + fund_result["amount"], 2)
        },
        "tax": tax_result,
        "result": {
            "gross_pay": gross,
            "si_personal": si_result["total"],
            "fund_personal": fund_result["amount"],
            "taxable_income": taxable_income,
            "tax_amount": tax_amount,
            "net_pay": net_pay,
            "si_company": round(si_company_total, 2),
            "fund_company": fund_result["company"],
            "company_cost": company_cost
        },
        "summary": f"{city} 税前{gross}元 → 实发{net_pay}元（社保{si_result['total']} + 公积金{fund_result['amount']} + 个税{tax_amount}）"
    }


def batch_calc(employees, city, method="monthly"):
    """
    批量计算
    employees: [{gross, si_base?, fund_rate?, fund_base?, special_deductions?, name?}, ...]
    返回: 所有员工的工资计算结果列表
    """
    results = []
    for emp in employees:
        r = calc_salary(
            gross=emp["gross"],
            city=city,
            si_base=emp.get("si_base"),
            fund_rate=emp.get("fund_rate"),
            fund_base=emp.get("fund_base"),
            special_deductions=emp.get("special_deductions", 0),
            cumulative_tax_paid=emp.get("cumulative_tax_paid", 0),
            month=emp.get("month", 1),
            method=method
        )
        r["name"] = emp.get("name", "")
        results.append(r)
    return results


def interactive_mode():
    """交互式工资计算"""
    print("=" * 50)
    print("  薪酬个税计算器")
    print("=" * 50)
    try:
        gross = float(input("税前月薪（元）：").strip())
        city = input("所在城市（如 北京/上海/深圳）：").strip() or "北京"
        si_base_str = input("社保基数（回车=按实际工资）：").strip()
        si_base = float(si_base_str) if si_base_str else None
        fund_rate_str = input("公积金比例（如 0.07 表示7%，回车=默认）：").strip()
        fund_rate = float(fund_rate_str) if fund_rate_str else None
        fund_base_str = input("公积金基数（回车=按实际工资）：").strip()
        fund_base = float(fund_base_str) if fund_base_str else None

        # 专项附加扣除
        print("\n--- 专项附加扣除（月/元）---")
        de_children = float(input("子女教育（几个孩子 × 2000）：").strip() or "0")
        de_infant = float(input("婴幼儿照护（几个孩子 × 2000）：").strip() or "0")
        de_edu = float(input("继续教育（400）：").strip() or "0")
        de_loan = float(input("住房贷款利息（1000）：").strip() or "0")
        de_rent = float(input("住房租金（800/1100/1500）：").strip() or "0")
        de_elderly = float(input("赡养老人（3000）：").strip() or "0")
        special_deductions = de_children + de_infant + de_edu + de_loan + de_rent + de_elderly

        result = calc_salary(gross, city, si_base, fund_rate, fund_base, special_deductions, method="detailed")
        print("\n" + json.dumps(result, ensure_ascii=False, indent=2))

    except (ValueError, KeyboardInterrupt):
        print("\n已取消。")


def main():
    parser = argparse.ArgumentParser(description="薪酬个税计算引擎")
    parser.add_argument("--city", default="北京", help="城市名称（默认：北京）")
    parser.add_argument("--gross", type=float, help="税前月薪")
    parser.add_argument("--si-base", type=float, help="社保基数")
    parser.add_argument("--fund-rate", type=float, help="公积金比例（如 0.07）")
    parser.add_argument("--fund-base", type=float, help="公积金基数")
    parser.add_argument("--deductions", type=float, default=0, help="专项附加扣除总额")
    parser.add_argument("--method", default="detailed", choices=["monthly", "annual", "detailed"],
                        help="计算方式")
    parser.add_argument("--batch", help="批量计算：传入JSON文件路径")
    parser.add_argument("--month", type=int, default=1, help="月份（1-12）")
    parser.add_argument("--cumulative-tax", type=float, default=0, help="累计已预扣税额")
    parser.add_argument("--year-end-bonus", type=float, help="全年一次性奖金金额")
    parser.add_argument("--interactive", "-i", action="store_true", help="交互模式")
    parser.add_argument("--output", "-o", help="结果输出JSON文件路径")

    args = parser.parse_args()

    if args.interactive:
        interactive_mode()
        return

    results = []

    # 全年一次性奖金
    if args.year_end_bonus is not None:
        bonus_result = calc_year_end_bonus_tax(args.year_end_bonus)
        print(json.dumps({"type": "year_end_bonus", "bonus": args.year_end_bonus, **bonus_result},
                         ensure_ascii=False, indent=2))
        return

    # 批量计算
    if args.batch:
        with open(args.batch, "r", encoding="utf-8") as f:
            employees = json.load(f)
        city = args.city
        results = batch_calc(employees, city, args.method)
    elif args.gross is not None:
        result = calc_salary(
            gross=args.gross,
            city=args.city,
            si_base=args.si_base,
            fund_rate=args.fund_rate,
            fund_base=args.fund_base,
            special_deductions=args.deductions,
            method=args.method,
            cumulative_tax_paid=args.cumulative_tax,
            month=args.month
        )
        results = [result]
    else:
        interactive_mode()
        return

    output = json.dumps(results if len(results) > 1 else results[0], ensure_ascii=False, indent=2)

    if args.output:
        output_path = Path(args.output)
        if not output_path.is_absolute():
            output_path = SKILL_DIR / "data" / output_path
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"结果已保存至: {output_path}")
    else:
        print(output)


if __name__ == "__main__":
    main()
