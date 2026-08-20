# CoursePilot 项目状态

更新时间：2026-08-20

这份文档是新开发者的快速入口。更完整的状态矩阵见
[docs/project_status.md](docs/project_status.md)，生成管线说明见
[docs/studykit_generation.md](docs/studykit_generation.md)。

## 一句话概括

CoursePilot 已完成可运行、可恢复、可审计的 StudyKit 分阶段生成内核，
并已落地本地账号注册/登录、Cookie 会话和可信 subject 画像隔离，同时将意图路由、
能力帮助、主动学习画像、CSDIY 课程导航、StudyKit 查询/材料/概念/练习能力和
多语言静态代码辅导接入 OpenAI 兼容对话 API；公共 SourceChunk 的 permission-first FTS5
接口和材料问答 adapter 已接线，但当前没有 approved 在线索引，私有资料权限、向量检索和
学习复盘仍未接成完整闭环。

本地学习界面现使用 Vite/React/TypeScript 构建：助手输出支持安全 Markdown、表格、代码高亮和
原生 MathML，用户消息与错误保持纯文本。模型原始 HTML、脚本、危险链接和远程图片均被阻断，
并保持现有严格 CSP、Cookie/CSRF 与内存会话边界。

2026-08-12 已将 `outputs/` 中每个课程版本的最新有效成果归档为
`data/archive/studykits.sqlite3`：12 builds、286 个 StudyKit；初始 12,008 个文本 checkpoint/
审计工件，CS186 身份修复后增加至 12,010 个，完整性复核为零问题。2026-08-13 又将 `data/` 迁移为私有
`JaamesQin/csdiy_agent-data` submodule，并用 Git LFS 管理 SQLite 与 anchored chunks。
2026-08-17 按 Schema、引用、逐题审计、build 完整性和归档身份一致性门禁完成批量人工批准；
MIT 6.7960 与 MIT 6.S081 另按仓库所有者的 reviewed-legacy 结论保留逐项豁免记录后批准。
UCB CS186 由直接父快照生成新指纹身份修复 build 并重新通过 exact-set 门禁。当前 9 个 build、
220 个 StudyKit 为 `approved`，其余 3 个 partial build、66 个 StudyKit 保持 `validated_draft`。
组合 Store 当前提供 220 个在线 StudyKit。

当前最成熟的链路是：

```text
课程 PDF
  → 页级 SourceChunk
  → EvidencePlan 与课程特定 evidence controls
  → LearningContent
  → PracticeFlow
  → 单次 QualityAudit 与依赖顺序回修
  → 确定性 StudyKit JSON/YAML/Markdown
  → Schema、引用、渲染和内部字段检查
```

## 当前已经完成

### StudyKit 标准与黄金样例

- 已冻结学科无关的 StudyKit v0.1 标准、SourceChunk Schema 和学习者渲染规则。
- Lecture 2 和 Lecture 8 的人工审核 StudyKit 继续作为质量评测样例；
  黄金样例不得反向写入通用 Prompt。
- 学习者版本隐藏 `expected_evidence`、评价规则和内部控制字段。
- 单题反馈只评价当前回答，不保存累计正确率或推断长期掌握度。

### 分阶段自动生成器

- 已实现 `StudyKitGenerator.generate(request, chunks)`。
- Evidence 阶段从本讲 SourceChunks 发现概念、评估要求、练习机会、
  `evidence_controls` 和来源风险。
- Content 和 Practice 只能继承 EvidencePlan 中存在的课程约束；
  术语翻译由 Content 统一负责。
- Audit 只运行一次；blocker 按 Evidence → Content → Practice 的依赖顺序
  各回修至多一次，不进行第二次语义 Audit。
- Audit blocker 在修复前会做字段所有权归一化和去重；Evidence、Content、Practice
  修复按依赖顺序传播。Audit 修复不会擅自改变原有 concept、requirement、control
  和 opportunity ID；新增或删除身份字段会被确定性拒绝或恢复。
- Audit 发现下游需要边界外的有效来源块时，会先修 EvidencePlan，
  再修对应 Content 或 Practice。
- 现已补充内容对齐的练习质量合同：每道练习必须有材料支持的具体设置、可观察结果、
  一致的提示/证据要求和相关锚点；同一单元的独立审计者必须逐题复核。该合同通过
  author prompt 与审计实现，不引入领域专用硬编码语义验证器。
- 已加入 offline-only selective repair：新 build 保存直接父快照，rich audit 绑定当前
  build 与 repair plan，并要求当前 practice ID 的逐题精确覆盖，不得缺失、重复或沿用
  stale ID。任一覆盖或绑定不匹配均阻止完成/false-complete；确定性 Schema 通过不是语义放行。
  六课 repair 已完成 161/161 validated、161/161 audited，六个最终 build 均为 `succeeded`；
  其中五课尚未关闭 course-level visual review，所以 catalog 仍不能标记全局 complete。
- 最终 StudyKit 由代码确定性组装，并校验 Schema、引用、顺序、唯一 ID、
  Markdown 可渲染性和内部字段泄漏。

### 模型调用可靠性

- 使用官方 DeepSeek OpenAI 兼容接口，阶段输出上限为 65,536 tokens。
- 空正文最多重试三次，非法 JSON 最多重试两次，长度截断最多重试一次。
- 重试保持同一 thinking 配置和完整上下文，不通过切换为 non-thinking
  规避空正文，也不复用截断正文。
- 每次调用保存 finish reason、token usage、request ID 和重试诊断。
- Pipeline 当前版本为 `studykit-pipeline-v0.11-019`，运行版本为 `21`；
  Prompt 当前版本为 `studykit-staged-v0.8-010`。

### Schema、工具与课程资料

- 已新增 EvidencePlan、LearningContent、PracticeFlow、QualityAudit 四个 Schema。
- 私有 `data` submodule 的精简远端保留 catalog、manifests、golden、anchored chunks、
  source/preparation provenance 和最新 SQLite；raw PDF、站点镜像、页图、reviewed 重复包及
  regression 仅可作为 ignored 本地数据。初始化命令见 `docs/private-data-submodule.md`。
- 已提供生成 CLI、质量 profile 评估脚本和 Lecture 并发回归调度器。
- MIT 6.7960 Fall 2024 manifest 已覆盖官方可用的 23 讲：Lecture 01–21、23、24；
  官方缺失的 Lecture 22、25 未创建占位单元。
- 23 讲 portable StudyKit 已完成结构、引用与渲染验证；其正式 archive 记录已按
  reviewed-legacy 人工结论批准并进入在线查询。被精简 submodule 排除的 reviewed/SourceChunks
  快照只可作为 ignored 本地数据；在线运行时使用合法 approved archive，并以既有 golden 回退。
- MIT 6.S081 Fall 2021 的 24 个有实质来源讲次也已完成 artifact、review 和
  输出一致性复核，并经 Lecture 07、15、17 随机语义/视觉抽查；正式 archive 已按
  reviewed-legacy 人工结论批准，raw、chunks、页图、reviewed 重复包和完整 build 不进入精简远端。
- Outline 页码只要求存在于本讲输入 SourceChunks，不要求每页都进入
  Content 的最小证据并集。
- Practice 的 Prompt 仍要求 5–8 题；验证器允许合理超出，以避免模型偶发
  数量偏差导致整讲失败。`simple` 题数量不设上限，但禁止复杂数值链。

### 多用户账号与学习画像

- 本地网页提供开放式用户名注册、密码登录、会话恢复和注销；密码使用
  Argon2id，数据库只保存会话令牌的 SHA-256 摘要。
- Cookie 使用 HttpOnly、SameSite=Strict；Cookie 认证的写请求需要会话绑定
  CSRF token，并校验浏览器 Origin。
- 账号画像 subject 固定为 `account:<uuid>`；旧 API Key 的 OpenAI `user`
  映射到 `legacy:<user>`，两个命名空间不能互访。
- SQLite Schema v3 保留历史画像并将其迁移到 legacy 命名空间，并增加了经 HMAC 索引的最小会话连续状态；未知数据库
  版本拒绝服务启动。
- 当前保存用户明确提供的学习方向、目标、每周时间、技术基础和讲解偏好；
  模型推断只作为 7 天待确认候选，不保存完整对话、代码、traceback 或模型推理。

### 在线 Agent 运行时

- `/v1/chat/completions` 已从固定回显切换为协议层之后的独立 Agent 编排层；
  OpenAI JSON、SSE、Bearer 和 `coursepilot-probe` 模型 ID 保持兼容。
- 在线理解生成有界 TaskPlan；专用能力优先，无法归类或规划校验失败时进入受约束的
  `general_assistance`，不再借用生成状态或只返回固定澄清。通用能力最多读取最近 30 条、
  48,000 字符对话及 confirmed 画像，并只输出无课程引用的一般知识。
- 能力目录集中维护已上线和未上线能力；`/help` 当前展示画像、代码辅导、课程导航、
  StudyKit 查询、材料问答、概念解释、练习选择、练习反馈和通用学习问答，Help 不触发画像观察。
- 未上线能力仅作为 Help/状态 metadata，Router、TaskPlanner 和执行入口均禁止将其作为可执行任务。
  明确的学习复盘、生成状态等自然语言请求转入 `general_assistance`，并向模型传入最小、受控的未上线能力边界。
- Cookie 会话只向 Agent 传入 `account:<uuid>`；API Key 请求的可选 `user` 只映射为
  `legacy:<user>`。画像支持查看、纠正、单项删除和全部删除。
- API Key 请求的可选顶层 `sessionId` 已接入 Schema v3 服务端连续状态。它仅在
  `account:`/`legacy:` 可信命名空间内生效，原始 ID 不入库，默认滑动保留 30 天；缺失或空值按新会话处理。
  状态只包含已验证课程/讲次、当前练习和最小指代信息，不保存 messages、代码、答案或 reasoning。
- 代码辅导使用 Python AST 与自包含 Tree-sitter language pack；C/C++、CUDA、
  ISPC、LaTeX、Java、Go、Rust、OCaml、Verilog、汇编等进入确定性结构解析，
  课程专用 DSL 明确降级为模型静态建议。所有路径始终返回 `ran_code=false`，
  作业代写请求由规则守卫阻断。
- 在线课程上下文读取 220 份 approved archive StudyKit，并保留 Lecture 2/8 中 Schema
  合法且人工批准的黄金 StudyKit 回退；
  材料模型只能引用允许列表内的真实页码，学习者输出不含 `expected_evidence`、
  evaluation、rubric、审计字段或本地路径。
- `CourseCatalogStore` 校验 119 个 CSDIY 课程目标、唯一身份、导航 provenance 和受控
  Manifest；安全课程知识投影把全量身份/方向/入门与后续价值提供给在线决策，同时排除路径、哈希、候选探测和审计诊断。课程导航精确查询保持确定性，个性化排序读取全部 confirmed 画像并分为“现在开始/长期目标”。
- `StudyKitLookupService` 已实现查询、材料问答、概念解释、练习选择和当前答案反馈；
  未配置模型时材料问答返回已审核摘要，练习反馈不做粗略判分。练习答案和历史均不持久化。
- 未配置 `DEEPSEEK_API_KEY`、模型失败或画像数据库不可用时均透明降级；个性化课程排序失败时明确标注为未结合画像的方向候选；通用问答不会进行
  第二次生成尝试，其他确定性能力仍能启动和响应。

### Web 客户端与学习者渲染

- `frontend/` 是 React/TypeScript 源码，Vite 将可部署文件构建到 `app/static/`；FastAPI 继续从同源 `/static` 提供资源，不引入 CDN、内联脚本或内联样式。
- 助手回复使用 MarkdownIt、Highlight.js、KaTeX 的 MathML-only 输出和 DOMPurify；Markdown 原始 HTML关闭，远程图片、脚本、表单和危险 URL 不可渲染。
- 流式回复可以增量预览，但发送给下一轮的历史始终保留原始 Markdown，不从已渲染 DOM 反向取值；用户文本、错误和用户名始终使用文本节点。
- 桌面 Chrome 与 `390×844` 移动视口已验证注册、会话恢复、CSRF、SSE、表格/代码/公式、复制代码和页面级无横向溢出。

### 测试状态

- 当前自动化测试：`623 passed`（Python 完整回归）；另有 18 项前端单元测试和 7 项 Chrome Playwright 流程。覆盖全课程知识投影、画像感知排序、能力可用性问句短路、未上线能力失败关闭与通用边界回答、浏览器签名与清小搭 `sessionId` 服务端连续状态、可信讲次继承与显式换课/换讲、练习 ID/位置别名、状态库故障降级、通用学习兜底和 loopback HTTP/SSE 回归。
- 测试覆盖阶段 Schema、Evidence controls、确定性 chunk 并集、引用、
  Markdown LaTeX、模型响应重试、恢复、单次 Audit 回修、非 CS 合成单元、
  CLI、质量 profile、数据库迁移、密码/会话安全、CSRF、限流、账号隔离、
  API Key 兼容、意图路由、画像生命周期、SQLite 并发、课程目录失败关闭、
  StudyKit 安全投影、材料/概念引用白名单、练习反馈降级、代码静态分析、
  学术诚信以及真实 HTTP/SSE。
- 最新一次有记录的 Lecture 1–8 外部并发回归（concurrency=8）结果为 `8/8`：
  8 讲均生成 JSON/YAML/Markdown，均通过确定性验证，未解决 blocker 为 0。
  详细机器摘要属于未纳入精简 submodule 的历史本地 regression 数据。
- 回归耗时约 26 分 42 秒；每讲学习时间均为 180 分钟，练习数为 8–9 道。
  共有 8 个 warning，全部由对应阶段模型修复；空响应重试 24 次后全部成功。
- 8 讲最终质量人工评分平均 `91/100`：Lecture 1 93、Lecture 2 85、
  Lecture 3 90、Lecture 4 91、Lecture 5 94、Lecture 6 91、Lecture 7 93、
  Lecture 8 91。所有结果仍标记为 `repairs_applied_unverified`，因为设计上不做
  二次语义 Audit。
- 当前残留重点是 Lecture 2 离线 profile 缺少规范 `forward pass` 概念和
  `transfer` 题型，以及 Lecture 8 对 LayerNorm 可学习参数的表述需要核对原始材料。

## 当前代码入口

| 功能 | 位置 |
| --- | --- |
| 分阶段生成器 | `app/generation/generator.py` |
| DeepSeek 模型适配与重试 | `app/generation/model.py` |
| 通用阶段 Prompt | `app/generation/prompts.py` |
| EvidenceBundle | `app/generation/evidence.py` |
| 阶段 Schema | `schemas/evidence-plan.schema.json` 等 |
| StudyKit 生成 CLI | `scripts/generate_studykit.py` |
| 八讲并发回归 | `scripts/run_lecture_regression.py` |
| PDF 解析 | `app/retrieval/parser.py` |
| 引用校验与渲染 | `app/retrieval/citations.py`、`app/retrieval/render.py` |
| 生成器测试 | `tests/generation/` |
| 账号与会话 | `app/auth/`、`app/api/auth.py` |
| 共享 SQLite 迁移 | `app/storage/database.py` |
| 在线 Agent 编排 | `app/agent/orchestrator.py` |
| 意图路由 | `app/agent/router.py` |
| 能力目录与 Help | `app/agent/capabilities.py` |
| CSDIY 课程目录与导航 | `app/catalog/courses.py`、`app/course_navigation/` |
| StudyKit 查询、材料/概念、练习 | `app/learning/` |
| 可信 subject SQLite 学习画像 | `app/profile/` |
| 静态代码辅导 | `app/code_tutor/` |
| 已审核 StudyKit 读取 | `app/catalog/studykits.py` |
| Web 前端源码与富文本渲染 | `frontend/` |
| FastAPI 部署静态资源 | `app/static/`（由 `npm run build` 生成） |

运行全部测试：

```bash
.venv/bin/pytest -q
npm run check
npm run test:e2e
```

## 尚未完成

1. 为 archive 文档完成独立人工批准，冻结 MaterialManifest、MaterialSet 和完整
   LearnerState 的最小接口；TaskPlan 与账号/画像事实基础已经实现。
2. 完成公共课程与用户私有资料的统一解析、存储、授权过滤、过期和删除。
3. 为已接线的公共 FTS5 检索发布 approved SourceChunk 索引并完成质量验收，再将
   当前 course/version/unit 范围扩展到 owner/session/material_set；按需要增加经审核的向量检索。
4. 让材料答疑在公共索引可用时使用已实现的 SourceChunk 路径，并继续把练习反馈、
   私有材料、学习复盘和后台生成状态接入同一权限边界。
5. 修复 Lecture 2 的离线 profile 对齐问题，核对 Lecture 8 的 LayerNorm 表述，
   并为 `repairs_applied_unverified` 结果安排人工语义复核。
6. 实现最小学习闭环，记录用户确认的学习证据，并输出概念、实现、
   迁移三个维度的复盘和下一步计划。
7. 完成清小搭账号级能力实测、生产部署、日志脱敏、失败诊断和安全测试。
8. 验收模板课程与未知私有资料两条端到端流程，再进行用户试用和 Demo 打磨。

这些工作可以在当前只读接口基础上并行开发；真正的串行依赖是：数据库导入和
公共 SourceChunk 索引发布可在现有只读接口上独立推进；私有检索仍必须先稳定
MaterialSet/权限接口，最后再关闭平台端到端和用户验收。

## 主要风险

- 引用页码存在不代表主张必然被来源支持，语义忠实性仍需模型审核和人工抽检。
- PDF 文本层会损坏公式、图形和阅读顺序，必要视觉结构不能完全自动恢复。
- 账号画像已经隔离；公共资料和用户私有 MaterialSet 尚未形成完整运行时授权链。
- 清小搭文件输入、稳定会话标识和文件保留能力仍需账号级实测。
- 本地网页登录已使用服务端验证的账号身份；API Key 请求的 `user` 仍只是逻辑标识，
  不是授权凭据，在清小搭稳定身份完成实测前只适用于受信网关。
- 在线代码辅导当前不执行代码；公共 SourceChunk 检索基础只接入材料问答，且当前没有
  approved 索引，因此实际课程引用仍来自 approved archive 或两份人工批准的黄金 StudyKit。
- v21 已完成新鲜模型全量回归并达到 8/8，但修复后未进行二次语义 Audit；
  外部模型结果仍需人工复核后才适合作为最终教材。

## 核心 Agent 完成定义

只有同时满足以下条件，才可以称核心 CoursePilot Agent 完成：

- 模板资料和私有资料统一映射为带权限的 MaterialSet；
- 检索按 owner/session/material_set、课程、版本和讲次过滤；
- 对话 API 可以路由生成、答疑、练习反馈、代码辅导和复盘；
- StudyKit 自动生成并通过 Schema、引用、渲染和安全检查；
- 模板课程和未知私有资料各完成一条端到端流程；
- 资料不足、身份未知、解析失败和模型失败都有透明降级；
- 清小搭生产入口、日志、安全和删除策略完成实测；
- 有固定离线评测、失败记录和真实用户试用结果。
# Online Agent P0–P2 status (2026-08-17)

Bounded multi-task planning, dependency-aware partial execution, source-partitioned provenance,
public FTS5 SourceChunk retrieval, optional signed conversation context, approved course-advice
sidecars, and artifact-bound static tutoring are implemented. Private MaterialSet authorization,
cross-system identity, per-candidate profile UI/schema, and reviewed vector retrieval remain deferred.

Online practice presentation now performs an automatic, single-call `structured_rewrite` without
mutating approved StudyKits. TaskPlan is budgeted separately; each concrete capability may call the
model once, and online profile/material second-pass reviewers were removed. Signed context v2 binds
only the active presentation kind/digest and remains backward compatible with v1.

Natural-language robustness now uses one model-owned turn understanding contract together with a
bounded TaskPlan. Deterministic code validates code spans, signed ordinals, Catalog/StudyKit identity,
profile mutations, evidence and permissions; it does not replace semantic understanding with keyword
tables. Inline/flattened code, Chinese unit/page references, correction phrasing, and context-bound
practice feedback no longer require learner-facing formatting workarounds. A
credentialed real-DeepSeek backend E2E runner validates the full Agent path outside offline pytest.
