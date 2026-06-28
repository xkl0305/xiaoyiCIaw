# Persona Visual Seed Avatar Policy

V111.1 fixes the seed-avatar issue. The visual persona layer must use the user-assigned first avatar as the identity reference. It must not silently replace that avatar with a random generated identity.

Canonical location:

- `assets/persona/seed_avatar.png` / `.jpg` / `.webp`

Fallback search locations:

- `.persona_visual/seed_avatar.*`
- `.persona_visual/avatar_seed.*`
- `memory_context/persona/assets/seed_avatar.*`
- `/tmp/xy_channel/*` when applying the patch, for user-uploaded avatar images

Rules:

1. Do not generate a fake seed avatar.
2. If the seed avatar is missing, report `seed_avatar_missing` and return a render plan only.
3. If the seed avatar exists, image generation drafts must use image-to-image mode.
4. Offline mode stays safe: `NO_EXTERNAL_API=true` returns a draft/render plan, not a real API call.
5. The avatar file is an asset, not a governance rule or execution module.
