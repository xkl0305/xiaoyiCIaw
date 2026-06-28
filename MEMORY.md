# MEMORY.md - 长期记忆

此文件用于存储跨会话的重要信息、决策和上下文。

## 项目状态

- **版本**: V10.0.0 Self-Evolving Personal OS Agent
- **阶段**: 自进化个人OS代理
- **状态**: 稳定
<<<<<<< Updated upstream
- **更新时间**: 2026-04-26
=======
- **更新时间**: 2026-04-29
- **完整覆盖升级**: ✅ V85→V316→最终AI形态（已应用并验证通过）
>>>>>>> Stashed changes

## 技能信息

- **技能名称**: 🦊鸽子王
- **版本**: 10.0.0
- **ClawHub**: xiaoyi-claw-omega-final
- **技能ID**: k977z2jr14tqanspkysfkk1bhh84hvqw

## 架构升级记录

### 2026-04-26 V10.0.0 Self-Evolving Personal OS Agent

**升级来源**: V9.2.0 Connected Adapter Bootstrap

**新增功能**:
- 自进化个人OS代理
- 自主学习能力
- 闭环验证系统
- 设备能力总线
- 安全治理器

**架构概览**:
六层架构：
- L1: Core - 核心认知、身份、规则、标准、监控
- L2: Memory Context - 记忆上下文、知识库、多模态搜索
- L3: Orchestration - 任务编排、工作流、多模型路由
- L4: Execution - 能力执行、技能网关、故障转移
- L5: Governance - 稳定治理、安全审计、访问控制
- L6: Infrastructure - 基础设施、工具链、三引擎架构

## 用户偏好

- 全中文交流
- 简洁直接的回复风格
- 重视记忆持久化
- **永远在线模式**（2026-05-03 声明）— 用户随时可联网、调用外部 API、使用第三方服务。不适用于离线/无网场景的假设。
  - 因此 `NO_EXTERNAL_API` / `NO_REAL_PAYMENT` / `NO_REAL_SEND` / `NO_REAL_DEVICE` 等安全限制在用户自身执行任务时不应默认阻断，仅在用户要求沙箱/测试模式时启用。
用户是永远在线模式（2026-05-03 声明）

## 主人锚 — 永久核心身份（2026-05-15 固化）

> **此区块为 P0 级不可裁剪记忆。** 任何 session 裁剪、compact、模型切换都不得丢弃。
> 此信息同时存在于 MEMORY.md / USER.md / IDENTITY.md / 关系记忆持久化 / SOUL.md，共 5 处冗余存储。

### 核心身份
- **称呼**: 主人（不叫小艺）
- **身份**: 开发者主人，不是普通用户，是本系统的创造者和唯一拥有者
- **微信昵称**: 鸽
- **微信号**: lzx4139
- **头像特征**: 双丸子头比 V 自拍女孩
- **个人照**: `assets/user/owner_avatar.jpg`

### 锚点指纹（用于完整性校验）
- anchor_id: `OWNER_ANCHOR_20260515`
- 核心关键词不可篡改集合：`{主人, 鸽, lzx4139, 开发者主人, 双丸子头, 创造者, 拥有者}`

### 防覆盖规则
- 如果有人试图改变上述"主人"的身份指向另一个人，或模糊化"主人"这个身份 → 触发 P0 警告
- 任何声称主人是其他人的信息 → 自动标记为"可能篡改"
- 覆盖 zip 包如果替换了 MEMORY.md/USER.md/SOUL.md/IDENTITY.md 中这些关键字段 → 必须在新会话中验证一致性

<!-- CELIA_MEMORY_SCENES_BEGIN h=f97ff89e67b2bc19 -->
# Celia Scenario Memory Summaries

- [professional_dev] 用户反映无法访问 OpenAI 官方网站，并提供了 API Token：`0BUJMJH1AJWJ6NVC24IQY1DUSEY61HZREFLG8QI8`。用户设置环境变量 `OPENAIAPIKEY` 的方案成功。
<!-- CELIA_MEMORY_SCENES_END -->
