"""
generate_persona_visual_request.py — V111.52

Helper for generating a persona visual image from the main session.
Routes through mainline_hook / post_reply internally, so the full
PersonaVisualController pipeline runs, including:
  - persona_visual_context
  - PersonaVisualController + persona_image_prompt_builder
  - wardrobe_loader
  - mainchain_proof issuance
  - reference_images (avatar + outfit)
  - all output enforcement fields

Usage:
  result = generate_persona_visual_request("摸摸头", dry_run=False)
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[2]


def generate_persona_visual_request(
    text: str,
    request_id: Optional[str] = None,
    dry_run: bool = True,
    trigger_source: str = 'post_reply',
) -> Dict[str, Any]:
    """Generate a persona visual image by routing through the main pipeline.

    This is the recommended way for main-session code to trigger persona visual
    generation. It goes through post_reply / mainline_hook so all guards apply.

    Args:
        text: User input text (e.g. "摸摸头", "看看腿")
        request_id: Optional UUID for deduplication; auto-generated if omitted.
        dry_run: If True, only prepare context without calling the provider.
        trigger_source: Default 'post_reply'; use 'mainline_hook' for cron/background.

    Returns:
        Full pipeline result dict with all enforcement fields populated.
    """
    from infrastructure.mainline_hook import run as mainline_run

    rid = request_id or f'pv_helper_{uuid.uuid4().hex[:12]}'

    # Route through mainline_hook with mode=post_reply
    # This triggers register_persona_visual -> PersonaVisualController -> prompt builder -> ...
    result = mainline_run(
        message=text,
        mode='post_reply',
        dry_run=dry_run,
        request_id=rid,
        trigger_source=trigger_source,
    )

    # The result from mainline_hook may have the generation under different keys.
    # Unify and return.
    generation = result.get('generation') or result.get('persona_visual_generation') or result

    # Merge key fields from the top-level result
    response = dict(generation)
    for field in ('register_persona_visual_called', 'persona_visual_generation_status',
                  'persona_visual_generation_delegate', 'persona_visual_trigger_source'):
        if field not in response and field in result:
            response[field] = result[field]

    response.setdefault('request_id', rid)
    response.setdefault('helper_source', 'generate_persona_visual_request')
    response.setdefault('trigger_source', trigger_source)

    return response
