# CoursePilot Developers Guide

更新时间：2026-08-08

本文说明下一阶段如何在现有 StudyKit 生成内核之上开发用户画像、代码辅导、资料检索、意图路由、清小搭多轮 Agent，以及 generator skill。本文的核心约束是：

> StudyKit 生成是慢速的离线 authoring 流程；Agent 在线请求必须优先读取数据库中已经生成并审核过的 StudyKit，不能在用户对话请求内同步等待生成。

## 1. 当前状态与设计结论

当前生成内核已经完成以下工作：

- 当前 Pipeline：`studykit-pipeline-v0.11-019`；Prompt：`studykit-staged-v0.8-010`；运行版本：`21`。
- Evidence → Content → Practice → Audit → 确定性组装的分阶段流程已经可运行。
- Audit 只执行一次；blocker 会按字段所有权归一化、去重，并按 Evidence → Content → Practice 依赖顺序最多回修一次。
- 回修保护已有 `concept`、`requirement`、`control`、`opportunity` ID；修复后仍标记为 `repairs_applied_unverified`。
- PracticeFlow/StudyKit 的学习顺序带有必填 `practice_ids`，每道练习必须至少出现一次。
- 标题优先取 manifest 的 `official_resource_title > unit.title`；`EvidencePlan` 等内部标签不会进入学习者文本。
- 生成器会输出 `01-evidence-plan.json`、`02-learning-content.json`、`03-practice-flow.json`、`04-quality-audit.json`、`04-quality-audit.resolution.json`、`05-studykit.json`、`studykit.yaml`、`studykit.md`、`run.json` 和 `validation.json`。

最新外部回归为 Lecture 1–8、concurrency=8、8/8 成功，平均人工质量分 91/100。所有结果通过确定性验证，但修复后的语义没有二次 Audit；因此数据库必须保存 `review_status`，不能把“生成成功”直接当成“已发布”。

当前在线 API 仍是清小搭协议探针：`app/api/chat_completions.py` 返回固定回显，并未接入真实课程、检索或 StudyKit。接下来的工作应在协议适配层之后增加 Agent 编排，不应把慢速 generator 直接塞进 `/v1/chat/completions` 请求处理函数。

当前本地生成器仍有明确边界：一个生成请求使用一个 `material_set_id`、一个课程单位、一个 source，并要求整数页码 anchor。多来源课程、网页标题 anchor、混合公共/私有资料需要先在 ingestion 层拆成可生成的 unit 或扩展生成器，不能由在线 Agent 临时拼接后绕过 Evidence 校验。

## 2. 总体架构

```text
课程 PDF / 用户文件
  → SourceChunk 解析与权限绑定
  → 离线生成队列
  → StudyKitGenerator
  → StudyKit 质量门禁
  → Catalog / StudyKit 数据库
  → 资料索引（SourceChunk + StudyKit）

清小搭
  → OpenAI 兼容协议适配层
  → 会话与上下文层
  → 意图路由
  → StudyKit / Retrieval / Profile / Code Tutor
  → 带来源的回答或下一步任务
```

在线请求的基本流程应当是：

```text
接收消息
  → 解析会话、用户、课程和讲次上下文
  → 识别意图
  → 读取对应 StudyKit（若存在）
  → 检索最小必要 SourceChunk / 用户代码
  → 调用对应能力
  → 输出答案、来源、任务状态和下一步建议
```

当 StudyKit 不存在或已经过期时，在线 Agent 应说明当前资料状态、使用已有 SourceChunk 回答可回答的内容，并提交离线生成任务。默认不在本轮等待生成完成。

## 3. StudyKit 生成对后续工作的影响

### 3.1 StudyKit 是课程能力的离线知识层

StudyKit 不是普通的长文本摘要，而是课程单位的结构化教学合同。后续能力应优先使用这些字段：

| StudyKit 字段 | 后续用途 |
| --- | --- |
| `course_id`、`course_version`、`unit_id`、`title` | 课程身份、路由和检索过滤 |
| `scope`、`outline` | 讲次边界、回答范围和课程导航 |
| `learning_objectives` | 用户画像中的目标掌握项、推荐下一步 |
| `prerequisites` | 前置知识诊断与补救建议 |
| `core_concepts`、`glossary` | 概念解释、术语统一和检索增强 |
| `common_misconceptions` | 纠错型回答和代码辅导中的概念检查 |
| `learning_sequence` | 学习计划、下一步活动和练习安排 |
| `practice` | 练习选择、练习反馈和迁移任务 |
| `citations` | 来源页码、证据锚点和回答引用 |
| `limitations`、`review` | 不确定性、材料缺口和人工复核提示 |

`expected_evidence`、评价规则、`evidence_controls`、内部诊断和模型调用信息属于 authoring/evaluation 数据。它们可以存储在受保护的数据库表中，但不能直接作为学习者可见文本或系统提示泄漏。

### 3.2 生成耗时决定了必须离线化

一次生成包含多个长响应阶段、独立 Audit、可能的 Evidence/Content/Practice 回修和确定性校验。当前 8 讲并发回归耗时约 26 分 42 秒；空正文重试也会增加耗时。由此产生以下实现规则：

1. 课程目录导入后，先批量建立离线生成任务。
2. 同一 `course_id + course_version + unit_id + material_set_id + pipeline_version + prompt_version` 只允许一个活动生成任务。
3. 生成任务必须可恢复、可重试、可观测；旧版本产物不能跨版本 resume。
4. 在线请求只读 `ready` 或明确允许的 `draft` StudyKit。
5. 生成失败不应阻塞课程浏览、资料检索或代码问题诊断。
6. 生成成功但 `review_status=repairs_applied_unverified` 时，面向用户的答案应保留来源和不确定性边界；是否可作为默认课程包由发布门禁决定。

### 3.3 推荐的生成状态

建议为每个课程单位维护独立的 `StudyKitBuild`：

```text
queued → running → generated → validated → ready
                         └────→ failed
ready → stale（输入、Prompt、Schema 或 Pipeline 版本变化）
```

建议字段：

```text
build_id
course_id
course_version
unit_id
material_set_id
input_fingerprint
manifest_hash
pipeline_version
prompt_version
model_name
status
review_status
output_dir / artifact_uri
validation_summary
created_at / started_at / finished_at
last_error
```

`ready` 表示确定性验证通过；`review_status` 单独表达 `approved`、`draft`、`audit_repairs_applied_unverified`、`needs_human_review` 等语义状态。不要用一个 `status` 字段同时表达运行状态和教学可信度。

## 4. 推荐实施顺序

用户提出的五项工作应按以下依赖顺序落地：

### P0：离线课程库和 StudyKit 读取层

这是所有在线能力的基础，但不属于用户可见功能：

- 选定首批模板课程与讲次；
- 将 SourceChunk 和 manifest 元数据导入数据库；
- 建立离线 `StudyKitBuild` 队列，批量生成并保存 YAML/JSON/Markdown；
- 建立 `get_ready_studykit(course, version, unit)` 读取接口；
- 为失败、过期、需要人工复核的产物提供状态查询；
- 将 StudyKit 和 SourceChunk 写入后续检索索引。

### P1：用户画像分析与代码辅导

这是第一批用户能力。画像分析应使用 StudyKit 的目标、前置知识、练习和用户确认证据；代码辅导应使用 StudyKit 的相关概念/练习和资料检索结果。两者共享会话、检索和权限层，但不要互相污染状态。

### P2：资料检索系统

先实现带严格元数据过滤的关键词/BM25 检索，再按真实使用效果增加向量检索和重排。检索必须同时支持原始 SourceChunk 和学习者可见 StudyKit 内容，但需要标记来源类型，避免把生成摘要误当作原始证据。

### P3：意图识别与路由

路由应在检索前确定任务类型、课程范围和所需上下文。能用确定性规则判断的场景不要每次调用模型；低置信度时再使用分类模型或小型 LLM，并要求结构化输出。

### P4：清小搭主题 Agent 和多层对话

保留现有 OpenAI 兼容协议，替换固定回显的内部实现。协议层只负责鉴权、请求解析、SSE/JSON 响应和错误契约；会话、路由、检索和能力执行放在应用层。

### P5：generator skill

最后把稳定的离线生成流程包装成开发者/运维可调用的 skill。Skill 用于课程 authoring、批量预生成、版本升级和诊断，不应成为普通用户在线问答时的隐式同步工具。

## 5. 第一批能力：用户画像分析

### 5.1 目标

用户画像不是根据一句话永久推断用户能力，而是维护可解释、可撤回、带时间和证据的学习状态。第一版只做课程学习相关画像：目标、前置知识、自评、练习表现、代码实践结果和用户主动确认的信息。

### 5.2 建议数据结构

```json
{
  "user_id": "…",
  "course_id": "…",
  "course_version": "…",
  "unit_id": "lecture-02",
  "goals": ["理解反向传播", "能够阅读训练代码"],
  "prerequisite_status": [
    {"item": "矩阵乘法", "level": "confirmed", "evidence_id": "…"}
  ],
  "objective_status": [
    {"objective_id": "ar-forward-pass", "status": "emerging", "evidence_id": "…"}
  ],
  "preferred_explanation_style": "example_first",
  "constraints": {"weekly_minutes": 180},
  "confidence": 0.7,
  "updated_at": "…"
}
```

必须区分：

- `confirmed`：用户明确确认，或存在可复查的练习/代码证据；
- `inferred`：系统暂时推断，必须带置信度和过期时间；
- `unknown`：没有足够证据，不得编造；
- `declined`：用户拒绝记录某项信息。

画像分析的输入优先级：

1. 用户明确陈述；
2. 用户确认的学习目标和限制；
3. StudyKit 中的 prerequisite/objective/practice 结构；
4. 练习回答、代码片段和反馈结果；
5. 模型推断，仅作为低置信度候选。

输出应包含“依据、置信度、建议下一步”，而不是只输出人格化标签。用户可以查看、修正和删除画像字段。

### 5.3 画像与 StudyKit 的连接

- 用 `learning_objectives.id` 作为稳定的能力键，不在画像中复制整段课程文本。
- 用 `prerequisites` 建立前置诊断项，用 `practice.objective_ids` 连接练习证据。
- 用 `learning_sequence` 生成下一步建议，但不把完成阅读自动视为掌握。
- 当 StudyKit 版本变化时，保留旧画像证据，并执行 objective ID 映射；不能静默覆盖历史记录。
- 画像不能改变原始 StudyKit、课程身份或用户权限。

## 6. 第一批能力：代码辅导

### 6.1 目标与边界

代码辅导先做“理解、诊断、验证、改进建议”，不直接提供可提交的完整作业答案。没有真实沙箱时只能做静态分析，并明确说明“未运行代码”。

典型流程：

```text
识别课程/讲次/练习
  → 读取对应 StudyKit objective、concept、practice 和 citation
  → 获取用户代码、错误信息、期望行为
  → 静态检查语法/形状/控制流/接口假设
  → 给出最小诊断、验证步骤和下一次尝试
  → 记录用户确认的代码学习证据
```

### 6.2 代码辅导上下文包

代码辅导不应把整门课程塞入 Prompt。建议构造带预算的 `CodeTutorContext`：

```text
unit identity
relevant learning objectives
one or two relevant concepts/glossary entries
one relevant practice question and public instructions
retrieved source chunks with page anchors
user code / traceback / test output
learner profile constraints
```

`expected_evidence` 和完整评分 rubric 只供受控的练习评估器使用。辅导模式只给学习者必要的提示、检查点和验证方法。

### 6.3 最小接口

建议先提供内部服务接口，而不是直接把实现写进 HTTP handler：

```python
async def tutor_code(
    *,
    user_id: str,
    conversation_id: str,
    course_context: CourseContext,
    code: str,
    error_text: str | None,
    question: str,
) -> TutorResult:
    ...
```

`TutorResult` 至少包含 `answer`、`citations`、`diagnostics`、`next_checks`、`ran_code` 和 `safety_notes`。`ran_code` 为 false 时不得用“运行结果表明”之类措辞。

## 7. 资料检索系统

### 7.1 数据边界

建议初版使用关系数据库保存权威元数据，使用数据库全文索引或独立检索引擎保存可搜索文本：

```text
Course
CourseVersion
Unit
MaterialSet
Source
SourceChunk
StudyKitBuild
StudyKitDocument
LearnerProfile
Conversation / Message
PracticeAttempt
CodeArtifact
GenerationJob
```

所有 `SourceChunk` 必须保留：`material_set_id`、`scope`、`owner_id`、`course_id`、`course_version`、`unit_id`、`source_id`、页码 anchor、`sha256`、parser version 和 parse warnings。公开模板资料与用户私有资料必须在查询层隔离，不能只靠 Prompt 约束。

### 7.2 检索接口

建议接口形态：

```python
async def search_materials(
    *,
    query: str,
    user_id: str | None,
    material_set_ids: list[str],
    course_id: str | None = None,
    course_version: str | None = None,
    unit_id: str | None = None,
    document_types: list[str] | None = None,
    top_k: int = 8,
) -> list[RetrievedChunk]:
    ...
```

默认过滤顺序：权限/`material_set_id` → 课程和讲次 → 文档类型 → 文本相关性 → 去重和上下文窗口。返回值必须包含 `chunk_id`、来源、页码、文本、相关性、scope 和索引版本。

### 7.3 StudyKit 如何进入检索

建议建立两类索引文档：

- `source_chunk`：原始材料，回答事实问题时优先；
- `studykit_section`：StudyKit 的概念、提纲、练习和限制，适合学习导航和解释。

回答中的事实引用优先落到 `source_chunk`；StudyKit 可以作为教学组织层和补充引用。若两者冲突，标记冲突并回到原始 chunk，不让生成摘要覆盖来源。

## 8. 意图识别与路由

### 8.1 建议的第一版意图集合

```text
course_navigation
studykit_lookup
material_question
concept_explanation
practice_selection
practice_feedback
code_tutoring
profile_analysis
learning_review
generation_status
admin_generate_studykit
fallback_clarification
```

普通用户请求不得直接触发 `admin_generate_studykit`；该意图只对后台任务、课程 authoring 或有权限的开发者开放。

### 8.2 路由顺序

```text
鉴权与租户识别
  → 解析 course/version/unit/material_set
  → 规则识别高置信意图
  → 低置信时调用结构化分类器
  → 检查所需上下文是否存在
  → 读取 StudyKit / 检索 / Profile
  → 调用能力
```

分类结果建议使用结构化对象：

```json
{
  "intent": "code_tutoring",
  "confidence": 0.93,
  "course_id": "…",
  "unit_id": "lecture-02",
  "required_context": ["user_code"],
  "clarifying_question": null
}
```

路由器不应自己回答复杂课程事实；它只负责决定能力、上下文和数据源。缺少课程身份时先询问或使用用户明确指定的私有资料范围。

## 9. 清小搭 Agent 与多层对话

### 9.1 协议层保持稳定

必须继续满足现有契约：

- `GET /v1/models`；
- `POST /v1/chat/completions`；
- `Authorization: Bearer <credential>`；
- `stream=false` 的 OpenAI 风格 JSON；
- `stream=true` 的 SSE：role → content → stop → `data: [DONE]`；
- 正确的 `finish_reason`、`usage` 和 HTTP 错误。

协议适配层不能依赖清小搭一定提供持久会话。每轮请求应能从 `messages` 恢复最小上下文；如果平台提供稳定会话 ID，再把它作为数据库索引，而不是唯一事实来源。

### 9.2 多层上下文

建议分为四层：

1. **Turn context**：当前问题、最近一轮回答、当前上传文件或代码。
2. **Conversation context**：会话摘要、已确认的课程/讲次、未完成任务、最近引用。
3. **Learner context**：用户主动确认的画像、偏好、学习限制和历史证据。
4. **Course context**：CourseManifest、StudyKit、SourceChunk 权限范围和版本。

每次调用只拼接完成当前任务所需的最小上下文。长会话使用摘要和结构化状态，不无限回传原始消息。模型返回的 reasoning 内容只用于当次展示，不写入下一轮用户消息或长期画像。

### 9.3 文件输入

清小搭文件通常以公网 OSS URL 传入。实现文件能力时必须：

- 只允许受信任 OSS 域名，防 SSRF；
- 收到请求后立即拉取 URL，不能把签名 URL 长期保存后再取；
- 校验类型、大小、超时和解析结果；
- 私有文件绑定当前 `owner_id`/`material_set_id`；
- 解析成 SourceChunk 后再进入检索或离线生成；
- 解析失败时返回可理解的降级信息，不伪造课程结论。

### 9.4 在线响应与离线任务

当用户问“帮我生成这一讲 StudyKit”时：

- 若已有 `ready` 版本，直接返回或提供学习入口；
- 若正在生成，返回任务状态和预计下一步，不重复创建任务；
- 若没有产物，创建后台 `GenerationJob` 并先提供资料检索/课程范围说明；
- 只有后台 authoring API 才允许等待或轮询完整生成结果。

这能避免清小搭网关超时，也能避免多个用户请求重复消耗长上下文模型调用。

## 10. 将 generator 包装成 skill

Skill 的目标是给开发者或后台 Agent 一个稳定的“课程单位离线生成”动作，而不是让普通用户直接调用内部脚本。

### 10.1 Skill 输入

```text
chunks_path
manifest_path
unit_id
output_dir 或 artifact_store key
language（默认 zh-CN）
target_minutes（默认 180）
generation policy（draft/strict）
```

Skill 必须先验证：manifest 与 chunks 的 course/version/unit/source/material_set 身份一致，文件可读，API 密钥已通过环境变量提供，输出目录不是已有不同版本的目录。

### 10.2 Skill 输出

```json
{
  "status": "succeeded",
  "build_id": "…",
  "unit_id": "lecture-02",
  "review_status": "audit_repairs_applied_unverified",
  "artifacts": {
    "studykit_json": "…",
    "studykit_yaml": "…",
    "learner_markdown": "…",
    "validation": "…",
    "run": "…"
  },
  "issues": [],
  "next_action": "human_review"
}
```

失败时必须返回 `failed_stage`、机器可读 issue、重试次数和可恢复性；不能只返回一段模型错误文本。

### 10.3 Skill 实现建议

- 用一个薄 wrapper 调用现有 `scripts/generate_studykit.py` 或 `StudyKitGenerator.generate()`，不要复制生成逻辑。
- 固定 Pipeline/Prompt/Schema 版本并写入 build metadata。
- 保留 `run.json`、`validation.json` 和 audit resolution，便于诊断和人工复核。
- `--resume` 只对完全相同的输入和版本指纹开放；版本变化必须新建 build。
- 提供单元生成和批量生成两种模式，批量模式限制并发和总预算。
- Skill 不读取或输出 `reasoning_content`，不把内部评估字段暴露给学习者。
- 提交前使用 mock model、最小 SourceChunk fixture 和一个真实已生成 Lecture 做 smoke test。

## 11. 建议的代码目录

当前目录可以逐步演进为：

```text
app/
  api/                 # 清小搭/OpenAI 兼容协议
  agent/               # context、intent、router、orchestration
  catalog/             # Course、Unit、MaterialSet、StudyKitBuild
  profile/             # LearnerProfile 与证据更新
  code_tutor/          # 静态代码诊断和辅导
  retrieval/           # parser、index、search、citation
  generation/          # StudyKitGenerator 与模型适配
  jobs/                # 离线生成、索引和重试队列
  storage/             # 数据库、对象存储、权限
skills/
  studykit-generator/  # 开发者/后台离线生成 skill
```

能力模块应返回结构化结果，再由 Agent renderer 统一生成 OpenAI JSON/SSE。不要让 profile、retrieval 或 code tutor 直接拼接 SSE 帧。

## 12. 验收标准

### P0 离线生成与数据库

- 可以批量创建课程单位生成任务，并做到幂等；
- 可以按课程版本和讲次读取 `ready` StudyKit；
- 失败任务保存 stage、issue、attempt、版本和输入指纹；
- public/private MaterialSet 查询严格隔离；
- 旧版本不能错误 resume；
- 生成任务不会阻塞在线聊天请求。

### P1 用户画像与代码辅导

- 画像每个结论都有来源、置信度和更新时间；
- 用户可以查看、修正和删除画像；
- 代码辅导回答包含相关 StudyKit/source citations；
- 未运行代码时明确说明，不能伪造测试结果；
- 对可提交作业只给诊断、提示和验证步骤，不直接代写完整答案。

### P2 检索与路由

- 检索结果带 `chunk_id`、页码、scope、material_set 和索引版本；
- 相同问题不会跨越用户权限或课程版本取资料；
- 路由低置信时先澄清，不把课程事实交给路由器臆测；
- 普通用户不能触发后台生成意图。

### P3 清小搭与 Skill

- 四项协议探测和多轮消息通过；
- SSE 不缓冲、不重复、不缺 stop/[DONE]；
- 会话超过上下文预算时能摘要而不是失败；
- 文件 URL 校验、解析、权限和超时有测试；
- generator skill 能完成 mock smoke test、真实 Lecture smoke test 和失败恢复测试。

## 13. 开发者第一步

建议按以下顺序开工：

1. 先建立 `StudyKitBuild`、`GenerationJob`、`StudyKitDocument` 和 `SourceChunk` 的数据库表及读取接口。
2. 使用当前 Lecture 1–8 产物填充离线 catalog，并把 `review_status` 保留为独立字段。
3. 实现 `profile_analysis` 和 `code_tutoring` 两个内部能力，均通过 StudyKit 读取层和检索接口获取上下文。
4. 为代码辅导准备静态分析器和“未运行代码”响应模板。
5. 再实现最小关键词检索和结构化意图路由。
6. 将路由接到 `/v1/chat/completions`，先保留非流式正确性，再接入 SSE 和长会话摘要。
7. 最后把稳定的离线入口包装成 `studykit-generator` skill，并加入批量任务与人工复核队列。

生成器是课程 authoring 基础设施，不是在线聊天中的即时工具；只要坚持离线优先、StudyKit 优先、原始 SourceChunk 可追溯、公共/私有资料隔离，后续五项工作可以逐步接入而不会被单次长模型调用绑死。
