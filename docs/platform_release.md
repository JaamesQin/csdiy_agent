# 平台发布记录

> 更新日期：2026-08-13
>
> 发布状态：多用户本地候选版本已验证，生产发布待执行

## 当前候选版本

- OpenAI 兼容 FastAPI 服务，保留 API Key、模型 ID、JSON/SSE 和错误契约；
- 用户名注册、密码登录、会话恢复和注销；
- Argon2id 密码 hash、仅摘要存储的会话令牌、Cookie/CSRF/Origin 防护；
- 账号和 legacy API Key 双命名空间的最小学习画像；
- SQLite Schema v1→v2 事务迁移；
- 不在服务器保存完整对话或代码；
- 标准错误响应和流式错误收尾；
- 规则优先的意图路由、八项可用能力的 `/help`、主动学习画像和多语言静态代码辅导；
- 119 个课程目标的失败关闭 Catalog 校验、确定性导航和三类状态展示；
- Lecture 2/8 已审核黄金 StudyKit 查询、材料/概念、练习选择和当前答案反馈；
- 带登录、功能总览、画像、课程、StudyKit、练习和代码辅导入口的本地聊天界面；
- selective practice repair 仅作为离线 fingerprinted build；保留 direct-parent snapshot，
  rich audit 绑定当前 build+repair plan，并要求逐题 practice ID exact coverage；
- 独立 StudyKit SQLite 归档已实现，但当前 286 个导入文档均为 `validated_draft`；它们不属于本次在线发布面，人工批准前不得切换 ready 查询。
- 在线 Store 已接入只读 archive adapter：build/document 双 `approved`、portable v0.1/v0.2.1 兼容、approved archive 优先和 golden 回退；当前在线范围仍为 Lecture 2/8。
- `data/` 是需要单独授权的私有 submodule；部署/测试主仓库前必须初始化 submodule 与 Git LFS。
- 303 项自动化测试通过，其中 4 项为独立 Uvicorn/loopback HTTP 测试。

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
| `COURSEPILOT_DB_PATH` | 建议显式设置 | 挂载在受限权限的持久卷中；当前仅存账号、会话和画像 |
| `COURSEPILOT_SESSION_TTL_HOURS` | 否 | 默认 12 小时 |
| `COURSEPILOT_COOKIE_SECURE` | 生产必须 | HTTPS 环境设为 `true` |
| `COURSEPILOT_ALLOWED_ORIGINS` | 生产必须 | 逗号分隔的完整 Origin，例如 `https://coursepilot.example.com` |
| `COURSEPILOT_TEST_MODE` | 否 | 生产保持 `false` |
| `DEEPSEEK_API_KEY` | 否 | 启用低置信路由、画像候选、材料问答、练习反馈和语义代码建议；未设置时透明降级 |
| `DEEPSEEK_BASE_URL` / `DEEPSEEK_MODEL` | 否 | 复用离线生成器的模型适配配置 |

禁止记录或提交 API Key、密码、Cookie、CSRF token、Argon2 hash 和数据库内容。
账号数据库与 `data/archive/studykits.sqlite3` 必须使用不同文件、权限和备份策略。账号库仍在
ignored `storage/`；StudyKit 归档在私有 submodule 中由 Git LFS 管理，不能因其可克隆就视为
online-ready 或绕过 document review status。

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

不得把 `/chat/completions` 重复附加到 `baseUrl`。

## 当前限制

- 当前执行功能帮助、画像、课程导航、StudyKit 查询、材料/概念、练习选择/反馈、代码辅导和澄清；学习复盘和生成状态仍降级；
- Catalog 仍读取 tracked registry/Manifest，StudyKit 仍读取 golden 文件；尚未接入数据库 MaterialSet、SourceChunk 检索或 RAG；
- 课程上下文仅覆盖 Lecture 2/8 人工批准的黄金 StudyKit；
- 代码只做 AST/Tree-sitter 静态分析，始终 `ran_code=false`；课程专用 DSL 可能只获得模型静态建议；
- API Key 请求的 `user` 是客户端提供的逻辑标识，只进入 legacy 命名空间，不是生产授权凭据；
- 尚未完成清小搭生产探测；
- selective repair 的任一 build/plan/audit 或 practice-ID coverage mismatch 都阻止 completion；
  deterministic Schema pass 不能单独放行。六课 repair builds 已 succeeded，但五课的课程级
  visual-review gate 仍阻止 catalog globally complete；
- 尚未实测 `file.url`；
- 本地测试不能证明云端代理不会缓冲 SSE；
- 本地测试不能证明云端冷启动满足清小搭超时要求。

## 降级方案

- 流式代理不稳定：保留非流式 JSON；
- 文件输入不可用：使用公开链接、文本粘贴或预上传样板资料；
- 长期状态不可用：输出可复制状态卡；
- DeepSeek 不可用：保留规则路由、功能帮助、课程导航、StudyKit 查询、概念解释、练习选择、显式画像识别和多语言静态诊断；材料问答返回已审核摘要，练习反馈不判分；
- 画像数据库不可用：继续本轮临时画像和代码辅导，并提示未保存；
- 云端候选版本异常：回退到最近一个完整测试通过的提交。

## 发布后检查

- [ ] `/health` 返回 200；
- [ ] 注册、登录、`/auth/me`、注销成功，错误密码不区分用户是否存在；
- [ ] Cookie 包含 HttpOnly、SameSite=Strict、Secure、Path=/ 且无 Domain；
- [ ] 缺少/错误 CSRF 的 Cookie 聊天返回 403；
- [ ] 账号 A 不能查看、删除账号 B 的画像；
- [ ] API Key legacy 用户不能访问账号画像；
- [ ] 正确/错误 API Key 分别返回 200/401；
- [ ] 非流式 JSON 与 SSE role/content/stop/`[DONE]` 正常；
- [ ] 课程导航将目录/authoring/在线 StudyKit 状态分开，且不输出未审核 candidate offering；
- [ ] Lecture 2/8 的查询、材料/概念、练习和反馈正常，未知页码不产生猜测；
- [ ] 无 DeepSeek 时练习反馈透明降级，不输出隐藏 rubric、分数或掌握度；
- [ ] 数据库版本为 2，备份和恢复演练通过；
- [ ] 反向代理限流、日志脱敏和 HTTPS 验证通过；
- [ ] 清小搭协议探测和真实试聊通过。
