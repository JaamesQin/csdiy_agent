# CoursePilot 项目状态

更新时间：2026-08-13

这份文档是新开发者的快速入口。更完整的状态矩阵见
[docs/project_status.md](docs/project_status.md)，生成管线说明见
[docs/studykit_generation.md](docs/studykit_generation.md)。

## 一句话概括

CoursePilot 已完成可运行、可恢复、可审计的 StudyKit 分阶段生成内核，
并已落地本地账号注册/登录、Cookie 会话和可信 subject 画像隔离，同时将意图路由、
能力帮助、主动学习画像和多语言静态代码辅导接入 OpenAI 兼容对话 API；资料权限、SourceChunk
检索、材料答疑、练习反馈和学习复盘仍未接成完整闭环。

2026-08-12 已将 `outputs/` 中每个课程版本的最新有效成果归档为
`data/archive/studykits.sqlite3`：12 builds、286 个 StudyKit、12,008 个文本 checkpoint/
审计工件，完整性复核为零问题。2026-08-13 又将 `data/` 迁移为私有
`JaamesQin/csdiy_agent-data` submodule，并用 Git LFS 管理 SQLite 与 anchored chunks。
数据库记录均为 `validated_draft`，未冒充人工批准或在线发布。

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
- 23 讲 portable StudyKit 已完成结构、引用与渲染验证，并经用户批准待未来数据库导入；
  紧凑包保存在 `data/reviewed/`，统一 SourceChunks 保存在本地 `data/sources/`，
  当前在线 Catalog 仍只读取既有 golden 文件。
- MIT 6.S081 Fall 2021 的 24 个有实质来源讲次也已完成 v0.2 artifact、review 和
  输出一致性复核，并经 Lecture 07、15、17 随机语义/视觉抽查。紧凑包仅本地保存在
  `data/reviewed/mit-6.s081-fall-2021/portable-v0.2.0/`；用户已确认派生 StudyKit
  可以上传，因此紧凑包进入 reviewed 目录，raw、chunks、页图和完整 build 仍留在 Git 外。
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
- SQLite Schema v2 保留历史画像并将其迁移到 legacy 命名空间；未知数据库
  版本拒绝服务启动。
- 当前保存用户明确提供的学习方向、目标、每周时间、技术基础和讲解偏好；
  模型推断只作为 7 天待确认候选，不保存完整对话、代码、traceback 或模型推理。

### 在线 Agent 运行时

- `/v1/chat/completions` 已从固定回显切换为协议层之后的独立 Agent 编排层；
  OpenAI JSON、SSE、Bearer 和 `coursepilot-probe` 模型 ID 保持兼容。
- 意图路由采用确定性规则优先、DeepSeek 结构化分类兜底；低置信请求先澄清，
  普通对话不能触发后台 StudyKit 生成。
- 能力目录集中维护已上线和未上线能力；`/help` 只展示学习画像与多语言代码辅导，
  `/help code`、`/help profile` 和对应自然语言询问返回具体用法，Help 不触发画像观察。
- Cookie 会话只向 Agent 传入 `account:<uuid>`；API Key 请求的可选 `user` 只映射为
  `legacy:<user>`。画像支持查看、纠正、单项删除和全部删除。
- 代码辅导使用 Python AST 与自包含 Tree-sitter language pack；C/C++、CUDA、
  ISPC、LaTeX、Java、Go、Rust、OCaml、Verilog、汇编等进入确定性结构解析，
  课程专用 DSL 明确降级为模型静态建议。所有路径始终返回 `ran_code=false`，
  作业代写请求由规则守卫阻断。
- 在线课程上下文只读取 Lecture 2/8 中 Schema 合法且人工批准的黄金 StudyKit；
  模型只能引用允许列表内的真实页码，内部 `expected_evidence` 和 rubric 不进入 Prompt。
- 未配置 `DEEPSEEK_API_KEY`、模型失败或画像数据库不可用时均透明降级，服务仍能启动和响应。

### 测试状态

- 当前自动化测试：`254 passed`（250 项普通测试，4 项 loopback HTTP/SSE 测试）。
- 测试覆盖阶段 Schema、Evidence controls、确定性 chunk 并集、引用、
  Markdown LaTeX、模型响应重试、恢复、单次 Audit 回修、非 CS 合成单元、
  CLI、质量 profile、数据库迁移、密码/会话安全、CSRF、限流、账号隔离、
  API Key 兼容、意图路由、画像生命周期、SQLite 并发、代码静态分析、
  学术诚信、引用白名单以及真实 HTTP/SSE。
- 最新一次全新 Lecture 1–8 外部并发回归（concurrency=8）结果为 `8/8`：
  8 讲均生成 JSON/YAML/Markdown，均通过确定性验证，未解决 blocker 为 0。
  详细结果见 `data/regression/studykit-v21-lectures-01-08/regression-summary.json`。
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
| 可信 subject SQLite 学习画像 | `app/profile/` |
| 静态代码辅导 | `app/code_tutor/` |
| 已审核 StudyKit 读取 | `app/catalog/studykits.py` |

运行全部测试：

```bash
.venv/bin/pytest -q
```

## 尚未完成

1. 冻结并实现 CourseManifest、MaterialManifest、MaterialSet 和 TaskPlan 的
   正式运行时接口；账号与画像事实表已完成，后续演进为完整 LearnerState。
2. 完成公共课程与用户私有资料的统一解析、存储、授权过滤、过期和删除。
3. 建立按用户、会话、课程、版本和讲次过滤的检索层；先关键词检索，
   再按需要增加向量检索和重排。
4. 在现有路由和代码辅导之上接入材料答疑、练习反馈、学习复盘、
   ready StudyKit 查询和后台生成状态。
5. 修复 Lecture 2 的离线 profile 对齐问题，核对 Lecture 8 的 LayerNorm 表述，
   并为 `repairs_applied_unverified` 结果安排人工语义复核。
6. 实现最小学习闭环，记录用户确认的学习证据，并输出概念、实现、
   迁移三个维度的复盘和下一步计划。
7. 完成清小搭账号级能力实测、生产部署、日志脱敏、失败诊断和安全测试。
8. 验收模板课程与未知私有资料两条端到端流程，再进行用户试用和 Demo 打磨。

这些工作可以在核心数据接口冻结后并行开发；真正的串行依赖是：
MaterialSet/权限与检索必须先提供稳定接口，Agent 编排随后接入，最后进行
平台端到端和用户验收。

## 主要风险

- 引用页码存在不代表主张必然被来源支持，语义忠实性仍需模型审核和人工抽检。
- PDF 文本层会损坏公式、图形和阅读顺序，必要视觉结构不能完全自动恢复。
- 账号画像已经隔离；公共资料和用户私有 MaterialSet 尚未形成完整运行时授权链。
- 清小搭文件输入、稳定会话标识和文件保留能力仍需账号级实测。
- 本地网页登录已使用服务端验证的账号身份；API Key 请求的 `user` 仍只是逻辑标识，
  不是授权凭据，在清小搭稳定身份完成实测前只适用于受信网关。
- 在线代码辅导当前不执行代码；课程引用仅来自两份人工批准的黄金 StudyKit，
  尚未接入原始 SourceChunk 检索。
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
