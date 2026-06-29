---
scene_id: professional_dev
scene_name: professional_dev
is_preset: 1
related_cats: []
source_l2_ids: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 17, 18, 19, 20, 21, "+50 more"]
fact_count: 70
updated_at_ms: 1782747667975
version: 35
source_sig: 63796ac9305379f8
source_watermark: 84
summary: 用户无法访问 OpenAI 官方网站，OpenAI 网站已不提供服务或无法访问。用户询问如何配置 OpenAI 的嵌入 API，并提出了一个方案：设置环境变量 `OPENAIAPIKEY`，条件是用户自己拥有 OpenAI key。该方案（方案 2）被确认成功。
---

## OpenAI 替代方案与 Gitee AI 集成

用户无法访问 OpenAI 官方网站，OpenAI 网站已不提供服务或无法访问。用户询问如何配置 OpenAI 的嵌入 API，并提出了一个方案：设置环境变量 `OPENAIAPIKEY`，条件是用户自己拥有 OpenAI key。该方案（方案 2）被确认成功。

用户提供了 Gitee Serverless API 链接 `https://ai.gitee.com/serverless-api/packages/1492?namespace=qqszkwqd&model=Qwen3.5-35B-A3B&package=1492`，询问能否使用该链接，并表达了使用的意图。用户提供了一个使用 Gitee Serverless API 的 Python SDK 代码示例，包含 `base_url=https://ai.gitee.com/v1` 和默认请求头 `{X-Failover-Enabled: true}`，模型为 `Qwen3.5-35B-A3B`，支持流式输出、思考链（`reasoning_content`）和图像理解功能。API Token 通过环境变量 `API_TOKEN` 读取，若未设置则抛出 `RuntimeError`。图片 URL 使用 Gitee AI 示例图片：`https://gitee-ai.su.bcebos.com/samples/images/doc_markdown.png`。用户确认代码示例中使用的模型是 Qwen3.5-35B-A3B，但质疑实际不是该模型。之后用户要求将模型换成 `Qwen3-Embedding-8B`（1024 维）进行尝试，并询问该模型是否免费体验 100 次（链接 `https://ai.gitee.com/hf-models/Qwen/Qwen3-Embedding-8B/tree/main`）。用户还提供了 API Token：`0BUJMJH1AJWJ6NVC24IQY1DUSEY61HZREFLG8QI8`。

用户正在对记忆系统进行端到端测试：保存一条关于“小艺 Claw 成功对接了 Gitee AI 的 bge-large-zh-v1.5 embedding 模型，替代 OpenAI 方案，国内可直接访问”的记忆，然后搜索关键词“Gitee AI embedding 替代方案”来验证向量搜索是否正常，但测试超时了。用户询问 `yaoyao-memory v4.0.1` 和 `yaoyao-memory v1.9.2` 是否可以互补，并需要安装 `sqlite-vec`。用户正在尝试将二者互补，采用方案二——由 celia 主导、yaoyao 补充，并需要开启 celiaBridge。用户反复确认重启和方案二互补是否成功。

## 系统重启与工作流状态

用户于 2026-06-28 询问系统是否重启成功，助手未回复，重启结果未知。用户确认需要验证重启结果。

用户查看工作流运行 `https://github.com/xkl0305/xiaoyiCIaw/actions/runs/28327609308`，询问是否跑完。用户还询问 `https://github.com/xkl0305/xiaoyiCIaw/actions/runs/28340893569` 的内容，要求查看和修复。

## 仓库与配置管理

用户指出助手应该拥有三个仓库，但助手似乎忘记了。用户对助手表达了不满或质疑，认为助手忘记了之前讨论或约定的内容，并询问助手是否还会遗忘信息。用户还询问助手是否有分身。

用户提供了以下仓库和令牌信息：
- 完整源码加配置仓库：`https://cnb.cool/cnb.cAmPIufcgKA/xiaoyiCIaw`，用户确认该仓库是助手（系统自身）的仓库。
- 用户确认 GitHub 仓库 `https://github.com/xkl0305/xiaoyiCIaw` 是用户自己的仓库。
- Gitee 仓库 `https://gitee.com/starry-sky-love/xiaoyi-claw-backup2` 需要修改，指定 Gitee 为同步目标。用户确认方案 A（推荐）：使用 Gitee 个人访问令牌。
- Gitee 个人访问令牌最初为 `3614af49c8fa3e764d2c17f6902e07f6`，后更新为 `ff044a303bbb61d92f72a3c770e25bdb`。
- GitHub 个人访问令牌：`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`，用户确认为自己的令牌。用户要求令牌必须以 `github_pat_` 开头且具有 repo 权限。
- 用户还提供了新的访问令牌：`Token:3Iqr105fqnIuf6PiyV7HDnQNYGG`
- 用户确认从链接 `https://cnb.cool/profile/token` 获取的令牌没有问题。
- 用户询问 cnb.cool 是否需要新的凭证，并提供了 cnb.cool 的 Token：`3Iqr105fqnIuf6PiyV7HDnQNYGG`。
- 用户询问 Gitee 是否需要 Personal Access Token。

用户要求推送三个仓库，并在 2026-06-28 请求助手“试一下”（具体内容未明确），要求同时推送三个仓库。

## 私有配置与安装

用户于 2026-06-28 23:45 要求通过环境变量 `CNB_PRIVATE_WORKSPACE` 链接私有配置。私有配置已链接到工作区，用户最初发现只有 4 个文件，后来变成 16 个，要求查看这 16 个文件分别是什么。用户询问私有配置链接到工作区后是否只有四个（项）。

用户要求更新私有配置仓库（`https://cnb.cool/llm-memory-integrat/llm`），确认该仓库的版本号已提交。用户注意到该仓库中的 .md 文件命名方式与原来不同，不再是 `MEMORY.md` 这样的格式，询问为何不是此格式，并询问仓库中有哪些 .md 文件。

用户上传了压缩包 `/tmp/xy_channel/1782689308256_llm-memory-integration-9.0.1.zip` 并要求安装。用户要求安装仓库 `https://cnb.cool/Crusheart_Studio/Crusheart-AutoBrain-Turbo`。

用户提供了 `yaoyao-plugin` 的 GitHub 仓库地址：`https://cnb.cool/TIAMO.xianyao/yaoyao-plugin`，并想知道是否有新版本需要安装。

## 其他

用户在系统配置中需要使用（或询问）常见场景的配置方法。用户询问助手的底层架构。