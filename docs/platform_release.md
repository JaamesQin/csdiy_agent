# 平台发布记录

> 更新日期：2026-08-09
>
> 发布状态：多用户本地候选版本已验证，生产发布待执行

## 当前候选版本

- OpenAI 兼容 FastAPI 服务，保留 API Key、模型 ID、JSON/SSE 和错误契约；
- 用户名注册、密码登录、会话恢复和注销；
- Argon2id 密码 hash、仅摘要存储的会话令牌、Cookie/CSRF/Origin 防护；
- 账号和 legacy API Key 双命名空间的最小学习画像；
- SQLite Schema v1→v2 事务迁移；
- 不在服务器保存完整对话或代码；
- 163 项自动化测试通过，其中 4 项为独立 Uvicorn/loopback HTTP 测试。

## 本地启动

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export COURSEPILOT_API_KEY="$(openssl rand -hex 32)"
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

浏览器访问 `http://127.0.0.1:8000/`，直接注册账号。浏览器不再接触全局 API Key。

## 生产环境变量

| 名称 | 必须 | 说明 |
| --- | --- | --- |
| `COURSEPILOT_API_KEY` | 是 | 至少 16 个随机字符，通过 Secret 注入；同时用于 legacy API 和 CSRF HMAC |
| `COURSEPILOT_DB_PATH` | 建议显式设置 | 挂载在受限权限的持久卷中 |
| `COURSEPILOT_SESSION_TTL_HOURS` | 否 | 默认 12 小时 |
| `COURSEPILOT_COOKIE_SECURE` | 生产必须 | HTTPS 环境设为 `true` |
| `COURSEPILOT_ALLOWED_ORIGINS` | 生产必须 | 逗号分隔的完整 Origin，例如 `https://coursepilot.example.com` |
| `COURSEPILOT_TEST_MODE` | 否 | 生产保持 `false` |
| `DEEPSEEK_API_KEY` | 按需 | 仅离线生成流程使用 |

禁止记录或提交 API Key、密码、Cookie、CSRF token、Argon2 hash 和数据库内容。

## 数据库升级

1. 停止所有写实例；
2. 使用 SQLite online backup，或在完全停止后同时备份 `.sqlite3`、`-wal`、`-shm`；
3. 使用相同持久卷启动一个新实例；
4. 启动迁移把 v1 画像 subject 改为 `legacy:<旧 user>`，创建账号/会话表并设置 `user_version=2`；
5. 验证注册、登录、API Key legacy 画像和两个账号间隔离；
6. 再扩容其他实例。

未知数据库版本会让启动失败，不允许降级覆盖。历史匿名画像不会认领到新账号，因为匿名 ID 不是所有权证明。

## 反向代理与 Cookie

- 全站 HTTPS；启用 HSTS 后再逐步扩大 max-age。
- `COURSEPILOT_COOKIE_SECURE=true`，不要修改 Cookie Domain。
- 将真实网页登录 Origin 放入 allowlist；不要使用通配符凭据 CORS。
- 应用默认使用 socket peer IP，不信任 `X-Forwarded-For`。生产网关应另行实施共享的注册/登录限流，并只在受信代理链中处理真实 IP。
- 不缓存 `/auth/*`；保持响应的 `Cache-Control: no-store`。
- 保留 CSP、`X-Frame-Options: DENY`、`nosniff` 和 `no-referrer`。

## 清小搭兼容配置

清小搭等受信集成继续使用：

```text
baseUrl: https://<production-domain>/v1
credential: <COURSEPILOT_API_KEY>
```

其请求体 `user` 只进入 legacy 命名空间。清小搭是否提供可验证账号身份仍需平台实测，不能把该字段映射为本地账号 UUID。

## 发布后检查

- [ ] `/health` 返回 200；
- [ ] 注册、登录、`/auth/me`、注销成功，错误密码不区分用户是否存在；
- [ ] Cookie 包含 HttpOnly、SameSite=Strict、Secure、Path=/ 且无 Domain；
- [ ] 缺少/错误 CSRF 的 Cookie 聊天返回 403；
- [ ] 账号 A 不能查看、删除账号 B 的画像；
- [ ] API Key legacy 用户不能访问账号画像；
- [ ] 正确/错误 API Key 分别返回 200/401；
- [ ] 非流式 JSON 与 SSE role/content/stop/`[DONE]` 正常；
- [ ] 数据库版本为 2，备份和恢复演练通过；
- [ ] 反向代理限流、日志脱敏和 HTTPS 验证通过；
- [ ] 清小搭协议探测和真实试聊通过。
