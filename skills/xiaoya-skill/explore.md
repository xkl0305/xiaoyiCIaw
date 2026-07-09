# explore — 音频详情

查看节目简介、声音列表与用户评分，了解内容是否符合你的兴趣。

## 工具列表

| 工具名 | 说明 | 典型场景 |
|--------|------|----------|
| `multiGetAlbumInfo` | 批量查询专辑详情 | 查看专辑标题、标签、分类、播放量等 |
| `multiGetTrackInfo` | 批量查询声音详情 | 查看声音标题、时长、播放量、简介等 |
| `multiGetTrackListOfAlbum` | 批量查询专辑声音列表 | "这个专辑有哪些声音" |
| `extractTrackFromAlbum` | 根据时效性从专辑抽取声音 | 从专辑里挑最新/最热的声音 |
| `sortByQuery` | 按需求排序声音 | 对声音列表按用户意图重排 |
| `queryAlbumComments` | 查询专辑评论/评价 | "这个专辑评价怎么样" |
| `queryTrackComments` | 查询声音评论/评价 | "看看这集声音的评论" |

## multiGetAlbumInfo

**功能**：查询专辑详细信息。

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `albumIdList` | string[] | 是 | 专辑ID列表 |

**回包**：格式化文本，专辑详情列表。

示例：
```
1. 专辑 《盗墓笔记》的ID是 27249251 ,它创建于2023-01-01 00:00:00，属于悬疑分类,由主播 xxx 倾情演播,截止目前累计播放量为 12.3亿,累计订阅量为 345.6万,它属于付费内容，用户需要付费才能收听；它的推荐分（满分10分）是9.8，它的质量分（满分10分）是9.5,它的标签包括【悬疑、推理】，截止目前，专辑下一共有120条声音，最新的一条声音更新于2023-05-01 00:00:00,声音的标题是《最新声音标题》，声音的ID是209631725，它的内容简介如下:【 内容简介...】。
```

## multiGetTrackInfo

**功能**：批量查询声音详细信息。

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `trackIdList` | string[] | 是 | 声音ID列表 |

**回包**：格式化文本，声音详情列表。

示例：
```
1. 声音《title》的ID是 123,创建于2023-01-01 00:00:00, 它属于专辑《album》（专辑ID:456),它属于悬疑内容，由主播 xxx倾情演播,截止目前累计播放量达1.2亿;它的质量分（满分10分）是9.5分,它的标签包括【悬疑、推理】，声音的时长为1200秒，它的内容简介如下: 【内容简介...】。
```

## multiGetTrackListOfAlbum

**功能**：批量查询专辑下的声音列表。

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `albumIdList` | string[] | 是 | 专辑ID列表 |
| `beginIndex` | integer | 否 | 开始索引，1表示第一条，inclusive |
| `endIndex` | integer | 否 | 结束索引，inclusive |
| `order` | string | 否 | 排序：`asc`（从旧到新）/`desc`（从新到旧） |

**回包**：格式化文本，专辑声音总数和指定范围的声音ID列表，每次最多返回100条。

示例：
```
专辑【ID：123】 下一共有50条声音，第1条至第20条的声音ID为：1,2,3,4,5,...
```

## extractTrackFromAlbum

**功能**：根据时效性从专辑抽取声音。

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `albumIdList` | string[] | 是 | 专辑ID列表 |
| `query` | string | 否 | 查询内容，用于时效性判断（如"最新一期""上一集"等） |

**回包**：格式化文本，声音详情（同 `multiGetTrackInfo` 格式）。

## sortByQuery

**功能**：按需求排序声音。

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `trackIdList` | string[] | 是 | 声音ID列表 |
| `query` | string | 否 | 查询内容 |

**回包**：格式化文本，排序后的声音列表。

## queryAlbumComments

**功能**：查询专辑的用户评论/评价（含评分、文字内容等），了解其他听众对专辑的反馈。

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `albumId` | long | 是 | 专辑 ID，必须为正整数 |
| `pageId` | int | 否 | 页码，默认 `1`，小于 `1` 时修正为 `1` |
| `pageSize` | int | 否 | 每页条数，默认 `10`，范围 `[1, 50]` |
| `order` | string | 否 | 排序方式，默认 `content-score-desc` |

**回包**：JSON 对象。

| 字段 | 类型 | 说明 |
|------|------|------|
| `comments` | list | 评论列表 |
| `comments[].commentId` | long | 评论 ID |
| `comments[].uid` | long | 评论用户 ID |
| `comments[].nickname` | string | 用户昵称 |
| `comments[].newAlbumScore` | int | 专辑评分（1~10） |
| `comments[].content` | string | 评论内容 |
| `comments[].likes` | int | 点赞数 |
| `comments[].replyCount` | int | 回复数量 |
| `comments[].liked` | boolean | 当前用户是否已点赞 |
| `comments[].createdAt` | long | 创建时间戳（毫秒） |
| `pageId` | int | 当前页码 |
| `pageSize` | int | 每页条数 |
| `maxPageId` | int | 最大页码 |
| `totalCount` | int | 总评论数 |
| `isCommentsFolded` | boolean | 评论是否折叠 |

## queryTrackComments

**功能**：查询声音的用户评论/评价，含主评论、回复与点赞信息。

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `trackId` | long | 是 | 声音 ID，必须为正整数 |
| `pageId` | int | 否 | 页码，默认 `1`，小于 `1` 时修正为 `1` |
| `pageSize` | int | 否 | 每页条数，默认 `10`，范围 `[1, 50]` |
| `order` | int | 否 | 排序方式，默认 `4` |
| `extraParams` | map | 否 | 扩展参数，例如 `{"show_version": "1"}` |

**回包**：JSON 对象。

| 字段 | 类型 | 说明 |
|------|------|------|
| `comments` | list | 评论列表 |
| `comments[].id` | long | 评论 ID |
| `comments[].uid` | long | 评论用户 ID |
| `comments[].nickname` | string | 用户昵称 |
| `comments[].content` | string | 评论纯文本内容 |
| `comments[].likes` | int | 点赞数 |
| `comments[].liked` | boolean | 当前用户是否已点赞 |
| `comments[].replyCount` | long | 回复数量 |
| `comments[].replies` | list | 回复列表（含 `ancestorId`、`parentId`、`content` 等） |
| `comments[].isTop` | boolean | 是否置顶 |
| `comments[].createdAt` | long | 创建时间戳（毫秒） |
| `pageId` | int | 当前页码 |
| `pageSize` | int | 每页条数 |
| `maxPageId` | int | 最大页码 |
| `totalCount` | int | 总评论数 |
| `topCount` | int | 置顶评论数 |
| `allowCommentType` | int | 评论权限类型 |
| `allowCommentTypeDesc` | string | 评论权限描述 |

## 工作流

1. 用户询问某专辑详情 → `multiGetAlbumInfo`
2. 用户问"有哪些声音" → `multiGetTrackListOfAlbum`
3. 用户想从专辑里挑最新/最热的 → `extractTrackFromAlbum`
4. 用户要求按特定需求排序 → `sortByQuery`
5. 用户说"播放这个" → 按 `SKILL.md` 深度链接规则本地拼接 `iting://` 与 `webLink`
6. 用户问"这个专辑评价怎么样" → `queryAlbumComments`
7. 用户问"这集声音的评论" → `queryTrackComments`
8. 展示专辑或声音列表时，附上跳转链接（客户端根据实际环境选择 `iting://` 或网页链接）

## 数据展示规范

- **内部标识不得暴露**：回包中的 `专辑ID`、`声音ID`、`评论ID`、`用户ID` 等内部标识仅用于内部上下文记忆或构造深度链接，**面向用户展示时不得主动以纯文本形式暴露**。重点展示标题、主播、播放量、分类、简介、评论内容等用户感知度高的信息
