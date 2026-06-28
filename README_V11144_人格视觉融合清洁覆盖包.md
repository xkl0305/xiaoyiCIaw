# V111.44 人格视觉融合清洁覆盖包

## 本包解决的问题
1. noskills 包缺 Seedream 执行器：新增 `memory_context/persona_runtime/providers/seedream_provider.py`，真实生图不再强依赖 `skills/`；同时保留 `skills.seedream_image_gen` 兼容 shim。
2. hooks 没内置：覆盖包直接包含 `.openclaw/hooks/pre_reply.py`、`post_reply.py`、`manifest.json`、`enabled`，并提供 apply 脚本自动 enable。
3. “偷偷看看你”误判为 `dynamic:你`：修复为偷看场景，不触发焦点二次图。
4. 去重早于焦点识别：post_reply 改为先解析 focus/outfit，再计算 dedupe key。
5. 一轮图片数量冲突：无焦点最多 1 张，有明确焦点请求最多 2 张。
6. 新衣柜没有完全融合：`moonfeather_robe`、`stardust_dream` 已接入 wardrobe profile、scene map、mood map。
7. 当前穿搭污染源码包：`current_outfit` 改存 `.persona_visual/runtime_wardrobe_state.json`，静态 `outfit_config.json` 不再携带运行态。
8. TOOLS.md 口径更新到 V111.44。

## 覆盖命令
```bash
unzip -o dalongxia_v11144_persona_visual_fusion_clean_overlay.zip -d /你的项目根目录
cd /你的项目根目录
PYTHONPATH=. python scripts/apply_v111_44_persona_visual_fusion_patch.py
```

## 验收命令
```bash
PYTHONPATH=. python scripts/audit_persona_visual_v111_44.py
PYTHONPATH=. pytest -q   tests/test_persona_visual_v111_44.py   tests/test_persona_visual_v111_43.py   tests/test_persona_visual_v111_42.py   tests/test_persona_visual_cross_outlet_dedupe_v111_41.py   tests/test_persona_visual_no_duplicate_v111_40.py
PYTHONPATH=. python scripts/mainline_bootstrap.py --probe
```

## 真实生图配置
要真实调用 Seedream，需要环境变量：
```bash
export SEEDREAM_API_URL="你的生成接口"
export SEEDREAM_API_KEY="你的key"
```
兼容：`SERVICE_URL`、`PERSONAL_API_KEY`、`PERSONAL-API-KEY`。
没有 key 时返回 `provider_not_ready`，不是触发链路失效。
