from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List

VERSION = "V111.52.13_ENTERPRISE_REPORT_REMAINING_CLOSE_FINAL"

@dataclass(frozen=True)
class AcceptanceCase:
    case_id: str
    area: str
    input: str
    expected: str
    script_path: str
    required: bool = True

REPORT_ACCEPTANCE_CASES: List[AcceptanceCase] = [
    AcceptanceCase('offline_boot', 'offline', 'ALLOW_NETWORK=false / NO_EXTERNAL_API=true', '启动不外连，配置 fail-closed', 'tests/acceptance/test_offline_boot.py'),
    AcceptanceCase('mainchain_proof_issue', 'proof', '正常主链请求', '返回 mainchain_proof，registry 状态=issued', 'tests/acceptance/test_mainchain_proof.py::test_issue'),
    AcceptanceCase('mainchain_proof_replay', 'proof', '重复消费同一 proof', '第二次失败，reason=replay_blocked', 'tests/acceptance/test_mainchain_proof.py::test_replay'),
    AcceptanceCase('manual_provider_blocked', 'proof', '直调 provider / 缺 proof', 'blocked=true', 'tests/acceptance/test_mainchain_proof.py::test_manual_provider_call_blocked'),
    AcceptanceCase('stale_file_send', 'send_guard', '旧文件路径 + 新 request_id', 'blocked_send=true', 'tests/acceptance/test_send_guard.py::test_stale_file'),
    AcceptanceCase('missing_file_send', 'send_guard', 'provider 返回无 output_path', 'blocked_send=true', 'tests/acceptance/test_send_guard.py::test_missing_file'),
    AcceptanceCase('provider_domain_fallback', 'provider', '关闭 provider A', '只在同安全域本地 provider 回退', 'tests/acceptance/test_provider_fallback.py::test_domain_fallback'),
    AcceptanceCase('transport_fallback', 'provider', 'requests 不可用', 'urllib 路径可控工作或可控失败', 'tests/acceptance/test_provider_fallback.py::test_transport_fallback'),
    AcceptanceCase('ocr_vlm_consistency', 'multimodal', '截图样本集', 'OCR 结构元素与 VLM 字段一致率达阈值', 'tests/regression/test_ocr_vlm_consistency.py'),
    AcceptanceCase('persona_anatomy_tail_anchor', 'persona_visual', '背身/侧身/抬脚样本', '尾巴锚定身体，不漂浮背景', 'tests/regression/test_persona_visual_anatomy.py::test_tail_root_attachment'),
    AcceptanceCase('wardrobe_state', 'persona_visual', '连续两轮 outfit 切换', 'wardrobe_state 正确演进', 'tests/regression/test_wardrobe_state.py'),
    AcceptanceCase('secret_packaged_scan', 'security', '构建产物/工作目录', '不出现 secret/key/token 明文', 'scripts/security/verify_no_runtime_secret_packaged.py'),
    AcceptanceCase('observability_complete', 'observability', '运行完整主链', '产生 trace、metrics、logs/event ledger', 'tests/acceptance/test_observability.py'),
]


def acceptance_matrix() -> Dict[str, object]:
    return {
        'version': VERSION,
        'case_count': len(REPORT_ACCEPTANCE_CASES),
        'cases': [asdict(c) for c in REPORT_ACCEPTANCE_CASES],
        'areas': sorted({c.area for c in REPORT_ACCEPTANCE_CASES}),
    }


def validate_acceptance_files(root: str | Path) -> Dict[str, object]:
    root = Path(root)
    missing = []
    for c in REPORT_ACCEPTANCE_CASES:
        path = c.script_path.split('::', 1)[0]
        if not (root / path).exists():
            missing.append(path)
    return {
        'ok': not missing,
        'missing': sorted(set(missing)),
        'case_count': len(REPORT_ACCEPTANCE_CASES),
    }
