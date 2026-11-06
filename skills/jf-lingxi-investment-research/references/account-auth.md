# 九方灵犀账号接入与交互说明

本说明介绍九方灵犀投资研究Skill的账号配置、授权交互及凭据处理要求。本服务由上海九方云智能科技有限公司提供；华为平台能力及接入要求以官方文档为准，业务接口、凭据格式与本地检查命令以本服务实现为准。

## 官方依据

- [Skill接入华为账号](https://developer.huawei.com/consumer/cn/doc/service/skill-huaweiidcount-0000002626985238)：授权管理、账号接口、SKILL.md账号声明及账号工具调用。
- [HarmonyOS Skill开发规范](https://developer.huawei.com/consumer/cn/doc/service/skill-development-standards-0000002592931546)：Skill名称、运行环境、目录及工具依赖。

## 应用与接口配置

| 配置 | 取值 |
|---|---|
| Skill名称 | `jf-lingxi-investment-research` |
| 华为 Web 应用名称 | 九方灵犀小艺账号服务 |
| APP ID | `101653523127265022` |
| OAuth Client ID | `119414417` |
| 账号API URL | `https://jf-lingxi-huawei-mcp-gw.techgp.cn/huawei/account` |
| 使用账号的域名 | `jf-lingxi-huawei-mcp-gw.techgp.cn` |
| MCP业务入口 | `https://jf-lingxi-huawei-mcp-gw.techgp.cn/huawei/mcp` |
| HTTPS业务入口 | `https://jf-lingxi-huawei-mcp-gw.techgp.cn/huawei/v1/skills/{tool_name}/analyze` |
| 业务请求头 | `login-token` |
| 运行环境 | `cloudSandbox`，Python 3.11及HTTPS访问能力 |
| 凭据来源 | `/home/sandbox/.openclaw/.xiaoyienv` |
| 本应用凭据字段 | `119414417_login_token`、`119414417_login_token_expire_time` |

账号API URL在小艺平台授权管理中配置，并将对应账号服务绑定到本Skill。账号API不是业务MCP入口，也不能直接等同于OAuth重定向地址。Client Secret及AK/SK只用于服务端与平台配置，不放入Skill包。

## 账号配置一致性要求

本Skill使用企业应用“九方灵犀小艺账号服务”完成账号授权，OAuth Client ID为 `119414417`。平台账号鉴权、Skill声明、客户端配置与服务端账号配置应保持一致。

1. Skill目录名、`SKILL.md` 的 `name`、客户端配置的 `skill_name` 及授权工具的 `skillName` 均为 `jf-lingxi-investment-research`。
2. `SKILL.md` 的凭据字段、`huawei_id_tool` 的 `clientId`、`client-config.json` 的 `client_id` 及服务端 `HUAWEI_CLIENT_ID` 使用同一应用的OAuth Client ID，不使用项目级客户端ID替代。
3. 平台为本Skill绑定对应的企业应用账号鉴权，并配置本说明所列的账号API URL及使用账号的域名。服务端 `HUAWEI_CLIENT_SECRET` 使用该应用OAuth Client ID配套的Client Secret。
4. 账号API的AK/SK用于平台与服务端之间的回调签名认证，与OAuth Client Secret用途不同；平台与服务端的回调凭据须一致，所有密钥均不得写入Skill包。
5. 获取手机号须具备对应应用的 `phone` 权限并取得用户授权；不同应用的权限不能相互替代。
6. 应用、账号鉴权绑定或接口配置变更后，应重新验证首次授权、凭据刷新、解绑及实际业务调用。

`phone` 是华为账号服务的应用级 scope，获取手机号前须完成对应权限申请及用户授权，详见[华为官方文档](https://developer.huawei.com/consumer/cn/doc/harmonyos-guides-v5/account-get-phonenumber-V5)。

保留包目录、SKILL.md的name、client-config.json的skill_name及账号工具skillName一致。导入后先执行 `python3 scripts/invoke.py info`，应返回 `package_version=1.0.0`、`name_consistent=true`。info是本包提供的离线检查命令，不读取账号凭据，不发网络请求。

## 用户交互流程

1. 用户在小艺中提出研究问题，Skill识别最匹配的一项研究能力；信息不足时先澄清。
2. 执行 `python3 scripts/invoke.py check-auth`，只检查本应用凭据与过期时间。
3. 若返回auth_required，说明需要授权，调用平台工具 `huawei_id_tool(clientId="119414417", skillName="jf-lingxi-investment-research")`。同一用户任务最多调用一次，等待工具实际完成。
4. 平台展示授权交互，用户选择同意或取消。展示卡片及用户口头确认均不代表工具成功；取消或工具失败时停止本次业务调用，不重复弹窗。
5. 工具明确成功后重新执行check-auth。仍缺少凭据时报告凭据未就绪并停止，不自行写入文件或推测Token。
6. 凭据可用后调用选定研究工具。请求头携带login-token，同一请求重试复用请求编号；业务成功后原文返回answer_markdown，不生成HTML。

MCP客户端按initialize、notifications/initialized、tools/call顺序交互。HTTPS客户端使用对应工具的analyze入口。一次研究只调用一个工具，最长约300秒；没有实际结果时不宣称完成。

## 平台与服务端职责

```text
Skill调用huawei_id_tool → 用户同意
→ 小艺平台请求账号API authorize
→ 上海九方云智能科技有限公司服务端验证请求、用authCode换取华为凭据并获取手机号
→ 服务端生成业务身份及登录凭据，返回账号响应
→ 平台完成凭据处理 → Skill重新check-auth
→ MCP或HTTPS业务调用 → 返回研究正文
```

账号API采用JSON-RPC，支持authorize、refreshToken、deauthorize。authorize在params.message.parts[].data中接收authCode和clientId。平台与账号API间使用AK/SK认证，请求头为accessKey、sign、ts，按官方HMAC-SHA256及Base64规则处理。

账号响应包含业务loginToken、loginRefreshToken及各自有效期。Skill脚本不代替平台发起authorize，也不持有华为OAuth Client Secret或账号API的AK/SK。

## 凭据及失败处理

- 仅读取本Client ID对应字段，不读取或展示其他应用凭据。支持JSON对象及key=value文本解析，不执行文件内容。
- 本服务业务Token格式为hw_at_前缀加64位字母、数字、下划线或短横线；有效期为带时区ISO 8601时间。这是上海九方云智能科技有限公司服务端约定，不是华为所有应用的通用格式。
- `credential_missing`：未读到本应用凭据；不能仅据此定位为签发或平台写入失败。
- `expiry_invalid`：有效期格式无法解析；停止调用，不把Token非空视为有效。
- 本地authorized只代表本地检查通过；服务端仍可能因凭据撤销等原因返回401。
- 业务401且本任务尚未调用账号工具时，允许刷新一次并重试一次。首次授权与刷新共用一次预算。网络超时、409、5xx不自动触发授权或重新提交研究。
- 日志及回答不输出Token、手机号、authCode、签名或完整凭据文件。故障反馈仅提供时间、Skill名、Client ID、工具错误、status/reason、请求编号及HTTP状态。
- 账号工具超时仅代表未及时取得结果，不能单凭超时确定手机、平台、网络或账号API哪一环节失败。
- Skill名称、Client ID、账号API URL、使用账号的域名或平台账号服务绑定发生变化时，重新完成一次真机授权及业务调用回归；配置未变化时，不在日常业务请求中重复执行发布验收流程。
