"""
孕妇孕周计算器 —— 确定性脚本
用法: python calc_pregnancy.py <预产期> [系统日期]
格式: YYYY-MM-DD
输出示例:
  WEEKS=18 DAYS=3 PHASE=中期 PHASE_CN=孕中期 DAYS_TOTAL=129
  WEEKS_ONLY=18  (仅输出孕周整数，用于调用方自行处理)

所有计算基于产科标准：末次月经 = 预产期 - 280天
"""

import sys
from datetime import date, timedelta


def calc(due_str: str, today_str: str | None = None):
    due_date = date.fromisoformat(due_str)
    today = date.fromisoformat(today_str) if today_str else date.today()
    lmp = due_date - timedelta(days=280)
    days_pregnant = (today - lmp).days

    if days_pregnant < 0:
        print("ERROR=预产期尚未到达，无法计算")
        sys.exit(1)

    weeks = days_pregnant // 7
    remain_days = days_pregnant % 7

    if weeks < 14:
        phase = "早期"
        phase_cn = "孕早期"
    elif weeks < 28:
        phase = "中期"
        phase_cn = "孕中期"
    else:
        phase = "晚期"
        phase_cn = "孕晚期"

    # 输出 KEY=VALUE 格式，方便调用方解析
    print(f"WEEKS={weeks}")
    print(f"DAYS={remain_days}")
    print(f"PHASE={phase}")
    print(f"PHASE_CN={phase_cn}")
    print(f"DAYS_TOTAL={days_pregnant}")
    print(f"LMP={lmp.isoformat()}")
    print(f"TODAY={today.isoformat()}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python calc_pregnancy.py <预产期YYYY-MM-DD> [系统日期YYYY-MM-DD]")
        sys.exit(1)
    due = sys.argv[1]
    today = sys.argv[2] if len(sys.argv) >= 3 else None
    calc(due, today)
