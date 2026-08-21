# 平台发布记录

> 更新日期：2026-08-21
>
> 发布状态：多用户本地候选版本已验证，生产发布待执行

## 当前候选版本

- OpenAI 兼容 FastAPI 服务，保留 API Key、模型 ID、JSON/SSE 和错误契约；
- 用户名注册、密码登录、会话恢复和注销；
- Argon2id 密码 hash、仅摘要存储的会话令牌、Cookie/CSRF/Origin 防护；
- 账号和 legacy API Key 双命名空间的最小学习画像；
- SQLite Schema v1→v2→v3 事务迁移；v3 增加经 HMAC 索引的最小对话连续状态；
- 不在服务器保存完整对话或代码；
- 标准错误响应和流式错误收尾；
- 有界 TaskPlan、九项可用能力的 `/help`、受约束的通用学习问答、主动学习画像和多语言静态代码辅导；
- 未上线能力仅保留 Help/状态 metadata；明确请求在 Planner/Router/执行入口失败关闭为带受控能力边界的通用回答；
- 119 个课程目标的失败关闭 Catalog 校验、安全学习决策投影、确定性精确导航、画像感知的单次模型排序和三类状态展示；
- 220 份 approved archive StudyKit 与 Lecture 2/8 golden 安全回退已接入查询、材料/概念、练习选择和当前答案反馈；
- 带登录、功能总览、画像、课程、StudyKit、练习和代码辅导入口的同源聊天界面；助手回复支持经清洗的 Markdown、表格、代码高亮和 MathML，用户/错误保持纯文本；
- 公共 permission-first FTS5、精确练习引用解析、材料/练习反馈 adapter 和 approved 索引构建已接线；当前没有部署 approved SourceChunk 索引，私有/向量检索尚未上线；
- selective practice repair 仅作为离线 fingerprinted build；保留 direct-parent snapshot，
  rich audit 绑定当前 build+repair plan，并要求逐题 practice ID exact coverage；
- 独立 StudyKit SQLite 归档已实现；严格门禁、明确 reviewed-legacy 人工批准和 CS186 新指纹身份修复后，当前 9 builds/220 documents 为 `approved`，另外 3/66 partial 记录保持 `validated_draft`。
- 在线 Store 已接入只读 archive adapter：build/document 双 `approved`、portable v0.1/v0.2.1/v0.2.2 兼容、approved archive 优先和 golden 回退；组合 Store 当前有 220 个 ready StudyKit。
- `data/` 是需要单独授权的私有 submodule；部署/测试主仓库前必须初始化 submodule 与 Git LFS。
- 完整私有数据可用时的历史 Python 基线为 623 项；本次 Exercise 契约 49 项独立回归及获准 loopback HTTP/SSE 5 项通过。另有 18 项前端单元测试和 7 项 Chrome Playwright 流程通过。

## 本地启动

从源码修改或重新生成 Web 客户端时先运行 `npm ci` 与 `npm run build`；只运行仓库已提交的
`app/static/` 时可省略这两步。

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
| `COURSEPILOT_DB_PATH` | 建议显式设置 | 挂载在受限权限的持久卷中；当前仅存账号、Cookie 会话、画像和最小对话连续状态 |
| `COURSEPILOT_SESSION_TTL_HOURS` | 否 | 默认 12 小时 |
| `COURSEPILOT_CONVERSATION_TTL_DAYS` | 否 | 清小搭 `sessionId` 状态滑动有效期，默认 30 天 |
| `COURSEPILOT_COOKIE_SECURE` | 生产必须 | HTTPS 环境设为 `true` |
| `COURSEPILOT_ALLOWED_ORIGINS` | 生产必须 | 逗号分隔的完整 Origin，例如 `https://coursepilot.example.com` |
| `COURSEPILOT_TEST_MODE` | 否 | 生产保持 `false` |
| `COURSEPILOT_ROBUST_INPUT` | 否 | 默认 `true`；首个发布周期可临时设为 `false` 回退旧 Planner 路径 |
| `COURSEPILOT_SOURCE_CHUNK_INDEX_PATH` | 否 | 默认 `data/indexes/source_chunks.sqlite3`；必须指向由 approved archive 离线构建的只读索引 |
| `DEEPSEEK_API_KEY` | 否 | 启用统一理解、画像感知课程排序、通用学习问答、画像候选、材料问答、练习反馈和语义代码建议；未设置时透明降级 |
| `DEEPSEEK_BASE_URL` / `DEEPSEEK_MODEL` | 否 | 复用离线生成器的模型适配配置 |

禁止记录或提交 API Key、密码、Cookie、CSRF token、Argon2 hash 和数据库内容。
账号数据库、`data/archive/studykits.sqlite3` 与可重建的 `data/indexes/source_chunks.sqlite3`
必须使用不同文件、权限和备份策略。账号库仍在
ignored `storage/`；StudyKit 归档在私有 submodule 中由 Git LFS 管理，不能因其可克隆就视为
online-ready 或绕过 document review status。

## 数据库升级

1. 停止所有写实例；
2. 使用 SQLite online backup，或在完全停止后同时备份 `.sqlite3`、`-wal`、`-shm`；
3. 使用相同持久卷启动一个新实例；
4. 启动迁移把 v1 画像 subject 改为 `legacy:<旧 user>`，创建账号/Cookie 会话表，v3 再创建 `conversation_states`并设置 `user_version=3`；
5. 验证注册、登录、API Key legacy 画像、`sessionId` 续接和命名空间隔离；
6. 再扩容其他实例。

未知数据库版本会让启动失败，不允许降级覆盖。历史匿名画像不会认领到新账号，因为匿名 ID 不是所有权证明。

## 反向代理与 Cookie

- 全站 HTTPS；启用 HSTS 后再逐步扩大 max-age。
- `COURSEPILOT_COOKIE_SECURE=true`，不要修改 Cookie Domain。
- 将真实网页登录 Origin 放入 allowlist；不要使用通配符凭据 CORS。
- 应用默认使用 socket peer IP，不信任 `X-Forwarded-For`。生产网关应另行实施共享的注册/登录限流，并只在受信代理链中处理真实 IP。
- 不缓存 `/auth/*`；保持响应的 `Cache-Control: no-store`。
- `/` 必须保持 `Cache-Control: no-cache`，避免旧入口引用已被下一次 Vite 构建替换的哈希资源。
- 保留 CSP、`X-Frame-Options: DENY`、`nosniff` 和 `no-referrer`。
- 不为 Markdown/公式渲染增加 `unsafe-inline`、`unsafe-eval` 或远程资源域名；生产资源全部由同源 `/static` 提供。

## 清小搭兼容配置

清小搭等受信集成继续使用：

```text
baseUrl: https://<production-domain>/v1
credential: <COURSEPILOT_API_KEY>
```

其请求体 `user` 只进入 legacy 命名空间。顶层可选 `sessionId` 在该可信命名空间内续接最小对话状态，响应无需回传；字段缺失或为空时不复用任何上一通状态。它不是授权凭据，也不能映射为本地账号 UUID。

不得把 `/chat/completions` 重复附加到 `baseUrl`。

## 当前限制

- 当前执行功能帮助、画像、课程导航、StudyKit 查询、材料/概念、练习选择/反馈、代码辅导和通用学习问答；学习复盘和生成状态仍降级；
- Catalog 仍读取 tracked registry/Manifest，StudyKit 使用 approved archive 优先与 golden 回退；公共 SourceChunk FTS5、精确练习引用解析和索引构建已接线，但当前部署没有 approved 索引，数据库 MaterialSet、私有/向量检索尚未上线；
- 课程上下文覆盖 220 份 approved archive StudyKit，并保留 Lecture 2/8 人工批准的黄金 StudyKit 回退；
- 代码辅导支持示例生成、解释、诊断、审阅、修复、重构和测试设计；输入与生成代码只做 AST/Tree-sitter 静态检查，始终 `ran_code=false`，课程专用 DSL 可能只获得模型静态建议；
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
- DeepSeek 不可用：通用学习问答透明降级；课程精确查询/列表仍可用，个性化推荐明确标注为未结合画像排序；保留功能帮助、StudyKit 查询、概念解释、练习选择、显式画像识别和确定性静态诊断；代码生成/改写透明说明模型不可用，不伪造示例；材料问答返回已审核摘要，练习反馈只返回原题提示和已验证来源标签；
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
- [ ] 助手 Markdown、表格、代码和 MathML 正常；用户 HTML 保持文本，远程图片/脚本/危险链接不能加载或执行；
- [ ] 课程导航将目录/authoring/在线 StudyKit 状态分开，且不输出未审核 candidate offering；
- [ ] 220 份 approved archive 与 Lecture 2/8 golden 回退的查询、材料/概念、练习和反馈正常，未知页码不产生猜测；
- [ ] 运行 `.venv/bin/python scripts/build_source_chunk_index.py --replace`，索引只包含 build/document 双 approved 且 chunks 哈希匹配的数据；
- [ ] heading-only、page-only 练习产生带可信来源标签的课程反馈；跨课程、伪造、未审核或哈希漂移引用全部进入通用反馈；
- [ ] 无证据时显示“通用反馈（未按当前课程材料核验）”固定声明；无 DeepSeek 时不输出隐藏 rubric、分数或掌握度，也不追加第二次模型调用；
- [ ] 账号/会话数据库版本为 3，备份和恢复演练通过；
- [ ] 反向代理限流、日志脱敏和 HTTPS 验证通过；
- [ ] 清小搭协议探测和真实试聊通过。
# Online Agent P0–P2 release note

The optional `coursepilot_context` extension is additive. Existing OpenAI-compatible envelopes and
the SSE role/content/single-stop/`[DONE]` order remain unchanged. Private retrieval and vector search
are not included in this release.

Practice selection now automatically performs one controlled structured rewrite and falls back to the
approved original on any model or validation failure. Context v2 adds only presentation kind/digest
continuity and accepts v1 tokens. TaskPlan is counted separately; every concrete online capability is
limited to one model call, with no second online semantic reviewer. Set
`COURSEPILOT_PRACTICE_REWRITE_ENABLED=false` for an immediate presentation rollback.

Practice feedback now resolves cited public SourceChunks exactly by chunk ID or source/anchor after
scope, course identity, approval, and hash checks. Portable v0.2.2 declares `course_grounded` versus
`general_only`; invalid course evidence falls back to a prominently labeled general-knowledge review
without changing the OpenAI-compatible HTTP/SSE contract or the one-call budget.
