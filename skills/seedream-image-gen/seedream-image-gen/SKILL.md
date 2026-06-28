# Seedream 5.0 Image Generation Skill

Provider-backed skill bridge for Seedream 5.0 image-to-image generation.

## Canonical ID

`seedream-image-gen`

## Execution

Use `python skills/seedream-image-gen/skill.py --prompt "..." --input-image path/to/image.jpg --dry-run` for diagnostics, or omit `--dry-run` for real provider calls.

The skill calls `memory_context.persona_runtime.providers.seedream_provider.generate_image` and therefore shares the same provider configuration:

- `SEEDREAM_API_URL`
- `SEEDREAM_API_KEY`
- `PERSONAL_UID` optional
- or `~/.openclaw/.xiaoyienv`

## Safety

This skill is provider-backed. It does not silently fall back to generic image generation.
