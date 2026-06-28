"""V111.15 scene image detector — real image understanding via xiaoyi-image-understanding.

from __future__ import annotations

Accepts scene_image_path and seed_image_path, validates they exist,
and produces a scene summary. If xiaoyi-image-understanding skill is available,
REALLY calls it to understand the image content.

Does NOT fake image understanding.
"""

import json
import os
import traceback
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from infrastructure.common.path_utils import get_workspace_root  # type: ignore
except Exception:
    def get_workspace_root(file: str | None = None) -> Path:
        cur = Path(file or __file__).resolve()
        for p in [cur] + list(cur.parents):
            if (p / "openclaw.json").exists():
                return p
        return Path.cwd().resolve()

ROOT = get_workspace_root(__file__)

# Known image extensions
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}


def _resolve_path(path_str: str) -> Optional[Path]:
    """Resolve a path string. Accepts relative (to ROOT) and absolute paths."""
    if os.path.isabs(path_str):
        p = Path(path_str)
    else:
        p = ROOT / path_str
    return p if (p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS) else None


def _get_skill_script_dir() -> Optional[Path]:
    """Return the xiaoyi-image-understanding scripts dir if available."""
    d1 = ROOT / "skills" / "xiaoyi-image-understanding" / "scripts"
    d2 = ROOT / "skills" / "xiaoyi_image_understanding" / "scripts"
    return d1 if d1.is_dir() else d2 if d2.is_dir() else None


def _real_image_understanding(image_path: str, prompt: str = "详细描述这张图片") -> Dict[str, Any]:
    """
    Actually call the xiaoyi-image-understanding skill to understand an image.
    
    Steps:
    1. If image_path is a local file, upload it first via file_upload.py to get a URL.
    2. Call image_understanding.py with the URL + prompt.
    3. Return the caption and metadata.
    """
    result = {
        "caption": None,
        "success": False,
        "error": None,
        "implementation_status": "image_understanding_call_failed",
        "method": None,
    }
    
    scripts_dir = _get_skill_script_dir()
    if not scripts_dir:
        result["error"] = "xiaoyi-image-understanding scripts dir not found"
        result["implementation_status"] = "needs_real_image_understanding_skill"
        return result
    
    # Step 0: Determine if local or remote
    is_local = os.path.isfile(image_path) if os.path.isabs(image_path) else (ROOT / image_path).is_file()
    file_url = image_path if image_path.startswith("http") else None
    
    try:
        if is_local and not image_path.startswith("http"):
            # Step 1: Upload local file
            upload_script = scripts_dir / "file_upload.py"
            if not upload_script.is_file():
                result["error"] = f"file_upload.py not found at {upload_script}"
                return result
            
            import importlib.util
            spec = importlib.util.spec_from_file_location("file_upload", str(upload_script))
            fu_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(fu_mod)
            
            resolved_path = str(ROOT / image_path) if not os.path.isabs(image_path) else image_path
            upload_result = fu_mod.upload_file(resolved_path)
            
            if not upload_result or not isinstance(upload_result, dict):
                result["error"] = f"file_upload returned non-dict: {upload_result}"
                return result
            
            file_url = upload_result.get("fileUrl")
            if not file_url:
                result["error"] = f"file_upload did not return fileUrl: {upload_result}"
                return result
            
            result["method"] = "local_upload_then_understand"
        else:
            # image_path is already a URL
            file_url = image_path
            result["method"] = "direct_url_understand"
        
        # Step 2: Call image_understanding
        iu_script = scripts_dir / "image_understanding.py"
        if not iu_script.is_file():
            result["error"] = f"image_understanding.py not found at {iu_script}"
            return result
        
        spec2 = importlib.util.spec_from_file_location("image_understanding", str(iu_script))
        iu_mod = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(iu_mod)
        
        understanding_result = iu_mod.image_understanding(file_url, prompt)
        
        if not understanding_result or not isinstance(understanding_result, dict):
            result["error"] = f"image_understanding returned non-dict: {understanding_result}"
            return result
        
        caption = understanding_result.get("caption")
        if not caption:
            result["error"] = f"image_understanding returned no caption: {understanding_result}"
            return result
        
        result["caption"] = caption
        result["success"] = True
        result["implementation_status"] = "image_understanding_succeeded"
        
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}\n{traceback.format_exc()[:200]}"
        result["implementation_status"] = "image_understanding_call_failed"
    
    return result


def detect_scene(
    scene_image_path: Optional[str] = None,
    seed_image_path: Optional[str] = None,
    message: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Detect scene from provided image paths.

    If xiaoyi-image-understanding skill is available, REAL image understanding
    is performed on the scene and/or seed images. Without it, we mark as
    needs_real_image_understanding_skill.
    """
    result = {
        "scene_image_found": False,
        "seed_image_found": False,
        "scene_summary": None,
        "scene_type": None,
        "visual_tags": [],
        "confidence": 0.0,
        "skill_status": "unknown",
        "implementation_status": "needs_real_image_understanding_skill",
        "image_understanding_result": None,
    }

    # Check scene_image_path
    scene_fp = _resolve_path(scene_image_path) if scene_image_path else None
    if scene_fp:
        result["scene_image_found"] = True
        result["visual_tags"].append("scene_image_provided")
    
    # Check seed_image_path
    seed_fp = _resolve_path(seed_image_path) if seed_image_path else None
    if seed_fp:
        result["seed_image_found"] = True
        result["visual_tags"].append("seed_image_provided")

    # Check if real image understanding skill exists
    scripts_dir = _get_skill_script_dir()
    skill_found = scripts_dir is not None

    if skill_found:
        result["skill_status"] = "available"
        
        # Try to understand images — prefer scene_image over seed_image
        image_to_understand = None
        if scene_fp:
            image_to_understand = str(scene_fp)
        elif seed_fp:
            image_to_understand = str(seed_fp)
        
        if image_to_understand:
            iu_result = _real_image_understanding(image_to_understand)
            result["image_understanding_result"] = iu_result
            
            if iu_result.get("success"):
                caption = iu_result.get("caption", "")
                result["scene_summary"] = caption
                result["implementation_status"] = "image_understanding_succeeded"
                # Extract visual tags from caption (simple keyword detection)
                caption_lower = caption.lower()
                tags = []
                if scene_fp:
                    tags.append("scene_understood")
                if "fox" in caption_lower or "fox" in caption_lower:
                    tags.append("fox_detected")
                if "cyber" in caption_lower or "robot" in caption_lower or "data" in caption_lower:
                    tags.append("cyber_theme")
                if "blue" in caption_lower or "purple" in caption_lower or "silver" in caption_lower:
                    tags.append("cool_tone")
                if "gold" in caption_lower or "warm" in caption_lower:
                    tags.append("warm_tone")
                result["visual_tags"].extend(tags)
            else:
                result["implementation_status"] = iu_result.get("implementation_status", "image_understanding_call_failed")
                result["scene_summary"] = f"IMAGE_UNDERSTANDING_FAILED: {iu_result.get('error', 'unknown')}"
        else:
            result["implementation_status"] = "skill_available_but_no_image_to_understand"
    else:
        result["skill_status"] = "missing"
        result["implementation_status"] = "needs_real_image_understanding_skill"
        result["scene_summary"] = "NO_REAL_IMAGE_UNDERSTANDING: skill xiaoyi-image-understanding not found in current package"

    # Determine scene_type and confidence based on images available
    if result["scene_image_found"] and result["seed_image_found"]:
        result["scene_type"] = "image_to_image"
        result["confidence"] = 0.85
    elif result["scene_image_found"]:
        result["scene_type"] = "image_only"
        result["confidence"] = 0.60
    elif result["seed_image_found"]:
        result["scene_type"] = "seed_only"
        result["confidence"] = 0.40
    else:
        result["scene_type"] = "text_only"
        result["confidence"] = 0.30

    return result


__all__ = ["detect_scene", "IMAGE_EXTENSIONS"]
