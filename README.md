# CoursePilot

CoursePilot 是一个面向中文计算机科学自学者的循证学习 Agent。仓库目前包含可审计的 StudyKit 离线生成内核、OpenAI 兼容 Agent 服务，以及带账号隔离的学习画像、课程导航、已审核 StudyKit 学习能力和静态代码辅导 MVP。

## 当前能力

- `GET /v1/models` 和 `POST /v1/chat/completions`，支持非流式 JSON 与 SSE；模型 ID 固定为 `coursepilot-probe`。
- 旧的 `Authorization: Bearer <COURSEPILOT_API_KEY>` 调用保持兼容，包括可选 OpenAI `user` 字段。
- 本地网页支持用户名注册、密码登录、会话恢复和注销，不再要求用户在浏览器中输入服务器 API Key。
- 网页将助手回复渲染为经过清洗的 Markdown、表格、语法高亮代码和原生 MathML 公式；用户消息与错误仍按纯文本显示，模型提供的原始 HTML、脚本和远程图片不会进入 DOM。
- 每个账号可以保存、查看和删除最小学习画像：学习方向、每周时间和明确陈述的技术基础。
- 画像按服务端账号 UUID 隔离；不保存完整对话、用户代码、traceback 或模型推理。
- 清小搭 API Key 请求支持顶层 `sessionId`：服务端只保存最小课程/讲次/练习连续状态，默认滑动保留 30 天；原始 ID 经 HMAC 后才入库，不保存完整 messages。
- 在线 Agent 已接入有界 TaskPlan、`/help` 能力目录、主动学习画像、课程导航、多语言静态代码辅导和受约束的通用学习问答兜底。
- 课程导航读取完整 CSDIY registry；精确查询和列表保持确定性，个性化推荐会同时使用全部 confirmed 学习画像（包括“没有编程基础”等负向背景）及全课程学习决策索引，并分成“现在开始/长期目标”。目录分类、离线 authoring 和在线 StudyKit 三种状态仍由后端可信渲染，未审核 candidate offering 不作为官方链接输出。
- StudyKit 查询、材料问答、课程概念解释、练习选择和当前答案反馈已经上线；默认读取层优先使用归档中 build/document 均为 `approved` 的记录，并回退到 Schema 合法、人工批准的 Lecture 2/8 黄金 StudyKit。当前归档有 9 个 approved build、220 个 approved StudyKit；golden 重复身份被归档优先覆盖，组合 Store 共提供 220 个在线 StudyKit。
- 分阶段 StudyKit 生成器执行 Evidence → Content → Practice → Audit → 确定性组装，并输出 JSON/YAML/Markdown。
- standard authoring 要求每道练习从 EvidencePlan/课程内容派生出具体、可求解的设置和可观察结果；
  独立审计者逐题复核内容关联、证据锚点和形成性质量。该语义门禁仍只在线下执行。
- selective practice repair 只在线下运行：从直接父 build 快照创建新的 fingerprinted build，
  rich audit 必须绑定当前 build+repair plan，并逐题精确覆盖当前 practice IDs（无缺失、重复或
  过期 ID）；任一不匹配都阻止完成和 false-complete，Schema 通过本身不足以放行。六课修复
  已达到 161/161 validated、161/161 audited 和 6/6 build succeeded；其中五课仍等待课程级
  visual-review closure，因此尚不能宣称 catalog 全局 complete。
- 已提供独立的 SQLite StudyKit 归档，保存每门课唯一的最新 build、最终 StudyKit、阶段 checkpoint 和验证/审计文本工件；课程归档与账号数据库隔离，`validated_draft` 不会自动上线。
- `data/` 已迁移为私有 Git submodule，并由 Git LFS 管理 SQLite 与 anchored chunks。当前精简
  快照包含 12 builds、286 个 StudyKit 和 12,010 个审计/阶段工件（含 CS186 身份修复 plan/audit）；原始 PDF、站点镜像、页面图
  和 reviewed 重复包不上传。

公共 SourceChunk 的 permission-first FTS5 接口和在线 adapter 已接入，但当前 checkout 没有可用的 approved 索引，因此材料问答仍会回退到 StudyKit，不能回答其未覆盖的任意原文细节。私有 MaterialSet、向量检索和学习复盘尚未上线；代码辅导当前只做静态分析，不执行用户代码。

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

用户可以检索 119 个现有课程目标；其中多数分类仍待独立审核，只有引用受控 Manifest 的课程才展示官方课程页。当前 220 个 approved archive StudyKit 可以进入在线学习，MIT 6.7960 Lecture 2/8 golden 保留为安全回退。未收录私有资料仍是后续能力，不会与公共目录或账号画像混合。

## 核心能力

- 主动学习画像：从用户明确陈述中识别学习方向、目标、基础、每周时间和讲解偏好；网页登录按账号保存，受信 API Key 客户端可使用 `legacy:<user>` 逻辑隔离，并支持查看、纠正和删除。
- 意图路由与帮助：规则优先、结构化模型兜底；`/help` 或“你有哪些功能”只列已上线能力。未上线能力仅保留帮助/状态说明，不得成为可执行路由；自然语言请求统一转入带明确能力边界的通用回答。
- 通用学习问答：专用能力无法覆盖当前学习请求时，使用一般知识直接回答；除最近最多 30 条/48,000 字符对话、已确认画像值和最小验签连续状态外，始终获得 119 门课程的安全极简索引，并按需获得最多 12 门学习者可见详情。模型 prose 与后端验证的课程 metadata 分区保存，不冒充课程材料、不运行代码、不提供可提交的完整作业答案。
- 课程导航：按课程名、学校、课程号或已确认学习方向检索 CSDIY registry；个性化推荐每阶段最多 3 门，列表最多 5 门，并明确区分目录、离线和在线状态。模型失败时只展示明确标注的未个性化方向候选。
- StudyKit 学习：查询学习包、按页码白名单回答材料问题、分层解释概念、选择不重复练习，并只对携带 practice ID 的当前答案给反馈。
- 代码辅导：支持按语言和约束生成最小完整示例，也可解释、诊断、审阅、修复、重构代码并设计测试；Python/Triton 使用 Python AST，其余主流语言使用离线 Tree-sitter 对输入或生成代码做结构检查。所有输出保持 `ran_code=false`，预期行为不冒充运行结果，也不代写可提交作业。
- 已审核 StudyKit 读取：统一 `StudyKitStore` 使用 220 份 approved archive StudyKit 优先、Lecture 2/8 golden 回退；不输出 `expected_evidence`、evaluation、rubric、本地路径或审计字段。
- 离线 StudyKit 生成：生成包含目标、前置知识、提纲、术语、练习、引用和限制说明的中文学习包。
- 检索基础：公共 SourceChunk 的 FTS5 范围过滤和运行时接线已完成；仍需发布 approved 索引，并继续实现 MaterialSet 权限、私有/向量检索和学习复盘。

## 技术路线

项目采用“清小搭平台入口 + 自研 Agent 后端”的架构：

```text
清小搭智能体广场
        ↓ OpenAI 兼容协议
协议适配层：鉴权、JSON、SSE、错误处理、文件 URL
        ↓
Agent 编排：意图路由、主动画像、课程导航、StudyKit 学习、多模式静态代码教练
        ↓
只读课程表与 approved archive/golden StudyKit；后续接入 MaterialSet、RAG 与复盘
```

当前已实现的接入契约包括：

- `POST /v1/chat/completions`；
- `GET /v1/models`；
- Bearer Token 鉴权；
- 非流式 OpenAI 兼容 JSON；
- 流式 SSE：role、content、stop、`data: [DONE]`；
- `usage`、`finish_reason`、脱敏服务错误和流式错误处理；
- 可选 OpenAI `user` 字段，用于本地/受信网关下的画像逻辑隔离。
- 可选顶层 `sessionId`，用于清小搭同一对话的服务端连续状态；响应不回传该字段。字段缺失或为空时按新会话处理。

清小搭文件 URL、音频输入和 PDF/PPT/Word 等附件尚未接入，不阻塞文本版 MVP。

## 当前阶段

截至 2026-08-20，项目处于“离线 StudyKit 生成与私有检索数据归档完成、220 份归档 StudyKit 经门禁或明确 legacy 人工批准上线、在线 Agent 与安全富文本学习界面已接入，公共 SourceChunk 检索基础已接线但等待 approved 索引与清小搭生产验证”阶段：

| 项目 | 状态 |
| --- | --- |
| 产品目标与 MVP 边界 | 已完成 |
| 用户流程与验收场景 | 已完成 |
| 清小搭接入协议调研 | 已完成 |
| 自研后端架构与仓库结构 | 已完成最小实现 |
| OpenAI 兼容 API 实现 | 已完成 |
| Bearer、Cookie 会话、`sessionId`、JSON、SSE 和错误契约测试 | 已完成；完整 Python 回归通过 |
| 本地账号、会话、CSRF 与画像隔离 | 已完成安全 MVP |
| TaskPlan、能力帮助、通用学习兜底、主动画像和多语言静态代码辅导 | 已完成首版 |
| CSDIY 课程导航 | 已完成全目录分级检索；目录分类仍按 registry 审核状态展示 |
| StudyKit 查询、材料/概念、练习选择/反馈 | 已完成 approved archive + golden 回退首版；公共 SourceChunk adapter 无索引/命中时严格降级 |
| 本地聊天测试界面 | 已接入账号登录、功能总览、画像、课程、StudyKit、练习和代码辅导入口；助手 Markdown/表格/代码/MathML 安全渲染通过 Chrome 验证 |
| 云端部署方式 | 已确认，等待生产版本部署 |
| 首个模板课程与核心讲次冻结 | 已完成：MIT 6.7960，Lecture 2 和 8 为核心 Demo |
| CourseManifest 与来源审核 | 已完成初稿 |
| Lecture 2 黄金 StudyKit | v0.1 已通过 Schema、引用、术语、公式方向复核和人工批准 |
| Lecture 8 StudyKit | v0.1 已完成 Schema、引用、术语、公式方向、练习事实性复核和人工批准 |
| 全课程 portable StudyKit 包 | MIT 6.7960 Lecture 01–21、23、24 共 23 讲已完成离线验证，并按仓库所有者的 reviewed-legacy 结论批准上线 |
| SourceChunk Schema 与 PDF 页级解析 | 已完成；Lecture 2、8 的 chunks 已在本地生成并通过校验，未随公开仓库上传 |
| 黄金 StudyKit 在线读取 | 已完成：Lecture 2、8，只读人工批准版本；统一 `StudyKitStore` 接口 |
| 私有检索数据归档 | 已完成精简快照：12 builds、286 documents；9 builds/220 documents 为 `approved`，其余 3/66 保持 `validated_draft` |
| 数据库 StudyKitStore | 已完成只读接入：build/document 双 `approved` 门禁，portable v0.1/v0.2.1 兼容，golden 回退 |
| 六课 practice repair | 161/161 validated、161/161 audited、6/6 build succeeded；五课仍需关闭课程级视觉复核 |
| 线上 SourceChunk 检索与 RAG | 公共 permission-first FTS5 接口和运行时 adapter 已完成；当前无 approved 索引，私有/向量检索未上线 |
| 清小搭接入探测与试聊 | 本地契约与真实 DeepSeek 多轮已验证；平台账号侧待实测 |
| 端到端 Demo、评测和用户试用 | 尚未开始 |

当前关键路径是：

1. 完成仍被门禁阻断的 CMU 15.213、MIT 6.031 和 UCB CS61B partial builds，并继续保持双 `approved` 在线门禁；
2. 为现有公共 FTS5 运行时发布 approved SourceChunk 索引并完成检索质量验收；
3. 冻结 MaterialSet/权限接口，将现有 course/version/unit 过滤扩展到 owner/session/material_set，再接入私有材料、练习反馈检索和学习复盘；
4. 验证清小搭稳定用户身份、消息历史、文件输入、状态和日志能力；
5. 将通过测试的后端部署到生产环境并完成端到端评测。

## 本地运行

先初始化私有数据 submodule 和 Git LFS 对象（需要该私有仓库的访问权限）：

```bash
git submodule update --init --recursive
git -C data lfs pull
```

StudyKit 检索归档位于 `data/archive/studykits.sqlite3`。完整边界见
[私有数据 submodule 说明](docs/private-data-submodule.md)。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

React/TypeScript 前端源码位于 `frontend/`，生产静态资源生成到并提交于 `app/static/`。修改前端后使用 Node 24：

```bash
npm ci
npm run build
```

仅运行已提交静态资源时不需要 Node；`app/static/` 整体由 Vite 生成，不要直接编辑，
应修改 `frontend/` 后重新构建。

设置本地接入密钥。配置 `DEEPSEEK_API_KEY` 后会启用统一理解、画像感知课程排序、通用学习问答、画像候选、语义材料问答、当前练习答案反馈和语义代码辅导；不配置时通用问答透明降级，课程导航仍可精确查询和列出课程，个性化推荐则明确降级为未个性化候选；StudyKit 查询、概念解释和练习选择仍可用，材料问答返回最相关的已审核摘要，练习反馈不做粗略判分：

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
| `COURSEPILOT_CONVERSATION_TTL_DAYS` | `30` | 清小搭 `sessionId` 最小连续状态的滑动有效期 |
| `COURSEPILOT_COOKIE_SECURE` | `false` | HTTPS 生产环境必须设为 `true` |
| `COURSEPILOT_ALLOWED_ORIGINS` | 当前请求 Origin | 可选，逗号分隔的网页登录 Origin allowlist |
| `COURSEPILOT_TEST_MODE` | `false` | 仅测试使用 |
| `COURSEPILOT_ROBUST_INPUT` | `true` | 启用自然语言、内联代码、压平围栏及中文讲次/页码解析；首个发布周期可设为 `false` 回退旧 Planner 路径 |
| `DEEPSEEK_API_KEY` | 无 | 可选；启用在线统一理解、通用学习问答、画像/材料问答/练习反馈/语义辅导，并用于离线生成 |

生产环境必须使用 HTTPS、持久化受限权限的数据库卷，并在反向代理层增加全局登录/注册限流。应用内限流只覆盖单进程实例。

## 认证接口

- `POST /auth/register`：创建账号并自动登录；输入 `username`、`password`。
- `POST /auth/login`：建立新会话。
- `GET /auth/me`：恢复当前 Cookie 会话并取得 CSRF token。
- `POST /auth/logout`：校验 `X-CSRF-Token` 后撤销服务端会话。

Cookie 认证的 `POST /v1/chat/completions` 同样要求 `X-CSRF-Token`。API Key Bearer 请求不依赖 Cookie，因此不要求 CSRF header。完整接口和迁移说明见 [账号认证与画像隔离](docs/account_authentication.md)。

## 测试

运行完整 Python 测试：

```bash
.venv/bin/pytest -q
```

当前 Python 基线为 `623 passed`。覆盖密码和令牌非明文存储、v1→v2→v3 迁移、账号与 `sessionId` 命名空间隔离、30 天滑动过期、CAS 并发保护、状态库故障降级、未上线能力路由失败关闭、JSON/SSE 契约、课程目录与 archive 门禁、全课程安全知识投影、画像感知课程排序、统一自然语言理解、浏览器签名与网关服务端连续状态、可信讲次继承、练习指代、通用学习兜底、静态代码诊断、生成管线和本地 HTTP/SSE。

前端门禁另包含 18 项 Vitest 单元测试和 7 项使用本机 Chrome 的 Playwright 流程：

```bash
npm run check
npm run test:e2e
```

这些测试覆盖 Markdown/MathML/代码渲染、DOM 清洗、SSE/JSON 终止与大小边界、Cookie/CSRF、认证竞态、原始多轮历史、复制代码和移动端横向溢出；Playwright 使用已安装的 `chrome` channel，不下载浏览器或系统依赖。

真实 DeepSeek 后端端到端验收不属于 pytest，使用合成消息、临时画像数据库和真实受审核 Store：

```bash
.venv/bin/python scripts/run_live_backend_e2e.py --suite smoke
.venv/bin/python scripts/run_live_backend_e2e.py --suite full \
  --report /tmp/coursepilot-live-e2e-full.json
```

运行器不会输出 Key、完整 prompt、模型正文、用户代码或画像证据，只报告场景结果、调用次数、usage 和延迟。
整改设计、用户/开发者双视角验收和完整新手测试流程见
[自然语言鲁棒性整改与端到端验证](docs/live-novice-agent-remediation-validation-20260819.md)。

## 安全与隐私

- 用户名不区分大小写；允许 3–32 位 ASCII 字母、数字、点、下划线和连字符。
- 密码长度为 12–128 个字符，使用 Argon2id（19 MiB、2 次迭代、并行度 1、随机 salt）。
- 数据库仅保存会话令牌的 SHA-256 摘要；原始令牌只存在于浏览器 HttpOnly Cookie。
- `sessionId` 与可信身份命名空间一起 HMAC 后索引 Schema v3 的最小连续状态；不存原始 ID、完整对话、代码、答案或模型推理。
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

仓库已经包含账号注册/登录与安全会话、OpenAI 兼容服务、有界 TaskPlan 与通用学习兜底、可信 subject 学习画像、CSDIY 课程导航、只读 approved archive + golden StudyKit 查询/材料/概念/练习能力、多语言静态代码辅导，以及完整的分阶段生成内核。公共 SourceChunk 的 permission-first FTS5 接口与材料问答 adapter 已实现，但当前 checkout 未部署 approved 索引；未收录私有资料、向量检索、跨会话练习状态和学习复盘仍属于后续阶段。
# Online Agent P0–P2

The online runtime's current planning, provenance, public retrieval, continuity-token, course-advice,
and static tutoring contracts are documented in
[`docs/online-agent-p0-p2.md`](docs/online-agent-p0-p2.md). Private MaterialSet access, cross-system
identity, and vector retrieval remain deferred.

Online model-call policy: TaskPlan is separate; each concrete capability uses at most one model call.
Practice selection automatically clarifies the selected approved question into explicit givens,
constraints, and deliverables, while invalid/model-unavailable output falls back to the original.
General assistance is a terminal fallback with confirmed profile values and a maximum
30-message/48,000-character window; it emits only uncited general-knowledge answers.
Disable this presentation layer with `COURSEPILOT_PRACTICE_REWRITE_ENABLED=false`.
