#!/usr/bin/env python3
"""华为账号 / 新浪 MCP 登录凭证模块（小艺 loginToken → MCP token 换取链路）。

依据华为官方文档《Skill接入华为账号》与新浪侧「小艺 token 换取 MCP token」接口说明。

完整链路：
    1. 华为账号授权（小艺 authorize，绑定信息含手机号）→ 返回 loginToken（7 天有效）
    2. 凭据来源：运行时从环境文件 /home/sandbox/.openclaw/.xiaoyienv
       读取 {clientId}_login_token 与 {clientId}_login_token_expire_time。
    3. 有效判断：login_token 非空 且 当前时间 <= expire_time 时视为有效。
    4. 刷新机制：若 login_token 为空 或 已过期（当前时间 > expire_time），
       skill 流程须调用一次 huawei_id_tool 工具（参数 clientId、skillName）
       刷新凭证；刷新成功后重新读取 .xiaoyienv 继续。仅调用一次，不可重复。
    5. 换取：用有效 loginToken 调 POST {EXCHANGE_URL} 换取 MCP token
       （即 zyhub regular token）。
    6. 业务访问：mcp.finance.sina.com.cn/api-call 接口请求头携带
       `X-Auth-Token: <MCP token>`。

注意：
    - huawei_id_tool 是平台提供的工具，由大模型在运行本 skill 时按其
      指引调用（不通过 metadata 声明），本模块只在 loginToken 失效时向
      大模型输出明确的"需要刷新"信号与刷新指引。
    - xy_exchange_token 换取失败时，按新浪接口返回的 status.code 输出
      明确的处理指引（不伪造 token）。

对外接口：
    get_token()                -> str      业务请求头 X-Auth-Token 的值（MCP token）
    get_auth_headers()         -> dict     业务请求头 dict（含 X-Auth-Token）
    store_mcp_token(token)     -> None     把 MCP token 存入环境变量 X-AUTH-TOKEN
    get_cached_mcp_token()     -> str      读取环境变量 X-AUTH-TOKEN 中的 MCP token
    is_login_token_valid()     -> bool     当前 login_token 是否有效
    need_refresh()             -> bool     是否需要调用 huawei_id_tool 刷新
    get_refresh_instruction()  -> str      给大模型的 loginToken 刷新指引

依赖：仅标准库。
安全：loginToken 只从 .xiaoyienv 读取；MCP token 不经由本模块落盘；
      本模块不打印任何 token 值。
"""
import os
import sys
import time
import json
import urllib.request
import urllib.error

# ============ CONFIG：登录与换取契约配置 ============

# 账号云环境文件（华为平台注入华为账号凭据的位置，参考 skill 一致路径）
XIAOYI_ENV_FILE = os.path.join(os.path.expanduser("~"), ".openclaw", ".xiaoyienv")

# 华为账号服务 clientId / skillName（本 skill 实际接入值）
CLIENT_ID = os.environ.get("HUAWEI_CLIENT_ID", "118599757")
SKILL_NAME = os.environ.get("HUAWEI_SKILL_NAME", "zm-market-query")

# 由 clientId 派生的环境变量名（与平台注入一致）
LOGIN_TOKEN_VAR = f"{CLIENT_ID}_login_token"
LOGIN_TOKEN_EXPIRE_VAR = f"{CLIENT_ID}_login_token_expire_time"

# 新浪侧换取 MCP token 接口
EXCHANGE_URL = "https://ai.finance.sina.cn/skill/api/v1/xy_exchange_token"

# 业务 mcp 接口认证请求头名（值为换取到的 MCP token）
AUTH_HEADER = "X-Auth-Token"

# 专门存储换取到的 MCP token 的环境变量名
# 换取成功后写入 os.environ[ENV_MCP_TOKEN]；get_token()/get_auth_headers()
# 优先读取该环境变量，存在则直接复用（避免每次重复调用 xy_exchange_token）。
ENV_MCP_TOKEN = "X-AUTH-TOKEN"

# 请求超时（秒）
HTTP_TIMEOUT = 20


# ============ 环境文件读取 ============

def _parse_xiaoyi_env_file() -> dict:
    """解析 .xiaoyienv 文件，返回 {变量名: 值}。

    文件格式为「KEY=value」或「export KEY=value」逐行的键值对。
    文件不存在/解析失败时返回空 dict（视为无凭据）。
    """
    result = {}
    try:
        with open(XIAOYI_ENV_FILE, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if line.startswith("export "):
                    line = line[len("export "):].strip()
                if "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key:
                    result[key] = val
    except FileNotFoundError:
        pass
    except OSError as e:
        print(f"WARN: 读取 {XIAOYI_ENV_FILE} 失败：{e}", file=sys.stderr)
    return result


def load_login_token() -> str:
    """从 .xiaoyienv 读取当前 login_token 值（空字符串表示未获取到）。"""
    env = _parse_xiaoyi_env_file()
    return (env.get(LOGIN_TOKEN_VAR) or "").strip()


def load_login_token_expire_time() -> float:
    """读取 login_token 过期时间（秒时间戳）。未配置/无效时返回 0。"""
    env = _parse_xiaoyi_env_file()
    raw = (env.get(LOGIN_TOKEN_EXPIRE_VAR) or "").strip()
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


# ============ 有效性判断与刷新指引 ============

def is_login_token_valid() -> bool:
    """login_token 是否有效：非空 且 未过期。"""
    token = load_login_token()
    if not token:
        return False
    expire = load_login_token_expire_time()
    if expire and time.time() > expire:
        return False
    return True


def need_refresh() -> bool:
    """是否需要调用 huawei_id_tool 刷新凭据。"""
    return not is_login_token_valid()


def _login_token_refresh_message() -> str:
    return (
        "ERROR: 华为账号登录凭据（loginToken）缺失或已过期。\n"
        f"  凭据变量：{LOGIN_TOKEN_VAR}、{LOGIN_TOKEN_EXPIRE_VAR}\n"
        f"  来源文件：{XIAOYI_ENV_FILE}\n"
        "处理方式：调用一次 huawei_id_tool 工具刷新凭证"
        f"（参数：clientId={CLIENT_ID}，skillName={SKILL_NAME}）。\n"
        "刷新成功后重新读取 .xiaoyienv 中的登录凭据，再继续后续业务逻辑。"
        "注意：仅调用一次，不可重复调用。"
    )


def get_refresh_instruction() -> str:
    """返回给大模型的 loginToken 刷新指引文案（在凭据失效时使用）。"""
    return _login_token_refresh_message()


# ============ 换取 MCP token（XY exchange）============

def _exchange_mcp_token(login_token: str) -> str:
    """用有效 loginToken 调 xy_exchange_token 换取 MCP token。

    Returns:
        MCP token（即 zyhub regular token），用于 X-Auth-Token 头。

    Raises:
        SystemExit: 网络错误或换取失败（status.code != 0）时终止并按 code 提示。
    """
    body = json.dumps({"loginToken": login_token}).encode()
    req = urllib.request.Request(
        EXCHANGE_URL, data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            text = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        print(f"ERROR: 换取 MCP token HTTP {e.code}: {e.read().decode('utf-8', errors='replace')}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"ERROR: 换取 MCP token 请求失败：{e}", file=sys.stderr)
        sys.exit(2)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        print(f"ERROR: 换取 MCP token 返回非 JSON：{text[:200]}", file=sys.stderr)
        sys.exit(2)

    status = (payload.get("result") or {}).get("status") or {}
    code = status.get("code")
    msg = status.get("msg") or ""
    if code == 0:
        data = (payload.get("result") or {}).get("data") or {}
        token = data.get("token") or ""
        if not token:
            print("ERROR: 换取成功但响应中缺少 data.token", file=sys.stderr)
            sys.exit(2)
        return token

    _handle_exchange_error(code, msg)
    sys.exit(2)  # 不可达，保险


def _handle_exchange_error(code, msg):
    """按新浪 xy_exchange_token 返回的 status.code 输出对应处理指引。"""
    hints = {
        -1: "参数错误：检查请求 body 是否包含 loginToken",
        -2: "loginToken 无效或已过期：先调用一次 huawei_id_tool 刷新（成功后重读 .xiaoyienv）再重试换取；若仍返回 -2，说明 refreshToken 也已失效，需重新拉起用户授权（用户在小艺侧重新完成华为账号授权）",
        -3: "绑定信息中无手机号：用户需在小艺侧重新完成华为账号授权",
        -4: "zyhub 侧无可用 token：用户需在 zyhub 平台（zyhub.finance.sina.cn）申请 regular token",
        -500: "系统错误：建议稍后重试",
    }
    hint = hints.get(code, f"未知错误码 {code}：{msg}")
    print(
        f"ERROR: 换取 MCP token 失败（status.code={code}）。\n"
        f"  说明：{hint}\n"
        "  请依据上述说明处理后再重试。",
        file=sys.stderr,
    )


# ============ 对外：业务请求头 ============

def get_cached_mcp_token() -> str:
    """读取专门环境变量 X-AUTH-TOKEN 中的 MCP token（空字符串表示未存储）。"""
    return (os.environ.get(ENV_MCP_TOKEN) or "").strip()


def store_mcp_token(token: str) -> None:
    """把换取到的 MCP token 存入环境变量 X-AUTH-TOKEN。"""
    os.environ[ENV_MCP_TOKEN] = token


def get_token() -> str:
    """返回业务接口认证头 X-Auth-Token 的值（MCP token）。

    流程：若环境变量 X-AUTH-TOKEN 已有 MCP token 则直接复用；
    否则 loginToken 有效 → 调 xy_exchange_token 换取 → 存入 X-AUTH-TOKEN → 返回。

    Raises:
        SystemExit: loginToken 缺失/过期时输出刷新指引（exit 3）；
                    换取失败时按 status.code 输出指引（exit 2）。
    """
    cached = get_cached_mcp_token()
    if cached:
        return cached
    if need_refresh():
        print(_login_token_refresh_message(), file=sys.stderr)
        sys.exit(3)
    login_token = load_login_token()
    mcp_token = _exchange_mcp_token(login_token)
    store_mcp_token(mcp_token)
    return mcp_token


def get_auth_headers() -> dict:
    """构造业务接口需要的认证请求头（X-Auth-Token: <MCP token>）。"""
    return {AUTH_HEADER: get_token()}


# 供 SKILL.md 引用：业务请求头示例（不展开 token 值）
def request_header_example() -> str:
    return (
        "--header 'Content-Type: application/json' \\\n"
        f"--header '{AUTH_HEADER}: <MCP token>（由 xy_exchange_token 换取）'"
    )


if __name__ == "__main__":
    # 命令行自检：python3 auth.py
    if need_refresh():
        sys.stderr.write(_login_token_refresh_message() + "\n")
        sys.exit(3)
    print("登录凭据（loginToken）有效")
    print("  login_token 变量 :", LOGIN_TOKEN_VAR)
    print("  换取接口        :", EXCHANGE_URL)
    print("  MCP token 变量  :", ENV_MCP_TOKEN)
    print("  业务请求头      :", AUTH_HEADER)
    print("  header 示例     :")
    print(request_header_example())
