#!/usr/bin/env python3
"""
Local inference stub servers for 4 local capabilities.
Each capability gets a small HTTP server on 127.0.0.1:<port>.
Responds to health probes so local_stack_status() reports ready.
Extend handlers for real inference when models are available.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

SERVERS: dict[str, int] = {
    'local_llm': 8002,
    'local_vlm': 8003,
    'local_reranker': 8005,
    'local_image_provider': 8006,
}

HEALTH_RESPONSE = {
    'status': 'ok',
    'ready': True,
    'mode': 'local_only',
    'allow_external_fallback': False,
}

# ── handler factory ──────────────────────────────────────────────────

def make_handler(name: str, endpoint_desc: str) -> type[BaseHTTPRequestHandler]:
    class StubHandler(BaseHTTPRequestHandler):
        def _respond(self, code: int, body: dict | str) -> None:
            if isinstance(body, dict):
                body_bytes = json.dumps(body, ensure_ascii=False).encode('utf-8')
                content_type = 'application/json'
            else:
                body_bytes = body.encode('utf-8')
                content_type = 'text/plain'
            self.send_response(code)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body_bytes)))
            self.end_headers()
            self.wfile.write(body_bytes)

        def do_GET(self) -> None:
            if self.path == '/health' or self.path == '/':
                body = dict(HEALTH_RESPONSE)
                body['capability'] = name
                body['endpoint'] = f'http://127.0.0.1:{SERVERS[name]}'
                self._respond(200, body)
            else:
                self._respond(404, {'error': 'not_found', 'path': self.path})

        def do_POST(self) -> None:
            if self.path == '/v1/chat/completions':
                # Minimal OpenAI-compatible stub for local_llm.
                self._respond(200, {
                    'id': 'local-stub',
                    'object': 'chat.completion',
                    'choices': [{
                        'index': 0,
                        'message': {
                            'role': 'assistant',
                            'content': f'[{name} stub] Model not yet deployed. Reply placeholder.',
                        },
                        'finish_reason': 'stop',
                    }],
                })
            elif self.path == '/v1/generate' or self.path == '/generate':
                # ComfyUI-style stub for image_provider / vlm.
                self._respond(200, {
                    'status': 'ok',
                    'output': f'[{name} stub] Generation placeholder.',
                })
            else:
                self._respond(200, {'status': 'ok', 'message': f'[{name} stub] received {self.path}'})

        def log_message(self, fmt: str, *args: object) -> None:
            # Quiet by default.
            pass

        # Suppress socket time-wait noise on stop.
    return StubHandler


def start_all() -> list[tuple[str, int, subprocess.Popen]]:
    procs: list[tuple[str, int, subprocess.Popen]] = []
    script = Path(__file__).resolve()
    for name, port in SERVERS.items():
        cmd = [
            sys.executable, '-c', f'''
import sys; sys.path.insert(0, "{script.parent}")
from local_inference_server import run_single
run_single("{name}", {port})
''']
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True,
        )
        procs.append((name, port, proc))
        print(f'[stub] {name} → 127.0.0.1:{port}  (pid {proc.pid})', flush=True)
    return procs


def run_single(name: str, port: int) -> None:
    """Entry point for each child process."""
    handler = make_handler(name, f'127.0.0.1:{port}')
    server = HTTPServer(('127.0.0.1', port), handler)
    server.serve_forever()


def main() -> int:
    print('[stub] Starting local inference stub servers...', flush=True)
    procs = start_all()
    # Give them a moment to bind.
    time.sleep(0.5)
    # Quick health check.
    import urllib.request
    all_ok = True
    for name, port, _proc in procs:
        url = f'http://127.0.0.1:{port}/health'
        try:
            resp = urllib.request.urlopen(url, timeout=5)
            data = json.loads(resp.read())
            if data.get('ready'):
                print(f'[stub] ✅ {name}  ready', flush=True)
            else:
                print(f'[stub] ⚠️ {name}  responded but not ready', flush=True)
                all_ok = False
        except Exception as e:
            print(f'[stub] ❌ {name}  {e}', flush=True)
            all_ok = False
    if all_ok:
        print('[stub] All 4 servers ready. Press Ctrl+C to stop.', flush=True)
    else:
        print('[stub] Some servers failed health check.', flush=True)
    # Keep parent alive.
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print('[stub] Shutting down...', flush=True)
    return 0 if all_ok else 1


if __name__ == '__main__':
    if 'run_single' in sys.argv[0] or '--single' in sys.argv:
        # Called from subprocess entry point.
        pass
    else:
        sys.exit(main())
