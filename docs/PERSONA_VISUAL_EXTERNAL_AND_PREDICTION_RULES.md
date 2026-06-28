# V111.2/V111.3 Persona Visual External Approval + Prediction Rules

- 默认只生成 visual summary / render plan / prompt draft，不调用外部图片 API。
- 禁止全局关闭 `NO_EXTERNAL_API`。
- 只有用户明确要求生成图片，或用户显式开启自动出图且通过预算/冷却/置信度守卫，才可以申请一次性视觉生成 token。
- token 只能用于 `seedream-image-gen`，purpose 必须是 `persona_visualization`。
- token 使用一次后立即失效。
- webhook、model call、git push、curl/wget、email、payment、device 仍然被阻断。
- mainline_hook 只能加载轻量预测摘要，不能直接调用 Seedream。
