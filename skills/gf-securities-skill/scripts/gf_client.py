#!/usr/bin/env python3
"""广发证券 GF Skills API 通用客户端核心。

所有 gf-* skill 的 CLI 都复用这个模块：负责解析 API Key、POST 调用统一入口
`https://mcp-api.gf.com.cn/gf-skills/skills/mcp/call`、按顶层 retcode 判断成败、
自动重试瞬断，并把业务数据（data.data）原样打印成 JSON。

LLM 不要手写 curl，调用各 skill 的 cli.py 即可，本模块由 cli.py import。

API Key 解析优先级：
    1. 环境变量 GF_SKILLS_APIKEY
    2. 文件 ~/.gf-skills/apikey（纯 key 一行）
    缺失时 → 打印引导文案并退出（提示去 https://hd.gf.com.cn/skills-market?channel=hwxyskills 获取）。

渠道（channel）解析优先级（用于请求头 x-gf-channel，标识 skill 发布渠道）：
    1. 环境变量 GF_SKILLS_CHANNEL
    2. 文件 ~/.gf-skills/channel（纯 channel 值一行）
    都读不到 → 不发送 x-gf-channel 头（可选，不影响调用）。
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# 接口 host：__GF_HOST__ 为发布占位符，发布页按所选环境（外网/内网/测试）整串替换。
# 默认外网；未经发布替换时直接用此默认值即可正常调用。
GF_HOST = "https://mcp-api.gf.com.cn"  # __GF_HOST__
ENDPOINT = GF_HOST + "/gf-skills/skills/mcp/call"
APIKEY_FILE = Path.home() / ".gf-skills" / "apikey"
CHANNEL_FILE = Path.home() / ".gf-skills" / "channel"
# 注册地址；hwxyskills 为发布占位符，发布打包时按渠道整串替换。
REGISTER_URL = "https://hd.gf.com.cn/skills-market?channel=hwxyskills"


def resolve_apikey() -> str:
    """env 优先，其次 ~/.gf-skills/apikey；都没有则报错退出。"""
    key = os.environ.get("GF_SKILLS_APIKEY", "").strip()
    if key:
        return key
    try:
        key = APIKEY_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        key = ""
    if key:
        return key
    sys.stderr.write(
        "ERROR: 未找到 GF Skills API Key。\n"
        f"  1. 去 {REGISTER_URL} 注册获取 API Key；\n"
        "  2. 持久化（本机所有 gf-* skill 复用，只需一次）：\n"
        f"     mkdir -p ~/.gf-skills && printf '%s' '<your_apikey>' > {APIKEY_FILE} && chmod 600 {APIKEY_FILE}\n"
        "  或临时设置环境变量：export GF_SKILLS_APIKEY=<your_apikey>\n"
    )
    raise SystemExit(2)


def resolve_channel() -> str:
    """解析发布渠道：env GF_SKILLS_CHANNEL 优先，其次 ~/.gf-skills/channel。

    读不到返回空字符串（调用方据此决定是否发送 x-gf-channel 头）。channel 为可选项，
    缺失不影响调用。
    """
    chan = os.environ.get("GF_SKILLS_CHANNEL", "").strip()
    if chan:
        return chan
    try:
        chan = CHANNEL_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        chan = ""
    return chan


def call(service_name: str, tool_name: str, args: dict, *, timeout: int = 40, retries: int = 2) -> dict:
    """调用 GF Skills 统一入口，返回解析后的 JSON dict。

    瞬断 / 5xx 自动重试 retries 次（该域名偶发 SSL 抖动）。
    """
    apikey = resolve_apikey()
    payload = json.dumps(
        {"service_name": service_name, "tool_name": tool_name, "args": args},
        ensure_ascii=False,
    ).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {apikey}",
        "User-Agent": "gf-skills-cli/1.0",
    }
    # 发布渠道标识：读到才发送，无则不传（可选头）。
    channel = resolve_channel()
    if channel:
        headers["x-gf-channel"] = channel

    last_err = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(ENDPOINT, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8")
            except Exception:
                pass
            # 4xx 不重试（鉴权 / 参数问题，重试无意义）
            if e.code < 500:
                return {
                    "retcode": -1,
                    "msg": f"HTTP {e.code}",
                    "error": _safe_error(body) or str(e),
                    "http_status": e.code,
                }
            last_err = f"HTTP {e.code}: {_safe_error(body) or str(e)}"
        except (urllib.error.URLError, TimeoutError) as e:
            last_err = str(getattr(e, "reason", e))
        if attempt < retries:
            time.sleep(1.0 + attempt)
    return {"retcode": -1, "msg": "request_failed", "error": last_err}


def _safe_error(body: str) -> str:
    try:
        parsed = json.loads(body)
        return parsed.get("error") or parsed.get("msg") or body[:500]
    except Exception:
        return body[:500]


def emit(resp: dict, *, raw: bool = False) -> None:
    """把响应打印成 JSON 到 stdout，并按顶层 retcode 设置退出码。

    raw=True 打印整个网关包裹；默认提取业务数据 data.data（取数固定走这里），
    顶层 retcode != 0 时打印完整响应并以非 0 退出，方便 LLM 看到错误。
    """
    retcode = resp.get("retcode")
    if retcode != 0:
        json.dump(resp, sys.stdout, ensure_ascii=False, indent=2)
        print()
        raise SystemExit(1)
    out = resp if raw else resp.get("data", {}).get("data", resp.get("data"))
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
    print()


def run(service_name: str, tool_name: str, args: dict, *, raw: bool = False) -> None:
    """call + emit 的便捷封装，cli.py 的子命令直接调它。"""
    emit(call(service_name, tool_name, args), raw=raw)


def parse_json_arg(text):
    """解析 --json 传入的 args JSON 字符串，返回 dict（None / 空 → {}）。

    便于参数特别多 / 含嵌套结构（如 strategyList）的接口整段传 args，
    不必逐个枚举命名参数。非法 JSON 或非对象时报错退出。
    """
    if not text:
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise SystemExit(f"ERROR: --json 不是合法 JSON：{e}")
    if not isinstance(data, dict):
        raise SystemExit(f"ERROR: --json 必须是 JSON 对象 {{...}}，收到：{type(data).__name__}")
    return data


def merge_args(base: dict, override: dict) -> dict:
    """合并两个 args dict，override 中非 None 的值覆盖 base。

    用法：base=--json 解析结果，override=显式命名参数 → 命名参数优先。
    """
    out = dict(base or {})
    for k, v in (override or {}).items():
        if v is not None:
            out[k] = v
    return out
