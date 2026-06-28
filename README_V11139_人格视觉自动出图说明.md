# V111.39 人格视觉自动出图覆盖包

## 这次已做好的核心项
1. **龙虾/助手输出优先自动触发**
   - 触发源优先级：`lobster_message -> assistant_message -> reply_text -> final_reply -> user_message`
   - 不再依赖你手动说“出图”关键词才触发。

2. **自动出图已打开**
   - `openclaw.json -> personaVisual.autoGenerate = true`
   - `generationConsentMode = auto_with_budget`
   - 适合“高功能情感 AI”风格的高频人格图。

3. **情感表达与场景应用增强**
   - 新增/增强：陪伴、安抚、轻偷看、俏皮、庆祝、成功确认、松一口气、认真倾听、温柔思考、害羞、疲惫、好奇、紧张等。
   - 自动给出更自然的表情提示、动作提示、场景提示。

4. **提示词自然化**
   - 自动出图桥接器现在会调用 `visual_persona_renderer.build_visual_prompt()`，把 mood / scene / expression / body state / background / camera 一起融合进去。
   - 出图结果比之前更像“有情绪、有动作、有场景”的人格图，而不是机械标签图。

5. **回复链路真实接入**
   - `ResponseRenderer.to_user_message()` 已接 `finalize_visible_reply()`。
   - `sitecustomize.py` 已加自动安装。
   - `mainline_bootstrap.enable()` 已补齐，可直接开启 hooks。

6. **衣柜自动切装优化**
   - 自动模式下默认屏蔽 `bikini` / `silver_bikini` 这类不适合高频自动人格图的衣装。
   - 自动优先按 `scene -> mood -> current_outfit` 选装，更自然。

## 你怎么覆盖
直接把压缩包解压到项目根目录覆盖同名文件即可。

## 建议执行
```bash
python scripts/mainline_bootstrap.py --enable
python scripts/mainline_bootstrap.py --probe
```

## 本次验证
已通过：
- `tests/test_persona_visual_v111_30.py`
- `tests/test_persona_visual_hook_activation_v111_31.py`
- `tests/test_persona_visual_reply_outlet_v111_32.py`
- `tests/test_persona_visual_v111_34_direct.py`