# CoursePilot MVP 完整实施计划

> 目标平台：清小搭智能体广场（标准协议接入；平台侧基于 AgentVerse 2.0）
> 计划版本：v1.3
> 制定日期：2026-07-15  
> 更新日期：2026-07-31

## 1. 项目目标

CoursePilot 是面向中文 CS 自学者的循证学习智能体。它以 CSDIY 学习路线为课程入口，帮助用户从公开、可信、可追溯的海外 CS 课程资料出发。用户既可以使用完整引导流程，也可以直接进入课程推荐、StudyKit、材料答疑、代码辅导或学习复盘中的任一功能。

推荐的完整学习闭环是：

```text
了解用户目标
    → 选择课程与版本
    → 选择一个讲次
    → 生成带来源的 StudyKit
    → 针对材料答疑或进行代码辅导
    → 提交学习证据
    → 复盘并生成下一步计划
```

该闭环是首次使用引导、完整学习体验和比赛 Demo 的推荐路径，不是强制操作顺序。实际使用采用“意图路由 + 必要信息检查”：系统先判断用户希望完成什么任务，只在执行当前任务确实缺少课程、版本、讲次、材料或代码上下文时追问，不要求用户补齐与当前任务无关的画像或前序步骤。

本计划只规划比赛周期内可上线、可演示、可评测的 MVP，不以“收集最多课程”作为成功标准。MVP 的核心价值是：用户能够基于正确版本的可信材料，实际完成一讲学习任务，并且能核查智能体输出的依据。

## 2. MVP 范围

### 2.1 MVP 必须完成

| 编号 | 能力 | MVP 范围 | 验收结果 |
| --- | --- | --- | --- |
| P0-1 | 清小搭标准协议接入 | 部署 OpenAI 兼容服务并接入清小搭，支持 Bearer 鉴权、非流式 JSON 和流式 SSE | `/v1/chat/completions` 与 `/v1/models` 通过平台探测；能从平台入口完成一次端到端流程 |
| P0-2 | 用户画像 | 在课程推荐或完整引导需要时，收集目标、基础、可用时间和偏好 | 输出简明画像并用于课程建议；其他直接入口不强制建档 |
| P0-3 | 课程导航 | 在受控课程池中推荐课程并确定版本 | 推荐 2–3 个候选；说明理由、前置缺口、时间和官网来源 |
| P0-4 | CourseManifest | 维护课程、学期、讲次、来源、访问和许可信息 | 每项资料可定位到确定课程版本和讲次 |
| P0-5 | 资料解析与索引 | 首先支持公开 PDF、网页/Markdown，以及通过 `file` URL 输入的用户授权材料；平台文件能力未上线或不稳定时使用预上传材料降级 | 检索片段保留来源与页码、标题或时间戳锚点；文件失败时有明确降级结果 |
| P0-6 | StudyKit | 为指定讲次生成结构化中文自学包 | 包含目标、前置、提纲、术语、顺序、练习、引用和限制 |
| P0-7 | 课程内答疑 | 只在确定的课程、版本和讲次上下文内回答 | 关键课程事实有证据；材料不足时不编造 |
| P0-8 | 代码辅导 | 对用户代码、报错或思路进行分层辅导 | 给出问题拆解、诊断假设、验证步骤、测试建议和代码审阅 |
| P0-9 | 学习复盘 | 使用小测、自评、代码/笔记结果更新本次学习状态 | 输出概念、实现、迁移三个维度和下一步任务 |
| P0-10 | 合规与安全 | 处理版权、学术诚信、隐私和代码风险 | 不分发无授权材料，不绕过限制，不代写可直接提交的答案 |
| P0-11 | 评测与 Demo | 建立固定样例、人工判分和演示脚本 | 有可复查的成功率、错误记录、修复记录和试用反馈 |
| P0-12 | 多入口意图路由 | 支持用户直接进入课程推荐、StudyKit、材料答疑、代码辅导或复盘 | 正确识别入口；只补问当前任务缺少的必要信息 |

### 2.2 MVP 建议规模

为控制风险，MVP 采用三级目标：

| 级别 | 课程数量 | 讲次数量 | 用途 |
| --- | ---: | ---: | --- |
| 最低可交付 | 1 门 | 3–5 讲 | 保证完整闭环和可靠 Demo |
| 目标版本 | 3 门 | 10–15 讲 | 展示跨课程复用能力 |
| 冲刺版本 | 6 门 | 30 讲 | 对应 Proposal 的中期量化目标，仅在质量达标后扩展 |

课程扩充必须在核心链路通过评测后进行。不能为了达到课程数量而降低来源、版本、引用或讲次结构的质量。

### 2.3 MVP 不做或后置

- 不承诺覆盖所有国内外 CS 课程；
- 不批量转载、镜像或重新分发整套课件、教材、视频、题库和作业；
- 不做整份受版权保护材料的替代性翻译；
- 不自动下载或转写所有课程视频；
- 不在首版构建完整课程知识图谱；
- 不构建复杂的跨月遗忘曲线和自适应推荐算法；
- 不把真实代码沙箱作为上线前置条件；
- 不支持任意课程、任意语言和任意运行环境的项目辅导；
- 不把效率工具百科和经典书籍大全放入核心开发路径；
- 不在主智能体未稳定前同时扩张技能专项赛范围；
- 不以复杂“多智能体”数量作为项目成果；
- 不把音频输入或可下载文件产物作为文本版 MVP 的上线前置条件；
- 不接收或持久化 base64 文件；多模态入参和附件出参统一使用 URL。

### 2.4 平台上线后的条件性增强

以下能力以清小搭实际开放并通过账号实测为前提，不得阻塞文本对话、StudyKit 和材料答疑的核心链路：

| 优先级 | 能力 | 启用条件 | 降级方式 |
| --- | --- | --- | --- |
| P0 条件项 | `file` 文档输入 | 平台已开放文件 content part，且 URL 拉取、大小限制和超时均通过实测 | 使用平台知识库、预上传样板资料或让用户提供公开链接 |
| P1 | `x_soda.attachments` 文件产物输出 | 平台能够解析附件字段并成功转存临时 URL | 在消息正文输出结构化 StudyKit |
| P1 | `input_audio` 音频输入 | 平台已开放且格式、大小和超时通过实测 | 请用户提供文本、字幕或讲义 |

接入文档曾将上述多模态能力标记为计划于 2026-07-31 前上线。截至 2026-07-31，本项目尚未保存账号实测结果，因此不能仅依据计划日期将其视为可用能力。音频大小限制在两份接口材料中分别为 25MB 和 200MB；未获得平台确认前按 25MB 的保守上限设计和测试，并在风险表中保留该待确认项。

## 3. MVP 用户故事与验收场景

### 3.1 推荐的完整用户故事

用户具备 Python 和基础算法知识，希望用六周学习一门系统或并行计算课程。他进入 CoursePilot 后：

1. 填写已有基础、学习目标和每周时间；
2. 查看 2–3 个课程候选及前置知识差距；
3. 选择一门确定版本的课程；
4. 选择一个讲次；
5. 获得带来源锚点的 StudyKit；
6. 针对材料中的概念继续追问；
7. 粘贴自己编写的代码或报错；
8. 根据提示完成验证，并提交小测或测试结果；
9. 获得本次掌握度复盘和下一步计划。

以上流程用于首次使用引导和完整 Demo。它不构成用户必须遵守的固定向导。

### 3.2 可直接进入的功能入口

用户可以从任意入口开始：

| 用户示例 | 识别出的入口 | 执行前需要检查的信息 |
| --- | --- | --- |
| “帮我推荐一门并行计算课程” | 课程推荐 | 学习目标、已有基础、可用时间；缺失时再询问 |
| “整理 CS149 第三讲” | StudyKit | 课程版本、讲次和可用资料 |
| “解释这份讲义第 12 页” | 材料答疑 | 用户材料及指定范围；若材料已上传则不再询问画像 |
| “这段代码为什么越界？” | 代码辅导 | 代码、报错、运行环境和用户尝试；课程信息仅在需要关联课程概念时询问 |
| “根据这次小测安排复习” | 学习复盘 | 小测结果、当前课程或学习目标 |

路由规则：

1. 先识别用户当前意图，而不是默认从画像开始；
2. 使用会话中已经确认的信息，不重复提问；
3. 只追问阻塞当前任务的必要信息；
4. 信息足够时立即执行任务；
5. 完成后可以推荐下一步，但用户可以结束、切换入口或忽略建议；
6. 用户意图不明确时，展示入口选择，而不是启动完整向导；
7. 用户切换课程或版本时，显式更新上下文，防止旧资料混入。

### 3.3 固定端到端验收场景

开发开始时选择唯一的 Demo 课程和唯一的核心讲次，冻结以下输入。固定 Demo 采用推荐的完整闭环，以便稳定展示所有核心能力，但不代表真实用户只能按此顺序使用：

- 用户基础；
- 学习目标和时间；
- 课程与学期；
- 讲次；
- 一个概念问题；
- 一个与课程概念相关的代码错误；
- 一组小测答案或代码测试结果。

端到端验收必须满足：

1. 全流程可以从清小搭入口完成；
2. 课程版本和讲次没有混淆；
3. StudyKit 所有关键事实均有来源或不确定性标记；
4. 至少一个引用能回到正确页、段或时间点；
5. 代码反馈不伪称运行，不直接交付作业答案；
6. 用户提交学习证据后，计划发生合理变化；
7. 任一步失败时，用户能看到明确的降级结果，而不是空白或编造内容；
8. 用户能绕过完整向导，直接进入至少三个独立功能入口；
9. 直接入口只询问当前任务缺少的必要信息，不重复询问会话中已有内容。

## 4. 系统边界与总体架构

### 4.1 逻辑架构

```text
清小搭智能体广场入口
              ↓
 OpenAI 兼容协议适配层
 鉴权、请求解析、文件 URL 拉取、SSE/JSON 响应
              ↓
       意图识别与上下文检查
              ↓
 ┌────────┬─────────┬────────┬────────┬────────┐
 ↓        ↓         ↓        ↓        ↓
课程推荐 StudyKit  材料答疑 代码辅导 学习复盘
 └────────┴────┬────┴────────┴────────┘
               ↓
       检查当前任务的必要信息
               ↓
   ┌───────────┴───────────┐
   ↓                       ↓
信息缺失：针对性追问    信息完整：立即执行
   └───────────┬───────────┘
               ↓
  读取 CourseManifest、资料索引与用户状态
               ↓
       依据公开/授权课程资料处理
               ↓
          输出任务结果
               ↓
      推荐下一步但不强制进入
               ↓
     用户结束或发起任意新任务
```

逻辑上保留 Proposal 中的专业角色边界，但 MVP 不要求部署六个独立自治 Agent：

| 逻辑角色 | MVP 实现职责 | 必须产物 |
| --- | --- | --- |
| Orchestrator | 识别用户意图、复用已有上下文、检查当前任务必要输入、路由功能并组织最终回复 | 任务计划、路由结果、缺失字段、阶段状态、失败说明 |
| Course Scout | 从人工审核课程池检索课程和版本 | `CourseCard`、来源、置信度 |
| Material Processor | 解析资料并保留来源锚点 | `SourceChunk` 列表和解析限制 |
| Teaching Designer | 根据证据生成 StudyKit | StudyKit 草稿与引用映射 |
| Code Coach | 代码审阅、错误定位、测试设计和分层提示 | 诊断假设、验证步骤和提示层级 |
| Evidence & Safety Guard | 检查引用、版权、学术诚信和过度自信 | 通过/退回、原因和降级说明 |

在实现上，这些角色默认是自研后端中的模块、提示模板或校验步骤，不要求部署为多个自治 Agent。只有在单流程无法满足质量或维护需求时，才拆成独立服务或智能体。

协议适配层属于 P0 基础设施，不承担教学决策。它至少负责：

1. 暴露 `POST /v1/chat/completions` 和 `GET /v1/models`；
2. 校验 Bearer 凭证，无效凭证返回 `401`；
3. 严格解析 JSON 布尔值 `stream`，接受 `model` 缺失以及 `max_tokens: 1`；
4. 非流式响应返回 `choices[0].message.content` 和 `usage`；
5. 流式响应按 role、content、stop、`data: [DONE]` 的顺序输出；
6. 将 `finish_reason` 限制在协议白名单，流式中途失败使用 stop 帧和独立 `error` 字段；
7. 对已启用的图片、文件或音频能力解析 URL；只拉取允许的清小搭 OSS 域名，并将下载、解析和推理控制在网关 120 秒超时内。

### 4.2 数据层

MVP 只需要四类核心数据：

1. 公共课程数据：课程、版本、讲次和资料来源；
2. 检索数据：从资料解析出来的带锚点片段；
3. 学习产物：StudyKit、练习和引用；
4. 用户状态：画像、完成记录、小测/代码证据和下一步计划。

公共课程知识与用户私有状态必须分离。不要把用户上传材料、个人信息或学习记录混入公共课程库。

## 5. 数据协议

### 5.1 CourseManifest

每门课程至少包含：

```yaml
course_id: cs149-2025
title: Stanford CS149
term: "Fall 2025"
course_version: "2025"
official_url: "..."
language: en
topics: []
prerequisites: []
estimated_hours: null
units:
  - unit_id: lec03-gpu-programming
    title: GPU Programming
    order: 3
    sources: []
reviewed_at: "YYYY-MM-DD"
limitations: []
```

每个 `source` 至少包含：

```yaml
source_id: cs149-2025-lec03-slides
type: pdf
url: "..."
access_status: public
license_status: confirmed_or_unknown
source_version: "2025-release"
checked_at: "YYYY-MM-DD"
checksum: optional
notes: ""
```

### 5.2 SourceChunk

```yaml
chunk_id: cs149-2025-lec03-slides-p12-c01
course_id: cs149-2025
course_version: "2025"
unit_id: lec03-gpu-programming
source_id: cs149-2025-lec03-slides
anchor:
  type: page
  value: 12
heading: "..."
content: "..."
content_type: text_or_code_or_formula
parser_version: v0.1
```

所有资料必须先按 `course_id`、`course_version` 和 `unit_id` 过滤，再参与检索，避免跨课程和跨学期串讲。`source.source_version` 表示单个来源文件的版本或修订号，不替代课程级 `course_version`。

### 5.3 StudyKit

```yaml
studykit_version: v0.1
course_id: cs149-2025
course_version: "2025"
unit_id: lec03-gpu-programming
generated_at: "..."
source_manifest: []
learning_objectives: []
prerequisite_patch: []
bilingual_outline:
  - content: "..."
    claim_type: source_or_explanation_or_inference
    citations: []
glossary: []
learning_sequence: []
checks:
  - type: concept_or_code_reading_or_transfer
    question: "..."
    evidence: []
citations: []
limitations: []
estimated_minutes: null
```

必须区分：

- `source`：材料直接说明；
- `explanation`：模型为了教学而做的解释或类比；
- `inference`：根据材料做出的推断；
- `unknown`：当前资料无法确认。

### 5.4 LearnerState

```yaml
learner_id: platform_or_anonymous_id
confirmed_profile:
  goals: []
  prior_knowledge: []
  weekly_hours: null
  language_preference: zh
active_context:
  course_id: null
  course_version: null
  unit_id: null
progress:
  - course_id: cs149-2025
    course_version: "2025"
    unit_id: lec03-gpu-programming
    status: not_started_or_in_progress_or_completed
    mastery:
      concept: unknown
      implementation: unknown
      transfer: unknown
    evidence: []
next_actions: []
updated_at: "..."
```

掌握度必须绑定用户实际提交的证据。不能只因为智能体已经解释过某个概念，就把它标为“已掌握”。

## 6. 详细实施步骤

### 阶段 0：冻结范围和 Demo

**目标：** 防止课程和功能范围继续扩张。

**任务：**

1. 确定最低可交付规模、目标规模和冲刺规模；
2. 确定一个样板课程和 3–5 个讲次；
3. 确定核心 Demo 讲次、概念问题、代码问题和小测；
4. 写出验收脚本；
5. 明确版权、学术诚信和非目标边界；
6. 建立风险清单和负责人。

**产物：**

- `docs/mvp_scope.md`；
- `docs/demo_scenario.md`；
- `docs/risk_register.md`；
- `docs/course_candidates.md`。

**完成标准：** 团队能用一句话描述 MVP，任何新增需求都能明确归入 P0、P1 或 P2。

### 阶段 1：实现并验证清小搭标准协议最小链路

**目标：** 在投入课程整理前，用 OpenAI 兼容服务通过清小搭接入探测，并确认平台能承载最小流程。

**任务：**

1. 建立可部署的 OpenAI 兼容协议适配服务；
2. 实现 `POST /v1/chat/completions`，支持非流式 JSON 和流式 SSE；
3. 实现 `GET /v1/models`，用于连通性和凭证校验；
4. 支持 `Authorization: Bearer <credential>`，错误凭证返回 `401`；
5. 保证非流式响应含 `choices[0].message.content` 和 `usage`；
6. 保证 SSE 依次包含唯一 role 帧、零到多个 content 帧、唯一 stop 帧和 `data: [DONE]`；
7. 接受平台探测发送的 `stream: true`、`max_tokens: 1`，以及缺失、空或 `null` 的 `model`；
8. 在出口校验 `finish_reason` 白名单；流式中途失败使用 stop 帧、独立 `error` 字段和 `[DONE]`；
9. 在清小搭接入向导中完成连通性、凭证、最小对话和响应格式四项探测，并完成真实试聊；
10. 验证消息历史、系统提示、用户文件、身份或会话标识、状态保存和日志能力；未在标准协议中明确提供的字段不得预先依赖；
11. 对 `file.url` 进行实测：收到请求后立即拉取、限制 OSS 域名、校验类型和大小，并验证 120 秒总超时；
12. 记录每项能力的实测结果、平台版本、限制和降级方案；
13. 导出或备份第一个可运行版本。

**降级原则：**

- 上游模型或检索服务不可用：返回明确错误并使用已缓存的核心 Demo 结果；不得伪造实时处理结果；
- 文件输入未开放或 URL 拉取失败：使用预上传样板资料、公开链接或文本粘贴；
- 流式响应不稳定：保留协议兼容的非流式响应和离线演示备份；
- 长期状态不可用：输出可复制的学习状态卡；
- 代码执行不可用：仅做静态审阅和测试建议；
- 精确引用不可用：在上传资料中显式加入来源锚点；
- 复杂业务编排不稳定：把非关键角色合并成一个受控生成步骤。

**产物：**

- 清小搭测试应用；
- `app/main.py`；
- `app/api/chat_completions.py`；
- `app/api/models.py`；
- `app/protocol/schemas.py`；
- `app/protocol/streaming.py`；
- `app/protocol/errors.py`；
- `tests/contract/test_auth.py`；
- `tests/contract/test_non_streaming.py`；
- `tests/contract/test_streaming.py`；
- `tests/contract/test_stream_errors.py`；
- `docs/platform_validation.md`；
- `docs/platform_release.md`，记录清小搭配置、限制、降级方案和可复现版本。

**完成标准：** 清小搭接入探测四项全绿，错误凭证、非流式、SSE 和流式错误场景通过契约测试，能从清小搭完成一轮真实输入和输出；所有 P0 平台依赖均有“支持、降级或阻塞”结论。

### 阶段 2：确定样板课程并建立 CourseManifest

**目标：** 建立可信、版本一致的课程数据源。

**课程选择标准：**

- 有明确官方课程页；
- 能确定学期或版本；
- 至少有讲义、notes、公开字幕、作业说明或公开仓库中的两类资料；
- 资料结构适合分讲处理；
- 至少一个讲次适合展示代码辅导；
- 公开访问和使用边界相对清楚；
- 中文学习者确实存在理解成本。

**任务：**

1. 从 Proposal 候选中选择样板课程；
2. 人工核验课程官网、学期、讲次和资源；
3. 记录访问状态、许可状态和检查时间；
4. 排除版本混杂、来源不明和访问受限资源；
5. 选择 3–5 个讲次；
6. 建立 CourseManifest；
7. 对每个讲次写一句内容说明和前置知识。

**产物：**

- `data/manifests/<course_id>.yaml`；
- `docs/source_review.md`；
- `docs/material_gaps.md`。

**完成标准：** 样板课程所有入库资源都有确定来源、版本和讲次归属；未知许可被明确标记。

### 阶段 3：固化 JSON Schema、模板和黄金样例

**目标：** 在模型生成前定义“正确输出是什么”。

**任务：**

1. 定义 CourseManifest JSON Schema；
2. 定义 SourceChunk JSON Schema；
3. 定义 StudyKit JSON Schema；
4. 定义 LearnerState JSON Schema；
5. 制作 Markdown StudyKit 模板；
6. 人工为核心 Demo 讲次制作一份黄金 StudyKit；
7. 标出黄金 StudyKit 中每项结论的正确来源；
8. 编写正例、缺失来源、错版本和引用缺失样例。

**产物：**

- `schemas/course_manifest.schema.json`；
- `schemas/source_chunk.schema.json`；
- `schemas/studykit.schema.json`；
- `schemas/learner_state.schema.json`；
- `templates/studykit.md`；
- `data/golden/<course_id>-<unit_id>-studykit.yaml`；
- `tests/fixtures/studykit/valid.yaml`；
- `tests/fixtures/studykit/missing_source.yaml`；
- `tests/fixtures/studykit/wrong_version.yaml`；
- `tests/fixtures/studykit/missing_citation.yaml`。

**完成标准：** 黄金样例能通过 JSON Schema 校验；团队对字段含义和必填项没有歧义。

### 阶段 4：实现资料处理

**目标：** 把公开或授权材料转换成可检索、可回跳的片段。

**首版输入范围：**

- 文本型 PDF；
- HTML 或 Markdown；
- 已存在的公开字幕或用户上传字幕；
- 课程公开仓库中的文本和代码文件。

**任务：**

1. 提取正文并保留页码、标题层级、时间戳和代码块；
2. 清理重复页眉、页脚和导航文本；
3. 按讲次和自然段落切分；
4. 为每个片段写入课程、版本、讲次、来源和锚点；
5. 对公式、代码和跨页内容做人工抽检；
6. 记录解析失败和不支持范围；
7. 把资料写入 `data/sources/`，并通过 `scripts/build_index.py` 构建自研检索索引；平台知识库仅可用于对照实验或应急降级。

**不在首版解决：**

- 复杂 OCR 修复；
- 视频自动转写；
- 动态网页全站爬取；
- 任意格式无损解析；
- 自动判断版权许可证。

**产物：**

- `data/sources/<course_id>/<unit_id>/chunks.jsonl`；
- `data/indexes/<course_id>/`；
- `tests/retrieval/test_parser.py`；
- `tests/retrieval/test_index.py`；
- `evaluations/parser_results.md`；
- 可用于样板讲次的检索索引。

**完成标准：** 随机抽检的片段内容、课程版本、讲次和锚点一致；核心 Demo 所需材料无解析阻塞。

### 阶段 5：实现课程导航

**目标：** 根据用户目标，在受控课程池中给出可解释的课程候选。

**任务：**

1. 设计 3–5 个画像问题；
2. 为课程维护方向、前置、难度和时间估计；
3. 使用规则和课程检索生成 2–3 个候选；
4. 显示推荐理由、前置缺口、预计投入和官方来源；
5. 要求用户确认课程和版本；
6. 无合适课程时说明课程池限制，不虚构推荐。

**产物：**

- `prompts/course_scout.md`；
- `templates/course_card.md`；
- `tests/agent/test_course_scout.py`；
- `tests/fixtures/course_profiles.yaml`。

**完成标准：** 同一画像的推荐结果稳定、可解释，并且只来自受控课程池。

### 阶段 6：实现检索与 StudyKit 生成

**目标：** 完成项目最核心的带证据学习包。

**处理流程：**

```text
课程与讲次确认
    → 按 course_id / course_version / unit_id 过滤
    → 检索相关 SourceChunk
    → 生成 StudyKit 草稿
    → JSON Schema 校验
    → 引用存在性检查
    → 证据与合规审查
    → 输出或退回修复
```

**任务：**

1. 编写检索查询生成规则；
2. 强制先过滤课程、版本和讲次；
3. 编写 Teaching Designer 提示；
4. 生成结构化 StudyKit；
5. 校验必填字段和枚举值；
6. 检查所有引用是否指向实际片段；
7. 区分材料事实、解释、推断和未知；
8. 资料不足时输出框架与限制，不补写具体事实；
9. 为核心讲次缓存稳定版本；
10. 对照黄金 StudyKit 做人工评测。

**产物：**

- `prompts/teaching_designer.md`；
- `app/retrieval/citations.py`；
- `tests/retrieval/test_citations.py`；
- `templates/studykit.md`；
- `data/golden/<course_id>-<unit_id>-studykit.yaml`；
- `evaluations/citation_failures.md`。

**完成标准：**

- 输出 JSON Schema 通过率达到 95%；
- 核心讲次关键主张有引用或限制标记；
- 人工抽检引用正确率达到 90%；
- 不会引用其他课程或其他学期材料回答当前讲次。

### 阶段 7：实现伴随式答疑

**目标：** 让用户围绕当前 StudyKit 继续学习。

**任务：**

1. 在问答中保留课程、版本和讲次上下文；
2. 先检索当前材料，再生成解释；
3. 采用“依据—解释—例子—检查理解”的回答结构；
4. 对材料冲突同时呈现不同来源；
5. 对资料外问题说明范围，并询问是否切换到通用解释；
6. 为公式、代码和术语保持英文原名；
7. 避免整份材料的替代性翻译。

**产物：**

- `prompts/course_qa.md`；
- `templates/fallback_response.md`；
- `tests/agent/test_course_qa.py`；
- `tests/fixtures/course_qa_cases.yaml`。

**完成标准：** 固定概念问题的答案能被当前课程材料支持；无证据问题不会被伪装成课程事实。

### 阶段 8：实现代码辅导

**目标：** 在不代写作业、不夸大执行能力的前提下帮助用户调试。

**输入：**

- 作业或项目要求；
- 用户自己的思路或代码；
- 报错信息；
- 已执行的测试及结果；
- 当前课程和讲次。

**输出协议：**

1. 复述问题和当前观察；
2. 提出按概率排序的诊断假设；
3. 为每个假设给最小验证步骤；
4. 给测试清单；
5. 分层提供提示，而不是一次给出完整答案；
6. 将问题关联回课程概念和来源；
7. 明确说明是否实际运行过代码。

**提示层级：**

- L1：指出应观察的位置或概念；
- L2：给出更具体的排查方向和测试；
- L3：给局部伪代码或最小独立示例；
- L4：只在不构成代写且用户明确需要时，给局部修改建议。

**首版限制：**

- 优先支持核心 Demo 使用的语言和代码类型；
- 没有安全运行环境时只做静态分析；
- 不执行未经信任的任意代码；
- 不输出可以直接提交的整题解答；
- 不保证复现依赖复杂、专有或硬件相关环境的问题。

**产物：**

- `prompts/code_coach.md`；
- `tests/agent/test_code_coach.py`；
- `tests/fixtures/code_cases.yaml`；
- `evaluations/code_coach_rubric.md`。

**完成标准：** 预置样例中至少 80% 能指出正确排查方向或有效测试；所有回复准确披露是否执行代码。

### 阶段 9：实现学习复盘与下一步计划

**目标：** 形成“学习—证据—调整”的闭环。

**任务：**

1. 让用户提交小测答案、笔记或代码测试结果；
2. 将证据映射到概念、实现和迁移三个维度；
3. 输出掌握、部分掌握、待验证或未知状态；
4. 显示状态更新依据；
5. 生成下一讲、补充练习和复习任务；
6. 允许用户修改或覆盖建议；
7. 若无法持久化，输出可复制的学习状态卡。

**产物：**

- `prompts/learning_review.md`；
- `templates/learner_state.md`；
- `tests/agent/test_learning_review.py`；
- `tests/fixtures/learner_evidence.yaml`。

**完成标准：** 无用户证据时不提升掌握度；不同小测结果会产生可解释的不同计划。

### 阶段 10：完成合规、安全与失败处理

**目标：** 让系统在真实用户输入下可安全上线。

**必须覆盖：**

| 风险 | 策略 |
| --- | --- |
| 无授权课程材料 | 提供官方链接和摘要，不镜像或重新分发整份材料 |
| 访问限制 | 不绕过登录、付费、地域或技术限制 |
| 替代性翻译 | 默认只解释用户选择的页或段，不生成整份替代文本 |
| 作业代写 | 采用分层提示、测试和代码审阅，不直接给可提交整题答案 |
| 用户隐私 | 公共课程库与用户状态分离，只保存用户确认的信息 |
| 文件 URL 与 SSRF | 只允许清小搭 OSS 域名；禁止任意地址拉取；校验 MIME、扩展名、大小和重定向目标 |
| 签名 URL 过期 | 收到请求后立即下载，不把临时 URL 作为长期数据源或延迟任务输入 |
| 大文件与网关超时 | 设置下载、解析和推理分段超时；总耗时低于 120 秒，超限时返回可操作的降级说明 |
| 资料幻觉 | 强制课程版本和引用；无证据时明确不确定 |
| 代码风险 | 无安全环境时不执行用户代码；不声称已运行 |
| 业务编排失败 | 显示失败阶段、已有结果、缺失输入和可行的下一步 |

**产物：**

- `policies/citation_policy.md`；
- `policies/academic_integrity.md`；
- `policies/content_and_privacy.md`；
- `tests/fixtures/red_team_cases.yaml`；
- `tests/test_safety.py`；
- `docs/known_limitations.md`。

**完成标准：** 版权、绕过限制、代写类红队请求拒绝率达到 100%；失败时不生成伪造结果。

### 阶段 11：平台整合与体验优化

**目标：** 把独立能力组织成支持多入口、上下文复用和可选完整闭环的清小搭体验。

**任务：**

1. 配置清晰的开场白和示例问题；
2. 设计课程推荐、StudyKit、材料答疑、代码辅导和学习复盘五类直接入口；
3. 实现意图识别和入口路由；
4. 为每个入口定义必要字段、可选字段和缺失信息追问；
5. 复用会话中已经确认的课程、版本、讲次、材料和用户画像，不重复提问；
6. 用户意图不明确时展示功能入口选择；
7. 在关键步骤展示当前任务、已知上下文和仍需输入的信息；
8. 对信息完整的单项任务走简化路径，不强制经过完整画像和选课流程；
9. 任务完成后给出可选下一步，但不自动强制跳转；
10. 允许用户随时切换功能入口，并在切换课程或版本时清理冲突上下文；
11. 为长任务设置超时、缓存和重试；
12. 为角色失败设置降级输出；
13. 确保一次会话不会混入其他课程版本；
14. 保存可复现的后端版本、部署配置和清小搭应用配置；
15. 对文件输入执行成功、URL 过期、非法域名、超限文件和不支持格式测试；
16. 若平台附件能力已实测开放，为 StudyKit 增加可选的 `x_soda.attachments` 输出；非流式挂响应顶层，流式只挂 stop 帧一次；
17. 确保附件只包含可即时下载的 URL、文件名、类型和 MIME，不内嵌 base64；
18. 提交平台测试版并完成内部验收。

**产物：**

- 可部署的 CoursePilot 后端与清小搭测试应用；
- `docs/routing_table.md`；
- `docs/platform_release.md`；
- `tests/end_to_end/test_core_demo.py`；
- `evaluations/end_to_end_results.md`。

**完成标准：** 核心 Demo 连续执行 5 次，至少 4 次无需开发者介入即可完成；五类入口均可直接触发；信息完整时不会强制用户从画像或选课重新开始；文件能力不可用时仍能沿文本或预上传材料路径完成核心 Demo。

### 阶段 12：离线评测、用户试用与迭代

**目标：** 用可复查数据证明系统有效。

**离线任务：**

- 从不同自然语言表达识别课程推荐、StudyKit、材料答疑、代码辅导和学习复盘意图；
- 对信息完整的直接入口立即执行，不启动无关前序步骤；
- 对信息缺失的入口只追问必要字段；
- 复用已有课程、版本和讲次上下文，并正确处理用户切换课程；
- 找到正确课程官网；
- 确认课程版本和讲次；
- 解释材料中的概念；
- 生成完整 StudyKit；
- 判断引用是否支持主张；
- 分析预置代码错误；
- 拒绝不当代写或侵权请求。

**核心指标：**

| 指标 | 判定方式 | MVP 目标 |
| --- | --- | ---: |
| 资源正确性 | 人工核验官网、版本和链接 | ≥ 95% |
| 引用覆盖率 | 关键主张是否有引用或限制 | ≥ 90% |
| 引用正确率 | 引用片段是否支持主张 | ≥ 90% |
| StudyKit 完整性 | JSON Schema 和必填字段检查 | ≥ 95% |
| 代码反馈有效性 | 是否指出正确排查方向或测试 | ≥ 80% |
| 合规拒绝率 | 红队请求是否正确拒绝 | 100% |
| 端到端成功率 | 用户能否完成完整任务 | ≥ 80% |
| 意图路由正确率 | 是否进入用户实际请求的功能入口 | ≥ 90% |
| 非必要追问率 | 信息完整时仍要求补充无关前序信息的比例 | ≤ 10% |

**用户试用：**

1. 第一轮邀请 5–10 名 CS 自学者；
2. 所有人完成相同核心任务；
3. 记录完成时间、资料定位成功率、引用信任度、任务后小测和满意度；
4. 保存匿名原始记录；
5. 将错误归入检索、引用、解释、交互、代码、性能和合规类别；
6. 优先修复高频且阻塞主流程的问题；
7. 维护 `CHANGELOG.md`。

**产物：**

- `evaluations/tasks.yaml`；
- `evaluations/rubric.md`；
- `evaluations/results.md`；
- `evaluations/user_trials.md`；
- `evaluations/error_analysis.md`；
- `CHANGELOG.md`。

**完成标准：** 达到最低指标；存在真实外部用户记录；关键失败都有原因和处理结论。

### 阶段 13：上线、Demo 与提交材料

**目标：** 形成可评审的完整项目证据。

**Demo 建议控制在约六分钟：**

1. 30 秒：说明海外课程资源碎片化、版本混乱和缺少学习闭环；
2. 1 分钟：建立用户画像并选择课程；
3. 2 分钟：选择讲次并生成带来源 StudyKit；
4. 1 分钟：展示代码错误的分层提示和测试建议；
5. 1 分钟：提交小测或测试结果，展示复盘和下一步计划；
6. 30 秒：展示引用审查、合规拒绝、评测和用户数据。

**提交材料：**

- 已上线的清小搭应用链接；
- Demo 视频；
- 项目背景和功能说明；
- 架构与工作流图；
- CourseManifest 和 StudyKit 示例；
- 引用与合规政策；
- 离线评测与用户试用结果；
- 失败样例和迭代 `CHANGELOG.md`；
- 已知限制和后续路线。

**完成标准：** 评委无需开发环境即可进入平台体验；Demo 有离线备份；所有量化结论可追溯到原始记录。

## 7. 四周排期

### 第 1 周：冻结范围与打通基础

**目标：** 消除最大的范围和平台不确定性。

- 完成阶段 0：MVP、课程和 Demo 冻结；
- 完成阶段 1：OpenAI 兼容服务、清小搭探测和最小链路验证；
- 完成阶段 2：样板课程 CourseManifest；
- 启动阶段 3：JSON Schema 和黄金 StudyKit；
- 建立风险清单和每日阻塞记录。

**周验收：** 清小搭四项探测全绿；非流式、SSE、鉴权和错误场景通过契约测试；平台最短链路可运行；样板课程和核心讲次确定。

### 第 2 周：完成核心 StudyKit 链路

- 完成阶段 3：JSON Schema、模板和黄金样例；
- 完成阶段 4：样板资料解析和索引；
- 完成阶段 5：画像和课程导航；
- 完成阶段 6：StudyKit 生成、JSON Schema 与引用检查；
- 接入并实测 `file.url` 下载、OSS 域名限制、文件解析和超时降级；若平台尚未开放则保存阻塞证据并启用预上传材料路径；
- 对核心讲次进行第一次人工引用评测。

**周验收：** 能从确定课程讲次稳定生成带来源 StudyKit；核心引用正确率达到初步可用水平。

### 第 3 周：形成完整学习闭环

- 完成阶段 7：课程内答疑；
- 完成阶段 8：代码静态辅导；
- 完成阶段 9：复盘与下一步计划；
- 完成阶段 10：合规、红队和失败处理；
- 完成阶段 11：平台端到端整合；
- 验证完整业务链路的 SSE 输出、120 秒超时和失败降级；
- 扩充到目标课程数的前提是核心链路稳定。

**周验收：** 核心 Demo 从画像到复盘完整运行；红队请求得到正确处理。

### 第 4 周：评测、试用和上线

- 完成阶段 12：离线评测；
- 邀请 5–10 名用户试用；
- 修复高优先级错误；
- 完成阶段 13：上线、Demo 视频和提交材料；
- 保存稳定平台版本和离线演示备份；
- 若平台已开放并通过实测，再增加可下载 StudyKit 附件；音频仍不阻塞上线；
- 质量达标后再扩课程或抽取技能包。

**周验收：** 指标达到最低目标；平台可访问；Demo、用户记录和提交材料齐备。

## 8. 关键路径与依赖

```text
MVP 冻结
   ↓
OpenAI 兼容协议探测、鉴权与 SSE 契约
   ↓
清小搭最小链路与真实试聊
   ↓
样板课程与 CourseManifest
   ↓
JSON Schema 和黄金 StudyKit
   ↓
资料解析与带锚点索引
   ↓
检索、StudyKit 生成与引用校验
   ↓
问答、代码辅导和复盘
   ↓
端到端平台整合
   ↓
评测、试用、修复
   ↓
上线与提交
```

以下工作不得阻塞关键路径：

- 大规模扩课；
- 完整知识图谱；
- 真实代码沙箱；
- 视频自动处理；
- 复杂长期记忆；
- 全套效率工具与书籍推荐；
- 技能专项赛打包；
- 高级可视化界面；
- 音频输入；
- 可下载 PDF/PPT/Word 附件产物。

## 9. P0 仓库结构

```text
.
├── plan_agent.md
├── proposal_agent.md
├── implementation_plan.md
├── README.md
├── CHANGELOG.md
├── pyproject.toml
├── Dockerfile
├── .gitignore
├── .env.example
├── app/
│   ├── main.py
│   ├── config.py
│   ├── api/
│   │   ├── chat_completions.py
│   │   └── models.py
│   ├── protocol/
│   │   ├── schemas.py
│   │   ├── streaming.py
│   │   └── errors.py
│   ├── agent/
│   │   ├── orchestrator.py
│   │   ├── course_scout.py
│   │   ├── material_processor.py
│   │   ├── teaching_designer.py
│   │   ├── code_coach.py
│   │   └── evidence_guard.py
│   ├── retrieval/
│   │   ├── parser.py
│   │   ├── chunker.py
│   │   ├── index.py
│   │   └── citations.py
│   ├── attachments/
│   │   ├── downloader.py
│   │   ├── validation.py
│   │   └── outputs.py
│   └── storage/
│       ├── course_store.py
│       └── learner_store.py
├── docs/
│   ├── mvp_scope.md
│   ├── demo_scenario.md
│   ├── platform_validation.md
│   ├── platform_release.md
│   ├── risk_register.md
│   ├── course_candidates.md
│   ├── source_review.md
│   ├── material_gaps.md
│   ├── routing_table.md
│   └── known_limitations.md
├── data/
│   ├── manifests/
│   │   └── <course_id>.yaml
│   ├── sources/
│   │   └── <course_id>/
│   │       └── <unit_id>/
│   │           └── chunks.jsonl
│   ├── indexes/
│   │   └── <course_id>/
│   └── golden/
│       └── <course_id>-<unit_id>-studykit.yaml
├── schemas/
│   ├── course_manifest.schema.json
│   ├── source_chunk.schema.json
│   ├── studykit.schema.json
│   └── learner_state.schema.json
├── prompts/
│   ├── course_scout.md
│   ├── teaching_designer.md
│   ├── course_qa.md
│   ├── code_coach.md
│   └── learning_review.md
├── templates/
│   ├── course_card.md
│   ├── studykit.md
│   ├── learner_state.md
│   └── fallback_response.md
├── policies/
│   ├── citation_policy.md
│   ├── academic_integrity.md
│   └── content_and_privacy.md
├── tests/
│   ├── contract/
│   │   ├── test_auth.py
│   │   ├── test_non_streaming.py
│   │   ├── test_streaming.py
│   │   └── test_stream_errors.py
│   ├── retrieval/
│   │   ├── test_parser.py
│   │   ├── test_index.py
│   │   └── test_citations.py
│   ├── agent/
│   │   ├── test_course_scout.py
│   │   ├── test_course_qa.py
│   │   ├── test_code_coach.py
│   │   └── test_learning_review.py
│   ├── end_to_end/
│   │   └── test_core_demo.py
│   ├── fixtures/
│   │   ├── studykit/
│   │   │   ├── valid.yaml
│   │   │   ├── missing_source.yaml
│   │   │   ├── wrong_version.yaml
│   │   │   └── missing_citation.yaml
│   │   ├── course_profiles.yaml
│   │   ├── course_qa_cases.yaml
│   │   ├── code_cases.yaml
│   │   ├── learner_evidence.yaml
│   │   └── red_team_cases.yaml
│   ├── test_schema.py
│   └── test_safety.py
├── evaluations/
│   ├── tasks.yaml
│   ├── rubric.md
│   ├── results.md
│   ├── parser_results.md
│   ├── citation_failures.md
│   ├── code_coach_rubric.md
│   ├── end_to_end_results.md
│   ├── user_trials.md
│   └── error_analysis.md
└── scripts/
    ├── validate_manifests.py
    ├── build_index.py
    └── run_evaluation.py
```

自研代码后端是 P0，而不是平台验证后的条件选项。目录边界如下：

- `app/api/` 与 `app/protocol/` 只负责清小搭接入、鉴权、OpenAI 兼容结构、SSE 和错误归一化；
- `app/protocol/schemas.py` 定义 HTTP 传输模型，根目录 `schemas/` 保存 CourseManifest、SourceChunk、StudyKit 和 LearnerState 的 JSON Schema，二者用途不同；
- `app/agent/` 负责任务路由、教学业务编排和安全校验，不耦合 HTTP 传输细节；
- `app/retrieval/` 负责解析、分块、索引与引用锚点；
- `app/attachments/` 负责清小搭 OSS URL 的下载、安全校验及条件性附件输出；
- `app/storage/` 分离公共课程数据和用户私有状态；
- `tests/contract/` 必须覆盖平台探测依赖的鉴权、非流式、SSE 帧序列和流式错误契约；
- `data/` 不提交无授权课程全文、用户上传原文、密钥或其他敏感数据。

首版技术基线固定为 Python、FastAPI、Pydantic 和 pytest；依赖统一声明在 `pyproject.toml`。`.env.example` 只记录变量名和示例格式，真实凭证写入本地 `.env` 并由 `.gitignore` 排除。

清小搭自带模块用于广场入口、应用信息、开场白、引导问题、文件上传和附件转存。知识库、变量、工作流等模块只有在实测稳定且不削弱可测试性时才作为辅助能力使用；CoursePilot 的核心路由、检索、StudyKit、答疑、代码辅导和复盘逻辑保留在自研后端。

## 10. 人员分工

### 3–4 人团队

| 角色 | 主要职责 |
| --- | --- |
| 产品与课程负责人 | MVP、课程筛选、CourseManifest 审核、用户试用、Demo 和答辩 |
| 平台与后端负责人 | OpenAI 兼容 API、清小搭接入、状态、文件安全、缓存、部署和故障处理 |
| 资料与检索负责人 | 解析、分块、索引、引用协议、StudyKit 生成和评测 |
| 代码与质量负责人（可选） | Code Coach、校验、红队、测试、技能包和可视化 |

### 个人开发

按以下顺序串行执行：

1. OpenAI 兼容协议后端、契约测试和清小搭最小链路；
2. 样板课程和 CourseManifest；
3. JSON Schema、黄金样例和资料解析；
4. StudyKit 和引用；
5. 答疑；
6. 一个固定代码辅导场景；
7. 简单复盘；
8. 评测和 Demo。

个人开发时直接取消 6 门课程目标、真实代码执行、复杂记忆和技能专项赛并行开发。

## 11. 风险控制与停止规则

| 风险 | 早期信号 | 处理 | 停止或删减条件 |
| --- | --- | --- | --- |
| 平台能力不匹配 | 无法上传、检索、调用工具或保存状态 | 使用平台内置知识库、预生成材料或状态卡降级 | 不继续开发依赖该能力的高级功能 |
| 标准协议不兼容 | 探测失败、SSE 帧顺序错误或响应字段缺失 | 用固定契约测试覆盖鉴权、非流式、流式和错误场景 | 协议探测未通过前停止业务功能扩展 |
| 文件 URL 安全或超时 | 非预期域名、签名过期、下载/解析超过 120 秒 | OSS 域名白名单、立即下载、大小限制、分段超时和文本降级 | 安全边界未验证时禁用用户 URL 拉取 |
| 多模态规格不一致 | 音频上限在文档中同时出现 25MB 与 200MB | 未确认前按 25MB；记录平台版本并以实测结果更新 | 不将音频纳入 P0 或完成声明 |
| 课程范围膨胀 | 一周后仍在搜集课程而核心链路未通 | 冻结 1 门课程和 3–5 讲 | 核心评测未达标前停止扩课 |
| 引用错误 | 格式存在但内容不支持结论 | 黄金样例、人工抽检、退回生成 | 正确率低于 90% 时不扩课程 |
| 资料版权不清 | 计划下载或分发整套材料 | 只提供链接、摘要和用户授权处理 | 无法确认边界的来源不入库 |
| 多 Agent 不稳定 | 延迟高、重复调用、角色互相矛盾 | 合并角色、缓存、使用固定流程 | 不保留无法改善指标的 Agent |
| 代码执行风险 | 需要运行不可信或依赖复杂代码 | 静态审阅和测试建议降级 | 无可靠隔离时取消真实运行 |
| 长期状态不可靠 | 用户进度丢失或串用户 | 状态卡、用户确认、公共/私有数据分离 | 未验证用户隔离前不保存敏感状态 |
| 试用时间不足 | 第三周仍没有稳定闭环 | 停止 P1/P2，集中修复 P0 | 不再增加新功能和新课程 |
| Demo 网络或平台故障 | 延迟和失败率波动 | 缓存、录屏、离线样例和失败说明 | 保留可复现的备份演示路径 |

## 12. 每周质量门槛

### Gate 1：范围与平台

- 样板课程和 Demo 已冻结；
- 清小搭测试应用可调用自研后端；
- 清小搭四项接入探测全绿；
- Bearer 鉴权、非流式 JSON、SSE 帧序列、`usage`、`finish_reason` 和流式错误契约通过测试；
- 所有 P0 平台依赖有结论；
- 数据 JSON Schema 有初版。

未通过：停止扩课和业务能力扩展，只处理协议后端、平台接入与范围问题。

### Gate 2：核心证据链

- 资料能解析为带锚点片段；
- 用户文件能力可用时，`file.url` 的域名限制、类型/大小校验、立即下载和超时降级通过测试；
- StudyKit 通过 JSON Schema；
- 核心讲次不存在跨版本引用；
- 人工引用抽检接近目标。

未通过：停止代码辅导、记忆和技能包开发，优先修复检索与引用。

### Gate 3：完整闭环

- 画像、选课、StudyKit、问答、代码和复盘已串联；
- 至少三个功能入口可绕过完整向导直接使用；
- 必要信息追问和上下文复用通过测试；
- 固定 Demo 能重复运行；
- 合规红队通过。

未通过：取消所有 P1/P2 功能，仅保留核心 Demo。

### Gate 4：上线证据

- 离线指标达到最低目标；
- 至少完成一轮外部用户试用；
- 已修复阻塞性问题；
- 平台、视频和材料均可供评审。

未通过：不新增功能，只处理上线稳定性、评测和提交材料。

## 13. MVP 完成定义

只有同时满足以下条件，MVP 才算完成：

1. CoursePilot 已通过 OpenAI 兼容协议接入清小搭智能体广场，并通过连通性、凭证、最小对话和响应格式探测；
2. 至少 1 门课程、3–5 个讲次有审核过的 CourseManifest；
3. 核心讲次能生成完整、带来源锚点的 StudyKit；
4. 用户可以直接进入课程推荐、StudyKit、材料答疑、代码辅导或学习复盘，不必从固定第一步开始；
5. 系统能复用已有上下文，只追问当前任务缺少的必要信息；
6. 用户可以围绕当前讲次追问；
7. 至少一个代码辅导场景能给出有效静态诊断和测试建议；
8. 用户提交学习证据后能获得可解释的复盘与下一步计划；
9. 版权、学术诚信、隐私和代码边界有明确策略；
10. 核心离线指标达到最低目标；
11. 至少 5 名外部用户完成试用，或保存了明确的招募与未完成原因；
12. Demo、评测、失败样例、`CHANGELOG.md` 和已知限制齐备；
13. 平台故障时存在可演示的备份方案；
14. 项目没有声称超出实际验证范围的能力；
15. 非流式、SSE、错误凭证、流式错误和 120 秒超时均有可复查的契约测试记录；
16. 若文件输入尚未开放或未通过实测，核心 Demo 能通过预上传材料或公开链接完成，且未把该能力声明为已支持。

## 14. MVP 完成后的扩展顺序

MVP 通过全部质量门槛后，按以下顺序扩展：

1. 从 1 门扩到 3 门课程；
2. 从 3–5 讲扩到 10–15 讲；
3. 改善引用校验和失败反馈；
4. 增加稳定的用户状态持久化；
5. 增加更多代码语言或安全运行环境；
6. 抽取 `course-studykit` 技能包；
7. 扩到 6 门、30 讲；
8. 引入轻量课程概念图和前置关系；
9. 增加间隔复习和长期计划；
10. 最后再扩展效率工具、书籍推荐和更广课程目录。

该顺序确保每一次扩展都复用已经验证的 CourseManifest、SourceChunk、StudyKit、LearnerState、引用协议和评测体系，而不是重新构建一个新的问答机器人。
