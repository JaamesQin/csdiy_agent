# CoursePilot StudyKit v0.1 冻结标准

版本：v0.1

冻结日期：2026-08-03

适用范围：模板课程和用户授权资料生成的中文 StudyKit。Lecture 2 与 Lecture 8 是本版本的核心验证样例。

本文是 StudyKit 的规范性标准。除非另有说明，“必须”表示生成器、校验器或审核者不得绕过的要求；“建议”表示质量目标，不是 Schema 硬约束。

## 1. 产物定义

StudyKit 是针对一个确定的 `course_id`、`course_version`、`unit_id` 和资料范围生成的结构化学习包。它不是原讲义的替代品，也不是课程全文翻译。

生成流程必须遵循：

```text
确认课程/版本/讲次和资料范围
    → 按权限过滤 MaterialSet
    → 检索 SourceChunk
    → 生成结构化 StudyKit 草稿
    → StudyKit Schema 校验
    → 引用存在性校验
    → 练习、术语和公式审核
    → 渲染学习者版本
```

内部结构化 YAML/JSON 与学习者版 Markdown 是两个不同产物。内部字段可以包含评分依据和审核信息，但这些字段不得默认展示给学习者。

## 2. 资料、来源和范围

### 2.1 允许的来源

- 模板模式只使用已审核 CourseManifest 中的资料。
- 用户模式只使用用户授权的 MaterialSet；课程身份可以未知。
- 每个 SourceChunk 必须保留 `material_set_id`、`scope`、`source_id`、课程/版本/讲次字段和来源锚点。
- 公共模板资料与用户私有资料必须按权限隔离；不得依靠向量相似度实现隔离。

### 2.2 不支持的来源

字幕、VTT、SRT、视频文字稿、视频元数据和时间戳引用不进入 v0.1 StudyKit 的索引和引用范围。第三方阅读材料只有在单独审核后才能进入资料范围；仅登记链接不等于已批准使用正文。

### 2.3 版本和讲次边界

生成前必须确定 `course_id`、`course_version` 和 `unit_id`，并先按这三个字段过滤检索范围。不能用另一学期、另一讲次或未确认的模板资料补齐当前内容。

用户上传资料如果无法识别课程或版本，必须保持 `unknown`/`null`，显示文件名和页码，不得猜测身份。

## 3. 前置知识标准

### 3.1 课程级前置

课程级前置知识必须描述稳定的能力层级，不得按某道练习的函数名或 API 细节倒推。CoursePilot 的通用建议最多保持以下三类：

1. Python、张量计算与 PyTorch 入门；
2. 线性代数、微积分和基础概率；
3. 机器学习与神经网络基础。

这些是 CoursePilot 的人工整理建议，不得冒充课程官网或 MIT 官方元数据。课程官方前置要求与 CoursePilot 建议必须分开存储和展示。

### 3.2 讲次前置

讲次可以增加真正与该讲内容相关的概念，例如 Lecture 2 的链式法则、MLP 和张量形状，Lecture 8 的 token、矩阵和局部性感受野。

不得把 `masked_fill`、`.isfinite()`、`.backward()` 等单个函数名列为课程或讲次的必备前置。具体 API 可以出现在 code-reading 题中，由代码上下文和提示解释。

### 3.3 前置检查

前置检查用于发现差距和提供补救路径，不代表学习者必须在开始前已经掌握本讲所有概念。softmax、argmax、位置编码、causal mask 等可以作为前置检查或本讲学习内容引入。

## 4. StudyKit 必备结构

StudyKit 必须通过 `schemas/studykit.schema.json`，并包含：

- `studykit_version`、`status`、课程/版本/讲次和标题；
- `scope`、包含来源和引用锚点类型；
- `learning_objectives`；
- `prerequisites`；
- `outline`；
- `core_concepts`；
- `glossary`；
- `learning_sequence`；
- `practice`；
- `practice_feedback_policy`；
- `citations`；
- `review`；
- `limitations`。

StudyKit 的 `course_id` 和 `course_version` 在用户未知资料模式可以为 `null`，但必须明确身份未知和来源范围。

## 5. 内容设计标准

### 5.1 学习目标

每个学习目标必须描述可观察的学习证据，例如“能够写出 Q、K、V 的形状关系”，而不是“理解 Transformer”。目标数量应覆盖本讲核心内容，但不追求穷举所有页面。

### 5.2 提纲和学习顺序

- `outline` 使用连续顺序和可解析的 PDF 页码范围。
- `learning_sequence` 的第一步可以是前置检查；后续每一步先给简短概念解释，再进入具体 practice。
- 每个步骤必须有 `activity` 和正整数时长；总时长应与 `estimated_study_time_minutes` 一致或在审核记录中解释差异。
- 学习任务不得只写“深入理解”“掌握思想”等无法执行的抽象指令。
- 概念解释应保持简短；练习负责检验具体知识，不把所有要求堆进学习顺序文字。

### 5.3 核心概念和术语

- 核心概念必须有明确的中英文术语、解释和至少一个页码引用。
- 来源总结、教学解释、迁移题和推断必须通过 `claim_type`、`teaching_note` 或限制说明区分。
- 数学和工程术语首次出现可保留英文或缩写，例如 SGD、MLP、DAG、QKV、MSA、ReLU、batch、forward pass。
- 中文译法必须在同一 StudyKit 内一致；不确定或容易混淆的词保留英文原名。
- 常见定义不得混淆，例如 permutation equivariance 不等于 permutation invariance，gradient summation at branches 不等于跨批次 gradient accumulation。

### 5.4 公式和矩阵

- 公式必须和来源页面的变量定义、维度和方向一致。
- 如果讲义记号与常见框架记号不同，必须在 `teaching_note` 或 glossary 中说明。
- 矩阵练习必须明确行/列 token 约定、Jacobian 布局和转置位置。
- 公式提取无法保留视觉结构时，必须要求回看原 PDF，不得依据破损的文本层猜测。

## 6. Practice 标准

### 6.1 必备字段

每道 practice 必须包含：

- 唯一 `id`；
- `level`；
- 具体 `question`；
- 简短 `hint`；
- `deliverable`；
- `expected_evidence`；
- `evaluation.full_credit` 和 `evaluation.partial_credit`；
- `source_pages`。

`expected_evidence` 和 `evaluation` 是内部审核字段，不得出现在默认学习者渲染版。

### 6.2 题型要求

- `concept`：辨析或解释一个知识点；不要求额外工程 API。
- `derivation`：给出足够明确的变量、关系和目标，允许检查局部推导。
- `implementation`：检查形状、模块组合或实现语义；不应要求猜测隐藏意图。
- `code_reading`：必须提供真实代码或明确的伪代码；只能给文字设定时不得标为 `code_reading`。
- `transfer`：把本讲规则迁移到一个新但可控的场景，必须给出明确目标。

题目应聚焦一个或少数相邻知识点，不得要求学生交付过大的诊断计划或多层嵌套任务。除非知识点本身要求，不强制固定步骤数量。

### 6.3 事实性

每道题的题干、设定、期望证据和评分描述都必须经过事实核对：

- 数值、形状、矩阵方向和公式可推导；
- 框架行为与实际代码语义一致；
- 架构顺序与来源图一致；
- `source_pages` 支持题目所声称的概念；
- 教学迁移不得写成来源原文事实。

## 7. 引用和证据标准

- v0.1 默认使用 PDF 一基页码锚点；不使用时间戳。
- 每个核心概念至少有一个引用。
- 每道 practice 的 `source_pages` 必须与默认 StudyKit 来源相符并能解析到实际 SourceChunk。
- 全局 `citations.pages` 的每一页都必须存在且不是空页。
- 引用只能证明对应范围内的主张；代码 API 迁移题可以引用相关概念页，但必须标为教学迁移或说明不是讲义原题。
- 引用检查通过不等于公式已经视觉正确；核心 Demo 仍需视觉页码和公式审核。

## 8. 单题反馈标准

`practice_feedback_policy` 固定为：

```yaml
scope: current_answer_only
persistence: none
aggregate_accuracy: disabled
aggregate_mastery: disabled
```

反馈可以指出本次回答正确的部分、最重要的错误/遗漏、简短修正方向和相关页码。反馈不得保存累计答题记录、总正确率、总分、通过题数或跨题掌握度推断。

## 9. 学习者渲染标准

默认 Markdown 必须展示：

- 学习目标、前置知识、提纲；
- 核心概念和页码来源；
- 学习顺序和简短概念解释；
- practice 题干、必要设定和作答要求；
- 限制说明。

默认 Markdown 必须隐藏：

- `expected_evidence`；
- `evaluation`；
- 默认 `hint`；
- 内部审核状态、生成调试信息和私有权限字段。

用户明确请求提示时，才返回该题的 hint；不因为答错自动泄漏完整评分依据。

## 10. 审核和生命周期

### 10.1 状态

- `draft`：结构化产物已生成，但尚未完成人工内容审核。
- `reviewed`：Schema、引用、术语、公式/矩阵方向、练习事实性和学习者渲染均已检查，并有人工批准记录。
- `published`：已作为稳定模板版本提供给用户；发布必须保留版本和审核日期。

Agent 自查可以写入 `review`，但不得冒充人工批准。核心 Demo 必须经过人工确认才能从 `draft` 提升为 `reviewed`。

### 10.2 发布门槛

发布前必须通过：

1. YAML/JSON Schema 校验；
2. 所有引用存在性校验；
3. 课程、版本、讲次和 checksum 对照；
4. 练习事实性核对；
5. 中文术语一致性核对；
6. 公式、矩阵方向和关键图示视觉核对；
7. 学习者渲染版检查，确认内部评分信息没有泄漏；
8. 无状态反馈策略检查；
9. 版权、学术诚信和用户资料权限检查。

## 11. 用户上传资料标准

- 用户资料建立私有 MaterialManifest 和 MaterialSet，不写入公共模板库。
- `owner_id`、`session_id` 和 `material_set_id` 必须参与授权过滤。
- 课程身份未知时继续处理，但不得自动并入模板课程。
- 私有原文、派生 chunks、索引和 StudyKit 遵循保留/删除策略。
- 只有用户明确确认后，私有资料才可以与公共模板资料进入同一混合检索范围。

## 12. 变更和版本标准

- 修改字段必填性、引用规则、反馈策略、权限规则或学习者可见性时，必须提升 StudyKit 版本或记录迁移说明。
- 只修正错别字、页码或不改变结构的措辞，可以保留 v0.1，但要更新审核日期和变更记录。
- 黄金 StudyKit 是规范样例，不得被当作其他讲次的事实来源。
- 新模板课程必须复用同一 Schema、SourceChunk、引用、practice 和反馈标准；不能为单个课程另造隐含规则。

## 13. 现有实现对应

| 标准产物 | 当前文件 |
| --- | --- |
| StudyKit Schema | `schemas/studykit.schema.json` |
| SourceChunk Schema | `schemas/source_chunk.schema.json` |
| PDF 分页解析 | `app/retrieval/parser.py`、`scripts/build_course_chunks.py` |
| 引用校验 | `app/retrieval/citations.py`、`scripts/validate_studykit.py` |
| 学习者渲染 | `app/retrieval/render.py`、`scripts/render_studykit.py` |
| 单题展示与反馈 | `app/retrieval/practice.py` |
| Lecture 2 黄金样例 | `data/golden/mit-6.7960-fall-2024-lecture-02-studykit.yaml` |
| Lecture 8 StudyKit 初稿 | `data/golden/mit-6.7960-fall-2024-lecture-08-studykit.yaml` |
| 练习事实核对 | `evaluations/lecture_02_08_practice_fact_check.md` |
| 前置知识对齐 | `evaluations/lecture_02_08_prerequisite_alignment.md` |

## 14. v0.1 明确不保证的能力

v0.1 不保证字幕或视频时间戳引用、任意 HTML/扫描 PDF 的高质量公式解析、自动判断课程身份、跨用户长期掌握度统计、自动运行用户代码或自动生成可提交作业答案。
