# V111.43 Full Merged 人格视觉总覆盖包

这个包是 41 + 42 + 43 的合并版，覆盖顺序为：

1. V111.41：跨出口去重 + Seedream 执行器接回 + 旧接口兼容
2. V111.42：衣柜真实切换 + 括号动作入 prompt + 焦点二次生成 + mainline 只预测、post_reply 统一生成
3. V111.43：通用焦点识别，不再只支持“看看腿”，支持“看看X / 拍张X / 摆个X / 摸摸X / X来一张”等结构

## 解决的问题

- 43 单包不一定完整包含 41 的底座问题。
- 换衣柜里的衣服没有真实切换。
- “看看腿”这类只是示例，现在换成通用“看看X”识别。
- 龙虾回复括号里的动作/状态直接进入生成提示词。
- pre_reply / post_reply / reply_outlet 多出口重复发图。
- workspace_light 缺 Seedream 真实执行器。

## 覆盖方法

```bash
unzip -o dalongxia_v11143_full_merged_persona_visual_overlay.zip -d /你的项目根目录
cd /你的项目根目录
python scripts/mainline_bootstrap.py --enable
```

## 验收命令

```bash
PYTHONPATH=. pytest -q \
  tests/test_persona_visual_cross_outlet_dedupe_v111_41.py \
  tests/test_persona_visual_v111_42.py \
  tests/test_persona_visual_v111_43.py \
  tests/test_persona_visual_no_duplicate_v111_40.py

PYTHONPATH=. python scripts/audit_persona_visual_v111_41.py
PYTHONPATH=. python scripts/mainline_bootstrap.py --probe
```

## 真实生图配置

有 Seedream 配置才会真实生成：

```bash
export SEEDREAM_API_URL="你的生成接口"
export SEEDREAM_API_KEY="你的key"
```

或者兼容：

```bash
export SERVICE_URL="你的生成接口"
export PERSONAL_API_KEY="你的key"
export PERSONAL_UID="你的uid"
```

没有 key 时系统会正常触发、生成 prompt 和计划，但返回 provider_not_ready / dry_run_ready，不会假装已经生成。
