# 账号认证与画像隔离

更新时间：2026-08-10

## 1. 目标与范围

本地网页要求用户先注册或登录，再访问聊天。账号身份由服务器验证，不能使用 OpenAI 请求体的 `user` 字段替代授权。

首版只持久化最小学习画像事实及短证据摘录，包括学习方向、目标、基础、每周时间和讲解偏好；模型推断作为 7 天待确认候选。系统不保存完整消息、代码、traceback 或模型推理。邮箱验证、找回/修改密码、账号删除和对话历史不在当前范围。

## 2. HTTP 接口

### `POST /auth/register`

```json
{"username":"alice","password":"at-least-12-characters"}
```

成功返回 `201`，创建账号和会话；用户名重复返回 `409`，字段不合法返回 `422`。

### `POST /auth/login`

输入与注册相同。成功返回 `200`；用户名不存在、密码错误和账号禁用统一返回 `401 Invalid username or password`。

### `GET /auth/me`

读取 `coursepilot_session` Cookie。成功返回：

```json
{
  "user": {"id":"…","username":"alice","created_at":"…"},
  "csrf_token":"…"
}
```

### `POST /auth/logout`

必须带 `X-CSRF-Token`。服务端撤销会话并清除 Cookie，成功返回 `204`。

## 3. 会话与 CSRF

- 原始会话令牌由 32 字节安全随机数生成，只通过 HttpOnly Cookie 发送。
- SQLite 只保存令牌的 SHA-256 摘要；数据库泄漏不能直接生成有效 Cookie。
- Cookie 使用 `SameSite=Strict`、`Path=/`、无 `Domain`、无持久 `Max-Age`。
- `COURSEPILOT_COOKIE_SECURE=true` 时增加 `Secure`；生产 HTTPS 必须启用。
- 服务端默认 12 小时绝对过期；注销设置 `revoked_at`，过期或撤销后不可恢复。
- Cookie 认证的聊天和注销必须提供与会话令牌绑定的 HMAC `X-CSRF-Token`。
- 浏览器登录、注册和注销验证 `Origin`；生产跨代理部署应显式设置 `COURSEPILOT_ALLOWED_ORIGINS`。

应用包含有界的单进程登录/注册限流：同一客户端和用户名 15 分钟内最多 5 次失败登录，同一客户端最多 30 次；注册每小时最多 10 次。生产多进程/多实例部署还必须在网关或共享限流器中实施全局限制，且默认不信任 `X-Forwarded-For`。

## 4. 密码与用户名

- 用户名为 3–32 位 ASCII，字母或数字开头，后续可包含字母、数字、`.`、`_`、`-`；登录时使用 `casefold()` 后的唯一键。
- 密码为 12–128 个字符。
- 密码使用 Argon2id：memory 19456 KiB、time cost 2、parallelism 1、32 字节 hash、16 字节随机 salt。
- 用户不存在时仍校验一个 dummy Argon2id hash，减少明显时序差异。
- 登录成功时调用 `check_needs_rehash`，参数变化后自动升级密码 hash。

## 5. 数据库 Schema 与迁移

SQLite `PRAGMA user_version=3`。共享迁移层创建：

- `users`：账号 UUID、显示/规范化用户名、密码 hash、时间和禁用标记。
- `auth_sessions`：令牌摘要、用户外键、创建/过期/撤销时间；账号删除时会话级联删除。
- `profile_facts`：按受信 subject 存储最小画像事实和证据摘录。
- `conversation_states`：按受信命名空间与 `sessionId` 的 HMAC 摘要存储最小连续状态、CAS revision 和滑动过期时间。

Schema v1 首次启动时在事务内执行：

1. 保留所有画像事实；
2. 将旧 `user_id` 改为 `legacy:<旧值>`；
3. 创建账号和 Cookie 会话表；
4. 创建对话连续状态表并设置版本 3。

Schema v2 升级 v3 时只增加 `conversation_states`，不再改写已有 `profile_facts.user_id`，避免重复添加 `legacy:` 前缀。

未知版本拒绝服务启动。升级前仍建议使用 SQLite online backup 或停止服务后复制数据库及 `-wal`/`-shm` 文件；不要只在服务运行时复制主文件。

## 6. 双身份兼容

`/v1/models` 和 `/v1/chat/completions` 同时接受：

- 账号 Cookie：有效画像 subject 固定为 `account:<uuid>`，忽略请求体 `user`。
- 服务器 API Key：有效画像 subject 为 `legacy:<request.user>`；缺少 `user` 时不持久化画像。

前缀由服务端添加。即使 legacy 客户端提交 `user="account:<uuid>"`，最终键也是 `legacy:account:<uuid>`，不会命中账号数据。

聊天 HTTP 层完成身份与 CSRF 校验后，只把上述可信 subject 传入 Agent。意图路由、
画像观察和静态代码辅导均不能直接读取或信任请求体 `user`。画像支持查看、纠正、
单项删除、拒绝记录、确认候选和全部删除。

## 7. 运维检查

- 数据库目录仅允许服务账号访问；默认 `storage/` 尝试设置 `0700`，数据库设置 `0600`。
- 生产必须使用 HTTPS、`COURSEPILOT_COOKIE_SECURE=true` 和明确的 Origin allowlist。
- API Key、密码、Cookie、CSRF token、Argon2 hash 不得写入应用日志。
- 定期清理备份、验证恢复流程，并在反向代理配置注册/登录的共享限流。
- `/health` 保持公开；OpenAI 接口的模型 ID、JSON/SSE 帧与错误封装保持兼容。
