"""Self-contained Streamable HTTP MCP client copied into a Huawei Skill."""

from __future__ import annotations

import argparse
import json
import re
import ssl
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import (
    HTTPRedirectHandler,
    HTTPSHandler,
    ProxyHandler,
    Request,
    build_opener,
)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class AuthRequired(ValueError):
    """Safe reason codes only; never include credential contents."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__("Authorization required")


def read_credentials(path: Path, client_id: str) -> str:
    raw = path.read_text(encoding="utf-8-sig")
    if raw.lstrip().startswith("{"):
        values = json.loads(raw)
    else:
        values = {}
        expected = {client_id + "_login_token", client_id + "_login_token_expire_time"}
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("export "):
                line = line[7:]
            key, sep, value = line.partition("=")
            if sep and key.strip() in expected:
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                    value = value[1:-1]
                values[key.strip()] = value
    if not isinstance(values, dict):
        raise AuthRequired("credential_format_invalid")
    login_credential = values.get(client_id + "_login_token", "")
    expiry = values.get(client_id + "_login_token_expire_time", "")
    if not login_credential:
        raise AuthRequired("credential_missing")
    if not isinstance(login_credential, str) or not re.fullmatch(r"hw_at_[A-Za-z0-9_-]{64}", login_credential):
        raise AuthRequired("credential_format_invalid")
    if not expiry:
        raise AuthRequired("expiry_missing")
    try:
        expiration = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
    except (ValueError, AttributeError, TypeError) as exc:
        raise AuthRequired("expiry_invalid") from exc
    if expiration.tzinfo is None:
        raise AuthRequired("expiry_invalid")
    if expiration <= datetime.now(UTC):
        raise AuthRequired("credential_expired")
    return login_credential


def rpc(
    opener,
    url: str,
    login_credential: str,
    method: str,
    params: dict,
    request_id: int,
    idempotency_key: str = "",
) -> dict:
    body = json.dumps(
        {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params},
        ensure_ascii=False,
    ).encode()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "login-token": login_credential,
    }
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    request = Request(  # noqa: S310 -- fixed validated HTTPS endpoint
        url,
        data=body,
        headers=headers,
        method="POST",
    )
    with opener.open(request, timeout=300) as response:
        raw = response.read(8 * 1024 * 1024 + 1)
        if len(raw) > 8 * 1024 * 1024:
            raise ValueError("Response too large")
        result = json.loads(raw)
    if not isinstance(result, dict) or result.get("jsonrpc") != "2.0":
        raise ValueError("Invalid MCP response")
    return result


def notify_initialized(opener, url: str, login_credential: str) -> None:
    """Complete the MCP handshake before invoking any tool."""
    request = Request(  # noqa: S310 -- fixed validated HTTPS endpoint
        url,
        data=b'{"jsonrpc":"2.0","method":"notifications/initialized"}',
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "login-token": login_credential,
        },
        method="POST",
    )
    with opener.open(request, timeout=15) as response:
        if response.status != 202 or response.read(1):
            raise ValueError("MCP initialized notification failed")


def execute(
    config: dict,
    login_credential: str,
    tool: str,
    question: str,
    idempotency_key: str,
) -> dict:
    base = config["base_url"].rstrip("/")
    parsed = urlsplit(base)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("HTTPS endpoint required")
    if tool not in config["tools"] or not re.fullmatch(
        r"[A-Za-z0-9_-]{1,128}", idempotency_key
    ):
        raise ValueError("Unknown tool")
    url = base + "/huawei/mcp"
    opener = build_opener(
        ProxyHandler({}),
        NoRedirect(),
        HTTPSHandler(context=ssl.create_default_context()),
    )
    initialized = rpc(
        opener,
        url,
        login_credential,
        "initialize",
        {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": config["skill_name"], "version": "1.0.0"},
        },
        1,
    )
    result = initialized.get("result")
    if (
        not isinstance(result, dict)
        or result.get("protocolVersion") != "2025-03-26"
    ):
        raise ValueError("MCP initialize failed")
    notify_initialized(opener, url, login_credential)
    called = rpc(
        opener,
        url,
        login_credential,
        "tools/call",
        {"name": tool, "arguments": {"question": question}},
        2,
        idempotency_key,
    )
    result = called.get("result")
    if not isinstance(result, dict) or result.get("isError") is True:
        raise ValueError("MCP tool failed")
    content = result.get("content")
    if not isinstance(content, list) or len(content) != 1:
        raise ValueError("Invalid MCP result")
    payload = json.loads(content[0].get("text", ""))
    if (
        not isinstance(payload, dict)
        or payload.get("status") != "completed"
        or not isinstance(payload.get("answer_markdown"), str)
    ):
        raise ValueError("Invalid research result")
    return payload


def package_info(config: dict) -> dict:
    """Public package metadata only; never access credentials or the network."""
    root = Path(__file__).resolve().parent.parent
    source = (root / "SKILL.md").read_text(encoding="utf-8-sig")
    sections = source.split("---", 2)
    front = sections[1] if len(sections) == 3 and not sections[0].strip() else ""
    declared = re.search(r"(?m)^name:\s*([a-z0-9-]+)\s*$", front)
    name = declared.group(1) if declared else ""
    referenced = set(re.findall(r"skillName\s*[=:]\s*[\"']?([a-z0-9-]+)", source))
    consistent = bool(name and name == root.name == config.get("skill_name") and referenced == {name})
    return {
        "status": "package_ready" if consistent else "configuration_error",
        "reason": None if consistent else "package_name_mismatch",
        "package_version": config.get("package_version", "legacy"),
        "skill_name": config.get("skill_name"),
        "declared_skill_name": name,
        "directory_name": root.name,
        "client_id": config.get("client_id"),
        "name_consistent": consistent,
        "check_scope": "package_metadata_only",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["info", "check-auth", "analyze"])
    parser.add_argument("--tool")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--request-id", default="")
    args = parser.parse_args(argv)
    config = json.loads(
        (Path(__file__).resolve().parent / "client-config.json").read_text(
            encoding="utf-8"
        )
    )
    try:
        info = package_info(config)
    except (OSError, ValueError):
        print('{"status":"configuration_error","reason":"package_metadata_unavailable"}')
        return 2
    if args.command == "info" or not info["name_consistent"]:
        print(json.dumps(info))
        return 0 if info["name_consistent"] else 2
    try:
        login_credential = read_credentials(
            Path("/home/sandbox/.openclaw/.xiaoyienv"), config["client_id"]
        )
    except (OSError, ValueError, TypeError, AttributeError, json.JSONDecodeError) as exc:
        print(
            json.dumps(
                {
                    "status": "auth_required",
                    "reason": getattr(exc, "reason", "credential_file_unavailable" if isinstance(exc, OSError) else "credential_format_invalid"),
                    "check_scope": "local_credentials_only",
                    "client_id": config["client_id"],
                    "skill_name": config["skill_name"],
                }
            )
        )
        return 2
    if args.command == "check-auth":
        print('{"status":"authorized","check_scope":"local_credentials_only"}')
        return 0
    try:
        if args.input is None or not args.tool:
            raise ValueError("Tool and input are required")
        payload = json.loads(args.input.read_text(encoding="utf-8-sig"))
        if (
            not isinstance(payload, dict)
            or set(payload) != {"question"}
            or not isinstance(payload["question"], str)
            or not payload["question"].strip()
        ):
            raise ValueError("Input must contain one question")
        result = execute(
            config,
            login_credential,
            args.tool,
            payload["question"],
            args.request_id,
        )
    except HTTPError as exc:
        result = {
            "status": "failed",
            "http_status": exc.code,
            "error": {
                "code": "AUTH_REQUIRED" if exc.code == 401 else "MCP_CALL_FAILED"
            },
            "automatic_retry": False,
        }
    except (OSError, ValueError, TypeError, URLError, json.JSONDecodeError):
        result = {
            "status": "failed",
            "error": {"code": "MCP_CLIENT_OR_NETWORK_ERROR"},
            "automatic_retry": False,
            "message": "调用状态未确认，不要自动重新提交研究。",
        }
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("status") == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())
