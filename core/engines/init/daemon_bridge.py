"""
Crusheart Daemon Bridge — 持久化 Python 守护进程
通过 Unix Domain Socket 接受 JSON-RPC 请求，在本进程中加载引擎模块直接执行。
避免每次调用 runPy() 冷启动 Python 进程的开销（30-50ms -> ~1ms）。

v6.6.0-fix:
  - ✅ 支持 --token 参数（连接鉴权）
  - ✅ Auth 分支：method: "auth" 时返回 token 比对结果
  - ✅ Ping 分支：method: "ping" 时返回 "pong"
  - ✅ rsplit(".", 1) 拆分 method，兼容 "script.py.run" 格式
  - ✅ _handle 读取整个 socket 缓冲区，逐行处理多个请求
"""

import os, sys, json, socket, threading, importlib.util, traceback, time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
DAEMON_SOCK = os.environ.get("CRUSHEART_DAEMON_SOCK") or f"/tmp/.crusheart-daemon-{os.getpid()}.sock"

ENGINE_GROUPS = ["init", "memory", "quality", "operations", "workflow", "hooks", "tools", "compat"]


class ModuleCache:
    """缓存已加载的引擎模块，避免重复 import"""
    def __init__(self):
        self._cache = {}
        self._result_cache = {}  # (script, func, args_tuple) -> (result, expiry_ts)
        self._result_cache_ttl = 5  # 5秒内相同输入直接返回缓存
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="daemon_bridge")

    def resolve_path(self, script_name: str) -> str:
        candidates = [
            os.path.join(WORKSPACE, script_name),
            os.path.join(WORKSPACE, "scripts", script_name),
        ]
        bundle_dir = os.path.join(os.path.dirname(__file__) or ".", "..", "..")
        candidates.append(os.path.join(bundle_dir, "bundle", script_name))
        for g in ENGINE_GROUPS:
            candidates.append(os.path.join(WORKSPACE, "core/engines", g, script_name))
        for c in candidates:
            if os.path.exists(c):
                return os.path.abspath(c)
        return ""

    def get_module(self, script_name: str):
        with self._lock:
            if script_name in self._cache:
                return self._cache[script_name]
            path = self.resolve_path(script_name)
            if not path:
                raise FileNotFoundError("Script not found: " + script_name)
            name = script_name.replace(".py", "").replace("/", "_")
            spec = importlib.util.spec_from_file_location(name, path)
            if spec is None or spec.loader is None:
                raise ImportError("Cannot load spec for " + script_name)
            mod = importlib.util.module_from_spec(spec)
            sys.path.insert(0, WORKSPACE)
            sys.path.insert(0, os.path.join(WORKSPACE, "scripts"))
            spec.loader.exec_module(mod)
            self._cache[script_name] = mod
            return mod

    def call(self, script_name: str, func_name: str, *args, timeout: float = 0):
        """调用模块函数，支持超时"""
        mod = self.get_module(script_name)
        fn = getattr(mod, func_name, None)
        if fn is None:
            fn = getattr(mod, "run", None)
            if fn is None:
                raise AttributeError("No function " + func_name + " or run() in " + script_name)
        if timeout > 0:
            future = self._executor.submit(fn, *args)
            try:
                return future.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                future.cancel()
                raise
        return fn(*args)

    def call_with_cache(self, script_name: str, func_name: str, *args, timeout: float = 0):
        """带TTL缓存调用，5秒内相同输入直接返回缓存结果"""
        cache_key = (script_name, func_name, args)
        now = time.time()
        with self._lock:
            if cache_key in self._result_cache:
                result, expiry = self._result_cache[cache_key]
                if now < expiry:
                    return result
        result = self.call(script_name, func_name, *args, timeout=timeout)
        with self._lock:
            self._result_cache[cache_key] = (result, now + self._result_cache_ttl)
        return result

    def call_batch(self, calls: list) -> list:
        """批量并行调用：calls = [(script, func, args_tuple), ...]"""
        futures = []
        for script, func, args in calls:
            future = self._executor.submit(self.call, script, func, *args)
            futures.append(future)
        results = []
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as e:
                results.append({"error": str(e)})
        return results

    def get_cache_stats(self) -> dict:
        """缓存统计"""
        with self._lock:
            return {
                "module_cache_size": len(self._cache),
                "result_cache_size": len(self._result_cache),
                "result_cache_ttl": self._result_cache_ttl,
            }


class DaemonServer:
    def __init__(self, token=""):
        self.cache = ModuleCache()
        self._running = True
        self.token = token
        self._started_at = time.time()

    def _handle_one_request(self, req, conn) -> dict:
        """处理一个 JSON-RPC 请求，返回响应字典"""
        method_str = req.get("method", "")
        req_id = req.get("id", 0)
        raw_args = req.get("params", [])
        timeout = req.get("timeout", 8.0)  # 默认8秒超时（修复3s不够问题）

        try:
            # Auth 分支
            if method_str == "auth":
                provided_token = raw_args[0] if raw_args else ""
                return {"jsonrpc": "2.0", "result": provided_token == self.token, "id": req_id}

            # Ping 分支（带状态统计）
            if method_str == "ping":
                return {"jsonrpc": "2.0", "result": {
                    "status": "ok",
                    "uptime_s": int(time.time() - self._started_at),
                    "cache_stats": self.cache.get_cache_stats(),
                }, "id": req_id}

            # Batch_run: 批量并行调用
            if method_str == "batch_run":
                calls = raw_args[0] if raw_args else []
                results = self.cache.call_batch(calls)
                return {"jsonrpc": "2.0", "result": results, "id": req_id}

            # 普通 RPC 调用（走TTL缓存）
            method_parts = method_str.rsplit(".", 1)
            script_name = method_parts[0] if len(method_parts) >= 1 else ""
            func_name = method_parts[1] if len(method_parts) >= 2 else "run"
            result = self.cache.call_with_cache(script_name, func_name, *raw_args, timeout=timeout)
            return {"jsonrpc": "2.0", "result": result, "id": req_id}

        except FileNotFoundError as e:
            return {"jsonrpc": "2.0", "error": {"code": -32001, "message": str(e)}, "id": req_id}
        except Exception as e:
            return {"jsonrpc": "2.0",
                    "error": {"code": -32000, "message": type(e).__name__ + ": " + str(e)},
                    "id": req_id}

    def _handle(self, conn):
        """持久连接处理循环：逐行读取 JSON-RPC 请求并响应"""
        try:
            remaining = b""
            while True:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                remaining += chunk
                # 从缓冲区逐行解析
                while True:
                    decoded = remaining.decode("utf-8", errors="replace")
                    idx = decoded.find("\n")
                    if idx < 0:
                        break
                    line = decoded[:idx]
                    remaining = remaining[idx+1:]
                    if not line.strip():
                        continue
                    req = json.loads(line)
                    resp = self._handle_one_request(req, conn)
                    try:
                        conn.sendall((json.dumps(resp, ensure_ascii=False) + "\n").encode("utf-8"))
                    except Exception:
                        pass
        except Exception as e:
            logging.warning("[daemon_bridge.py] _handle error: " + str(e))
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def serve(self):
        try:
            os.remove(DAEMON_SOCK)
        except OSError:
            pass
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(DAEMON_SOCK)
        server.listen(16)
        os.chmod(DAEMON_SOCK, 0o600)
        print("[daemon] Ready on " + DAEMON_SOCK, file=sys.stderr, flush=True)
        while self._running:
            try:
                conn, _ = server.accept()
                t = threading.Thread(target=self._handle, args=(conn,), daemon=True)
                t.start()
            except KeyboardInterrupt:
                break
            except Exception:
                logging.exception("[daemon_bridge.py] suppressed")
                pass
        server.close()
        try:
            os.remove(DAEMON_SOCK)
        except OSError:
            pass


if __name__ == "__main__":

    # --test/--self-check: 基础自检（#48）
    if "--test" in sys.argv or "--self-check" in sys.argv:
        try:
            from core.engines.init.self_check import run_self_check
        except ImportError:
            print("❌ self_check 模块不可用")
            sys.exit(1)

        checks = [("import self", lambda: None)]
        sys.exit(run_self_check(__name__, __file__,
            custom_checks=checks, verbose=True))

    # 解析 --token 参数
    token = ""
    if "--token" in sys.argv:
        idx = sys.argv.index("--token")
        if idx + 1 < len(sys.argv):
            token = sys.argv[idx + 1]

    if "--daemon" in sys.argv:
        DaemonServer(token=token).serve()
    elif len(sys.argv) >= 3:
        # 直接调用模式（不含 --daemon）
        script = sys.argv[1]
        func = sys.argv[2]
        args = [json.loads(a) for a in sys.argv[3:]]
        cache = ModuleCache()
        result = cache.call(script, func, *args)
        print(json.dumps(result, ensure_ascii=False))
    else:
        print("Usage:")
        print("  python3 daemon_bridge.py --daemon [--token <token>]")
        print("  python3 daemon_bridge.py <script> <func> [args...]")
