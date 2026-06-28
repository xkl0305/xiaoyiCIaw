# V111.43 人格视觉通用焦点识别覆盖包

## 解决的问题
V111.42 里“看看腿 / 摸摸头 / 看腰”只是写死的示例。V111.43 改成通用焦点意图解析：用户说“看看X / 给我看X / 来张X / 拍张X / 摆个X / 比个X / 摸摸X / X给我看看”等，都能把 X 提取为焦点目标，并生成第二张焦点图规划。

## 核心改动
1. 新增 `memory_context/persona_runtime/persona_visual_focus_intent.py`
   - 统一解析焦点请求。
   - 内置常见焦点：腿、尾巴、耳朵、头发、眼睛、手势、摸头、腰、衣服/裙摆/披风/饰品、鞋、翅膀、pose、脸/表情。
   - 对未知焦点走动态提取：如“看看铃铛”“看看项链细节”“看看尾巴尖”都会生成 `dynamic:<目标>` 或映射到对应焦点。
   - 对敏感焦点自动安全改写或自动阻断，不让自动人格图走露骨方向。

2. 更新 `persona_visual_auto_generation_bridge.py`
   - 不再只识别腿/摸头/腰。
   - 现在会调用通用焦点解析器。
   - 龙虾回复括号里的动作描述继续进入 stage direction prompt。
   - 如果检测到焦点，会规划 `secondary_generation`。

3. 保留 V111.42 的修复
   - 衣柜中文衣装识别与 current_outfit 持久化。
   - 去重 key 不依赖 request_id。
   - mainline_hook 不再直接生成，统一委托 post_reply hook。
   - Seedream provider 适配器。

## 覆盖命令
```bash
unzip -o dalongxia_v11143_persona_visual_universal_focus_overlay.zip -d /你的项目根目录
cd /你的项目根目录
python scripts/mainline_bootstrap.py --enable
pytest -q tests/test_persona_visual_v111_43.py tests/test_persona_visual_v111_42.py tests/test_persona_visual_no_duplicate_v111_40.py
python scripts/mainline_bootstrap.py --probe
```

## 真实生图前提
必须配置以下之一：
```bash
export SEEDREAM_API_URL="你的生成接口"
export SEEDREAM_API_KEY="你的key"
```
或：
```bash
export SERVICE_URL="你的生成接口"
export PERSONAL_API_KEY="你的key"
```
没有 key 时系统会返回 `provider_not_ready` 或 `dry_run_ready`，不会假装已经生成。
