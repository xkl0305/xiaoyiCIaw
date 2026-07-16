#!/usr/bin/env python3
"""广发证券金融数据 CLI（伞状聚合，一个 CLI 涵盖全部 9 个工具）。

按子命令调用，不同工具参数不同。LLM 不要手写 curl，直接调本 CLI。
底层走 GF Skills 统一入口，接口 host / 渠道由发布页按占位符替换（见 gf_client.py）。

子命令一览：
    f10          股票 F10 基础信息         --code --market
    valuation    多股市值 / PE / PB 估值   --codes ...
    compare      两股财务指标对比          --codes --year --report-type
    lhb          龙虎榜上榜个股            --date --market
    fund         基金详情                 --code
    invest       基金定投回测             --code --balance --rate --start --end --strategy ...
    etf-search   ETF 多维筛选             --trak-type --roc1m ... / --arg K=V
    etf-rank     ETF 榜单排名             --type --size ...
    etf-super    ETF 超级资金异动         --type

每个子命令都支持 --json '<args 的 JSON 对象>'（参数多 / 含嵌套时整段传），
命名参数覆盖 --json 同名字段；--raw 打印网关完整响应。

一行示例：
    python scripts/cli.py f10 --code 000776 --market SZ
    python scripts/cli.py etf-rank --type 4 --size 20
    python scripts/cli.py compare --codes SZ000783 SZ000776 --year 2025 --report-type 9

env 依赖：GF_SKILLS_APIKEY 优先，其次 ~/.gf-skills/apikey
        （去 https://hd.gf.com.cn/skills-market?channel=hwxyskills 获取）。
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gf_client


def _merge(json_args, override):
    """base=--json 解析结果，override=显式命名参数（None 跳过）。"""
    base = gf_client.parse_json_arg(json_args)
    return gf_client.merge_args(base, {k: v for k, v in override.items() if v is not None})


def _need(parser, args, keys):
    missing = [k for k in keys if args.get(k) in (None, "", [])]
    if missing:
        parser.error(f"缺少必填参数：{', '.join(missing)}（用命名参数或 --json 提供）")


# ── 各工具 handler ───────────────────────────────────────────

def cmd_f10(p, a):
    args = _merge(a.json_args, {
        "code": a.code.strip() if a.code else None,
        "market": a.market,
    })
    _need(p, args, ["code", "market"])
    gf_client.run("wechat_f10", "f10_basic_post", args, raw=a.raw)


def cmd_valuation(p, a):
    codes = [c.strip().upper() for c in (a.codes or []) if c.strip()] or None
    args = _merge(a.json_args, {"stock_codes": codes})
    if "stock_codes" in args:
        args["stock_codes"] = [str(c).strip().upper() for c in args["stock_codes"]]
    _need(p, args, ["stock_codes"])
    gf_client.run("quant", "common_basic_post", args, raw=a.raw)


def cmd_compare(p, a):
    codes = [c.strip().upper() for c in (a.codes or []) if c.strip()] or None
    args = _merge(a.json_args, {
        "stock_codes": codes, "year": a.year, "report_type": a.report_type,
    })
    if "stock_codes" in args:
        args["stock_codes"] = [str(c).strip().upper() for c in args["stock_codes"]]
    _need(p, args, ["stock_codes", "year", "report_type"])
    if len(args["stock_codes"]) != 2:
        p.error("compare 需要恰好 2 只股票代码")
    if int(args["report_type"]) not in (1, 6, 9, 12):
        p.error("report_type 必须是 1 / 6 / 9 / 12")
    args["report_type"] = int(args["report_type"])
    gf_client.run("quant", "compare_indicator_post", args, raw=a.raw)


def cmd_lhb(p, a):
    args = _merge(a.json_args, {"date": a.date, "market": a.market})
    if "date" in args:
        args["date"] = int(args["date"])
    if "market" in args and isinstance(args["market"], str):
        args["market"] = args["market"].lower()
    _need(p, args, ["date", "market"])
    gf_client.run("lhb", "lhb_aborttrade_market_date_get", args, raw=a.raw)


def cmd_fund(p, a):
    args = _merge(a.json_args, {"tradeCode": a.code.strip() if a.code else None})
    _need(p, args, ["tradeCode"])
    gf_client.run("jijin_info", "finance-api_product_fund_detail_get", args, raw=a.raw)


def cmd_invest(p, a):
    strategy = None
    if any(v is not None for v in (a.strategy, a.expect_income_ratio, a.back_rate,
                                   a.prod_index_type, a.prod_average_type, a.lock_period)):
        strategy = {"prodAIRationType": str(a.strategy if a.strategy is not None else 0)}
        for key, val in (("prodIndexType", a.prod_index_type),
                         ("prodAverageType", a.prod_average_type),
                         ("expectIncomeRatio", a.expect_income_ratio),
                         ("backRate", a.back_rate),
                         ("lockPeriod", a.lock_period)):
            if val is not None:
                strategy[key] = val

    def _date(d):
        return d.replace("-", "") if d else d

    override = {
        "tradeCode": a.code.strip() if a.code else None,
        "balance": a.balance,
        "rate": a.rate,
        "startDate": _date(a.start),
        "endDate": _date(a.end),
        "enFundDate": a.en_fund_date,
    }
    if strategy is not None:
        override["strategyList"] = [strategy]
    args = _merge(a.json_args, override)
    _need(p, args, ["tradeCode", "balance", "rate", "startDate", "endDate", "strategyList"])
    if not isinstance(args.get("strategyList"), list) or not args["strategyList"]:
        p.error("strategyList 必须是非空数组")
    gf_client.run("fund_invest", "finance_api_product_invest_compute_post", args, raw=a.raw)


_SEARCH_FLAGS = {
    "search": "search", "type": "type", "trak_type": "trakType",
    "one_trak_name": "oneTrakName", "trade_code": "tradeCode",
    "trade_t0": "tradeT0", "margin_trade": "marginTrade",
    "roc1m": "roc1m", "roc1y": "roc1y", "return1y": "return1y", "return3y": "return3y",
    "max_drawdown1y": "maxDrawdown1y", "sharp_ratio1y": "sharpRatio1y",
    "valuation_result": "valuationResult", "index_temp_type": "indexTempType",
    "asset_scale": "assetScale", "sort": "sort", "start": "start", "limit": "limit",
    "add_real_time_roc": "addRealTimeRoc",
}
# 判断"是否算一个筛选条件"时排除的纯分页/展示键
_SEARCH_NON_FILTER = {"sort", "start", "limit", "addRealTimeRoc"}


def cmd_etf_search(p, a):
    override = {}
    for attr, key in _SEARCH_FLAGS.items():
        v = getattr(a, attr, None)
        if v is not None:
            override[key] = v
    # --arg K=V 透传（中间优先级）
    arg_kv = {}
    for item in (a.arg or []):
        if "=" not in item:
            p.error(f"--arg 需要 KEY=VALUE，收到：{item!r}")
        k, v = item.split("=", 1)
        k = k.strip()
        if not k:
            p.error(f"--arg 的 KEY 不能为空：{item!r}")
        arg_kv[k] = int(v) if v.lstrip("-").isdigit() else v
    # 优先级：--json < --arg < 命名 flag
    args = gf_client.merge_args(gf_client.merge_args(gf_client.parse_json_arg(a.json_args), arg_kv), override)
    if "limit" not in args:
        args["limit"] = 20
    if not any(k not in _SEARCH_NON_FILTER for k in args):
        p.error("至少需要一个筛选条件（如 --trak-type / --roc1m / --arg K=V），仅分页/排序不够")
    gf_client.run("etf_search", "finance_api_inclusive_etf_list_get", args, raw=a.raw)


def cmd_etf_rank(p, a):
    override = {"type": a.type, "size": a.size, "page": a.page,
                "sameIndexFilter": a.same_index_filter, "continueRiseLimit": a.continue_rise_limit}
    args = _merge(a.json_args, override)
    _need(p, args, ["type"])
    args["type"] = int(args["type"])
    if args["type"] not in (1, 2, 3, 4, 12, 13):
        p.error("type 必须是 1/2/3/4/12/13")
    args.setdefault("size", 20)
    args.setdefault("page", 0)
    gf_client.run("etf_rank", "finance-api_product_etf_rank_get", args, raw=a.raw)


_SUPER_TYPES = ["大幅流入", "大幅流出", "持续流入", "持续流出"]


def cmd_etf_super(p, a):
    args = _merge(a.json_args, {"type": a.type})
    _need(p, args, ["type"])
    if args["type"] not in _SUPER_TYPES:
        p.error(f"type 必须是：{' / '.join(_SUPER_TYPES)}")
    gf_client.run("etf-super-fund", "gfmiddle_eits_super_fund_etf_superfund_get", args, raw=a.raw)


# ── argparse 装配 ─────────────────────────────────────────────

def _add_common(sp):
    sp.add_argument("--json", dest="json_args", metavar="JSON",
                    help="直接传完整 args 的 JSON 对象；与命名参数同用时命名参数覆盖同名字段")
    sp.add_argument("--raw", action="store_true", help="打印网关完整响应（默认只打印 data.data）")


def main():
    p = argparse.ArgumentParser(
        description="广发证券金融数据 CLI（9 个工具，按子命令调用）",
        epilog="示例：python scripts/cli.py etf-rank --type 4 --size 20",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    # f10
    sp = sub.add_parser("f10", help="股票 F10 基础信息")
    sp.add_argument("--code", help="证券代码纯数字，如 000776")
    sp.add_argument("--market", type=lambda s: s.strip().upper(), choices=["SH", "SZ"], help="市场：SH/SZ")
    _add_common(sp); sp.set_defaults(func=cmd_f10)

    # valuation
    sp = sub.add_parser("valuation", aliases=["basic"], help="多股市值 / PE / PB 估值")
    sp.add_argument("codes", nargs="*", help="带前缀大写代码，如 SZ000776 SH600000")
    sp.add_argument("--codes", dest="codes", nargs="+", help="同上（显式）")
    _add_common(sp); sp.set_defaults(func=cmd_valuation)

    # compare
    sp = sub.add_parser("compare", help="两股财务指标对比")
    sp.add_argument("--codes", nargs="+", help="恰好两只带前缀大写代码")
    sp.add_argument("--year", help="报告年份，如 2025")
    sp.add_argument("--report-type", dest="report_type", type=int, choices=[1, 6, 9, 12],
                    help="1 一季 / 6 中报 / 9 三季 / 12 年报")
    _add_common(sp); sp.set_defaults(func=cmd_compare)

    # lhb
    sp = sub.add_parser("lhb", help="龙虎榜上榜个股")
    sp.add_argument("--date", type=int, help="日期 YYYYMMDD，如 20260313")
    sp.add_argument("--market", type=str.lower, choices=["sh", "sz"], help="市场（小写）：sh/sz")
    _add_common(sp); sp.set_defaults(func=cmd_lhb)

    # fund
    sp = sub.add_parser("fund", help="基金详情")
    sp.add_argument("--code", "--trade-code", dest="code", help="基金交易代码，如 519002")
    _add_common(sp); sp.set_defaults(func=cmd_fund)

    # invest
    sp = sub.add_parser("invest", help="基金定投回测")
    sp.add_argument("--code", dest="code", help="基金代码")
    sp.add_argument("--balance", type=float, help="每期定投金额（元）")
    sp.add_argument("--rate", choices=["0", "1", "2", "3"], help="0 每月 / 1 每周 / 2 每天 / 3 每双周")
    sp.add_argument("--start", help="开始日期 YYYYMMDD 或 YYYY-MM-DD")
    sp.add_argument("--end", help="结束日期 YYYYMMDD 或 YYYY-MM-DD")
    sp.add_argument("--en-fund-date", dest="en_fund_date", help="扣款日，如 1")
    sp.add_argument("--strategy", type=int, choices=range(0, 6),
                    help="0 普通/1 均线/2 目标止盈/3 移动止盈/4 均线+目标/5 均线+移动")
    sp.add_argument("--expect-income-ratio", dest="expect_income_ratio", help="目标止盈收益率，如 0.2")
    sp.add_argument("--back-rate", dest="back_rate", help="移动止盈回撤比例")
    sp.add_argument("--prod-index-type", dest="prod_index_type")
    sp.add_argument("--prod-average-type", dest="prod_average_type")
    sp.add_argument("--lock-period", dest="lock_period")
    _add_common(sp); sp.set_defaults(func=cmd_invest)

    # etf-search
    sp = sub.add_parser("etf-search", help="ETF 多维筛选")
    sp.add_argument("--search"); sp.add_argument("--type")
    sp.add_argument("--trak-type", dest="trak_type"); sp.add_argument("--one-trak-name", dest="one_trak_name")
    sp.add_argument("--trade-code", dest="trade_code")
    sp.add_argument("--trade-t0", dest="trade_t0", type=int); sp.add_argument("--margin-trade", dest="margin_trade", type=int)
    sp.add_argument("--roc1m"); sp.add_argument("--roc1y"); sp.add_argument("--return1y"); sp.add_argument("--return3y")
    sp.add_argument("--max-drawdown1y", dest="max_drawdown1y"); sp.add_argument("--sharp-ratio1y", dest="sharp_ratio1y")
    sp.add_argument("--valuation-result", dest="valuation_result", type=int)
    sp.add_argument("--index-temp-type", dest="index_temp_type", choices=["low", "ord", "high"])
    sp.add_argument("--asset-scale", dest="asset_scale")
    sp.add_argument("--sort"); sp.add_argument("--start", type=int); sp.add_argument("--limit", type=int)
    sp.add_argument("--add-real-time-roc", dest="add_real_time_roc", type=int)
    sp.add_argument("--arg", action="append", metavar="KEY=VALUE", help="透传任意参数，可多次")
    _add_common(sp); sp.set_defaults(func=cmd_etf_search)

    # etf-rank
    sp = sub.add_parser("etf-rank", help="ETF 榜单排名")
    sp.add_argument("--type", type=int, choices=[1, 2, 3, 4, 12, 13],
                    help="1 涨幅/2 跌幅/3 换手/4 主力资金/12 净申购/13 溢价率")
    sp.add_argument("--size", type=int); sp.add_argument("--page", type=int)
    sp.add_argument("--same-index-filter", dest="same_index_filter", type=int)
    sp.add_argument("--continue-rise-limit", dest="continue_rise_limit", type=int)
    _add_common(sp); sp.set_defaults(func=cmd_etf_rank)

    # etf-super
    sp = sub.add_parser("etf-super", help="ETF 超级资金异动")
    sp.add_argument("--type", choices=_SUPER_TYPES, help="大幅流入/大幅流出/持续流入/持续流出")
    _add_common(sp); sp.set_defaults(func=cmd_etf_super)

    args = p.parse_args()
    args.func(p, args)


if __name__ == "__main__":
    main()
