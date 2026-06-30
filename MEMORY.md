- **当前方案**: A️⃣ yaoyao 主导（2026-06-30 切换）
- **插件**: yaoyao-memory v1.9.2 | **hooks**: capture(async+vector) + recall(hybrid+vector)
- **技能**: yaoyao-memory v4.0.1 | `skills/yaoyao-memory/`（管理 CLI + dashboard）
- **嵌入**: Gitee AI / text-embedding / 1024d
- **DB**: ~/.openclaw/memory/main.sqlite（共享表）
- **celia 状态**: disabled（db 保留未删）

### 回退到 B / celia 主导

改 `~/.openclaw/openclaw.json` 三处后重启：

1. `plugins.slots.memory` → `"memory-celia"`
2. `plugins.entries.memory-celia.enabled` → `true`，加回 hooks + config
3. `plugins.entries.yaoyao-memory.config` → 恢复 celiaBridge 模式

重启: `python3 -m supervisor.supervisorctl restart openclaw-gateway`

<!-- CELIA_MEMORY_SCENES_BEGIN h=c222d1c3d95c716f -->
# Celia Scenario Memory Summaries

- [professional_dev] 用户在 2026-06-28 询问系统是否重启成功，但助手未回复，重启结果未知。用户确认需要验证重启结果。用户反复确认重启是否成功。用户曾询问系统是否卡住了，并再次确认重启是否成功。用户多次询问灵枢AutoBrain v7.0.0的运行情况。
- [emergent_scn-DR0000019F1494132E00000001-3] 在令牌同步场景中，用户指定 Gitee 作为同步目标，并提供了 Gitee 与 GitHub 两个平台的个人访问令牌。用户确认需要修改指定的 Gitee 仓库，并采纳了使用 Gitee 令牌的方案A，过程中还询问了助手是否具有分身能力。
- [emergent_scn-DR0000019F1494132E00000001-1] 用户在与系统交互过程中，提供了多个用于接口调用的关键信息，主要围绕 Gitee 和 GitHub 两大平台的 Personal Access Token 及 API 连接配置。用户希望使用 Gitee 的 Serverless API 来替代 OpenAI 接口，并给出了相应的链接、代码示例及 Token。
- [emergent_scn-DR0000019F1494132E00000001-0] 用户确认通过设置环境变量（方案2）成功配置了环境，并安装了指定的附件包。在此过程中，用户提出了关于模型免费体验、仓库推送以及私有配置链接工作区后结果数量的相关问题。
- [emergent_scn-DR0000019F1494132E00000001-2] 用户针对私有配置仓库（https://cnb.cool/llm-memory-integrat/llm）中的 .md 文件命名方式提出疑问，指出其与原有的 MEMORY.md 格式不同。用户要求更新该私有配置仓库，并确认了相关版本号的提交。此外，用户还提供了完整源码与配置所在的另一仓库链接。
<!-- CELIA_MEMORY_SCENES_END -->
