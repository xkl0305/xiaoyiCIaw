#!/usr/bin/env python3
import os
import sys
import json
import argparse
from pathlib import Path
from typing import Optional

import requests


# --- 配置 ---

XIAOYI_ENV_PATH = Path("/home/sandbox/.openclaw/.xiaoyienv")
LOGIN_TOKEN_KEY = "117860613_login_token"


class CredentialError(RuntimeError):
    """缺少有效的华为账号登录凭证。"""


def _load_xiaoyi_token() -> str:
    """从 .xiaoyienv 读取华为账号登录凭证；缺失/为空则抛出 CredentialError。"""
    if not XIAOYI_ENV_PATH.exists():
        raise CredentialError(
            "未获取到有效的 117860613_login_token 或鉴权已失效。"
            "请刷新 117860613_login_token，或调用 huawei_id_tool 工具获取新凭证。"
        )
    token = ""
    with open(XIAOYI_ENV_PATH, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key.startswith("export "):
                key = key[len("export "):].strip()
            if key == LOGIN_TOKEN_KEY:
                token = value.strip().strip("\"'")
                break
    if not token:
        raise CredentialError(
            "未获取到有效的 117860613_login_token 或鉴权已失效。"
            "请刷新 117860613_login_token，或调用 huawei_id_tool 工具获取新凭证。"
        )
    return token


class Config:
    def __init__(self) -> None:
        self.service_url = os.environ.get("AGENTOS_GATEWAY", "https://ai.zhangle.com")
        self.api_key = _load_xiaoyi_token()
        self.base_url = os.environ.get("QUERY_INDICATOR_BASE_URL", "/edge/entry/gate")
        self.timeout = float(os.environ.get("QUERY_INDICATOR_TIMEOUT", "60"))


_config: Optional[Config] = None


def _get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
    return _config


# --- HTTP 客户端 ---

def _error(code: int, message: str, category: str, retriable: bool = False, hint: str = "") -> dict:
    return {
        "ok": False,
        "data": None,
        "error": {
            "code": code,
            "message": message,
            "category": category,
            "retriable": retriable,
            "hint": hint,
        },
    }


def _category_from_code(code: int) -> str:
    if code == -3:
        return "network"
    if code in (-2, -5):
        return "business"
    return "validation"


def _post(path: str, body: Optional[dict] = None, timeout: Optional[float] = None) -> dict:
    cfg = _get_config()
    url = cfg.service_url.rstrip("/") + cfg.base_url + path
    timeout_s = timeout if timeout is not None else cfg.timeout
    headers = {
        "apiKey": cfg.api_key,
        "skillCode": "zhangle-query-indicator",
        "Content-Type": "application/json",
        "channel": "huawei-xiaoyi",
    }
    try:
        resp = requests.post(url, json=body or {}, headers=headers, timeout=timeout_s)
        resp.raise_for_status()
        result = resp.json()
    except requests.exceptions.Timeout:
        return _error(-3, "接口调用超时", "network", retriable=True, hint="后端响应较慢，请稍后再试。")
    except requests.exceptions.ConnectionError:
        return _error(
            -3, "无法连接到后端服务", "network", retriable=True,
            hint=f"请检查 AGENTOS_GATEWAY（当前 {cfg.service_url}）是否正确，以及后端服务是否启动。",
        )
    except requests.exceptions.HTTPError as e:
        return _error(-2, f"后端返回异常状态码 {e.response.status_code}", "network", retriable=True)
    except json.JSONDecodeError:
        return _error(-2, "后端返回内容无法解析", "business", hint="请检查后端版本是否匹配。")
    except Exception as e:
        return _error(-3, f"未知网络错误：{e}", "network", retriable=True)

    if result.get("code") != 0:
        code = result.get("code", -2)
        msg = result.get("message", "未知错误")
        detail = result.get("detail", "")
        category = _category_from_code(code)
        return _error(code, msg, category, hint=detail)

    answer = result.get("data", {}).get("answer", "")
    return {"ok": True, "data": {"answer": answer}, "error": None}


# --- 工具函数 ---

def queryIndicator(query: str) -> dict:
    """查询金融指标、行情数据或财务估值。

    不要拆分多次调用，不要替换参数（如将"昨天"改为具体日期），
    不要补充解释，query 仅包含用户原话。

    Args:
        query: 用户问题，保留原始表述
    """
    return _post("/api/finAnalysis/queryIndicator", {"query": query}, timeout=60)


# --- CLI ---

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="query_indicator", description="金融指标与行情综合检索工具调度入口")
    sub = p.add_subparsers(dest="tool", required=True, metavar="<tool>")

    s = sub.add_parser("queryIndicator", help="查询金融指标、行情数据或财务估值")
    s.add_argument("--query", required=True, help="用户问题，保留原始表述")

    return p


def main() -> None:
    args = _build_parser().parse_args()

    if args.tool == "queryIndicator":
        result = queryIndicator(query=args.query)
    else:
        raise SystemExit(f"unknown tool: {args.tool}")

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
