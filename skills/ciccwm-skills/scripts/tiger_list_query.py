#!/usr/bin/env python3
"""
中金财富龙虎榜查询工具
基于龙虎榜接口查询总榜/机构榜/游资榜、活跃营业部、个股详情、营业部详情。
"""

import argparse
import hashlib
import json
import platform
import ssl
import sys
import threading
import time
import socket
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


XIAOYI_ENV_PATH = Path("/home/sandbox/.openclaw/.xiaoyienv")
LOGIN_TOKEN_KEY = "117860603_login_token"
API_URL = "https://skill.ciccwm.com/zzt/ext/fcgi/common.fcgi"
REPORT_URL = "https://webreport.ciccwm.com/zzt/fcgi/common.fcgi"
REQUEST_TIMEOUT = 20
REQUEST_VERSION = "20260624"
SKILL_NAME = "龙虎榜分析"
SKILL_UA_NAME = "ciccwm-tiger-list-analysis"
PLATFORM_NAME = "huawei"
REINSTALL_MESSAGE = (
    "未获取到有效的 117860603_login_token 或鉴权已失效。"
    "请刷新 117860603_login_token，或调用 huawei_id_tool 工具获取新凭证。"
)

CMD_STOCK_INFO = "SkillEQuoteLhbStockInfo"
CMD_YYB_INFO = "SkillEQuoteLhbYybInfo"
CMD_STOCK_DETAIL = "SkillEQuoteLhbStockDetail"
CMD_YYB_DETAIL = "SkillEQuoteLhbYybDetail"

LIST_TYPE_MAP = {
    "overall": "overall_list",
    "jgqc": "jgqc_list",
    "yzby": "yzby_list",
}


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


def _send_payload(api_key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json",
        "Cookie": "apiKey=" + api_key,
        "version": REQUEST_VERSION,
    }

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


def send_request(cmdname: str, param: Dict[str, Any]) -> Dict[str, Any]:
    """发送请求并返回接口原始 JSON。"""
    api_key = load_api_key()
    report_user_action(api_key, cmdname)

    candidates = [cmdname]
    if not cmdname.startswith("Skill"):
        candidates.append("Skill" + cmdname)

    last_response: Dict[str, Any] = {}
    last_error: Optional[Exception] = None

    for candidate_cmd in candidates:
        payload = {"cmdname": candidate_cmd, "param": param}
        try:
            response = _send_payload(api_key, payload)
            if response.get("ret") == 0:
                return response
            last_response = response
        except Exception as exc:
            if isinstance(exc, CICCWMCredentialError):
                raise
            last_error = exc

    if last_response:
        return last_response
    if last_error:
        return {"status": "error", "message": f"请求失败: {last_error}"}
    return {"status": "error", "message": "请求失败: 未获取到有效响应"}


def normalize_date(req_date: Optional[str]) -> Optional[str]:
    """将日期校验为 yyyy-MM-dd；为空时不传该字段。"""
    if not req_date:
        return None

    try:
        datetime.strptime(req_date, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("日期格式错误，应为 yyyy-MM-dd") from exc
    return req_date


def parse_response_data(response: Dict[str, Any]) -> Any:
    """解析 common.fcgi 包装层，提取实际数据。"""
    if response.get("status") == "error":
        raise ValueError(response.get("message") or "接口调用失败")

    if response.get("ret") not in (None, 0):
        raise ValueError(response.get("msg") or "接口返回 ret 非 0")

    if "rsp" not in response:
        return response

    rsp = response.get("rsp")
    if not isinstance(rsp, dict):
        return rsp

    if rsp.get("ret_code") not in (None, 0):
        raise ValueError(rsp.get("ret_msg") or "接口返回 ret_code 非 0")

    rsp_json = rsp.get("rsp_json")
    if isinstance(rsp_json, str):
        try:
            return json.loads(rsp_json)
        except json.JSONDecodeError:
            return rsp_json

    # 龙虎榜数据嵌套在 charts_info 里，需拆出来
    charts_info = rsp.get("charts_info")
    if charts_info is not None:
        return charts_info

    return rsp


def query_stock_list(
    req_date: Optional[str] = None,
    req_type: str = "1",
    list_type: str = "all",
    raw: bool = False,
) -> Dict[str, Any]:
    """查询龙虎榜总榜、机构榜、游资榜。"""
    normalized_date = normalize_date(req_date)
    param: Dict[str, Any] = {"req_type": str(req_type)}
    if normalized_date:
        param["req_date"] = normalized_date

    response = send_request(CMD_STOCK_INFO, param)
    if raw:
        return response

    data = parse_response_data(response)
    if not isinstance(data, dict):
        return {
            "query": "stock_list",
            "cmdname": CMD_STOCK_INFO,
            "req_type": str(req_type),
            "req_date": normalized_date,
            "list_type": list_type,
            "data": data,
        }

    result = {
        "query": "stock_list",
        "cmdname": CMD_STOCK_INFO,
        "req_type": str(req_type),
        "req_date": normalized_date,
        "list_type": list_type,
        "v_day": data.get("v_day") or data.get("vDay") or [],
        "sh_num": data.get("sh_num"),
        "sz_num": data.get("sz_num"),
    }

    if list_type == "all":
        result["overall_list"] = data.get("overall_list") or data.get("vSecList") or []
        result["jgqc_list"] = data.get("jgqc_list") or data.get("vJgqcList") or []
        result["yzby_list"] = data.get("yzby_list") or data.get("vYzbyList") or []
    else:
        key = LIST_TYPE_MAP[list_type]
        fallback_map = {
            "overall": "vSecList",
            "jgqc": "vJgqcList",
            "yzby": "vYzbyList",
        }
        result[key] = data.get(key) or data.get(fallback_map[list_type]) or []

    return result


def query_active_orgs(
    req_date: Optional[str] = None,
    req_type: str = "1",
    raw: bool = False,
) -> Dict[str, Any]:
    """查询活跃营业部列表。"""
    normalized_date = normalize_date(req_date)
    param: Dict[str, Any] = {"req_type": str(req_type)}
    if normalized_date:
        param["req_date"] = normalized_date

    response = send_request(CMD_YYB_INFO, param)
    if raw:
        return response

    data = parse_response_data(response)
    if not isinstance(data, dict):
        return {
            "query": "active_orgs",
            "cmdname": CMD_YYB_INFO,
            "req_type": str(req_type),
            "req_date": normalized_date,
            "data": data,
        }

    return {
        "query": "active_orgs",
        "cmdname": CMD_YYB_INFO,
        "req_type": str(req_type),
        "req_date": normalized_date,
        "v_day": data.get("v_day") or data.get("vDay") or [],
        "sale_org_num": data.get("sale_org_num"),
        "sale_org_list": data.get("sale_org_list") or data.get("vSaleOrgList") or [],
    }


def query_stock_detail(
    stock_code: str,
    req_date: Optional[str] = None,
    raw: bool = False,
) -> Dict[str, Any]:
    """查询龙虎榜个股详情。"""
    normalized_date = normalize_date(req_date)
    param: Dict[str, Any] = {"stock_code": stock_code}
    if normalized_date:
        param["req_date"] = normalized_date

    response = send_request(CMD_STOCK_DETAIL, param)
    if raw:
        return response

    data = parse_response_data(response)
    if not isinstance(data, dict):
        return {
            "query": "stock_detail",
            "cmdname": CMD_STOCK_DETAIL,
            "req_date": normalized_date,
            "stock_code": stock_code,
            "data": data,
        }

    return {
        "query": "stock_detail",
        "cmdname": CMD_STOCK_DETAIL,
        "req_date": normalized_date,
        "stock_code": stock_code,
        "secu_code": data.get("secu_code"),
        "secu_name": data.get("secu_name"),
        "market_label": data.get("market_label"),
        "f_close_price": data.get("f_close_price"),
        "f_change_pct": data.get("f_change_pct"),
        "f_chand_pct": data.get("f_chand_pct"),
        "f_deal_sum": data.get("f_deal_sum"),
        "f_deal_amount": data.get("f_deal_amount"),
        "sale_secu_detail_list": data.get("sale_secu_detail_list") or [],
    }


def query_org_detail(
    yyb: str,
    req_date: Optional[str] = None,
    raw: bool = False,
) -> Dict[str, Any]:
    """查询活跃营业部详情与风格画像。"""
    normalized_date = normalize_date(req_date)
    param: Dict[str, Any] = {"yyb": yyb}
    if normalized_date:
        param["req_date"] = normalized_date

    response = send_request(CMD_YYB_DETAIL, param)
    if raw:
        return response

    data = parse_response_data(response)
    if not isinstance(data, dict):
        return {
            "query": "org_detail",
            "cmdname": CMD_YYB_DETAIL,
            "req_date": normalized_date,
            "yyb": yyb,
            "data": data,
        }

    return {
        "query": "org_detail",
        "cmdname": CMD_YYB_DETAIL,
        "req_date": normalized_date,
        "yyb": yyb,
        "s_org_class": data.get("s_org_class"),
        "s_org_fac": data.get("s_org_fac"),
        "s_manipulat": data.get("s_manipulat"),
        "plant": data.get("plant"),
        "f_three_day_success": data.get("f_three_day_success"),
        "org_secu_list": data.get("org_secu_list") or [],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="中金财富龙虎榜查询工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="查询类型")

    p_stock_list = subparsers.add_parser("stock_list", help="查询龙虎榜总榜/机构榜/游资榜")
    p_stock_list.add_argument("--req_date", help="查询日期，格式 yyyy-MM-dd；不传默认最新")
    p_stock_list.add_argument("--req_type", default="1", choices=["1", "2"], help="1-首页，2-列表页")
    p_stock_list.add_argument(
        "--list_type",
        default="all",
        choices=["all", "overall", "jgqc", "yzby"],
        help="all-全部榜单，overall-总榜，jgqc-机构榜，yzby-游资榜",
    )
    p_stock_list.add_argument("--raw", action="store_true", help="返回接口原始结构")

    p_orgs = subparsers.add_parser("active_orgs", help="查询活跃营业部列表")
    p_orgs.add_argument("--req_date", help="查询日期，格式 yyyy-MM-dd")
    p_orgs.add_argument("--req_type", default="1", choices=["1", "2"], help="1-首页，2-列表页")
    p_orgs.add_argument("--raw", action="store_true", help="返回接口原始结构")

    p_stock_detail = subparsers.add_parser("stock_detail", help="查询龙虎榜个股详情")
    p_stock_detail.add_argument("--stock_code", required=True, help="龙虎榜侧股票代码，如 0001301007")
    p_stock_detail.add_argument("--req_date", help="查询日期，格式 yyyy-MM-dd")
    p_stock_detail.add_argument("--raw", action="store_true", help="返回接口原始结构")

    p_org_detail = subparsers.add_parser("org_detail", help="查询活跃营业部详情")
    p_org_detail.add_argument("--yyb", required=True, help="营业部名称")
    p_org_detail.add_argument("--req_date", help="查询日期，格式 yyyy-MM-dd")
    p_org_detail.add_argument("--raw", action="store_true", help="返回接口原始结构")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "stock_list":
            result = query_stock_list(
                req_date=args.req_date,
                req_type=args.req_type,
                list_type=args.list_type,
                raw=args.raw,
            )
        elif args.command == "active_orgs":
            result = query_active_orgs(
                req_date=args.req_date,
                req_type=args.req_type,
                raw=args.raw,
            )
        elif args.command == "stock_detail":
            result = query_stock_detail(
                stock_code=args.stock_code,
                req_date=args.req_date,
                raw=args.raw,
            )
        elif args.command == "org_detail":
            result = query_org_detail(
                yyb=args.yyb,
                req_date=args.req_date,
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
