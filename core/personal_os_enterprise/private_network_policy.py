from __future__ import annotations

from typing import Dict

VERSION = "V111.52.13_ENTERPRISE_REPORT_REMAINING_CLOSE_FINAL"


def private_network_policy() -> Dict[str, object]:
    return {
        'version': VERSION,
        'mode': 'single_machine_first_private_network_later',
        'external_internet_egress': False,
        'allowed_bind_hosts': ['127.0.0.1', 'localhost', '::1'],
        'future_private_cidr_allowed_with_explicit_profile': True,
        'node_id_required_for_multi_node': True,
        'proof_registry_records_issuer_node_id': True,
        'node_secret_rotation_required': True,
        'backup_restore_drill_required': True,
    }
