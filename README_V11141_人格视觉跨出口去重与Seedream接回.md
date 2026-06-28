# V111.41 人格视觉跨出口去重与 Seedream 接回覆盖包

## 修复点

1. 跨出口去重：`post_reply`、`reply_outlet`、`event_adapter` 即使携带不同 `request_id`，同一句回复 + 同一 mood + 同一 semantic_scene 也只允许一次视觉输出。
2. 兼容旧接口：`observe_turn()` 恢复顶层 `mood / semantic_scene / auto_generation_candidate`；`render_plan()` 恢复 `purpose / visual_scope / generic_image_generation`。
3. Seedream 能力接回：补回 `skills/seedream_image_gen` 与 `skills/seedream-image-gen`。支持两种运行模式：
   - 直接模式：`SEEDREAM_API_URL` 或 `SEEDREAM_GENERATOR_URL` + `SEEDREAM_API_KEY` / `ARK_API_KEY` / `VOLCENGINE_API_KEY`
   - 小艺模式：`~/.openclaw/.xiaoyienv` 内包含 `SERVICE_URL`、`PERSONAL-API-KEY`、`PERSONAL-UID`
4. 默认图仍为手动兜底：`scene_default_config.json.auto_image_send=false`，不会再用默认图冒充实时生成。

## 覆盖后验证

```bash
cd /你的项目根目录
PYTHONPATH=. python scripts/mainline_bootstrap.py --enable
PYTHONPATH=. python scripts/audit_persona_visual_v111_41.py
PYTHONPATH=. pytest -q tests/test_persona_visual_cross_outlet_dedupe_v111_41.py tests/test_persona_visual_no_duplicate_v111_40.py
```

## 真实生图必需条件

如果审计里 `seedream_provider_module_installed=true` 但 `real_generation_ready=false`，说明代码已接回，但凭证/端点没配好。至少满足下面二选一：

```bash
export SEEDREAM_API_URL="你的Seedream生成端点"
export SEEDREAM_API_KEY="你的key"
```

或：

```text
~/.openclaw/.xiaoyienv
SERVICE_URL=...
PERSONAL-API-KEY=...
PERSONAL-UID=...
```
