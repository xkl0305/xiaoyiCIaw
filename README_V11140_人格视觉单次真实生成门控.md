# V111.40 人格视觉单次真实生成门控覆盖包

## 修复的问题
1. 之前 `pre_reply + post_reply + reply_outlet` 多链路都会触发，导致同一轮回复一次性发多张重复图。
2. `scene_default_config.json` 默认图被设置成自动优先发送，导致看起来像“发图了”，实际不是 Seedream 实时生图。
3. 没有 dedupe gate，同一句“搞定了/偷偷看”等可能被多次派发。

## 本版策略
- `pre_reply`：只检测情绪和场景，不生成、不发图。
- `post_reply`：唯一允许生成的阶段。
- `persona_visual_dedupe_gate`：同一文本/同一 mood/scene 在 45 秒内只允许一次图像输出。
- `scene_default_config.auto_image_send=false`：默认图只作为手动兜底预览，不再自动连发。
- Seedream 可用时真实生成；缺 `SEEDREAM_API_KEY` 时返回 `provider_not_ready`，不冒充已生图。

## 覆盖后命令
```bash
python scripts/mainline_bootstrap.py --enable
PYTHONPATH=. python scripts/audit_persona_visual_v111_40.py
PYTHONPATH=. pytest -q tests/test_persona_visual_no_duplicate_v111_40.py
```

## 真实生图前提
如果运行环境没有 `SEEDREAM_API_KEY`，系统不会真实生图，只会返回 `provider_not_ready` 或 `dry_run_ready`。这不是触发失败，是生图 provider 没就绪。