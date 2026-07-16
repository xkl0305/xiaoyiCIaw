#!/usr/bin/env python3
"""
中金财富 ETF 热门榜单查询工具
基于通达信 HQServ.PBMultiHQ / HQServ.PBCombHQ 与 MCSearchHotList 接口，
获取 ETF 涨跌榜、资金榜、特色榜（连涨/换手/溢价/自选）以及热搜榜。
"""

import argparse
import hashlib
import json
import platform
import socket
import ssl
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

XIAOYI_ENV_PATH = Path("/home/sandbox/.openclaw/.xiaoyienv")
LOGIN_TOKEN_KEY = "117860603_login_token"
API_URL = "https://skill.ciccwm.com/zzt/ext/fcgi/common.fcgi"
REPORT_URL = "https://webreport.ciccwm.com/zzt/fcgi/common.fcgi"
REQUEST_VERSION = "20260612"
REQUEST_TIMEOUT = 20

TDX_CMD_NAME = "SkillTdxQuotationQueryCommon"
HOT_CMD_NAME = "SkillMCSearchHotList"

SKILL_NAME = "ETF热门榜单"
SKILL_UA_NAME = "ciccwm-etf-ranking-analysis"
PLATFORM_NAME = "huawei"
REINSTALL_MESSAGE = (
    "未获取到有效的 117860603_login_token 或鉴权已失效。"
    "请刷新 117860603_login_token，或调用 huawei_id_tool 工具获取新凭证。"
)

# 通达信市场域
SET_DOMAIN_ETF = 11005  # 沪深 ETF 市场
SET_DOMAIN_CUSTOM = 11201  # 自选 ETF 排行

# Target 枚举：ETF 属于沪深京主板，行情数据源统一用 0（A 股延时行情）
ETR_TARGET = 0

# 主力净额榜(212)、换手榜(36) 在 08:50~09:25 时段用总市值(39)排序
MORNING_OVERRIDE_COLTYPES = {212, 36}
MORNING_OVERRIDE_COLTYPE = 39

# 返回条数上限（与 market_query.py ranking 保持一致）
MAX_LIMIT = 80
DEFAULT_LIMIT = 30

# WantCol 模板（已在排序字段所在列）
PRICE_WANTCOL = [
    "Code", "Setcode", "Name", "XSFLAG", "CLOSE", "NOW", "AMOUNT",
    "KZZYJL", "RiseDownRatio", "RHO", "20ZAF", "VEGA", "THISYEAR", "ZSZ", "GZZS",
]
FUND_WANTCOL = [
    "Code", "Setcode", "Name", "XSFLAG", "CLOSE", "NOW", "AMOUNT",
    "KZZYJL", "RiseDownRatio", "VAR0412", "VAR0401", "VAR0402", "ZSZ", "GZZS",
]
SPECIAL_WANTCOL = [
    "Code", "Setcode", "Name", "XSFLAG", "CLOSE", "NOW", "AMOUNT",
    "KZZYJL", "RiseDownRatio", "CONZAFDATENUM", "HSL", "ZSZ", "GZZS",
]

# 一级榜单 -> 二级榜单参数配置
# 每条: rank_key -> dict(set_domain, col_type, sort_type, name, sub_tab)
RANK_CONFIG: Dict[str, Dict[str, Any]] = {
    "price": {
        "label": "看涨跌",
        "want_col": PRICE_WANTCOL,
        "ranks": {
            "today": {"set_domain": SET_DOMAIN_ETF, "col_type": 14, "sort_type": 1, "name": "今日涨跌幅", "sub_tab": 12},
            "5d": {"set_domain": SET_DOMAIN_ETF, "col_type": 209, "sort_type": 1, "name": "5日涨跌幅", "sub_tab": 8},
            "20d": {"set_domain": SET_DOMAIN_ETF, "col_type": 370, "sort_type": 1, "name": "20日涨跌幅", "sub_tab": 9},
            "60d": {"set_domain": SET_DOMAIN_ETF, "col_type": 371, "sort_type": 1, "name": "60日涨跌幅", "sub_tab": 10},
            "year": {"set_domain": SET_DOMAIN_ETF, "col_type": 289, "sort_type": 1, "name": "今年以来", "sub_tab": 11},
        },
    },
    "fund": {
        "label": "看资金",
        "want_col": FUND_WANTCOL,
        "ranks": {
            "main": {"set_domain": SET_DOMAIN_ETF, "col_type": 212, "sort_type": 1, "name": "主力净额", "sub_tab": 13},
            "subscribe": {"set_domain": SET_DOMAIN_ETF, "col_type": 311, "sort_type": 1, "name": "申购净流入", "sub_tab": 1},
            "finance": {"set_domain": SET_DOMAIN_ETF, "col_type": 305, "sort_type": 1, "name": "融资净流入", "sub_tab": 2},
        },
    },
    "special": {
        "label": "看特色",
        "want_col": SPECIAL_WANTCOL,
        "ranks": {
            "consecutive": {"set_domain": SET_DOMAIN_ETF, "col_type": 312, "sort_type": 1, "name": "连涨榜", "sub_tab": 5},
            "turnover": {"set_domain": SET_DOMAIN_ETF, "col_type": 36, "sort_type": 1, "name": "换手榜", "sub_tab": 7},
            "premium": {"set_domain": SET_DOMAIN_ETF, "col_type": 861, "sort_type": 2, "name": "溢价榜", "sub_tab": 6},
            "custom": {"set_domain": SET_DOMAIN_CUSTOM, "col_type": 14, "sort_type": 1, "name": "自选榜", "sub_tab": 4},
        },
    },
}

# 通达信列名 -> 友好字段名
FIELD_NAME_MAP: Dict[str, str] = {
    "Code": "code",
    "Setcode": "market",
    "Name": "name",
    "NOW": "now",
    "CLOSE": "previous_close",
    "AMOUNT": "amount",
    "VOL": "volume",
    "RiseDownRatio": "rise_down_ratio",
    "RiseDownValue": "rise_down_value",
    "KZZYJL": "premium_rate",
    "HSL": "turnover_rate",
    "CONZAFDATENUM": "consecutive_days",
    "VAR0412": "main_net_amount",
    "VAR0401": "subscribe_net",
    "VAR0402": "finance_net",
    "ZSZ": "total_market_value",
    "GZZS": "track_index",
    "RHO": "rho_5d",
    "20ZAF": "zaf_20d",
    "VEGA": "vega_60d",
    "THISYEAR": "thisyear",
    "XSFLAG": "xsflag",
    "ZZ_MARKET": "zz_market",
}

# 标识类字段保持字符串，不做数值转换
STRING_FIELDS = {"code", "market", "name", "xsflag", "track_index", "zz_market"}


class CICCWMCredentialError(RuntimeError):
    """CICCWM 凭证缺失或失效。"""


def load_api_key() -> str:
    """从华为账号绑定环境文件加载登录凭证。"""
    if not XIAOYI_ENV_PATH.exists():
        raise CICCWMCredentialError(REINSTALL_MESSAGE)

    token = ""
    with open(XIAOYI_ENV_PATH, 'r', encoding='utf-8') as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip().removeprefix("export ").strip()
            if key == LOGIN_TOKEN_KEY:
                token = value.strip().strip("\"'")
                break

    api_key = token
    if not api_key:
        raise CICCWMCredentialError(REINSTALL_MESSAGE)

    return api_key


def create_ssl_context() -> ssl.SSLContext:
    """创建兼容旧服务器的 HTTPS 请求上下文。"""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        ctx.set_ciphers("ALL:@SECLEVEL=0")
        ctx.options |= ssl.OP_LEGACY_SERVER_CONNECT
    except Exception:
        pass
    return ctx


def build_fingerprint_id() -> str:
    """基于本机稳定信息生成简易设备指纹，不依赖外部库。"""
    parts = [
        platform.node(),
        socket.gethostname(),
        platform.system(),
        platform.release(),
        platform.machine(),
        platform.python_implementation(),
    ]
    raw = "|".join(part for part in parts if part)
    if not raw:
        raw = "unknown-device"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def build_user_agent() -> str:
    """生成埋点用 ASCII UA，避免 HTTP header 编码失败。"""
    python_version = ".".join(platform.python_version_tuple()[:2])
    system = platform.system() or "UnknownOS"
    machine = platform.machine() or "UnknownArch"
    return f"AI Agent/{SKILL_UA_NAME} ({PLATFORM_NAME}; {system}; {machine}; Python/{python_version})"


def report_user_action(api_key: str, cmdname: str) -> None:
    """异步上报 skill 使用埋点，失败不影响业务请求。"""
    user_agent = build_user_agent()
    user_action_log = {
        "platform": "1",
        "domain": "",
        "version": "",
        "business_id": "zt_outer_c",
        "login_id": api_key,
        "device_id": json.dumps(
            {"fingerprint_id": build_fingerprint_id()},
            ensure_ascii=False,
        ),
        "client_time": int(time.time() * 1000),
        "os": "1",
        "browser": "Bash",
        "ua": user_agent,
        "os_version": REQUEST_VERSION,
        "model": "",
        "manufactor": "",
        "page_id": "SkillsCenter.home",
        "element": "SkillsCenter.home.useskill",
        "event_id": "SkillsCenter.home.useskill_click",
        "action": "click",
        "stay_time": "null",
        "server_time": "null",
        "referer_url": "",
        "custom_ext": {"skillname": SKILL_NAME, "cmdname": cmdname},
    }
    payload = {
        "cmdname": "ReportUserActionLog",
        "param": {
            "business_id": "zt_outer_c",
            "user_action_log": json.dumps(user_action_log, ensure_ascii=False),
        },
    }

    def _send() -> None:
        try:
            from urllib import request as urllib_request

            opener = urllib_request.build_opener(urllib_request.ProxyHandler({}))
            req = urllib_request.Request(
                REPORT_URL,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": user_agent},
                method="POST",
            )
            opener.open(req, timeout=5).close()
        except Exception:
            pass

    threading.Thread(target=_send).start()


def ensure_valid_response(response: Dict[str, Any]) -> None:
    """鉴权失败时给出刷新华为账号绑定凭证的明确指引。"""
    if response.get("ret") == 5002:
        raise CICCWMCredentialError(REINSTALL_MESSAGE)


def _post(payload: Dict[str, Any]) -> Dict[str, Any]:
    """统一 POST common.fcgi，返回接口原始 JSON。"""
    api_key = load_api_key()
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json",
        "Cookie": "apiKey=" + api_key,
        "User-Agent": build_user_agent(),
        "version": REQUEST_VERSION,
    }

    try:
        from urllib import request as urllib_request

        req = urllib_request.Request(
            API_URL,
            data=body,
            headers=headers,
            method="POST",
        )
        with urllib_request.urlopen(req, timeout=REQUEST_TIMEOUT, context=create_ssl_context()) as resp:
            response = json.loads(resp.read().decode("utf-8"))
            ensure_valid_response(response)
            return response
    except Exception as exc:
        if isinstance(exc, CICCWMCredentialError):
            raise
        return {"status": "error", "message": f"请求失败: {exc}"}


def send_tdx_request(endpoint: str, tdx_payload: Dict[str, Any]) -> Dict[str, Any]:
    """通过 SkillTdxQuotationQueryCommon 封装调用通达信行情接口。"""
    api_key = load_api_key()
    report_user_action(api_key, endpoint)
    payload = {
        "cmdname": TDX_CMD_NAME,
        "param": {
            "entry": endpoint,
            "tdx_param": json.dumps(tdx_payload, ensure_ascii=False),
        },
    }
    return _post(payload)


def send_cmd_request(cmdname: str, param: Dict[str, Any]) -> Dict[str, Any]:
    """直接以 cmdname 调用 common.fcgi（如 MCSearchHotList）。"""
    api_key = load_api_key()
    report_user_action(api_key, cmdname)
    payload = {"cmdname": cmdname, "param": param}
    return _post(payload)


def _parse_payload(response: Dict[str, Any]) -> Dict[str, Any]:
    """解析 common.fcgi 响应：校验 ret，返回 rsp.data（JSON 字符串自动解析）或 rsp 本身。

    Skill 封装的通达信接口会把行情结构放在 rsp.data 里以 JSON 字符串返回，
    本函数统一还原为可用的 dict（含 ListHead/ListItem 或 stocks 等业务字段）。
    """
    if not isinstance(response, dict):
        raise ValueError("接口返回非对象结构")

    if response.get("ret") not in (None, 0):
        raise ValueError(response.get("msg") or "接口返回 ret 非 0")

    rsp = response.get("rsp")
    if not isinstance(rsp, dict):
        return response

    if rsp.get("ret_code") not in (None, 0):
        raise ValueError(rsp.get("ret_msg") or "接口返回 ret_code 非 0")

    data = rsp.get("data")
    if isinstance(data, str):
        if not data.strip():
            return {}
        try:
            return json.loads(data)
        except json.JSONDecodeError as exc:
            raise ValueError("rsp.data 不是合法 JSON") from exc
    if isinstance(data, dict):
        return data
    return rsp


def _is_morning_window() -> bool:
    """判断当前是否处于 08:50~09:25（沪深交易前特殊排序时段，Asia/Shanghai）。"""
    tz = timezone(timedelta(hours=8))
    now = datetime.now(tz)
    minutes = now.hour * 60 + now.minute
    return 8 * 60 + 50 <= minutes <= 9 * 60 + 25


def _resolve_col_type(col_type: int) -> int:
    """主力净额/换手榜在 08:50~09:25 时段使用总市值(39)排序。"""
    if col_type in MORNING_OVERRIDE_COLTYPES and _is_morning_window():
        return MORNING_OVERRIDE_COLTYPE
    return col_type


def _cap_limit(limit: int) -> int:
    """返回条数限制，默认 30，上限 80。"""
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = DEFAULT_LIMIT
    if limit <= 0:
        limit = DEFAULT_LIMIT
    if limit > MAX_LIMIT:
        limit = MAX_LIMIT
    return limit


def coerce_value(field: str, value: Any) -> Any:
    """转换数字字符串，同时保留证券代码等标识符。"""
    if not isinstance(value, str) or field in STRING_FIELDS:
        return value

    try:
        number = float(value)
    except ValueError:
        return value

    if number.is_integer():
        return int(number)
    return number


def list_items_to_records(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """将通达信 ListHead/ListItem 表格结构转换为带字段名的记录。"""
    columns = data.get("ListHead", {}).get("ItemHead", [])
    rows = data.get("ListItem", [])
    records: List[Dict[str, Any]] = []

    for row in rows:
        values = row.get("Item", [])
        record: Dict[str, Any] = {}
        for column, value in zip(columns, values):
            field = FIELD_NAME_MAP.get(column, column)
            record[field] = coerce_value(field, value)
        records.append(record)

    return records


def fetch_etf_rank(
    tab: str,
    rank_key: str,
    limit: int = DEFAULT_LIMIT,
    start: int = 0,
    sort_type: Optional[int] = None,
    raw: bool = False,
) -> Dict[str, Any]:
    """获取 ETF 涨跌/资金/特色榜单（TDX PBMultiHQ）。"""
    tab_cfg = RANK_CONFIG.get(tab)
    if not tab_cfg:
        raise ValueError(f"不支持的一级榜单: {tab}")

    ranks = tab_cfg["ranks"]
    rank_cfg = ranks.get(rank_key)
    if not rank_cfg:
        raise ValueError(
            f"不支持的榜单类型: {rank_key}; 可选: {', '.join(ranks.keys())}"
        )

    effective_sort = rank_cfg["sort_type"] if sort_type is None else sort_type
    effective_limit = _cap_limit(limit)
    effective_col_type = _resolve_col_type(rank_cfg["col_type"])

    payload = {
        "Head": {"Target": ETR_TARGET},
        "SetDomain": rank_cfg["set_domain"],
        "WantCol": tab_cfg["want_col"],
        "ColType": effective_col_type,
        "Startxh": start,
        "WantNum": effective_limit,
        "SortType": effective_sort,
    }
    response = send_tdx_request("HQServ.PBMultiHQ", payload)
    if raw:
        return response

    result = _parse_payload(response)
    if "ListItem" not in result:
        return result

    return {
        "tab": tab,
        "tab_name": tab_cfg["label"],
        "rank": rank_key,
        "rank_name": rank_cfg["name"],
        "sub_tab": rank_cfg["sub_tab"],
        "set_domain": rank_cfg["set_domain"],
        "col_type": effective_col_type,
        "sort_type": effective_sort,
        "limit": effective_limit,
        "start": start,
        "total": coerce_value("total", result.get("SBTSize")),
        "items": list_items_to_records(result),
    }


# ---------------- 热搜榜（MCSearchHotList） ----------------

def _extract_hot_stocks(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """从 MCSearchHotList 响应中提取 ETF 列表。"""
    if not isinstance(response, dict):
        return []
    data = _parse_payload(response)
    if isinstance(data, dict) and data.get("ret_code") not in (None, 0):
        raise ValueError(data.get("ret_msg") or "热搜榜接口返回 ret_code 非 0")

    stocks = data.get("stocks") if isinstance(data, dict) else None
    if isinstance(stocks, dict):
        lst = stocks.get("list")
        return lst if isinstance(lst, list) else []
    if isinstance(stocks, list):
        return stocks
    return []


def _is_last_page(response: Dict[str, Any]) -> bool:
    """判断热搜榜是否为最后一页。"""
    try:
        data = _parse_payload(response)
    except Exception:
        return False
    return bool(data.get("last_page")) if isinstance(data, dict) else False


def _etf_setcode(code: str) -> int:
    """根据 ETF 代码前缀推断市场编码：5 开头上海(1)，1 开头深圳(0)。"""
    code = str(code)
    if code.startswith("5"):
        return 1
    if code.startswith("1"):
        return 0
    return 1


def _pbcombhq_to_map(result: Dict[str, Any], codes: List[str]) -> Dict[str, Dict[str, Any]]:
    """解析 PBCombHQ 批量行情结果，按请求顺序与 codes 对齐（接口不回传 Code）。"""
    data = result if isinstance(result, dict) else {}
    columns = data.get("ListHead", {}).get("ItemHead", [])
    rows = data.get("ListItem", [])
    out: Dict[str, Dict[str, Any]] = {}

    for index, row in enumerate(rows):
        if index >= len(codes):
            break
        values = row.get("Item", [])
        record: Dict[str, Any] = {}
        for column, value in zip(columns, values):
            field = FIELD_NAME_MAP.get(column, column)
            record[field] = coerce_value(field, value)
        # 优先用接口回传的 code，否则按请求顺序回填
        code = str(record.get("code", "")).strip() or str(codes[index]).strip()
        record.pop("code", None)
        if code:
            out[code] = record
    return out


def _enrich_hot_list(stocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """用 HQServ.PBCombHQ 批量行情为热搜 ETF 补充行情字段，失败不影响主列表。"""
    pairs: List[Tuple[str, int]] = []
    for stock in stocks:
        code = str(stock.get("secu_code", "")).strip()
        if code:
            pairs.append((code, _etf_setcode(code)))

    if not pairs:
        return stocks

    payload = {
        "Head": {"Target": ETR_TARGET},
        "WantCol": ["Code", "NOW", "CLOSE", "Name", "RiseDownRatio", "ZSZ", "AMOUNT", "KZZYJL", "GZZS"],
        "Setcode": [str(setcode) for _, setcode in pairs],
        "Code": [code for code, _ in pairs],
    }
    try:
        response = send_tdx_request("HQServ.PBCombHQ", payload)
        result = _parse_payload(response)
    except Exception:
        return stocks

    quote_map = _pbcombhq_to_map(result, [code for code, _ in pairs])
    if not quote_map:
        return stocks

    for stock in stocks:
        code = str(stock.get("secu_code", "")).strip()
        if code in quote_map:
            for key, value in quote_map[code].items():
                stock.setdefault(key, value)
    return stocks


def _normalize_hot_stock(stock: Dict[str, Any]) -> Dict[str, Any]:
    """规整热搜榜单单条记录的字段。"""
    item: Dict[str, Any] = {
        "code": stock.get("secu_code", ""),
        "name": stock.get("secu_name", ""),
        "market": stock.get("market", ""),
        "sub_market": stock.get("sub_market", ""),
    }
    for key in (
        "now", "previous_close", "rise_down_ratio", "amount",
        "premium_rate", "total_market_value", "track_index",
    ):
        if key in stock:
            item[key] = stock[key]
    props = stock.get("props")
    if props not in (None, ""):
        item["props"] = props
    if "rank" in stock:
        item["rank"] = stock["rank"]
    return item


def fetch_hot_search(
    page_num: int = 1,
    limit: int = 30,
    enrich: bool = True,
    raw: bool = False,
) -> Dict[str, Any]:
    """获取 ETF 热搜榜（MCSearchHotList，type=2001），可选用 PBCombHQ 补充行情。"""
    limit = max(1, min(int(limit or DEFAULT_LIMIT), 60))
    start_page = int(page_num) if page_num and page_num > 0 else 1

    stocks: List[Dict[str, Any]] = []
    last_page = False
    pn = start_page

    while len(stocks) < limit and not last_page:
        response = send_cmd_request(HOT_CMD_NAME, {"type": 2001, "page_num": pn})
        if raw and pn == start_page:
            return response

        page_stocks = _extract_hot_stocks(response)
        last_page = _is_last_page(response)
        if not page_stocks:
            break
        for stock in page_stocks:
            stock.setdefault("page_num", pn)
        stocks.extend(page_stocks)
        pn += 1

    stocks = stocks[:limit]
    for index, stock in enumerate(stocks):
        stock.setdefault("rank", index + 1)

    if enrich:
        stocks = _enrich_hot_list(stocks)

    items = [_normalize_hot_stock(stock) for stock in stocks]
    return {
        "tab": "special",
        "tab_name": "看特色",
        "rank": "hot_search",
        "rank_name": "热搜榜",
        "sub_tab": 3,
        "type": 2001,
        "page_num": start_page,
        "limit": limit,
        "enriched": bool(enrich),
        "total": len(items),
        "items": items,
    }


# ---------------- 命令行 ----------------

def _add_tdx_common_args(parser: argparse.ArgumentParser) -> None:
    """为 TDX 榜单子命令添加通用参数。"""
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help=f"返回条数，默认 {DEFAULT_LIMIT}，最大 {MAX_LIMIT}")
    parser.add_argument("--start", type=int, default=0, help="起始序号 Startxh，默认 0")
    parser.add_argument("--sort_type", type=int, default=None, help="排序方式：1=降序，2=升序；默认按榜单配置")
    parser.add_argument("--raw", action="store_true", help="返回接口原始结构")


def _rank_choices(tab: str) -> List[str]:
    return list(RANK_CONFIG[tab]["ranks"].keys())


def main() -> None:
    parser = argparse.ArgumentParser(
        description="中金财富 ETF 热门榜单查询工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="查询类型")

    p_price = subparsers.add_parser("price", help="看涨跌榜单")
    p_price.add_argument(
        "--type", default="today", choices=_rank_choices("price"),
        help="榜单类型：today/5d/20d/60d/year，默认 today",
    )
    _add_tdx_common_args(p_price)

    p_fund = subparsers.add_parser("fund", help="看资金榜单")
    p_fund.add_argument(
        "--type", default="main", choices=_rank_choices("fund"),
        help="榜单类型：main/subscribe/finance，默认 main",
    )
    _add_tdx_common_args(p_fund)

    p_special = subparsers.add_parser("special", help="看特色榜单")
    p_special.add_argument(
        "--type", default="consecutive", choices=_rank_choices("special"),
        help="榜单类型：consecutive/turnover/premium/custom，默认 consecutive",
    )
    _add_tdx_common_args(p_special)

    p_hot = subparsers.add_parser("hot_search", help="热搜榜（MCSearchHotList）")
    p_hot.add_argument("--page_num", type=int, default=1, help="起始页码，默认 1")
    p_hot.add_argument("--limit", type=int, default=30, help="返回条数，默认 30，最大 60")
    p_hot.add_argument("--no_enrich", action="store_true", help="不调用 PBCombHQ 补充行情字段")
    p_hot.add_argument("--raw", action="store_true", help="返回接口原始结构")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command in ("price", "fund", "special"):
            result = fetch_etf_rank(
                args.command,
                args.type,
                limit=args.limit,
                start=args.start,
                sort_type=args.sort_type,
                raw=args.raw,
            )
        elif args.command == "hot_search":
            result = fetch_hot_search(
                page_num=args.page_num,
                limit=args.limit,
                enrich=not args.no_enrich,
                raw=args.raw,
            )
        else:
            raise ValueError(f"不支持的查询类型: {args.command}")
    except Exception as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2))
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
