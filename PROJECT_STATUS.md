# CoursePilot 项目状态

更新时间：2026-08-07

这份文档是新开发者的快速入口。更完整的状态矩阵见
[docs/project_status.md](docs/project_status.md)，生成管线说明见
[docs/studykit_generation.md](docs/studykit_generation.md)。

## 一句话概括

CoursePilot 已完成可运行、可恢复、可审计的 StudyKit 分阶段生成内核，
但尚未把资料权限、检索、生成、答疑、练习反馈和学习复盘接成面向用户的
端到端课程 Agent。

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
- Audit 发现下游需要边界外的有效来源块时，会先修 EvidencePlan，
  再修对应 Content 或 Practice。
- 最终 StudyKit 由代码确定性组装，并校验 Schema、引用、顺序、唯一 ID、
  Markdown 可渲染性和内部字段泄漏。

### 模型调用可靠性

- 使用官方 DeepSeek OpenAI 兼容接口，阶段输出上限为 65,536 tokens。
- 空正文最多重试三次，非法 JSON 最多重试两次，长度截断最多重试一次。
- 重试保持同一 thinking 配置和完整上下文，不通过切换为 non-thinking
  规避空正文，也不复用截断正文。
- 每次调用保存 finish reason、token usage、request ID 和重试诊断。
- Pipeline 当前版本为 `studykit-pipeline-v0.6-012`，
  Prompt 当前版本为 `studykit-staged-v0.5-007`。

### Schema、工具与课程资料

- 已新增 EvidencePlan、LearningContent、PracticeFlow、QualityAudit 四个 Schema。
- 已提供生成 CLI、质量 profile 评估脚本和 Lecture 并发回归调度器。
- MIT 6.7960 Fall 2024 manifest 已覆盖 Lecture 1–8 所需讲次元数据。
- Outline 页码只要求存在于本讲输入 SourceChunks，不要求每页都进入
  Content 的最小证据并集。
- Practice 的 Prompt 仍要求 5–8 题；验证器允许合理超出，以避免模型偶发
  数量偏差导致整讲失败。`simple` 题数量不设上限，但禁止复杂数值链。

### 测试状态

- 当前自动化测试：`127 passed`。
- 测试覆盖阶段 Schema、Evidence controls、确定性 chunk 并集、引用、
  Markdown LaTeX、模型响应重试、恢复、单次 Audit 回修、非 CS 合成单元、
  CLI 和质量 profile。
- 最新一次新鲜 Lecture 1–8 并发回归结果为 `6/8`：
  Lecture 1、2、5、6、7、8 完整生成；Lecture 3 和 4 失败。
- Lecture 3 的失败来自 Practice 改写全局 limitation；Lecture 4 的失败来自
  assembly 内部字段泄漏阻断 Content 术语回修。这两类通用流程问题已在
  v0.6.012 修复并通过本地测试，但按要求尚未再次调用模型做全量复验。
- 人工检查仍发现 Lecture 2 有一题复杂数值链被误标为 `simple`，
  Lecture 5 的练习工作量和矩阵数量措辞需要改进；语义 Audit 仍不能替代人工复核。

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

运行全部测试：

```bash
.venv/bin/pytest -q
```

## 尚未完成

1. 冻结并实现 CourseManifest、MaterialManifest、MaterialSet、LearnerState
   和 TaskPlan 的运行时接口。
2. 完成公共课程与用户私有资料的统一解析、存储、授权过滤、过期和删除。
3. 建立按用户、会话、课程、版本和讲次过滤的检索层；先关键词检索，
   再按需要增加向量检索和重排。
4. 将 StudyKitGenerator、材料答疑、练习反馈和代码辅导接入现有
   OpenAI 兼容对话 API，完成意图识别和任务路由。
5. 新鲜复验 v0.6.012，争取 Lecture 1–8 稳定 8/8，并加强复杂数值题、
   工作量和答案一致性检查。
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
- 公共资料、用户私有资料和学习状态尚未形成完整运行时隔离。
- 清小搭文件输入、稳定会话标识和文件保留能力仍需账号级实测。
- 当前 6/8 回归之后的流程修复只通过自动化测试，尚无新鲜模型全量结果。

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
