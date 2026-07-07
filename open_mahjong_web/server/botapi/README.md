# Bot API 使用说明

面向 QQ 机器人等第三方集成的查询接口。挂载在现有 `/api` 反代下，**无需额外 Nginx 配置**。

`info` 与 `records` 的**请求参数、响应 JSON 结构与公开 `/api/player` 完全一致**；额外提供 `rank` 段位查询。

基础路径：

```
https://salasasa.cn/api/bot/player/
```

本地开发：

```
http://localhost:3000/api/bot/player/
```

## 鉴权

所有 `/api/bot` 请求必须在 HTTP Header 中携带 JWT：

```
Authorization: Bearer <你的 Bot API 令牌>
```

- 令牌由站点管理员使用 `scripts/issue-bot-token.js` 签发后提供，**请勿泄露**。
- 服务端通过环境变量 `BOT_API_JWT_SECRET` 校验签名；载荷须包含 `"aud": "botapi"`。
- 无效或过期令牌返回 `401`。

### 管理员签发令牌

在 `open_mahjong_web` 目录下：

```bash
# 永不过期（推荐交给长期运行的 Bot）
node scripts/issue-bot-token.js my-qq-bot

# 可选：指定有效期（秒）
node scripts/issue-bot-token.js my-qq-bot 86400
```

## 限流

生产环境下，每个 Bot 名称（JWT 中的 `bot_name`）**每分钟最多 120 次成功请求**；超限返回 `429`。

## 接口列表

| 方法 | 路径 | 对应公开 API | 说明 |
|------|------|--------------|------|
| GET | `/api/bot/player/info/:key` | `/api/player/info/:key` | 玩家信息与各规则战绩 |
| GET | `/api/bot/player/records/:key` | `/api/player/records/:key` | 对局记录列表（分页） |
| GET | `/api/bot/player/rank-stats/:key` | `/api/player/rank-stats/:key` | 顺位统计（可按 tier 筛选） |
| GET | `/api/bot/player/rank/:key` | — | **Bot 独有**：国标段位与 PT |

`:key` 支持 **数字 user_id** 或 **用户名 username**。

### 示例文件

每个接口在 `examples/` 下提供 **请求** 与 **响应** 示例：

| 接口 | 请求示例 | 响应示例 |
|------|----------|----------|
| info | [`info.request.json`](./examples/info.request.json) | [`info.response.json`](./examples/info.response.json) |
| records | [`records.request.json`](./examples/records.request.json) | [`records.response.json`](./examples/records.response.json) |
| rank-stats | [`rank-stats.request.json`](./examples/rank-stats.request.json) | [`rank-stats.response.json`](./examples/rank-stats.response.json) |
| rank | [`rank.request.json`](./examples/rank.request.json) | [`rank.response.json`](./examples/rank.response.json) |

### records / rank-stats 可选 Query 参数

与 `/api/player/records/:key`、`/api/player/rank-stats/:key` 相同：

| 参数 | 说明 |
|------|------|
| `limit` | 每页条数，1–50，默认 20 |
| `offset` | 偏移，默认 0 |
| `rule` | 规则，如 `guobiao`、`riichi` |
| `sub_rule` | 子规则 |
| `tier` | 场次：`rank`、`custom`、`events`、`beginner`、`intermediate`、`advanced`、`mcrpl` |
| `room_type` | 房间类型 |
| `match_tier` | 匹配档位 |
| `game_type` | 局制：`dongfeng`、`banzhuang`、`xifeng`、`quanzhuang` |
| `date_from` / `date_to` | 时间范围（ISO 8601） |

## 错误响应

| HTTP | 含义 |
|------|------|
| 401 | 缺少或无效的 Bot API 令牌 |
| 404 | 用户不存在 |
| 429 | 请求过于频繁 |
| 500 | 服务器内部错误 |

```json
{ "success": false, "message": "错误说明" }
```

## curl 示例

```bash
TOKEN="你的JWT"

curl -s -H "Authorization: Bearer $TOKEN" \
  "https://salasasa.cn/api/bot/player/info/10000001"

curl -s -H "Authorization: Bearer $TOKEN" \
  "https://salasasa.cn/api/bot/player/records/10000001?tier=rank&limit=5"

curl -s -H "Authorization: Bearer $TOKEN" \
  "https://salasasa.cn/api/bot/player/rank-stats/10000001?tier=intermediate&rule=guobiao"

curl -s -H "Authorization: Bearer $TOKEN" \
  "https://salasasa.cn/api/bot/player/rank/10000001"
```

## 与 `/api/player` 的区别

| 项目 | `/api/player` | `/api/bot/player` |
|------|---------------|-------------------|
| 鉴权 | 无 | JWT |
| info / records / rank-stats 响应 | 基准 | **相同** |
| rank（国标段位 PT） | 无 | 有 |
| 限流 | 按 IP 30 次/分钟 | 按 Bot 名 120 次/分钟 |

## 环境变量

| 变量 | 说明 |
|------|------|
| `BOT_API_JWT_SECRET` | **必填**，HS256 签名密钥 |

## 部署说明

Bot API 与 `/api/player` 等同走现有 `location /api/` 反代，部署 Node 新版本并配置 `BOT_API_JWT_SECRET` 即可，**无需修改 Nginx**。
