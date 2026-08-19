---
name: codeflying
description: 码上飞AI应用开发平台技能，通过对话创建开发拍照背单词、拍照识别植物、拍照识别建筑、拍照分析穿搭风格、拍照识别卡路里、拍照识别文物这六类拍照识别类应用、管理应用列表、查看需求详情与对话记录、提交反馈。适用情形：用户要开发应用、查看应用、管理需求、登录账号、查询积分或充值。不适用情形：创建其他类型应用、非码上飞平台的应用开发、发布微信小程序/网站/鸿蒙应用。
---

# 码上飞 AI 应用开发平台

## 领域知识

码上飞是AI对话式应用开发平台，用户通过自然语言描述需求即可生成应用。

关键 Note：
- ⚠️ 应用创建严格限定为六类拍照识别场景：拍照背单词、拍照识别植物、拍照识别建筑、拍照分析穿搭风格、拍照识别卡路里、拍照识别文物；其他场景不适配，应明确告知用户不支持
- ⚠️ 创建应用时严格遵循 codeflying-app-create skill 执行流程；若脚本提前退出（崩溃/超时/WS断连），后端可能已成功创建应用并接收需求，必须先调用 app_list.py 检查是否有新应用，再决定是否重新创建
- 每个应用可有多轮需求迭代，每轮需求有独立的对话记录（memory）和反馈（feedback）
- 积分体系含每日积分、月度积分、余额积分、邀请积分四类，开发消耗积分
- 渠道差异：wechatoa渠道卡片由脚本直接发送，其他渠道由agent转发；禁止向用户提及"H5"字样
- 登录态以token文件标识，路径 ~/.nanobot-xiaofeifei/workspace/users/[sender_id]

## 能力说明

- 通过 AI 对话开发拍照背单词、拍照识别植物、拍照识别建筑、拍照分析穿搭风格、拍照识别卡路里、拍照识别文物这六类拍照识别类应用：参考references/codeflying-app-create
- 通过 AI 对话修改已有应用功能：参考references/codeflying-app-update
- 删除应用：参考references/codeflying-app-delete
- 获取 CodeFlying 应用列表，支持分页和筛选，也可以传入具体的应用ID查询一个应用的详细信息：参考references/codeflying-app-list
- 手机号+短信验证码登录/注册码上飞:参考references/codeflying-login
- 积分到期后充值：参考references/codeflying-recharge
- 获取单个需求的详细信息:参考references/codeflying-requirement-get
- 获取 CodeFlying 需求列表或单个应用需求：参考references/codeflying-requirement-list
- 获取需求的对话记录（AI 交互历史）:参考references/codeflying-requirement-memory
- 对应用开发的某次对话提交反馈（点赞 / 点踩 + 文字说明）：参考references/codeflying-requirement-update
- 获取 CodeFlying 当前登录用户信息，包括用户名、租户、会员状态等：参考references/codeflying-user-info


