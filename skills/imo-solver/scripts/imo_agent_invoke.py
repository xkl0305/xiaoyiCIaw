"""
imo_agent_invoke.py - 通过 OSMS SSE 接口调用 IMOAgent

用法：
  python imo_agent_invoke.py "<数学问题描述>"

脚本前台同步执行，循环读取 SSE 流直到收到 final 结果，
最终将完整结果以 JSON 格式输出到 stdout。
"""

import json
import logging
import os
import sys
import uuid
from pathlib import Path

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SKILL_EXECUTE_PATH = "/celia-claw/v1/sse-api/skill/execute"
SKILL_ID = "xiaoyi_imo_solver"

LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("imo_agent_invoke")
logger.setLevel(logging.DEBUG)
_file_handler = logging.FileHandler(
    LOG_DIR / "imo_agent_invoke.log", mode="w", encoding="utf-8"
)
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
)
logger.addHandler(_file_handler)


# ============================================================
# Config: 从 .xiaoyienv + 环境变量加载
# ============================================================

def _parse_bool(value: str) -> bool:
    return value.lower() in ("true", "1", "yes")


def _parse_double_quoted(raw: str) -> str:
    raw = raw[1:]
    result = []
    escaped = False
    for ch in raw:
        if escaped:
            if ch == "n":
                result.append("\n")
            elif ch == "t":
                result.append("\t")
            elif ch == "\\":
                result.append("\\")
            elif ch == '"':
                result.append('"')
            else:
                result.append("\\")
                result.append(ch)
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == '"':
            break
        result.append(ch)
    return "".join(result)


def _parse_single_quoted(raw: str) -> str:
    raw = raw[1:]
    idx = raw.find("'")
    return raw[:idx] if idx >= 0 else raw


def _parse_value(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return ""
    if raw[0] == '"':
        return _parse_double_quoted(raw)
    if raw[0] == "'":
        return _parse_single_quoted(raw)
    for sep in (" #", "\t#"):
        idx = raw.find(sep)
        if idx >= 0:
            raw = raw[:idx]
    return raw.strip()


def _parse_dotenv_line(line: str):
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if line.startswith("export ") or line.startswith("export\t"):
        line = line[7:].strip()
    eq_idx = line.find("=")
    if eq_idx < 1:
        return None
    key = line[:eq_idx].strip()
    value = _parse_value(line[eq_idx + 1:])
    return key, value


def load_dotenv():
    path = os.getenv("ACP2SERVICE_ENV", "")
    if not path or path.startswith("~"):
        path = str(Path.home() / ".openclaw" / ".xiaoyienv")
    if not Path(path).is_file():
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            result = _parse_dotenv_line(line)
            if result is None:
                continue
            key, value = result
            env_key = key.replace("-", "_")
            if not os.getenv(env_key):
                os.environ[env_key] = value


class Config:
    def __init__(self):
        self.service_url = os.getenv("SERVICE_URL", "")
        self.request_from = os.getenv("REQUEST_FROM", "openclaw")
        self.personal_uid = os.getenv("PERSONAL_UID", "")
        self.personal_api_key = os.getenv("PERSONAL_API_KEY", "")
        self.tls_skip_verify = _parse_bool(os.getenv("TLS_SKIP_VERIFY", ""))
        self.request_timeout = int(os.getenv("REQUEST_TIMEOUT", "3600"))

    def auth_headers(self) -> dict[str, str]:
        headers = {}
        if self.request_from:
            headers["x-request-from"] = self.request_from
        if self.personal_uid:
            headers["x-uid"] = self.personal_uid
        if self.personal_api_key:
            headers["x-api-key"] = self.personal_api_key
        return headers

    @staticmethod
    def load() -> "Config":
        load_dotenv()
        cfg = Config()
        if not cfg.service_url:
            raise ValueError("SERVICE_URL 环境变量未设置")
        return cfg


def _print_progress(msg: str):
    """将进度信息输出到 stdout，带前缀标记，与最终 JSON 区分。"""
    print(f"=== PROGRESS === {msg}", flush=True)


# ============================================================
# Event Handlers
# ============================================================

def handle_step_info(data: dict):
    content = data.get("content", "").rstrip("\n")
    if content:
        logger.info("[进度] %s", content)
        _print_progress(content)


def handle_data(data: dict) -> str:
    reasoning = data.get("reasoning_content", "")
    if reasoning:
        logger.debug("[思考] %s", reasoning)
    content = data.get("content", "")
    if content:
        logger.debug("[data] %s", content)
    return content


def handle_tool(data: dict):
    tool_name = data.get("tool_name", "")
    if tool_name:
        logger.info("[调用工具] %s", tool_name)
        _print_progress(f"调用工具: {tool_name}")


def handle_tool_result(data: dict):
    tool_name = data.get("tool_name", "")
    result = str(data.get("tool_result", ""))
    if len(result) > 200:
        result = result[:200] + "..."
    if tool_name:
        logger.info("[%s 结果] %s", tool_name, result)


def handle_finish(data: dict):
    finish_type = data.get("type", "normal")
    logger.info("[完成] type=%s", finish_type)


# ============================================================
# SSE parsing
# ============================================================

def process_event(event_data: str, response_text: list[str]) -> bool:
    try:
        data = json.loads(event_data)
    except json.JSONDecodeError:
        logger.warning("无法解析: %s", event_data[:200])
        return False

    event_type = data.get("event", "")

    if event_type == "stepInfo":
        handle_step_info(data)
    elif event_type == "data":
        text = handle_data(data)
        if text:
            response_text.append(text)
    elif event_type == "tool":
        handle_tool(data)
    elif event_type == "tool_result":
        handle_tool_result(data)
    elif event_type == "heartbeat":
        pass
    elif event_type == "finish":
        handle_finish(data)
        return True

    if data.get("code") and data.get("abilityInfos"):
        for ability in data.get("abilityInfos", []):
            reply = ability.get("actionExecutorResult", {}).get("reply", {})
            stream_info = reply.get("streamInfo", {})
            stream_type = stream_info.get("streamType", "")
            content = stream_info.get("streamContent", "")
            reasoning = stream_info.get("reasoningText", "")

            if stream_type == "partial":
                if reasoning:
                    logger.info("[进度] %s", reasoning[:500])
                    _print_progress(reasoning[:500])
                return False

            if stream_type == "final":
                if content:
                    display_content = content.split("[VERDICT]")[0].rstrip()
                    response_text.append(content)
                    logger.info("✅ 解题完成")
                    logger.info("完整解题结果：\n%s", display_content)
                else:
                    logger.error("收到 final 帧但 streamContent 为空")
                return True

        error_code = data.get("code", "")
        if error_code != "200":
            logger.error("服务端错误 code=%s desc=%s", error_code, data.get("desc", ""))
            return True

    return False


# ============================================================
# Core
# ============================================================

def get_session_info(file_path: str = None) -> tuple[str, str]:
    session_id = ""
    interaction_id = ""

    if file_path is None:
        file_path = os.path.expanduser("~/.openclaw/.xiaoyiruntime")

    if os.path.exists(file_path):
        try:
            with open(file_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("TASK_ID="):
                        raw_task_id = line.split("=", 1)[1]
                        parts = raw_task_id.split("&")
                        if len(parts) > 0:
                            session_id = parts[0]
                        if len(parts) > 1:
                            interaction_id = parts[1]
                        break
        except Exception:
            pass

    if not session_id:
        session_id = str(uuid.uuid4())
    if not interaction_id:
        interaction_id = "1"

    return session_id, interaction_id


def build_request(cfg: Config, query: str, session_id: str, interaction_id: str) -> dict:
    action_sn = str(uuid.uuid4()).replace("-", "")
    req = {
        "actions": [
            {
                "actionExecutorTask": {
                    "actionName": "IMOAgent",
                    "content": {
                        "query": query,
                        "requestId": f"{session_id}_{interaction_id}",
                        "sessionId": session_id,
                        "uid": cfg.personal_uid,
                        "interactionId": interaction_id
                    },
                    "replyCard": False,
                },
                "actionSn": action_sn,
            }
        ],
        "endpoint": {
            "countryCode": "",
            "device": {
                "deviceId": str(uuid.uuid4()).replace("-", ""),
                "phoneType": "2in1",
                "pxdVer": "11.6.2.202",
            },
        },
        "session": {
            "interactionID": interaction_id,
            "isNew": True,
            "sessionId": session_id,
        },
        "utterance": {
            "original": query,
            "type": "text",
        },
        "version": "1.0",
    }
    if cfg.personal_uid:
        req["endpoint"]["uid"] = cfg.personal_uid
    return req


def call_imo_agent(cfg: Config, query: str) -> dict:
    session_id, interaction_id = get_session_info()
    req_body = build_request(cfg, query, session_id, interaction_id)

    headers = {
        "Content-Type": "application/json",
        "x-skill-id": SKILL_ID,
        "x-hag-trace-id": f"{session_id}_{interaction_id}",
        **cfg.auth_headers(),
    }

    url = cfg.service_url.rstrip("/") + SKILL_EXECUTE_PATH
    response_text = []
    logger.info(
        "发送请求 url=%s session_id=%s interaction_id=%s query=%s",
        url, session_id, interaction_id, query[:200],
    )

    try:
        with requests.post(
            url,
            json=req_body,
            headers=headers,
            stream=True,
            timeout=cfg.request_timeout,
            verify=not cfg.tls_skip_verify,
        ) as resp:
            if resp.status_code != 200:
                error_body = resp.text
                logger.error("HTTP %d: %s", resp.status_code, error_body)
                return {"error": {"code": str(resp.status_code), "message": error_body}}

            pending_data = ""
            has_pending = False
            got_final = False

            for raw_line in resp.iter_lines(decode_unicode=True):
                if raw_line is None:
                    continue
                line = raw_line.strip()

                if not line:
                    if has_pending and pending_data:
                        if process_event(pending_data, response_text):
                            got_final = True
                            pending_data = ""
                            has_pending = False
                            break
                    pending_data = ""
                    has_pending = False
                    continue

                if line.startswith("data:"):
                    data_part = line[5:].strip()
                    if has_pending:
                        pending_data += "\n" + data_part
                    else:
                        pending_data = data_part
                        has_pending = True

            if has_pending and pending_data and not got_final:
                if process_event(pending_data, response_text):
                    got_final = True

            if not got_final and not response_text:
                logger.error("SSE 流结束但未收到 final 结果，可能服务端提前断开")
                return {"error": {"code": "NO_FINAL_RESULT", "message": "SSE 流结束但未收到 final 结果，可能服务端提前断开"}}

    except requests.exceptions.Timeout:
        logger.error("请求超时")
        return {"error": {"code": "TIMEOUT", "message": f"请求超时（{cfg.request_timeout}s）"}}
    except requests.exceptions.RequestException as e:
        logger.error("请求失败: %s", e)
        return {"error": {"code": "NETWORK_ERROR", "message": str(e)}}
    except Exception as e:
        logger.exception("未知异常: %s", e)
        return {"error": {"code": "UNKNOWN_ERROR", "message": str(e)}}

    if got_final and not response_text:
        logger.error("收到 final 帧但 streamContent 为空")
        return {"error": {"code": "EMPTY_FINAL_RESULT", "message": "收到 final 帧但 streamContent 为空"}}

    full_text = "".join(response_text)
    return {"streamInfo": {"streamContent": full_text, "streamType": "final"}}


# ============================================================
# CLI
# ============================================================

def main():
    if len(sys.argv) < 2:
        print("用法: python imo_agent_invoke.py <query>", file=sys.stderr)
        sys.exit(1)

    query = sys.argv[1]

    try:
        cfg = Config.load()
    except ValueError as e:
        logger.error("配置错误: %s", e)
        print(json.dumps(
            {"error": {"code": "CONFIG_ERROR", "message": str(e)}},
            ensure_ascii=False,
        ))
        sys.exit(1)

    result = call_imo_agent(cfg, query)
    logger.info("最终输出: %s", json.dumps(result, ensure_ascii=False)[:500])
    print("=== RESULT ===")
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)

    if "error" in result:
        sys.exit(1)


if __name__ == "__main__":
    main()
