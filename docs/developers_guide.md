# CoursePilot Developers Guide

更新时间：2026-08-10

本文说明下一阶段如何在现有 StudyKit 生成内核之上开发用户画像、代码辅导、资料检索、意图路由、清小搭多轮 Agent，以及 generator skill。本文的核心约束是：

> StudyKit 生成是慢速的离线 authoring 流程；Agent 在线请求必须优先读取数据库中已经生成并审核过的 StudyKit，不能在用户对话请求内同步等待生成。

## 1. 当前状态与设计结论

当前生成内核已经完成以下工作：

- `skills/studykit-generator` v0.2.0 已完成并批准发布；四讲对齐盲评选择 `standard` 为默认质量挡位，调用方仍可显式选择 `fast` 或 `strict`。
- `quality_mode` 与 `delivery_policy` 已分离；前者控制生成/视觉复核深度，后者控制 unresolved 是否允许交付。
- unit 可按宿主能力并行，同一 unit 的 01→05 保持顺序；每阶段 checkpoint，并记录 worker 与 coordinator 墙钟时间。
- standard 的后续优化聚焦公式与证据表示：JSON round-trip 后的 LaTeX、逐页 `formula_unresolved`、索引约定，以及可见页面与隐藏叠加文本的明确边界。

- 当前 Pipeline：`studykit-pipeline-v0.11-019`；Prompt：`studykit-staged-v0.8-010`；运行版本：`21`。
- Evidence → Content → Practice → Audit → 确定性组装的分阶段流程已经可运行。
- Audit 只执行一次；blocker 会按字段所有权归一化、去重，并按 Evidence → Content → Practice 依赖顺序最多回修一次。
- 回修保护已有 `concept`、`requirement`、`control`、`opportunity` ID；修复后仍标记为 `repairs_applied_unverified`。
- PracticeFlow/StudyKit 的学习顺序带有必填 `practice_ids`，每道练习必须至少出现一次。
- 标题优先取 manifest 的 `official_resource_title > unit.title`；`EvidencePlan` 等内部标签不会进入学习者文本。
- 生成器会输出 `01-evidence-plan.json`、`02-learning-content.json`、`03-practice-flow.json`、`04-quality-audit.json`、`04-quality-audit.resolution.json`、`05-studykit.json`、`studykit.yaml`、`studykit.md`、`run.json` 和 `validation.json`。

最新外部回归为 Lecture 1–8、concurrency=8、8/8 成功，平均人工质量分 91/100。所有结果通过确定性验证，但修复后的语义没有二次 Audit；因此数据库必须保存 `review_status`，不能把“生成成功”直接当成“已发布”。

2026-08-10 的 host-authored portable 构建已覆盖官方可用的 23 讲并全部通过确定性
验证；经随机语义抽查后，紧凑包已保存到
`data/reviewed/mit-6.7960-fall-2024/portable-v0.1.0/`，状态为“批准待数据库导入”。
统一 chunks 保存在忽略版本控制的 `data/sources/.../full-course-v0.1.0/`。
数据库导入器必须适配 portable `citation.anchor` 结构；在适配完成前，在线运行时
继续只读现有 golden 文件。

当前在线 API 已从固定回显升级为首批 Agent 运行时：`app/api/chat_completions.py`
仍只负责 OpenAI 协议，实际编排位于 `app/agent/`。运行时已经执行主动学习画像、
规则优先的意图路由和 Python 静态代码辅导，并可只读 Lecture 2/8 人工批准的
黄金 StudyKit。完整 Catalog、SourceChunk 检索、材料答疑、练习反馈和复盘仍未接入。
慢速 generator 继续与 `/v1/chat/completions` 严格隔离。

账号是当前唯一可信的本地用户身份。Cookie 会话解析为 `account:<uuid>`；旧的
API Key 客户端继续把 OpenAI `user` 映射到 `legacy:<user>`。请求体 `user`
不能覆盖账号身份。完整认证、CSRF 和数据库迁移契约见
[账号认证与画像隔离](account_authentication.md)。

当前自动化测试基线为 `210 passed`。在线模型通过现有 `DeepSeekModel` 惰性加载；
未配置 `DEEPSEEK_API_KEY` 时规则路由、显式画像抽取和 Python AST 诊断仍可用。

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

### 3.4 manifest 与 SourceChunk 的获取和 bootstrap

Skill 的输入不是“必须事先存在的两个路径”，而是一个可选的课程上下文加任意数量、任意格式的原始资料集合。已有 manifest/chunks 时复用；缺失时，Skill 必须先完成 ingestion/bootstrap，再进入 StudyKit authoring：

```text
原始资料（PDF / 网页 / Markdown / DOCX / PPTX / 图片 / 用户文件，数量不限）
  → 资料清单、权限和哈希
  → 选择确定性 parser；无 parser 时由当前模型做受约束的结构化归一化
  → Source / MaterialSet / Unit 与 manifest 候选
  → 带来源锚点的 SourceChunk 集合
  → 身份、权限、Schema、覆盖和 provenance 门禁
  → Evidence → Content → Practice → Audit → StudyKit
```

两条输入路径必须同时被 Skill 支持：

1. **已有产物**：从 Catalog/Job 或本地 fixture 读取 CourseManifest/MaterialManifest 与 SourceChunk JSONL，重新校验后直接进入 authoring。
2. **bootstrap**：调用者只提供原始资料时，Skill 先枚举每个资料、分配稳定 `source_id`/`material_set_id`、计算哈希并判断 scope；对每个来源选择 parser。PDF 等已有本地 parser 的格式优先使用确定性脚本；没有可用 parser 的格式由当前模型从原文/文件内容生成候选 manifest、单位划分和 SourceChunk，但必须保留原文片段、来源 ID、可复核锚点、`parser_version`、`parse_warnings` 和 `provenance= model_assisted`。

当前仓库的确定性 PDF 路径是 `scripts/build_course_chunks.py`；它执行文本抽取、空白/噪声归一化、重复行去除、页码锚点和 `schemas/source_chunk.schema.json` 校验，不调用模型。当前仓库的本地 fixture 是：

```text
manifest:
  data/manifests/mit-6.7960-fall-2024.yaml
chunks:
  data/sources/mit-6.7960-fall-2024/lecture-02/chunks.jsonl
```

模型生成的 manifest 只能是候选：课程身份、官方标题、来源许可、权限和 URL 等代码/人工审核字段没有证据时必须保持 `null`/`unknown`，不得臆造。模型生成的 chunks 只能做可追溯分段和格式归一化，不能把摘要冒充原文证据；每个 chunk 必须保留原始引用片段或可定位的原文范围，并标注模型辅助风险，进入人工或确定性门禁后才能用于 StudyKit。

任意数量资料应先形成一个 `MaterialSet`，保留每个 `source_id` 和 source-specific anchor；若资料属于不同课程、版本、权限或无法确认的单位，Skill 必须拆成多个 material set/unit，而不是混合生成。当前 v0.1 生成器仍只接受单 source 和 page/整数 anchor，因此要实现本节的任意格式/数量能力，Skill 需要在进入生成器前完成分源、单位拆分或扩展 SourceChunk/引用适配层；不能静默绕过现有限制。

当前仓库的本地 fixture 是：

```text
manifest:
  data/manifests/mit-6.7960-fall-2024.yaml
chunks:
  data/sources/mit-6.7960-fall-2024/lecture-02/chunks.jsonl
```

公共模板课程的 manifest 由课程目录/人工审核流程维护，包含 `course_id`、`course_version`、`unit_id`、官方标题和已批准的 `source_id`、哈希、权限与许可信息。生产环境中它们应来自 Catalog/数据库或对象存储，而不是由在线 Agent 自由选择文件。

PDF 资料先由 ingestion 解析为保留页码锚点的 SourceChunk。例如本地开发可以使用：

```bash
.venv/bin/python scripts/build_course_chunks.py \
  --pdf <approved-pdf> \
  --output data/sources/<course-version>/<unit-id>/chunks.jsonl \
  --material-set-id <material-set-id> \
  --course-id <course-id> \
  --course-version <course-version> \
  --unit-id <unit-id> \
  --source-id <source-id> \
  --scope public
```

该命令只负责解析和 `SourceChunk` Schema 校验，不负责生成学习内容。私有资料必须使用 `--scope private --owner-id <owner-id>`，并在数据库层绑定当前用户；不能把私有 chunks 放入公共 manifest 或公共索引。网页标题锚点、多来源资料和混合 material set 需要在 ingestion 层拆分或扩展 Schema，不能让 Skill 绕过身份校验。

Skill 的调用者应从 Catalog/Job 传入已解析的 `manifest_ref` 和 `chunk_set_ref`（本地开发时可以是上述路径），并同时传递其 hash、`material_set_id`、`unit_id`、parser/schema 版本和权限上下文。Skill 必须重新核对 manifest 与所有 chunks 的课程、版本、讲次、来源和 material set；任一输入缺失或不一致时返回 `fix_inputs`/`awaiting_ingestion`，不得让模型猜测 manifest 或补写 chunks。

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

首版已经实现。画像事实保存在 SQLite，代码辅导只读取确认后的必要画像字段；
两者共享编排和 StudyKitStore，但不保存用户代码，也不把代码表现自动当作长期掌握度。
由于 SourceChunk 检索尚未完成，课程上下文当前只来自黄金 StudyKit。

### P2：资料检索系统

先实现带严格元数据过滤的关键词/BM25 检索，再按真实使用效果增加向量检索和重排。检索必须同时支持原始 SourceChunk 和学习者可见 StudyKit 内容，但需要标记来源类型，避免把生成摘要误当作原始证据。

### P3：意图识别与路由

首版已经实现。路由在任何课程读取前确定任务类型，规则高置信命中时不调用模型；
其余请求通过结构化 DeepSeek 输出分类。置信度低于 `0.70` 或课程身份不能由
StudyKitStore 验证时只返回一个澄清问题。

### P4：清小搭主题 Agent 和多层对话

现已在保留 OpenAI 兼容协议的前提下替换固定回显。协议层只负责鉴权、请求解析、
SSE/JSON 响应和错误契约；画像、路由和代码辅导位于应用层。后续检索、答疑和复盘
也必须沿用这一边界。

### P5：generator skill

稳定的离线生成流程现已包装为模型可读的 `studykit-generator` v0.2.0 skill。Skill 是 authoring 规范和操作流程，由被调用的 Agent/模型直接阅读并撰写阶段产物；它不调用外部模型，也不应成为普通用户在线问答时的隐式同步工具。需要批量、无人值守生成时，另行使用 provider-specific CLI 或后台 Job。

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

当前实现位于 `app/profile/`，采用追加事实表而不是覆盖整份 JSON。网页登录使用
`account:<uuid>`，API Key 请求的可选 OpenAI `user` 映射为 `legacy:<user>`；有可信
subject 时默认保存到 `storage/coursepilot.sqlite3`，也可通过 `COURSEPILOT_DB_PATH`
指定路径。没有逻辑用户标识的 API Key 请求只从本轮 `messages` 建立临时画像。
明确陈述直接为 `confirmed`；模型推断为 7 天过期的 `inferred` 候选，确认前不参与
正式建议。画像不保存完整对话、代码或 traceback。

API Key 请求中的 `user` 只是客户端提供的逻辑标识，不是授权凭据，不能访问
`account:` 命名空间。清小搭稳定用户身份尚未完成账号级验证，因此 legacy 持久画像
只适用于受信网关；本地网页使用服务端验证的账号会话。

### 5.3 画像与 StudyKit 的连接

- 用 `learning_objectives.id` 作为稳定的能力键，不在画像中复制整段课程文本。
- 用 `prerequisites` 建立前置诊断项，用 `practice.objective_ids` 连接练习证据。
- 用 `learning_sequence` 生成下一步建议，但不把完成阅读自动视为掌握。
- 当 StudyKit 版本变化时，保留旧画像证据，并执行 objective ID 映射；不能静默覆盖历史记录。
- 画像不能改变原始 StudyKit、课程身份或用户权限。

当前实现位于 `app/profile/`，保存用户明确提供的学习方向、目标、每周分钟数、技术
基础和讲解偏好，支持查看、纠正、单项删除、拒绝记录和全部删除；模型推断只作为
7 天待确认候选。这是 LearnerState 的安全最小切片，不保存完整消息、代码或推断型
掌握度；后续扩展必须继续使用认证层提供的 trusted subject，不能重新信任客户端 `user`。

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

该接口已经在 `app/code_tutor/` 实现。Python 使用 `ast.parse` 和少量保守规则；
其他语言只提供标记为静态的模型建议。`ran_code` 在当前版本恒为 `false`。模型只
能返回上下文允许列表中的 citation token，再由代码映射到人工审核 StudyKit 的
真实 source/page。`expected_evidence`、evaluation rubric 和 authoring 字段在
构造 Prompt 前被移除。作业完整解答请求在调用模型前由确定性规则拒绝。

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

当前 `/v1/chat/completions` 没有后台 authoring 权限入口，因此即使规则或模型识别为
`admin_generate_studykit` 也只返回拒绝说明。首版实际 handler 为
`profile_analysis`、`code_tutoring` 和 `fallback_clarification`；其他意图会被正确
识别，但透明说明尚未接入，不生成课程事实。

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

本地网页还支持 `/auth/register`、`/auth/login`、`/auth/me` 和 `/auth/logout`。
`/v1/*` 同时接受 API Key Bearer 和账号 Cookie；Cookie 写请求必须带
`X-CSRF-Token`，API Key 客户端不受该要求影响。协议层只把可信 subject 交给
画像/检索模块，不允许能力模块自行解析用户名、Cookie 或请求体 `user`。

协议适配层不能依赖清小搭一定提供持久会话。每轮请求应能从 `messages` 恢复最小上下文；如果平台提供稳定会话 ID，再把它作为数据库索引，而不是唯一事实来源。

当前实现保持 `coursepilot-probe` 模型 ID 兼容，并将可选 `user` 透传到画像层。
本地网页会在浏览器 `localStorage` 生成匿名 UUID；清空聊天不会删除画像，用户需要
发送“删除我的画像”执行服务器侧删除。

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

Skill 的目标是让被调用的 Agent 直接完成一个可追溯的“课程单位离线 authoring”动作，而不是隐藏一个外部 LLM client。现有 `skills/studykit-generator/SKILL.md` 已实现证据规划、内容撰写、练习设计、分挡 Audit、修复、组装、验证、并行计划和计时记录；本节同时作为其集成规范。

Skill 与现有 `scripts/generate_studykit.py` 的边界必须保持清楚：后者是显式配置 DeepSeek 的批处理 CLI，可以由后台任务调用；前者不读取 API key、不创建 provider client、不发起网络请求，也不把失败转交给另一个模型。当前 Agent 就是实际的撰写者。

当前仓库已提供可直接调用和打包安装的 `studykit-generator` v0.2.0。四讲独立生成、匿名盲评、Critical 人工复核、默认挡位决策和全仓库测试均已完成，可进入发布流程。

### 10.1 Skill 输入

```text
materials[]（任意数量的已授权文件、文本或文件引用）
manifest_ref（可选；已有 CourseManifest/MaterialManifest，本地可为路径）
chunk_set_ref（可选；已有 SourceChunk 集合，本地可为 JSONL 路径）
unit_id
output_dir 或 artifact_store key
language（默认 zh-CN）
target_minutes（默认 180）
quality mode（fast/standard/strict，默认 standard）
delivery policy（draft/publish，默认 draft）
```

调用者还应提供已知的 `course_id`、`course_version`、`material_set_id`、输入 hash、parser/schema 版本和权限上下文；未知字段可以为空，便于 Skill 在 bootstrap 中生成候选。Skill 必须先检查：若 manifest/chunks 已提供则验证其身份；若缺失则对 `materials[]` 执行清单、parser 选择、manifest/chunk 候选生成、provenance 标注和门禁。权限和许可必须允许使用，输出目录不能是已有不同版本的目录。Skill 不要求、不读取或转发任何外部模型 API key；模型调用由宿主 Agent 自身完成，因此 skill 的输入不包含 provider、endpoint、model 或 retry 配置。

当 `materials[]`、`manifest_ref` 和 `chunk_set_ref` 都缺失时，Skill 返回 `awaiting_materials`；当资料存在但没有可复核文本/锚点时返回 `ingestion_failed` 或 `needs_human_review`，不能直接生成 StudyKit。

### 10.2 Skill 输出

```json
{
  "status": "succeeded",
  "build_id": "…",
  "unit_id": "lecture-02",
  "review_status": "audit_repairs_applied_unverified",
  "ingestion_status": "reused | deterministic | model_assisted | needs_human_review",
  "artifacts": {
    "manifest": "…",
    "chunks": "…",
    "ingestion_report": "…",
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

- 让当前模型先按 `SKILL.md` 完成 ingestion/bootstrap，再写阶段 JSON；不要在 skill 中 import `DeepSeekModel`、读取 `DEEPSEEK_API_KEY` 或调用任何远程 endpoint。
- `materials[]` 不得因格式或数量被静默丢弃。为每个来源写入 ingestion report；确定性 parser、模型辅助归一化和人工确认必须可区分、可恢复、可审计。
- 只复用仓库中的 Schema、SourceChunk、manifest 和确定性工具；`scripts/validate_studykit.py` 与 `scripts/render_studykit.py` 可用于本地检查和渲染。需要多 source、heading/slide/paragraph anchor 时，先扩展 Schema/引用适配层，再调用 StudyKit 生成核心。
- 固定 Pipeline/Prompt/Schema 版本并写入 `run.json`；保留 `validation.json` 和 audit resolution，便于诊断和人工复核。
- `resume` 只对完全相同的输入和版本指纹开放；版本变化必须新建 build。若上下文中没有旧阶段产物，不要伪造 resume。
- Skill 允许宿主使用隔离子任务并行处理 unit；同一 unit 内阶段保持顺序，coordinator 独占 ingestion、fingerprint 和批次汇总。provider 客户端与凭证仍不属于 skill。
- Standard authoring 在装配前检查 LaTeX 单层转义、EvidencePlan 公式/索引覆盖、逐页 unresolved 记录和隐藏文本边界；这些检查不扩大为 strict 的全页复核。
- Skill 不读取或输出 `reasoning_content`，不把内部评估字段暴露给学习者。
- 交付前运行本地 Schema、引用、学习顺序和 Markdown 检查；出现未解决 blocker 时不输出成功 Markdown。

## 11. 建议的代码目录

当前目录可以逐步演进为：

```text
app/
  api/                 # 清小搭/OpenAI 兼容协议
  auth/                # 密码、账号、会话、CSRF 与限流
  agent/               # context、intent、router、orchestration
  catalog/             # Course、Unit、MaterialSet、StudyKitBuild
  profile/             # LearnerProfile 与证据更新
  code_tutor/          # 静态代码诊断和辅导
  retrieval/           # parser、index、search、citation
  generation/          # StudyKitGenerator 与模型适配
  jobs/                # 离线生成、索引和重试队列
  storage/             # 共享 SQLite 迁移、后续对象存储与权限
skills/
  studykit-generator/  # 开发者/后台离线生成 skill
```

能力模块应返回结构化结果，再由 Agent renderer 统一生成 OpenAI JSON/SSE。不要让 profile、retrieval 或 code tutor 直接拼接 SSE 帧。

其中 `app/agent/`、`app/catalog/studykits.py`、`app/profile/` 和 `app/code_tutor/`
已经落地。Catalog 当前是只读文件适配器，storage 当前只覆盖画像 SQLite；jobs、
MaterialSet 数据库和在线 retrieval 仍是后续工作。

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

以上 P1 条件已由自动化测试覆盖；“代码辅导包含课程引用”仅在课程/讲次能匹配
Lecture 2/8 黄金 StudyKit 时成立。通用代码问题会明确没有课程来源上下文。

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
- generator skill 在没有 manifest/chunks 时能从单个或多个 PDF、网页、Markdown、DOCX/PPTX 和用户文件完成 ingestion/bootstrap；已有确定性 parser 时优先复用，否则生成带 provenance 的模型辅助候选；
- generator skill 不静默丢弃资料，能保留每个 source、scope、anchor 和 ingestion report，并完成 mock smoke test、真实 Lecture smoke test 和失败恢复测试。

## 13. 开发者第一步

建议按以下顺序开工：

1. 将当前只读黄金 StudyKitStore 演进为 `StudyKitBuild`、`StudyKitDocument` 和
   `SourceChunk` 的正式数据库读取接口，并保留独立 `review_status`。
2. 实现 MaterialSet、owner/session 权限和最小关键词检索；事实引用优先回到
   原始 SourceChunk。
3. 在现有意图路由中接入 StudyKit 查询、材料答疑、练习反馈、学习复盘和生成状态。
4. 将当前画像事实表连接到 StudyKit objective/prerequisite 和用户确认的练习证据，
   但继续禁止由阅读行为自动推断掌握度。
5. 完成清小搭稳定用户身份、文件输入、长会话、生产日志和删除策略实测。
6. 最后把稳定的离线入口包装成 `studykit-generator` skill，并加入批量任务与人工复核队列。

生成器是课程 authoring 基础设施，不是在线聊天中的即时工具；只要坚持离线优先、StudyKit 优先、原始 SourceChunk 可追溯、公共/私有资料隔离，后续五项工作可以逐步接入而不会被单次长模型调用绑死。
