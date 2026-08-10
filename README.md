# CoursePilot

CoursePilot 是一个面向中文计算机科学自学者的循证学习 Agent。仓库目前包含可审计的 StudyKit 离线生成内核、OpenAI 兼容协议服务，以及带账号隔离的本地学习画像 MVP。

## 当前能力

- `GET /v1/models` 和 `POST /v1/chat/completions`，支持非流式 JSON 与 SSE；模型 ID 固定为 `coursepilot-probe`。
- 旧的 `Authorization: Bearer <COURSEPILOT_API_KEY>` 调用保持兼容，包括可选 OpenAI `user` 字段。
- 本地网页支持用户名注册、密码登录、会话恢复和注销，不再要求用户在浏览器中输入服务器 API Key。
- 每个账号可以保存、查看和删除最小学习画像：学习方向、每周时间和明确陈述的技术基础。
- 画像按服务端账号 UUID 隔离；不保存完整对话、用户代码、traceback 或模型推理。
- 分阶段 StudyKit 生成器执行 Evidence → Content → Practice → Audit → 确定性组装，并输出 JSON/YAML/Markdown。

在线聊天当前仍以协议回显和最小画像管理为主；课程检索、材料答疑、完整代码辅导和学习复盘尚未接入在线编排。

## 身份与数据边界

服务支持两个互不相交的身份空间：

```text
网页登录 Cookie 会话
  → 服务端验证账号
  → account:<随机账号 UUID>
  → 只读写该账号画像

受信 API Key 调用
  → 请求体可选 user
  → legacy:<user>
  → 只读写 legacy 画像
```

账号会话会忽略请求体中的 `user`，因此客户端不能通过伪造字段访问其他账号。持有服务器全局 API Key 的旧集成仍可使用 legacy 数据，但不能构造 `account:` 身份。历史 Schema v1 画像在首次启动时事务性迁移到 legacy 命名空间，不会自动认领到新账号。

## 本地运行

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export COURSEPILOT_API_KEY="$(openssl rand -hex 32)"
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

打开 `http://127.0.0.1:8000/`，注册用户名和至少 12 个字符的密码后即可进入聊天。账号密码使用 Argon2id 哈希；浏览器只持有 HttpOnly、SameSite=Strict 的会话 Cookie。

外部 OpenAI 兼容客户端仍可使用 API Key：

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer $COURSEPILOT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"coursepilot-probe","user":"trusted-client-user","messages":[{"role":"user","content":"你好"}]}'
```

## 配置

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `COURSEPILOT_API_KEY` | 无 | 必填，至少 16 个字符；兼容 API Key，同时绑定 CSRF token |
| `COURSEPILOT_DB_PATH` | `storage/coursepilot.sqlite3` | 账号、会话和画像事实的 SQLite 文件 |
| `COURSEPILOT_SESSION_TTL_HOURS` | `12` | 服务端会话绝对有效期 |
| `COURSEPILOT_COOKIE_SECURE` | `false` | HTTPS 生产环境必须设为 `true` |
| `COURSEPILOT_ALLOWED_ORIGINS` | 当前请求 Origin | 可选，逗号分隔的网页登录 Origin allowlist |
| `COURSEPILOT_TEST_MODE` | `false` | 仅测试使用 |
| `DEEPSEEK_API_KEY` | 无 | 仅离线生成流程需要 |

生产环境必须使用 HTTPS、持久化受限权限的数据库卷，并在反向代理层增加全局登录/注册限流。应用内限流只覆盖单进程实例。

## 认证接口

- `POST /auth/register`：创建账号并自动登录；输入 `username`、`password`。
- `POST /auth/login`：建立新会话。
- `GET /auth/me`：恢复当前 Cookie 会话并取得 CSRF token。
- `POST /auth/logout`：校验 `X-CSRF-Token` 后撤销服务端会话。

Cookie 认证的 `POST /v1/chat/completions` 同样要求 `X-CSRF-Token`。API Key Bearer 请求不依赖 Cookie，因此不要求 CSRF header。完整接口和迁移说明见 [账号认证与画像隔离](docs/account_authentication.md)。

## 测试

```bash
.venv/bin/pytest -q
```

当前基线为 `163 passed`，其中真实 HTTP 测试会绑定 `127.0.0.1` 临时端口。覆盖密码和令牌非明文存储、v1→v2 迁移、并发注册、会话过期/撤销、CSRF、同源校验、限流、跨账号隔离、legacy 兼容、JSON/SSE 契约、生成与检索模块。

## 安全与隐私

- 用户名不区分大小写；允许 3–32 位 ASCII 字母、数字、点、下划线和连字符。
- 密码长度为 12–128 个字符，使用 Argon2id（19 MiB、2 次迭代、并行度 1、随机 salt）。
- 数据库仅保存会话令牌的 SHA-256 摘要；原始令牌只存在于浏览器 HttpOnly Cookie。
- Cookie 写操作使用会话绑定的 HMAC CSRF token，并拒绝非 allowlist Origin。
- API 响应设置 CSP、`nosniff`、`DENY` framing 和 `no-referrer`。
- 首版不支持邮箱、找回密码、修改密码、账号删除或完整对话历史；用户仍可发送“删除我的画像”删除画像事实。
- 只索引公开、开放许可或用户有权使用的课程材料；不提供可提交的完整作业答案。

## 文档

- [文档索引](docs/README.md)
- [账号认证与画像隔离](docs/account_authentication.md)
- [项目状态](PROJECT_STATUS.md)
- [全局进度](docs/project_status.md)
- [Developers Guide](docs/developers_guide.md)
- [平台发布记录](docs/platform_release.md)
- [平台验证记录](docs/platform_validation.md)
- [StudyKit 分阶段生成](docs/studykit_generation.md)
