# 同程程心 Skills 配置说明

> 💡 **提示**：本技能使用 **apikey** 请求头进行认证，凭证来源为 `.xiaoyienv` 文件或环境变量。

---

## 凭据说明

### 主认证方式：.xiaoyienv 凭证

统一使用 `.xiaoyienv` 文件读取账号凭证：

| 环境变量 | 说明 |
|----------|------|
| `117660163_login_token` | 账号凭证。从 `/home/sandbox/.openclaw/.xiaoyienv` 文件中读取 |
| `117660163_login_token_expire_time` | 凭证过期时间。当前时间大于该值时，需先刷新凭证再继续调用 |

**认证流程**：

1. 从 `.xiaoyienv` 文件读取 `117660163_login_token`。
2. 若凭证为空，或当前时间大于 `117437361_login_token_expire_time`（即已过期），调用一次 `huawei_id_tool`（参数：clientId=117660163,skillName=tc-chengxin）刷新凭证。
3. 刷新成功后重新读取 `.xiaoyienv` 文件，再继续后续业务逻辑。
4. 所有请求头统一使用 `apikey: ${117660163_login_token}`。

**约束**：

- 凭据只从 `.xiaoyienv` 文件读取，禁止写死到代码或示例以外的固定位置。

### 兜底认证（CHENGXIN_API_KEY）

当 `.xiaoyienv` 凭证不可用且无法通过 `huawei_id_tool` 刷新时，从环境变量 `CHENGXIN_API_KEY` 读取兜底凭证：

- 存在则通过请求头 `apikey: ${CHENGXIN_API_KEY}` 调用接口。

**获取 CHENGXIN_API_KEY**：

1. 打开 **同程旅行 APP** 或 **同程旅行小程序**（微信 - 我 - 服务 → 火车票机票/酒店民宿）
2. 在顶部搜索栏中搜索「**程心激活码**」
3. 按页面提示完成申领即可获取 API Key
4. 将申领页面上的 **程心激活码（API Key）** 配置为环境变量 `CHENGXIN_API_KEY` 即可使用

> 💡 **快捷方式**：也可以直接回复「**帮我把 xxxxx（激活码）配置到 tc-chengxin 这个 skill 上**」，助手会自动帮你完成配置。

---

## 请求头规范

| 场景 | 请求头 |
|------|--------|
| 正常（凭证可用） | `apikey: ${117660163_login_token}` |
| 兜底（凭证不可用） | `apikey: ${CHENGXIN_API_KEY}` |
| 通用 | `Content-Type: application/json` |

---

## 接口地址

各 `scripts/*-query.js` 通过 `scripts/lib/api-client.js` 调用程心网关，**基础 URL** 为：

`https://wx.17u.cn/skills/gateway/api/v1/gateway`

具体资源在基础路径后拼接，例如 `/trainResource`、`/flightResource`、`/hotelResource` 等（与脚本内常量一致）。

## 网络要求

- 支持公网访问
- 无网络环境限制

---

## 📞 客服支持

使用过程中遇到问题？同程旅行提供 7×24 小时服务：

- **📞 旅行者热线**：**95711**
- **💬 在线客服**：[https://www.ly.com/public/newhelp/CustomerService.html](https://www.ly.com/public/newhelp/CustomerService.html)

---

## 📝 输出格式规范

详见主 `references/output-format.md`，包含各品类的表格/卡片列定义、预订链接格式、底部引导语等完整说明。

---

## 📦 响应结构

详见 `../SKILL.md` 中的响应结构说明。
