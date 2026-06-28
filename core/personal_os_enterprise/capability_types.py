from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

CAPABILITY_KIND_LOCAL_LLM = 'local_llm'
CAPABILITY_KIND_LOCAL_VLM = 'local_vlm'
CAPABILITY_KIND_LOCAL_OCR = 'local_ocr'
CAPABILITY_KIND_LOCAL_ASR = 'local_asr'
CAPABILITY_KIND_LOCAL_TTS = 'local_tts'
CAPABILITY_KIND_LOCAL_EMBEDDING = 'local_embedding'
CAPABILITY_KIND_LOCAL_RERANKER = 'local_reranker'
CAPABILITY_KIND_LOCAL_IMAGE_PROVIDER = 'local_image_provider'
CAPABILITY_KIND_PERSONA_VISUAL = 'persona_visual'
CAPABILITY_KIND_FILE = 'file_operation'
CAPABILITY_KIND_DEVICE = 'device_action'

LOCAL_MODEL_CAPABILITIES = {
    CAPABILITY_KIND_LOCAL_LLM,
    CAPABILITY_KIND_LOCAL_VLM,
    CAPABILITY_KIND_LOCAL_OCR,
    CAPABILITY_KIND_LOCAL_ASR,
    CAPABILITY_KIND_LOCAL_TTS,
    CAPABILITY_KIND_LOCAL_EMBEDDING,
    CAPABILITY_KIND_LOCAL_RERANKER,
    CAPABILITY_KIND_LOCAL_IMAGE_PROVIDER,
}

@dataclass(frozen=True)
class CapabilitySpec:
    name: str
    kind: str
    status: str = 'declared'
    connection_mode: str = 'local_only'
    side_effect: bool = False
    requires_side_effect_proof: bool = False
    allow_external_fallback: bool = False
    provider: str = ''
    command: str = ''
    endpoint: str = ''
    model_path: str = ''
    description: str = ''
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'kind': self.kind,
            'status': self.status,
            'connection_mode': self.connection_mode,
            'side_effect': self.side_effect,
            'requires_side_effect_proof': self.requires_side_effect_proof,
            'allow_external_fallback': self.allow_external_fallback,
            'provider': self.provider,
            'command': self.command,
            'endpoint': self.endpoint,
            'model_path': self.model_path,
            'description': self.description,
            'tags': list(self.tags),
        }

@dataclass(frozen=True)
class CapabilityRoute:
    intent_type: str
    required_capabilities: List[str]
    optional_capabilities: List[str] = field(default_factory=list)
    side_effect_action: str = ''
    confidence: float = 0.0
    reason: str = ''
    fail_closed: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            'intent_type': self.intent_type,
            'required_capabilities': list(self.required_capabilities),
            'optional_capabilities': list(self.optional_capabilities),
            'side_effect_action': self.side_effect_action,
            'confidence': self.confidence,
            'reason': self.reason,
            'fail_closed': self.fail_closed,
        }
