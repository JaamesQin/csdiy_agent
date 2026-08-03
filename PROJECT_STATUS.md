# CoursePilot 项目状态

更新时间：2026-08-03

这份文档是给新加入项目的开发者看的。它回答三个问题：现在已经有什么、为什么还没有完成、下一步应该先做什么。

## 一句话概括

CoursePilot 已经完成了一个可复查的课程资料和 StudyKit 验证切片，但还没有把这条链路接成“用户对话 → 自动解析/检索 → 自动生成 StudyKit → 继续答疑”的运行时 Agent。

当前最成熟的流程是：

```text
MIT 6.7960 PDF
  → 页级 SourceChunk
  → 带页码引用的 StudyKit
  → Schema/引用/公式/术语/练习审核
  → 学习者版 Markdown
  → 单题即时点评
```

## 当前已经完成

### 产品和课程范围

- 已确定项目面向中文 CS 自学者，接入清小搭的 OpenAI 兼容后端。
- 支持两种入口：
  - 从审核过的模板课程中推荐课程、提供官方下载链接、选择讲次；
  - 处理用户自己上传但项目尚未预收录的资料。
- 已确定公共模板资料、用户私有资料和学习状态必须隔离。
- 首个模板课程已冻结为 MIT 6.7960 Deep Learning Fall 2024。
- 选定 Lecture 1、2、4、8、9；Lecture 2 和 Lecture 8 是核心 Demo。

### StudyKit 标准

[StudyKit v0.1 冻结标准](docs/studykit_standard.md) 已确定：

- StudyKit 的必备字段和 Schema；
- PDF 页码引用和 SourceChunk 结构；
- 课程级前置知识与讲次前置知识的粒度；
- practice 的题型、作答要求和隐藏评分依据；
- `code_reading` 必须包含代码或明确伪代码；
- 学习者版隐藏 `expected_evidence`、评分规则和默认提示；
- 反馈只点评当前答案，不统计累计正确率或掌握度；
- `draft`、`reviewed`、`published` 生命周期；
- 公共/私有资料的权限和保留边界。

### 资料解析和验证

- 已实现 PDF 页级解析器，每页生成一个 SourceChunk。
- 每个 chunk 保留课程、版本、讲次、来源和一基页码锚点。
- 已处理 PDF 隐藏公式文本和重复辅助文本问题。
- Lecture 2 已生成 81 个 chunks。
- Lecture 8 已生成 55 个 chunks，并验证了同一解析器可以复用。
- 已实现 SourceChunk Schema、StudyKit Schema 和引用存在性校验。

### 两个核心 StudyKit

- Lecture 2 StudyKit 已人工审核并标记 `reviewed`。
- Lecture 8 StudyKit 已人工审核并标记 `reviewed`。
- 两份 StudyKit 都已经完成：
  - Schema 校验；
  - 页码引用校验；
  - 术语一致性检查；
  - 公式和矩阵方向检查；
  - 练习题事实性检查；
  - 学习者版渲染。
- Lecture 2 和 Lecture 8 的练习均包含具体题目；代码阅读题包含真实代码或伪代码。

### 当前代码组件

| 功能 | 位置 |
| --- | --- |
| PDF 解析 | `app/retrieval/parser.py` |
| SourceChunk 校验 | `app/retrieval/schema_validation.py`、`schemas/source_chunk.schema.json` |
| StudyKit 引用校验 | `app/retrieval/citations.py` |
| practice 展示和当前答案点评 | `app/retrieval/practice.py` |
| 学习者版 Markdown 渲染 | `app/retrieval/render.py` |
| 构建分页 chunks | `scripts/build_course_chunks.py` |
| 校验 StudyKit | `scripts/validate_studykit.py` |
| 渲染 StudyKit | `scripts/render_studykit.py` |
| 课程身份和官方来源 | `data/manifests/mit-6.7960-fall-2024.yaml` |
| Lecture 2 StudyKit | `data/golden/mit-6.7960-fall-2024-lecture-02-studykit.yaml` |
| Lecture 8 StudyKit | `data/golden/mit-6.7960-fall-2024-lecture-08-studykit.yaml` |

## 还没有完成

### 最大缺口：StudyKit 还不是自动生成的

目前的 Lecture 2 和 Lecture 8 是人工制作的黄金样例。它们证明了“正确的 StudyKit 应该是什么样”，但还不能证明运行时 Agent 能够根据检索材料自动生成同等质量的 StudyKit。

尚缺少：

- `StudyKitGenerator`；
- Teaching Designer 生成提示；
- 根据 SourceChunk 组织证据并生成结构化 YAML 的接口；
- 自动失败修正和资料不足降级；
- 与两个黄金样例的自动评测。

### 数据和检索层

- CourseManifest 尚无正式 JSON Schema。
- MaterialManifest、MaterialSet 尚无完整运行时实现。
- LearnerState Schema 尚未实现。
- 尚无线上关键词/向量检索索引。
- Lecture 1、4、9 尚未生成 chunks。
- HTML、Markdown、纯文本和用户文件输入尚未接入统一运行时管线。

### 用户上传和权限

设计已经确定，但运行时还没有完全实现：

- 用户文件 URL 下载和安全检查；
- `owner_id`、`session_id`、`material_set_id` 授权过滤；
- 私有原文、派生 chunks 和索引的保留/删除；
- 课程身份未知时继续处理；
- 用户确认后才允许公共/私有混合检索。

### Agent 对话能力

尚未完成真正的课程 Agent 编排：

- 课程推荐和讲次路由；
- 根据当前任务只追问必要信息；
- 材料范围内答疑；
- 代码辅导；
- 学习复盘；
- StudyKit 生成与现有 OpenAI 兼容 API 的连接。

### 平台和测试

- 本地 OpenAI 兼容 API 已有基础实现和契约测试。
- 清小搭生产连通性、文件输入、会话标识和状态能力尚未完成账号级实测。
- retrieval 相关测试目前通过；仓库原有 Web UI 测试曾出现长时间不返回，需要单独定位。

## 目前最难的地方

### 1. PDF 不是可靠的纯文本来源

公式、矩阵方向、图示关系和隐藏辅助文本可能在 PDF 文本层损坏。解析器只能提供候选文本，核心 StudyKit 仍然必须做视觉审核。

### 2. 引用正确不等于解释正确

页码存在性检查只能确认页面存在，不能证明主张真的被页面支持。因此核心概念、练习事实、术语和公式方向必须分别审核。

### 3. 公共资料和用户资料不能混用

用户上传文件可能没有课程名、版本或讲次。系统必须允许身份未知，同时确保不同用户和会话不能互相检索资料。

### 4. 黄金样例和自动生成之间有鸿沟

人工写好的 YAML 很容易看起来正确，但自动生成器还必须处理证据不足、错版本、引用缺失、公式歧义和过度抽象的练习题。

### 5. 平台能力仍需实测

OpenAI 兼容协议通过本地测试不代表清小搭已经开放文件上传、稳定会话 ID 或完整状态能力。

## 下一步建议

建议按以下顺序推进。

### P0：完成可运行的 StudyKit 生成闭环

1. 定义 CourseManifest、MaterialManifest、LearnerState 的最小 Schema。
2. 实现 `MaterialSet` 授权过滤和页级检索接口。
3. 实现 `StudyKitGenerator`，输入课程上下文和 SourceChunk，输出结构化 StudyKit 草稿。
4. 串联 Schema、引用、权限、限制说明和学习者渲染检查。
5. 用 Lecture 2 黄金样例回归，再用 Lecture 8 作为独立验证。

### P1：做核心 Demo 端到端验收

完成以下可演示流程：

```text
选择 MIT 6.7960
  → 选择 Lecture 2 或 Lecture 8
  → 读取/解析讲义
  → 自动生成 StudyKit
  → 追问一个概念
  → 完成一道 practice
  → 获得当前答案点评
```

同时修复或隔离 Web UI 长时间不返回的测试问题。

### P2：接入未收录用户资料

1. 实现安全文件输入和临时私有存储。
2. 建立 MaterialManifest 和私有 MaterialSet。
3. 完成 owner/session 授权过滤。
4. 用一份未收录 PDF 验收“课程身份未知但可以继续生成 StudyKit”。

### P3：扩展课程覆盖

在 P0/P1 通过评测后，再生成 Lecture 1、4、9 chunks，并制作或自动生成相应 StudyKit。不要在自动生成和权限链路稳定前单纯增加讲次数量。

## 下一阶段完成定义

只有满足以下条件，才可以说“核心 StudyKit Agent 完成”：

- 模板资料和用户资料都能统一映射为 MaterialSet；
- 检索按课程、版本、讲次和权限过滤；
- StudyKit 由生成器生成，而不是复制人工 YAML；
- 每个输出通过 Schema 和引用校验；
- 学习者版不泄漏内部评分信息；
- Lecture 2 和 Lecture 8 各完成一次端到端自动生成；
- practice 可以获得当前答案点评，且无累计正确率统计；
- 身份未知、资料不足和解析失败时有明确降级说明。

## 开发者快速入口

安装依赖并运行 retrieval 测试：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
.venv/bin/pytest -q tests/retrieval
```

校验现有两个 StudyKit：

```bash
.venv/bin/python scripts/validate_studykit.py \
  data/golden/mit-6.7960-fall-2024-lecture-02-studykit.yaml \
  --chunks data/sources/mit-6.7960-fall-2024/lecture-02/chunks.jsonl

.venv/bin/python scripts/validate_studykit.py \
  data/golden/mit-6.7960-fall-2024-lecture-08-studykit.yaml \
  --chunks data/sources/mit-6.7960-fall-2024/lecture-08/chunks.jsonl
```

完整规范和历史决策入口：

- [StudyKit v0.1 冻结标准](docs/studykit_standard.md)
- [全局进度](docs/project_status.md)
- [完整实施计划](implementation_plan.md)
- [文档索引](docs/README.md)
