# CoursePilot

CoursePilot 是一个面向中文计算机科学自学者的循证学习 Agent。仓库目前包含可审计的 StudyKit 离线生成内核、OpenAI 兼容 Agent 服务，以及带账号隔离的学习画像、课程导航、已审核 StudyKit 学习能力和静态代码辅导 MVP。

## 当前能力

- `GET /v1/models` 和 `POST /v1/chat/completions`，支持非流式 JSON 与 SSE；模型 ID 固定为 `coursepilot-probe`。
- 旧的 `Authorization: Bearer <COURSEPILOT_API_KEY>` 调用保持兼容，包括可选 OpenAI `user` 字段。
- 本地网页支持用户名注册、密码登录、会话恢复和注销，不再要求用户在浏览器中输入服务器 API Key。
- 每个账号可以保存、查看和删除最小学习画像：学习方向、每周时间和明确陈述的技术基础。
- 画像按服务端账号 UUID 隔离；不保存完整对话、用户代码、traceback 或模型推理。
- 在线 Agent 已接入规则优先的意图路由、`/help` 能力目录、主动学习画像、课程导航、多语言静态代码辅导和透明降级。
- 课程导航读取冻结的 CSDIY 课程表，分别展示目录分类、离线 authoring 和在线 StudyKit 三种状态；未审核 candidate offering 不作为官方链接输出。
- StudyKit 查询、材料问答、课程概念解释、练习选择和当前答案反馈已经上线；在线内容仍只读取 Schema 合法、人工批准的 Lecture 2/8 黄金 StudyKit。
- 分阶段 StudyKit 生成器执行 Evidence → Content → Practice → Audit → 确定性组装，并输出 JSON/YAML/Markdown。

SourceChunk 检索、私有 MaterialSet 和学习复盘尚未接入在线编排；材料问答不能回答 StudyKit 未覆盖的任意原文细节。代码辅导当前只做静态分析，不执行用户代码。

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

用户可以检索 118 个现有课程目标；其中多数分类仍待独立审核，只有引用受控 Manifest 的课程才展示官方课程页，只有 Lecture 2/8 两讲能进入在线 StudyKit 学习。未收录私有资料仍是后续能力，不会与公共目录或账号画像混合。

## 核心能力

- 主动学习画像：从用户明确陈述中识别学习方向、目标、基础、每周时间和讲解偏好；网页登录按账号保存，受信 API Key 客户端可使用 `legacy:<user>` 逻辑隔离，并支持查看、纠正和删除。
- 意图路由与帮助：规则优先、结构化模型兜底；`/help` 或“你有哪些功能”只列已上线能力，各能力的 `/help` 主题和自然语言询问返回具体用法。
- 课程导航：按课程名、学校、课程号或已确认学习方向检索 CSDIY 课程表；推荐最多 3 门，列表最多 5 门，并明确区分目录、离线和在线状态。
- StudyKit 学习：查询学习包、按页码白名单回答材料问题、分层解释概念、选择不重复练习，并只对携带 practice ID 的当前答案给反馈。
- 代码辅导：Python/Triton 使用 Python AST，C/C++、CUDA、ISPC、LaTeX、Java、Go、Rust、函数式语言、Web/SQL、Verilog 和汇编等使用离线 Tree-sitter 语法解析；提供诊断、假设、验证步骤和下一次尝试，不运行用户代码，也不代写可提交作业。
- 已审核 StudyKit 读取：所有在线课程事实通过 `StudyKitStore` 读取 Lecture 2/8 黄金 StudyKit；不输出 `expected_evidence`、evaluation、rubric、本地路径或审计字段。
- 离线 StudyKit 生成：生成包含目标、前置知识、提纲、术语、练习、引用和限制说明的中文学习包。
- 规划中：数据库 StudyKitStore、MaterialSet 权限、在线 SourceChunk 检索、私有材料和学习复盘。

## 技术路线

项目采用“清小搭平台入口 + 自研 Agent 后端”的架构：

```text
清小搭智能体广场
        ↓ OpenAI 兼容协议
协议适配层：鉴权、JSON、SSE、错误处理、文件 URL
        ↓
Agent 编排：意图路由、主动画像、课程导航、StudyKit 学习、静态代码辅导
        ↓
只读课程表与已审核 StudyKit；后续接入数据库、MaterialSet、RAG 与复盘
```

当前已实现的接入契约包括：

- `POST /v1/chat/completions`；
- `GET /v1/models`；
- Bearer Token 鉴权；
- 非流式 OpenAI 兼容 JSON；
- 流式 SSE：role、content、stop、`data: [DONE]`；
- `usage`、`finish_reason`、脱敏服务错误和流式错误处理；
- 可选 OpenAI `user` 字段，用于本地/受信网关下的画像逻辑隔离。

清小搭文件 URL、音频输入和 PDF/PPT/Word 等附件尚未接入，不阻塞文本版 MVP。

## 当前阶段

截至 2026-08-12，项目处于“离线生成内核、账号系统、课程导航和首批 StudyKit 学习能力完成，等待 SourceChunk 检索与清小搭生产验证”阶段：

| 项目 | 状态 |
| --- | --- |
| 产品目标与 MVP 边界 | 已完成 |
| 用户流程与验收场景 | 已完成 |
| 清小搭接入协议调研 | 已完成 |
| 自研后端架构与仓库结构 | 已完成最小实现 |
| OpenAI 兼容 API 实现 | 已完成 |
| Bearer、Cookie 会话、JSON、SSE 和错误契约测试 | 已完成；294 项测试通过 |
| 本地账号、会话、CSRF 与画像隔离 | 已完成安全 MVP |
| 意图路由、能力帮助、主动画像和多语言静态代码辅导 | 已完成首版 |
| CSDIY 课程导航 | 已完成全目录分级检索；目录分类仍按 registry 审核状态展示 |
| StudyKit 查询、材料/概念、练习选择/反馈 | 已完成 golden-only 首版；无 SourceChunk 时严格降级 |
| 本地聊天测试界面 | 已接入账号登录、功能总览、画像、课程、StudyKit、练习和代码辅导入口 |
| 云端部署方式 | 已确认，等待生产版本部署 |
| 首个模板课程与核心讲次冻结 | 已完成：MIT 6.7960，Lecture 2 和 8 为核心 Demo |
| CourseManifest 与来源审核 | 已完成初稿 |
| Lecture 2 黄金 StudyKit | v0.1 已通过 Schema、引用、术语、公式方向复核和人工批准 |
| Lecture 8 StudyKit | v0.1 已完成 Schema、引用、术语、公式方向、练习事实性复核和人工批准 |
| 全课程 portable StudyKit 包 | Lecture 01–21、23、24 共 23 讲已验证并批准待入库；暂存于 `data/reviewed/`，尚未接入在线 Catalog |
| SourceChunk Schema 与 PDF 页级解析 | 已完成；Lecture 2、8 的 chunks 已在本地生成并通过校验，未随公开仓库上传 |
| 黄金 StudyKit 在线读取 | 已完成：Lecture 2、8，只读人工批准版本；统一 `StudyKitStore` 接口 |
| 线上 SourceChunk 检索与 RAG | 尚未开始 |
| 清小搭接入探测与试聊 | 尚未开始 |
| 端到端 Demo、评测和用户试用 | 尚未开始 |

当前关键路径是：

1. 将当前文件型 `StudyKitStore` 替换为经过迁移和导入验证的数据库实现；
2. 冻结 MaterialSet/权限接口并建立 owner/session/course/version/unit 过滤的 SourceChunk 检索；
3. 接入私有材料和基于用户确认证据的学习复盘；
4. 验证清小搭稳定用户身份、消息历史、文件输入、状态和日志能力；
5. 将通过测试的后端部署到生产环境并完成端到端评测。

## 本地运行

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

设置本地接入密钥。配置 `DEEPSEEK_API_KEY` 后会启用低置信路由、画像候选、语义材料问答、当前练习答案反馈和语义代码辅导；不配置时课程导航、StudyKit 查询、概念解释和练习选择仍可用，材料问答返回最相关的已审核摘要，练习反馈不做粗略判分：

```bash
export COURSEPILOT_API_KEY="$(openssl rand -hex 32)"
# 可选：export DEEPSEEK_API_KEY="..."
# 可选：export COURSEPILOT_DB_PATH="/absolute/path/coursepilot.sqlite3"
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

打开 `http://127.0.0.1:8000/`，注册用户名和至少 12 个字符的密码后即可进入聊天。账号密码使用 Argon2id 哈希；浏览器只持有 HttpOnly、SameSite=Strict 的会话 Cookie。

外部 OpenAI 兼容客户端仍可使用 API Key，并可带逻辑用户标识；服务端会将其限定在 `legacy:` 命名空间：

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer $COURSEPILOT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"coursepilot-probe","user":"trusted-client-user","messages":[{"role":"user","content":"我想学系统方向，每周 6 小时，而且有 Python 基础。"}]}'
```

## 配置

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `COURSEPILOT_API_KEY` | 无 | 必填，至少 16 个字符；兼容 API Key，同时绑定 CSRF token |
| `COURSEPILOT_DB_PATH` | `storage/coursepilot.sqlite3` | 账号、会话和画像事实的 SQLite 文件；当前不存 StudyKit 或练习答案 |
| `COURSEPILOT_SESSION_TTL_HOURS` | `12` | 服务端会话绝对有效期 |
| `COURSEPILOT_COOKIE_SECURE` | `false` | HTTPS 生产环境必须设为 `true` |
| `COURSEPILOT_ALLOWED_ORIGINS` | 当前请求 Origin | 可选，逗号分隔的网页登录 Origin allowlist |
| `COURSEPILOT_TEST_MODE` | `false` | 仅测试使用 |
| `DEEPSEEK_API_KEY` | 无 | 可选；启用在线结构化路由/画像/材料问答/练习反馈/语义辅导，并用于离线生成 |

生产环境必须使用 HTTPS、持久化受限权限的数据库卷，并在反向代理层增加全局登录/注册限流。应用内限流只覆盖单进程实例。

## 认证接口

- `POST /auth/register`：创建账号并自动登录；输入 `username`、`password`。
- `POST /auth/login`：建立新会话。
- `GET /auth/me`：恢复当前 Cookie 会话并取得 CSRF token。
- `POST /auth/logout`：校验 `X-CSRF-Token` 后撤销服务端会话。

Cookie 认证的 `POST /v1/chat/completions` 同样要求 `X-CSRF-Token`。API Key Bearer 请求不依赖 Cookie，因此不要求 CSRF header。完整接口和迁移说明见 [账号认证与画像隔离](docs/account_authentication.md)。

## 测试

运行全部测试：

```bash
.venv/bin/pytest -q
```

当前基线为 `294 passed`，其中 4 项真实 HTTP 测试会绑定 `127.0.0.1` 临时端口。覆盖密码和令牌非明文存储、v1→v2 迁移、账号隔离、JSON/SSE 契约、课程目录校验与分级、上下文解析、StudyKit 安全投影、材料引用白名单、概念解释、练习选择/反馈降级、隐藏字段防泄漏、多语言静态诊断、生成管线和真实本地 HTTP/SSE。

## 安全与隐私

- 用户名不区分大小写；允许 3–32 位 ASCII 字母、数字、点、下划线和连字符。
- 密码长度为 12–128 个字符，使用 Argon2id（19 MiB、2 次迭代、并行度 1、随机 salt）。
- 数据库仅保存会话令牌的 SHA-256 摘要；原始令牌只存在于浏览器 HttpOnly Cookie。
- Cookie 写操作使用会话绑定的 HMAC CSRF token，并拒绝非 allowlist Origin。
- API 响应设置 CSP、`nosniff`、`DENY` framing 和 `no-referrer`。
- 首版不支持邮箱、找回密码、修改密码、账号删除或完整对话历史；用户仍可发送“删除我的画像”删除画像事实。
- 只索引公开、开放许可或用户有权使用的课程材料；不提供可提交的完整作业答案。

## MVP 范围

最低可交付版本覆盖：

- 1 门经过审核的课程；
- 3–5 个讲次；
- 1 个可重复演示的核心讲次；
- 带来源锚点的 StudyKit；
- 至少一个材料答疑、代码辅导和学习复盘场景；
- 至少三个可以绕过完整向导的直接功能入口。

大规模课程收集、真实代码沙箱、完整知识图谱、复杂长期记忆、音频输入和高级附件输出均不阻塞 MVP。

## 材料与合规

- 只索引公开、开放许可或用户有权使用的材料；
- 不绕过登录、付费、地域或技术访问限制；
- 不镜像和重新分发无授权的整套课程资料；
- 不生成可替代原材料的整份受保护内容；
- 不直接提供可提交的完整作业答案；
- 公共模板课程、用户私有资料和用户学习状态相互隔离；
- 未收录资料无需匹配模板课程；不能确认的课程身份保持未知；
- 用户文件 URL 仅允许受信任的清小搭 OSS 域名，防止 SSRF；
- 没有可靠沙箱时只进行静态代码分析，不声称已经运行代码。
- API Key 请求的 `user` 是客户端提供的逻辑标识，不是授权凭据，只能映射为 `legacy:<user>`；网页登录只使用服务端验证的 `account:<uuid>`。
- 画像不保存完整对话或代码；模型推断只作为 7 天待确认候选，确认前不参与正式建议。

## 文档

- [文档索引](docs/README.md)
- [账号认证与画像隔离](docs/account_authentication.md)
- [项目状态](PROJECT_STATUS.md)
- [全局进度](docs/project_status.md)
- [Developers Guide](docs/developers_guide.md)
- [平台发布记录](docs/platform_release.md)
- [平台验证记录](docs/platform_validation.md)
- [StudyKit 分阶段生成](docs/studykit_generation.md)

## 开发状态说明

仓库已经包含账号注册/登录与安全会话、OpenAI 兼容服务、规则优先的意图路由与能力目录、可信 subject 学习画像、CSDIY 课程导航、只读黄金 StudyKit 查询/材料/概念/练习能力、多语言静态代码辅导，以及完整的分阶段生成内核。Lecture 2/8 的原始 PDF 和抽取 chunks 仅保留在本地；线上 SourceChunk 检索、未收录私有资料、跨会话练习状态和学习复盘仍属于后续阶段。
