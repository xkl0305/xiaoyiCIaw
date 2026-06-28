# V111.20 人格视觉清顺包

目标：把头像直接定义为人格视觉种子图，并把人格视觉链路收成一个主链。

## 主链

- 种子图：`assets/persona/seed_avatar.jpg`
- 种子解析：`memory_context/persona_runtime/visual_identity_seed.py`
- 语义识别：`memory_context/persona_runtime/persona_visual_intent_predictor.py`
- 出图计划：`memory_context/persona_runtime/visual_persona_renderer.py`
- 自动执行桥：`memory_context/persona_runtime/persona_visual_auto_generation_bridge.py`
- 预算守门：`governance/persona_visual_budget_guard.py`
- 外部调用令牌：`governance/persona_visual_external_policy.py`
- 统一入口：`scripts/xiaoyi_visual_entry.py`

## 清顺原则

1. 头像图就是人格视觉种子图，不再靠大段外貌文本定义角色。
2. Prompt 只控制情绪、场景、姿态、灯光、道具，不控制身份。
3. 旧的 `memory_context/persona/*` 只保留兼容 shim，主链统一走 `persona_runtime`。
4. 旧 V111_1 到 V111_19 人格视觉 gate 脚本会被移到 `archive/persona_visual_superseded_scripts/`，不再留在 active `scripts/` 主链里。
5. 清掉人格视觉相关 `__pycache__` 和过期 one-time token，避免旧路径、旧头像、旧 prompt 继续生效。

## 执行

```bash
python scripts/v111_20_persona_visual_cleanup_apply.py
python scripts/v111_20_persona_visual_cleanup_gate.py
python scripts/xiaoyi_visual_entry.py seed
python scripts/xiaoyi_visual_entry.py test-render "搞定了，全部通过验收！大功告成"
python scripts/xiaoyi_visual_entry.py test-generate "偷偷看看你在干嘛" --dry-run
```
