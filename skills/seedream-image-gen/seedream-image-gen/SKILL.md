# Seedream Image Generation Skill (Huawei Cloud)

Provider-backed skill bridge for Xiaoyi image generation via Huawei Cloud.

## Canonical ID

`seedream-image-gen`

## Execution

Use `python skills/seedream-image-gen/skill.py --prompt "..." --input-image path/to/image.jpg --dry-run` for diagnostics, or omit `--dry-run` for real provider calls.

The skill calls `memory_context.persona_runtime.providers.huawei_provider.*` (Huawei Cloud channel) and reads credentials from:

- `SERVICE_URL` (default: `celia-claw-drcn.ai.dbankcloud.cn`)
- `PERSONAL_API_KEY` / `PERSONAL-API-KEY`
- `PERSONAL_UID` / `PERSONAL-UID`
- or `~/.openclaw/.xiaoyienv`

## Safety

This skill is provider-backed. It does not silently fall back to generic image generation.
