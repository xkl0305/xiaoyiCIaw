from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

VERSION = 'V111.52.10_LOCAL_RUNTIME_ACTUALIZATION_FINAL'
ACCEPTED_VERSIONS = {VERSION, 'V111.52.11_LOCAL_RUNTIME_METADATA_AND_ACCEPTANCE_CLOSE_FINAL'}
ROOT = Path(__file__).resolve().parents[2]


def _load_json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


class _LocalHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        _ = self.rfile.read(int(self.headers.get('Content-Length') or '0'))
        if self.path.endswith('/v1/embeddings'):
            body = {'data': [{'embedding': [0.1, 0.2, 0.3]}]}
        elif self.path.endswith('/v1/ocr'):
            body = {'text': 'local ocr ok'}
        else:
            body = {'choices': [{'message': {'content': 'local llm ok'}}]}
        raw = json.dumps(body).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args):
        return


def _start_server():
    srv = HTTPServer(('127.0.0.1', 0), _LocalHandler)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    return srv, srv.server_port


def _package_clean() -> dict:
    from infrastructure.packaging.source_runtime_boundary import package_clean_check
    return package_clean_check(ROOT)


def _strict_openclaw() -> bool:
    obj = _load_json('openclaw.json')
    top_ok = all([
        obj.get('ALLOW_NETWORK') is False,
        obj.get('NO_EXTERNAL_API') is True,
        obj.get('OFFLINE_MODE') is True,
        obj.get('ONLINE_MODE') is False,
        obj.get('NO_REAL_PAYMENT') is True,
        obj.get('NO_REAL_SEND') is True,
    ])
    rt = obj.get('runtime') or {}
    rt_ok = all([
        rt.get('ALLOW_NETWORK') is False,
        rt.get('NO_EXTERNAL_API') is True,
        rt.get('OFFLINE_MODE') is True,
        rt.get('ONLINE_MODE') is False,
        rt.get('NO_REAL_PAYMENT') is True,
        rt.get('NO_REAL_SEND') is True,
    ])
    return top_ok and rt_ok and obj.get('PERSONAL_OS_ENTERPRISE_VERSION') in ACCEPTED_VERSIONS


def _local_provider_execution() -> dict:
    srv, port = _start_server()
    old = {k: os.environ.get(k) for k in ['LOCAL_LLM_ENDPOINT','LOCAL_EMBEDDING_ENDPOINT','LOCAL_OCR_COMMAND','LOCAL_LLM_COMMAND']}
    try:
        os.environ['LOCAL_LLM_ENDPOINT'] = f'http://127.0.0.1:{port}'
        os.environ['LOCAL_EMBEDDING_ENDPOINT'] = f'http://127.0.0.1:{port}'
        with tempfile.TemporaryDirectory() as td:
            script = Path(td) / 'fake_ocr.py'
            script.write_text('import sys\nprint("ocr command ok")\n', encoding='utf-8')
            image = Path(td) / 'img.png'
            image.write_bytes(b'fake')
            os.environ['LOCAL_OCR_COMMAND'] = f'{sys.executable} {script} {{image_path}}'
            from core.personal_os_enterprise.local_providers import run_local_llm, run_local_embedding, run_local_ocr
            # Use a temporary runtime root so verification does not write .openclaw/state into source workspace.
            runtime_root = Path(td)
            llm = run_local_llm('hello', root=runtime_root)
            emb = run_local_embedding('hello', root=runtime_root)
            ocr = run_local_ocr(str(image), root=runtime_root)
            return {
                'llm_executed': llm.get('status') == 'executed' and not llm.get('blocked'),
                'embedding_executed': emb.get('status') == 'executed' and not emb.get('blocked'),
                'ocr_executed': ocr.get('status') == 'executed' and not ocr.get('blocked'),
                'llm': llm,
                'embedding': emb,
                'ocr': ocr,
            }
    finally:
        srv.shutdown()
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _non_local_rejected() -> bool:
    old = os.environ.get('LOCAL_LLM_ENDPOINT')
    try:
        os.environ['LOCAL_LLM_ENDPOINT'] = 'https://example.com/v1'
        from core.personal_os_enterprise.local_runtime_probe import probe_capability
        out = probe_capability('local_llm', root=ROOT)
        return out.get('ready') is False and out.get('reason') == 'non_local_endpoint'
    finally:
        if old is None:
            os.environ.pop('LOCAL_LLM_ENDPOINT', None)
        else:
            os.environ['LOCAL_LLM_ENDPOINT'] = old


def _model_hash_verify() -> bool:
    proc = subprocess.run([sys.executable, '-S', 'scripts/verify_model_cache_hash.py'], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc.returncode == 0 and 'passed' in proc.stdout


def main() -> int:
    version = _load_json('xiaoyi_persona_visual/version.json')
    release = _load_json('release_manifest.json')
    hook = _load_json('.openclaw/hooks/manifest.json')
    clean = _package_clean()
    provider = _local_provider_execution()
    checks = {
        'version_json_aligned': version.get('version') in ACCEPTED_VERSIONS,
        'release_manifest_aligned': release.get('version') in ACCEPTED_VERSIONS and release.get('local_runtime_actualization') is True,
        'hook_manifest_aligned': hook.get('version') in ACCEPTED_VERSIONS,
        'openclaw_runtime_strict_local': _strict_openclaw(),
        'package_clean_check_full': clean.get('clean') is True,
        'local_llm_adapter_executable': provider.get('llm_executed') is True,
        'local_embedding_adapter_executable': provider.get('embedding_executed') is True,
        'local_ocr_command_adapter_executable': provider.get('ocr_executed') is True,
        'non_local_endpoint_rejected': _non_local_rejected(),
        'model_hash_manifest_verifies': _model_hash_verify(),
        'secret_workflow_templates_present': (ROOT / '.sops.yaml').exists() and (ROOT / '.env.example').exists() and (ROOT / 'deploy/load_secrets.sh').exists(),
        'enterprise_acceptance_runner_present': (ROOT / 'scripts/acceptance/run_all_enterprise_acceptance.sh').exists(),
    }
    overall = all(checks.values())
    print(json.dumps({'overall': 'passed' if overall else 'failed', 'version': VERSION, 'checks': checks, 'package_clean': clean, 'provider_probe': {k: v for k, v in provider.items() if k.endswith('_executed')}}, ensure_ascii=False, indent=2))
    return 0 if overall else 1


if __name__ == '__main__':
    raise SystemExit(main())
