#!/usr/bin/env python3
"""
中金财富基金产品信息查询模块
支持公募基金搜索、基金档案、费率明细、持仓概况、历史表现、分红公告与横向对比。
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
import warnings
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

warnings.filterwarnings("ignore")

XIAOYI_ENV_PATH = Path("/home/sandbox/.openclaw/.xiaoyienv")
LOGIN_TOKEN_KEY = "117860603_login_token"
API_BASE = "https://skill.ciccwm.com/zzt/ext/fcgi/common.fcgi"
REPORT_URL = "https://webreport.ciccwm.com/zzt/fcgi/common.fcgi"
REQUEST_VERSION = "20260612"
REQUEST_TIMEOUT = 20
SKILL_NAME = "基金产品信息"
SKILL_UA_NAME = "ciccwm-fund-product-info"
PLATFORM_NAME = "huawei"
DISCLAIMER = "本服务提供的数据仅供参考，不构成投资建议，投资有风险，入市需谨慎。"
HISTORY_NOTE = "历史表现不代表未来收益。"
REINSTALL_MESSAGE = (
    "未获取到有效的 117860603_login_token 或鉴权已失效。"
    "请刷新 117860603_login_token，或调用 huawei_id_tool 工具获取新凭证。"
)

CMD_NAMES = {
    "search": "SkillCmdFmSearchFund",
    "detail": "SkillCmdFmQryFundProductInfo",
    "manager": "SkillCmdFmQryFundManagerList",
    "position": "SkillCmdFmQryPositionDistributionList",
    "scale": "SkillCmdFmQryScaleShareList",
    "dividend": "SkillCmdFmQryDividendList",
    "announcement": "SkillCmdFmQryAnnouncementList",
    "phase_market": "SkillCmdFmQryPhaseMarketList",
    "fixed_period_rate": "SkillCmdFmQryFundFixedPeriodRate",
    "duration_nav": "SkillCmdFmBatchGetDurationNav",
}

RISK_LEVEL_LABELS = {
    1: "低风险",
    2: "中低风险",
    3: "中风险",
    4: "中高风险",
    5: "高风险",
}

PRODUCT_SELL_STATUS_LABELS = {
    0: "未上架",
    1: "即将开售",
    2: "买入",
    3: "继续买入",
    4: "已售罄",
    5: "募集已结束",
    6: "封闭中",
    7: "已到期或已下架",
    8: "申购结束",
}

PURCHASE_OPEN_RULE_LABELS = {
    1: "不开放申购",
    2: "完全开放式",
    3: "根据定开区间决定是否可申购",
}

REDEEM_OPEN_RULE_LABELS = {
    1: "不支持手动赎回",
    2: "完全开放式",
    3: "根据定开区间决定是否可赎回",
    4: "每月固定某些天不能手动赎回",
}


class CICCWMCredentialError(RuntimeError):
    """CICCWM 凭证缺失或失效。"""


class CICCWMApiError(RuntimeError):
    """CICCWM 接口返回业务错误。"""


class FundResolveError(RuntimeError):
    """基金搜索或解析失败。"""


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
    """创建兼容旧服务器的 SSL 上下文。"""
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
    raw = "|".join(part for part in parts if part) or "unknown-device"
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
    ret = response.get("ret")
    if ret in (None, 0, "0"):
        return
    if ret == 5002:
        raise CICCWMCredentialError(REINSTALL_MESSAGE)
    msg = response.get("msg") or "接口返回业务错误"
    msgno = response.get("msgno")
    detail = f"ret={ret}, msg={msg}"
    if msgno:
        detail = f"{detail}, msgno={msgno}"
    raise CICCWMApiError(detail)


def send_request(cmd_key: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """发送基金业务请求。"""
    cmdname = CMD_NAMES[cmd_key]
    api_key = load_api_key()
    report_user_action(api_key, cmdname)
    payload = {"cmdname": cmdname, "param": params}
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    from urllib import request as urllib_request

    req = urllib_request.Request(
        API_BASE,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Cookie": f"apiKey={api_key}",
            "User-Agent": build_user_agent(),
        },
        method="POST",
    )
    opener = urllib_request.build_opener(
        urllib_request.ProxyHandler({}),
        urllib_request.HTTPSHandler(context=create_ssl_context()),
    )
    with opener.open(req, timeout=REQUEST_TIMEOUT) as response:
        result = json.loads(response.read().decode("utf-8"))
    ensure_valid_response(result)
    return result


def get_path(data: Dict[str, Any], *path: str, default: Any = None) -> Any:
    """安全读取嵌套字典字段。"""
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def compact_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """移除空值，保留 0 和 False。"""
    return {key: value for key, value in data.items() if value not in (None, "", [], {})}


def to_int(value: Any) -> Optional[int]:
    """将接口枚举值转为 int，无法转换时返回 None。"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def enum_label(mapping: Dict[int, str], value: Any) -> Optional[str]:
    """输出枚举中文标签，未知枚举保留 code。"""
    code = to_int(value)
    if code is None:
        return None
    return mapping.get(code, f"未知状态(code={code})")


def first_list(*values: Any) -> List[Any]:
    """从候选字段中取第一组列表。"""
    for value in values:
        if isinstance(value, list):
            return value
    return []


def normalize_candidate(item: Dict[str, Any]) -> Dict[str, Any]:
    """规范化搜索候选基金字段。"""
    risk_level = item.get("risk_level") or item.get("risk_level_name")
    product_sell_status = item.get("product_sell_status")
    return compact_dict(
        {
            "fund_short_name": item.get("fund_short_name")
            or item.get("product_short_name")
            or item.get("product_sub_name"),
            "fund_code": item.get("fund_code") or item.get("code"),
            "fund_name": item.get("fund_name") or item.get("product_name") or item.get("name"),
            "product_id": item.get("product_id") or item.get("fund_id"),
            "product_id_note": "内部产品ID",
            "fund_type": item.get("fund_type") or item.get("fund_type_name") or item.get("category_name"),
            "risk_level": risk_level,
            "risk_level_label": enum_label(RISK_LEVEL_LABELS, risk_level),
            "product_sell_status": product_sell_status,
            "product_sell_status_label": enum_label(PRODUCT_SELL_STATUS_LABELS, product_sell_status),
            "purchase_open_rule": item.get("purchase_open_rule"),
            "purchase_open_rule_label": enum_label(PURCHASE_OPEN_RULE_LABELS, item.get("purchase_open_rule")),
            "template_category": item.get("template_category"),
            "raw": item,
        }
    )


def normalize_product(detail_rsp: Dict[str, Any]) -> Dict[str, Any]:
    """从详情响应提取基金档案摘要。"""
    rsp = detail_rsp.get("rsp", {}) if isinstance(detail_rsp, dict) else {}
    product_info = rsp.get("product_info") or {}
    base_info = product_info.get("base_info") or {}
    trade_rule = product_info.get("trade_rule") or {}
    op_info = product_info.get("op_info") or {}
    product_ext = rsp.get("product_ext") or {}
    fund_supply = product_ext.get("fund_supply") or {}
    product_date_info = product_ext.get("product_date_info") or {}
    fund_info = rsp.get("fund_info") or {}
    fund_archive = rsp.get("fund_archive") or {}
    manager_list = first_list(
        rsp.get("fund_manager_list"),
        product_ext.get("fund_manager_list"),
        fund_info.get("fund_manager_list"),
    )

    risk_level = (
        base_info.get("suitability_risk_level")
        or product_info.get("risk_level")
        or product_info.get("risk_level_name")
    )
    purchase_open_rule = trade_rule.get("purchase_open_rule")
    redeem_open_rule = trade_rule.get("redeem_open_rule")
    product_sell_status = product_ext.get("product_sell_status") or op_info.get("sale_state")

    return compact_dict(
        {
            "fund_short_name": base_info.get("brief_name")
            or product_info.get("fund_short_name")
            or product_info.get("product_short_name"),
            "fund_code": base_info.get("fund_code")
            or fund_supply.get("fund_code")
            or product_info.get("fund_code")
            or fund_info.get("fund_code")
            or rsp.get("fund_code"),
            "fund_name": base_info.get("full_name") or product_info.get("fund_name") or product_info.get("product_name"),
            "product_id": base_info.get("product_id") or product_info.get("product_id") or rsp.get("product_id"),
            "product_id_note": "内部产品ID",
            "fund_type": product_info.get("fund_type")
            or product_info.get("fund_type_name")
            or product_ext.get("fund_type")
            or fund_archive.get("fund_type"),
            "risk_level": risk_level,
            "risk_level_label": enum_label(RISK_LEVEL_LABELS, risk_level),
            "establish_date": base_info.get("establish_date")
            or product_date_info.get("establish_date")
            or product_info.get("establish_date")
            or fund_archive.get("establish_date"),
            "fund_scale": product_ext.get("fund_scale") or fund_archive.get("fund_scale"),
            "performance_benchmark": product_ext.get("performance_benchmark")
            or fund_supply.get("benchmark")
            or fund_archive.get("performance_benchmark"),
            "fund_manager": base_info.get("fund_manager_desc")
            or product_ext.get("fund_manager")
            or product_info.get("fund_manager"),
            "managers": manager_list,
            "manager_inst_id": get_path(base_info, "inst_conf", "manager_inst_id"),
            "custodian_inst_id": get_path(base_info, "inst_conf", "custodian_inst_id"),
            "fund_custodian": product_ext.get("fund_custodian"),
            "purchase_open_rule": purchase_open_rule,
            "purchase_open_rule_label": enum_label(PURCHASE_OPEN_RULE_LABELS, purchase_open_rule),
            "redeem_open_rule": redeem_open_rule,
            "redeem_open_rule_label": enum_label(REDEEM_OPEN_RULE_LABELS, redeem_open_rule),
            "product_sell_status": product_sell_status,
            "product_sell_status_label": enum_label(PRODUCT_SELL_STATUS_LABELS, product_sell_status),
            "nav": rsp.get("nav") or product_ext.get("nav"),
            "acc_nav": rsp.get("acc_nav") or product_ext.get("acc_nav"),
            "nav_date": rsp.get("nav_date") or product_ext.get("nav_date"),
        }
    )


def extract_fee_sections(detail_rsp: Dict[str, Any]) -> Dict[str, Any]:
    """从详情响应提取费率相关字段。"""
    rsp = detail_rsp.get("rsp", {}) if isinstance(detail_rsp, dict) else {}
    product_info = rsp.get("product_info") or {}
    trade_rule = product_info.get("trade_rule") or {}
    op_info = product_info.get("op_info") or {}
    product_ext = rsp.get("product_ext") or {}
    product_trade_rule = product_ext.get("product_trade_rule") or {}
    return compact_dict(
        {
            "subscribe_fee_desc": op_info.get("subscribe_fee_desc") or product_trade_rule.get("subscribe_fee_desc"),
            "purchase_fee_desc": op_info.get("purchase_fee_desc") or product_trade_rule.get("purchase_fee_desc"),
            "redeem_fee_desc": op_info.get("redeem_fee_desc") or product_trade_rule.get("redeem_fee_desc"),
            "subscribe_charge_detail": trade_rule.get("subscribe_charge_detail")
            or product_trade_rule.get("subscribe_charge_detail"),
            "purchase_charge_detail": trade_rule.get("purchase_charge_detail")
            or product_trade_rule.get("purchase_charge_detail"),
            "redeem_charge_detail": trade_rule.get("redeem_charge_detail") or product_trade_rule.get("redeem_charge_detail"),
            "business_fee": trade_rule.get("business_fee") or product_trade_rule.get("business_fee"),
            "rate_discount": product_info.get("rate_discount") or rsp.get("rate_discount") or product_ext.get("rate_discount"),
            "trade_rule": product_trade_rule or trade_rule,
            "raw_fee_fields": compact_dict(
                {
                    key: value
                    for source in (product_info, product_ext, trade_rule, op_info, product_trade_rule)
                    for key, value in source.items()
                    if "fee" in str(key).lower() or "rate" in str(key).lower()
                }
            ),
        }
    )


def extract_report_date(detail_rsp: Dict[str, Any]) -> Optional[str]:
    """从详情响应中提取可能的报告期。持仓查询默认不使用该推导日期。"""
    rsp = detail_rsp.get("rsp", {}) if isinstance(detail_rsp, dict) else {}
    product_ext = rsp.get("product_ext") or {}
    fund_supply = product_ext.get("fund_supply") or {}
    report_datas = first_list(rsp.get("report_datas"), rsp.get("report_data"))
    if report_datas and isinstance(report_datas[0], dict):
        return report_datas[0].get("date") or report_datas[0].get("report_date")
    return fund_supply.get("fund_date") or rsp.get("date") or rsp.get("report_date")


def is_empty_position_rsp(rsp: Dict[str, Any]) -> bool:
    """判断持仓接口是否没有返回可展示的结构化持仓。"""
    return not (rsp.get("targets") or rsp.get("industs") or rsp.get("assets"))


def extract_holding_report_date(rsp: Dict[str, Any]) -> Optional[str]:
    """从持仓响应中提取报告期。"""
    assets = rsp.get("assets")
    if isinstance(assets, dict) and assets.get("date"):
        return assets.get("date")
    for key in ("targets", "industs"):
        items = rsp.get(key)
        if isinstance(items, list) and items and isinstance(items[0], dict) and items[0].get("date"):
            return items[0].get("date")
    return rsp.get("date") or rsp.get("report_date")


def build_holding_summary(rsp: Dict[str, Any]) -> Dict[str, Any]:
    """构建面向用户的持仓摘要，结构化数据为空时保留原始响应便于排查。"""
    summary = compact_dict(
        {
            "targets": rsp.get("targets"),
            "industries": rsp.get("industs"),
            "assets": rsp.get("assets"),
            "heavy_stocks": rsp.get("heavy_stocks") or rsp.get("stock_list"),
            "heavy_bonds": rsp.get("heavy_bonds") or rsp.get("bond_list"),
            "industry_distribution": rsp.get("industry_distribution") or rsp.get("industry_list"),
            "asset_distribution": rsp.get("asset_distribution") or rsp.get("position_distribution"),
        }
    )
    if not summary:
        summary["raw_position"] = rsp
    return summary


def extract_fund_code(detail_rsp: Dict[str, Any], fallback: Optional[str] = None) -> Optional[str]:
    """从详情响应中提取基金代码。"""
    profile = normalize_product(detail_rsp)
    return profile.get("fund_code") or fallback


def search_funds(keyword: str, page: int = 1, size: int = 10, raw: bool = False) -> Dict[str, Any]:
    """按关键词搜索公募基金候选。"""
    if not keyword:
        raise ValueError("keyword 不能为空")
    page = max(page, 1)
    size = min(max(size, 1), 20)
    response = send_request(
        "search",
        {
            "keyword": keyword,
            "recpage": page,
            "reccnt": size,
            "search_type": 1,
        },
    )
    if raw:
        return with_disclaimer({"query": {"keyword": keyword, "page": page, "size": size}, "raw": response})

    rsp = response.get("rsp", {}) if isinstance(response, dict) else {}
    funds = first_list(rsp.get("hedge_funds"), rsp.get("funds"), rsp.get("records"), rsp.get("list"))
    candidates = [normalize_candidate(item) for item in funds if isinstance(item, dict)]
    total_count = rsp.get("total") or rsp.get("total_count")
    total_pages = rsp.get("pages") or rsp.get("total_pages")
    return with_disclaimer(
        {
            "query": {"keyword": keyword, "page": page, "page_size": size},
            "page": page,
            "page_size": size,
            "returned_count": len(candidates),
            "count": len(candidates),
            "total_count": total_count,
            "total_pages": total_pages,
            "has_more": bool(total_pages and page < int(total_pages)),
            "display_note": "默认展示当前页候选；如需查看更多，请继续查询下一页。",
            "candidates": candidates,
        }
    )


def resolve_product(
    product_id: Optional[str] = None,
    keyword: Optional[str] = None,
    select_first: bool = False,
) -> Tuple[str, Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """解析查询对象，返回 product_id、候选基金与多候选响应。"""
    if product_id:
        if product_id.isdigit() and len(product_id) == 6 and product_id.startswith("0"):
            keyword = product_id
        else:
            return product_id, None, None
    if keyword:
        pass
    else:
        raise FundResolveError("请提供 product_id 或 keyword")

    if product_id and keyword == product_id:
        select_first = True
    elif product_id:
        return product_id, None, None

    search_result = search_funds(keyword)
    candidates = search_result.get("candidates", [])
    if not candidates:
        raise FundResolveError(f"未搜索到匹配的公募基金: {keyword}")

    if len(candidates) > 1 and not select_first:
        return "", None, {
            "status": "multiple_candidates",
            "message": "搜索命中多只基金，请指定 product_id，或使用 --select-first 选择第一条候选。",
            "query": {"keyword": keyword},
            "candidates": candidates,
            "disclaimer": DISCLAIMER,
        }

    candidate = candidates[0]
    resolved_product_id = candidate.get("product_id")
    if not resolved_product_id:
        raise FundResolveError("搜索结果缺少 product_id，无法继续查询详情")
    return str(resolved_product_id), candidate, None


def with_disclaimer(payload: Dict[str, Any], history_note: bool = False) -> Dict[str, Any]:
    """追加统一风险声明。"""
    payload["disclaimer"] = DISCLAIMER
    if history_note:
        payload["history_note"] = HISTORY_NOTE
    return payload


def fetch_detail(product_id: str, raw: bool = False) -> Dict[str, Any]:
    """查询基金详情原始响应。"""
    response = send_request("detail", {"product_id": product_id, "need_wealth_article": 1})
    if raw:
        return with_disclaimer({"query": {"product_id": product_id}, "raw": response})
    return response


def fetch_managers(fund_code: str, raw: bool = False) -> Dict[str, Any]:
    """查询基金经理列表。"""
    response = send_request("manager", {"fund_code": fund_code, "state": 1})
    if raw:
        return response
    rsp = response.get("rsp", {}) if isinstance(response, dict) else {}
    managers = first_list(rsp.get("managers"), rsp.get("fund_manager_list"), rsp.get("list"))
    return {"managers": managers}


def fetch_profile(
    product_id: Optional[str] = None,
    keyword: Optional[str] = None,
    select_first: bool = False,
    raw: bool = False,
) -> Dict[str, Any]:
    """查询基金档案。"""
    resolved_product_id, candidate, multi = resolve_product(product_id, keyword, select_first)
    if multi:
        return multi

    detail = fetch_detail(resolved_product_id)
    if raw:
        return with_disclaimer(
            {
                "query": {"product_id": resolved_product_id, "keyword": keyword},
                "candidate": candidate,
                "raw": detail,
            }
        )

    profile = normalize_product(detail)
    fund_code = profile.get("fund_code")
    if fund_code and not profile.get("managers"):
        try:
            profile.update(fetch_managers(str(fund_code)))
        except Exception:
            pass

    return with_disclaimer(
        {
            "query": {"product_id": resolved_product_id, "keyword": keyword},
            "candidate": candidate,
            "profile": profile,
        }
    )


def fetch_fees(
    product_id: Optional[str] = None,
    keyword: Optional[str] = None,
    select_first: bool = False,
    raw: bool = False,
) -> Dict[str, Any]:
    """查询基金费率明细。"""
    resolved_product_id, candidate, multi = resolve_product(product_id, keyword, select_first)
    if multi:
        return multi
    detail = fetch_detail(resolved_product_id)
    if raw:
        return with_disclaimer(
            {
                "query": {"product_id": resolved_product_id, "keyword": keyword},
                "candidate": candidate,
                "raw": detail,
            }
        )
    return with_disclaimer(
        {
            "query": {"product_id": resolved_product_id, "keyword": keyword},
            "candidate": candidate,
            "fund": normalize_product(detail),
            "fees": extract_fee_sections(detail),
        }
    )


def fetch_holding(
    product_id: Optional[str] = None,
    keyword: Optional[str] = None,
    select_first: bool = False,
    date: Optional[str] = None,
    raw: bool = False,
) -> Dict[str, Any]:
    """查询基金持仓概况。"""
    resolved_product_id, candidate, multi = resolve_product(product_id, keyword, select_first)
    if multi:
        return multi

    detail = fetch_detail(resolved_product_id)
    fund = normalize_product(detail)
    fund_code = extract_fund_code(detail, candidate.get("fund_code") if candidate else None)
    requested_date = date

    if not fund_code:
        raise FundResolveError("详情响应缺少 fund_code，无法查询持仓概况")

    params: Dict[str, Any] = {"fund_code": fund_code, "query_type": [1, 2, 3]}
    if requested_date:
        params["date"] = requested_date
    position = send_request("position", params)
    rsp = position.get("rsp", {}) if isinstance(position, dict) else {}
    fallback_reason = None
    if requested_date and is_empty_position_rsp(rsp):
        fallback_reason = f"指定日期 {requested_date} 未返回结构化持仓，已改为不传 date 查询最新季度数据。"
        position = send_request("position", {"fund_code": fund_code, "query_type": [1, 2, 3]})
        rsp = position.get("rsp", {}) if isinstance(position, dict) else {}

    if raw:
        return with_disclaimer(
            {
                "query": {
                    "product_id": resolved_product_id,
                    "keyword": keyword,
                    "fund_code": fund_code,
                    "date": requested_date,
                },
                "candidate": candidate,
                "detail_raw": detail,
                "position_raw": position,
                "fallback_reason": fallback_reason,
            }
        )

    holding_report_date = extract_holding_report_date(rsp)
    return with_disclaimer(
        compact_dict(
            {
                "query": {
                    "product_id": resolved_product_id,
                    "keyword": keyword,
                    "fund_code": fund_code,
                    "date": requested_date,
                },
                "candidate": candidate,
                "fund": fund,
                "holding_report_date": holding_report_date,
                "fallback_reason": fallback_reason,
                "holding": build_holding_summary(rsp),
            }
        )
    )


def fetch_phase_market(fund_code: str, raw: bool = False) -> Dict[str, Any]:
    """查询阶段涨跌幅。"""
    response = send_request("phase_market", {"fund_code": fund_code})
    if raw:
        return response
    return response.get("rsp", {}) if isinstance(response, dict) else {}


def fetch_fixed_period_rate(fund_code: str, raw: bool = False) -> Dict[str, Any]:
    """查询固定周期收益率。"""
    response = send_request("fixed_period_rate", {"fund_code": fund_code, "period_type": 1})
    if raw:
        return response
    return response.get("rsp", {}) if isinstance(response, dict) else {}


def fetch_duration_nav(fund_code: str, raw: bool = False) -> Dict[str, Any]:
    """查询区间净值。"""
    response = send_request("duration_nav", {"fund_code": fund_code, "begin_date": "", "end_date": "", "reccnt": 20})
    if raw:
        return response
    return response.get("rsp", {}) if isinstance(response, dict) else {}


def fetch_performance(
    product_id: Optional[str] = None,
    keyword: Optional[str] = None,
    select_first: bool = False,
    include_fixed: bool = False,
    include_nav: bool = False,
    raw: bool = False,
) -> Dict[str, Any]:
    """查询基金历史表现。"""
    resolved_product_id, candidate, multi = resolve_product(product_id, keyword, select_first)
    if multi:
        return multi

    detail = fetch_detail(resolved_product_id)
    fund = normalize_product(detail)
    fund_code = extract_fund_code(detail, candidate.get("fund_code") if candidate else None)
    if not fund_code:
        raise FundResolveError("详情响应缺少 fund_code，无法查询历史表现")

    phase = fetch_phase_market(fund_code, raw=raw)
    fixed = fetch_fixed_period_rate(fund_code, raw=raw) if include_fixed else None
    nav = fetch_duration_nav(fund_code, raw=raw) if include_nav else None

    return with_disclaimer(
        compact_dict(
            {
                "query": {"product_id": resolved_product_id, "keyword": keyword, "fund_code": fund_code},
                "candidate": candidate,
                "fund": fund,
                "phase_market": phase,
                "fixed_period_rate": fixed,
                "duration_nav": nav,
            }
        ),
        history_note=True,
    )


def fetch_events(
    product_id: Optional[str] = None,
    keyword: Optional[str] = None,
    select_first: bool = False,
    raw: bool = False,
) -> Dict[str, Any]:
    """查询基金分红与公告。"""
    resolved_product_id, candidate, multi = resolve_product(product_id, keyword, select_first)
    if multi:
        return multi

    detail = fetch_detail(resolved_product_id)
    fund = normalize_product(detail)
    fund_code = extract_fund_code(detail, candidate.get("fund_code") if candidate else None)
    if not fund_code:
        raise FundResolveError("详情响应缺少 fund_code，无法查询分红公告")

    dividend = send_request("dividend", {"fund_code": fund_code})
    announcement = send_request(
        "announcement",
        {"fund_code": fund_code, "search_keyword": "", "ann_type": "", "recnum": 0, "reccnt": 20},
    )
    if raw:
        return with_disclaimer(
            {
                "query": {"product_id": resolved_product_id, "keyword": keyword, "fund_code": fund_code},
                "candidate": candidate,
                "dividend_raw": dividend,
                "announcement_raw": announcement,
            }
        )

    dividend_rsp = dividend.get("rsp", {}) if isinstance(dividend, dict) else {}
    announcement_rsp = announcement.get("rsp", {}) if isinstance(announcement, dict) else {}
    return with_disclaimer(
        {
            "query": {"product_id": resolved_product_id, "keyword": keyword, "fund_code": fund_code},
            "candidate": candidate,
            "fund": fund,
            "dividend": first_list(
                dividend_rsp.get("fund_divident_list"),
                dividend_rsp.get("dividends"),
                dividend_rsp.get("list"),
                dividend_rsp.get("records"),
            ),
            "announcement": first_list(
                announcement_rsp.get("fund_ann_list"),
                announcement_rsp.get("announcements"),
                announcement_rsp.get("list"),
                announcement_rsp.get("records"),
            ),
        }
    )


def compare_funds(
    items: Iterable[str],
    select_first: bool = False,
    include_fees: bool = False,
    include_performance: bool = False,
    raw: bool = False,
    strategy: str = "manual",
) -> Dict[str, Any]:
    """横向对比多只基金。"""
    item_list = list(items)
    effective_strategy = "first" if select_first else strategy
    results: List[Dict[str, Any]] = []
    for item in item_list:
        identifier = str(item).strip()
        if not identifier:
            continue
        use_product_id = identifier.isdigit() and len(identifier) > 6
        profile = fetch_profile(
            product_id=identifier if use_product_id else None,
            keyword=None if use_product_id else identifier,
            select_first=effective_strategy == "first",
            raw=raw,
        )
        if profile.get("status") == "multiple_candidates":
            results.append({"input": identifier, "status": "multiple_candidates", "candidates": profile.get("candidates", [])})
            continue

        item_result: Dict[str, Any] = {
            "input": identifier,
            "candidate": profile.get("candidate"),
            "profile": profile.get("profile") or profile.get("raw"),
        }
        product_id = get_path(profile, "query", "product_id")
        if include_fees and product_id:
            fees = fetch_fees(product_id=product_id, raw=raw)
            item_result["fees"] = fees.get("fees") or fees.get("raw")
        if include_performance and product_id:
            performance = fetch_performance(product_id=product_id, raw=raw)
            item_result["performance"] = {
                "phase_market": performance.get("phase_market"),
                "fixed_period_rate": performance.get("fixed_period_rate"),
                "duration_nav": performance.get("duration_nav"),
            }
        results.append(item_result)

    return with_disclaimer(
        {
            "query": {"items": item_list, "selection_strategy": effective_strategy},
            "selection_note": (
                "已按第一条搜索候选进行对比，适合自动化测试；对正式解读建议让用户确认具体基金。"
                if effective_strategy == "first"
                else "关键词命中多只基金时返回候选，不自动选择。"
            ),
            "funds": results,
        },
        history_note=include_performance,
    )


def positive_int(value: str) -> int:
    """argparse 正整数校验。"""
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("必须为正整数")
    return parsed


def add_common_resolve_args(parser: argparse.ArgumentParser) -> None:
    """为需要解析基金的子命令添加通用参数。"""
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--product_id", help="基金产品 ID，已知时可直接查询详情")
    group.add_argument("--keyword", help="基金名称、简称或代码关键词")
    parser.add_argument("--select-first", action="store_true", help="搜索命中多只基金时选择第一条候选")
    parser.add_argument("--raw", action="store_true", help="返回接口原始数据")


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="中金财富基金产品信息查询")
    subparsers = parser.add_subparsers(dest="command", required=True)

    search_parser = subparsers.add_parser("search", help="搜索公募基金候选")
    search_parser.add_argument("--keyword", required=True, help="基金名称、简称或代码关键词")
    search_parser.add_argument("--page", type=positive_int, default=1, help="页码，默认 1")
    search_parser.add_argument("--size", type=positive_int, default=10, help="每页数量，默认 10，最大 20")
    search_parser.add_argument("--raw", action="store_true", help="返回接口原始数据")

    profile_parser = subparsers.add_parser("profile", help="查询基金档案")
    add_common_resolve_args(profile_parser)

    fees_parser = subparsers.add_parser("fees", help="查询费率明细")
    add_common_resolve_args(fees_parser)

    holding_parser = subparsers.add_parser("holding", help="查询持仓概况")
    add_common_resolve_args(holding_parser)
    holding_parser.add_argument("--date", help="持仓报告期，例如 2025-12-31；不传则尝试使用详情报告期")

    performance_parser = subparsers.add_parser("performance", help="查询历史表现")
    add_common_resolve_args(performance_parser)
    performance_parser.add_argument("--include_fixed", action="store_true", help="同时查询固定周期收益率")
    performance_parser.add_argument("--include_nav", action="store_true", help="同时查询区间净值")

    events_parser = subparsers.add_parser("events", help="查询分红与公告")
    add_common_resolve_args(events_parser)

    compare_parser = subparsers.add_parser("compare", help="横向对比多只基金")
    compare_parser.add_argument("--items", nargs="+", required=True, help="基金关键词或 product_id 列表")
    compare_parser.add_argument("--select-first", action="store_true", help="搜索命中多只基金时选择第一条候选")
    compare_parser.add_argument(
        "--strategy",
        choices=["manual", "first"],
        default="manual",
        help="多候选选择策略，默认 manual 返回候选；first 选择第一条候选",
    )
    compare_parser.add_argument("--include_fees", action="store_true", help="对比时包含费率明细")
    compare_parser.add_argument("--include_performance", action="store_true", help="对比时包含历史表现摘要")
    compare_parser.add_argument("--raw", action="store_true", help="返回接口原始数据")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """命令行入口。"""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "search":
            result = search_funds(args.keyword, page=args.page, size=args.size, raw=args.raw)
        elif args.command == "profile":
            result = fetch_profile(args.product_id, args.keyword, args.select_first, args.raw)
        elif args.command == "fees":
            result = fetch_fees(args.product_id, args.keyword, args.select_first, args.raw)
        elif args.command == "holding":
            result = fetch_holding(args.product_id, args.keyword, args.select_first, args.date, args.raw)
        elif args.command == "performance":
            result = fetch_performance(
                args.product_id,
                args.keyword,
                args.select_first,
                args.include_fixed,
                args.include_nav,
                args.raw,
            )
        elif args.command == "events":
            result = fetch_events(args.product_id, args.keyword, args.select_first, args.raw)
        elif args.command == "compare":
            result = compare_funds(
                args.items,
                select_first=args.select_first,
                include_fees=args.include_fees,
                include_performance=args.include_performance,
                raw=args.raw,
                strategy=args.strategy,
            )
        else:
            parser.error(f"不支持的命令: {args.command}")
            return 2

        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        error_payload = with_disclaimer({"error": str(exc), "type": exc.__class__.__name__})
        print(json.dumps(error_payload, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
