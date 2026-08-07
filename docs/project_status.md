# CoursePilot 全局进度

更新时间：2026-08-07

状态口径：

- 已完成：已有实现、测试和可复查产物。
- 进行中：核心实现存在，但尚未达到生产或端到端验收门槛。
- 待完成：已有设计，尚无完整运行时实现。
- 外部待确认：依赖清小搭账号或生产环境实测。

## 一、总体判断

项目已经从“人工 StudyKit 样例和验证工具”推进到“自动分阶段生成内核”。
当前生成器能够从 SourceChunks 建立 EvidencePlan，动态发现本讲课程约束，
生成 Content 和 Practice，执行一次独立 Audit，并确定性输出
StudyKit JSON/YAML/Markdown。

尚未完成的是产品运行时闭环：用户资料接入、MaterialSet 权限、在线检索、
Agent 意图路由、材料答疑、学习状态、清小搭生产部署和真实用户验收。

## 二、能力状态矩阵

| 能力 | 当前状态 | 发布前缺口 |
| --- | --- | --- |
| StudyKit 标准 | 已完成 | 根据端到端使用情况做兼容性演进 |
| SourceChunk/PDF 解析 | 已完成基础能力 | HTML、Markdown、纯文本和用户文件统一入口 |
| 分阶段 StudyKitGenerator | 已完成 | v0.6.012 新鲜全量模型复验 |
| Evidence controls | 已完成 | 扩大非 CS 和来源冲突评测 |
| DeepSeek 调用可靠性 | 已完成基础机制 | 生产速率、超时和成本监控 |
| 单次 Audit 回修 | 已完成 | 提升复杂工作量和答案一致性召回 |
| Schema/引用/渲染 | 已完成 | 加入在线权限与检索边界检查 |
| CourseManifest | 有 YAML manifest | 正式 Schema、Catalog 和运行时 API |
| MaterialManifest/MaterialSet | 待完成 | 存储、权限、过期、删除和混合授权 |
| 检索 | 待完成 | 元数据过滤、关键词检索、可选向量检索 |
| OpenAI 兼容 API | 有协议服务 | 接入真实课程 Agent 路由 |
| 材料答疑/代码辅导 | 有设计和局部组件 | 运行时编排与端到端测试 |
| LearnerState/复盘 | 待完成 | 最小 Schema、证据更新和删除能力 |
| 清小搭接入 | 本地协议已验证 | 账号级文件、会话、超时和生产实测 |
| 自动化测试 | 127 项通过 | 端到端、权限、安全和生产测试 |

## 三、已经完成的生成闭环

```text
GenerationRequest + SourceChunks
  → EvidenceBundle
  → EvidencePlan
  → LearningContent
  → PracticeFlow
  → QualityAudit
  → 最多一次依赖顺序回修
  → 确定性 StudyKit
  → JSON Schema / citation / render validation
```

关键约束：

- 通用 Prompt 不包含特定讲次的 Jacobian、QKV 或矩阵布局事实。
- 符号、术语、顺序、单位、表示和来源风险由 Evidence 阶段从资料发现。
- 下游不能创造 EvidencePlan 中不存在的课程控制。
- Practice 题型由资料和学习目标决定，CS 资料可以使用代码、调试和形式推理；
  非 CS 资料不会被强制生成数学题或代码题。
- `numeric_complexity` 只允许 `none/simple`；simple 数量不限，但每题必须轻量。
- Audit 只运行一次；回修后明确标记为 `repairs_applied_unverified`，
  仍需人工复核。

## 四、生成质量与回归状态

Prompt 固定为 `studykit-staged-v0.5-007`，当前 Pipeline 为
`studykit-pipeline-v0.6-012`。

最近一次使用冻结 Prompt 的 Lecture 1–8 八路并发回归：

| 讲次 | 结果 | Audit |
| --- | --- | --- |
| Lecture 1 | 成功，8 题 | pass |
| Lecture 2 | 成功，8 题 | pass |
| Lecture 3 | Practice 验证失败 | 未进入 Audit |
| Lecture 4 | Audit/assembly 编排失败 | fail |
| Lecture 5 | 成功，9 题 | pass |
| Lecture 6 | 成功，6 题 | pass |
| Lecture 7 | 成功，6 题 | pass |
| Lecture 8 | 成功，8 题 | repairs applied, unverified |

总结果为 `6/8`。失败后完成的 v0.6.012 修复包括：

- Practice 的 global limitations 由代码从 EvidencePlan 确定性继承；
- 标题中的 `EvidencePlan` 和内部解析诊断名不再进入学习者文本；
- 已由最终验证解决的 assembly 内部字段问题不再阻断同一 Audit 中的
  Content/Practice 回修；
- Evidence 边界外的下游修复会先提升为 Evidence repair，再按依赖顺序执行。

这些修复已有自动化测试，但按要求没有再执行第三轮模型全量回归。

仍需关注的语义问题：

- Lecture 2 的完整前向、反向和权重更新题属于复杂数值链，
  Audit 未识别其被误标为 `simple`。
- Lecture 5 练习总工作量偏大，且一处矩阵数量措辞不一致。
- `repairs_applied_unverified` 的产物必须进入人工复核队列。

## 五、下一阶段工作

1. 冻结 Manifest、MaterialSet、LearnerState 和 TaskPlan 的最小接口。
2. 完成公共课程和私有用户资料的统一解析、存储、授权与删除。
3. 建立带 owner/session/course/version/unit 过滤的检索层。
4. 将生成、答疑、练习反馈和代码辅导接入 OpenAI 兼容对话 API。
5. 新鲜验证 v0.6.012，并加强复杂数值题、工作量和答案一致性审核。
6. 实现基于用户确认证据的最小学习状态与复盘。
7. 完成清小搭实测、生产部署、日志脱敏和安全测试。
8. 验收模板课程与未知私有资料两条端到端流程，开展用户试用。

## 六、并行开发建议

在核心 Schema 和接口冻结后，可分为四条并行工作流：

- Agent/API：意图路由、上下文管理和对话编排；
- Material/Retrieval：资料输入、MaterialSet、权限和检索；
- Quality/Evaluation：生成回归、语义审核、离线评测和红队；
- Platform/Product：清小搭实测、部署、前端、Demo 和用户试用。

MaterialSet 与检索接口是 Agent 编排的主要前置依赖；端到端和平台验收必须在
各工作流集成后串行关闭。

## 七、下一阶段完成定义

- 模板和私有资料都能映射到授权 MaterialSet；
- 检索结果按权限和课程范围过滤，并保留来源锚点；
- 对话入口能执行 StudyKit、材料答疑、练习反馈、代码辅导和复盘；
- 每个 StudyKit 通过 Schema、引用、渲染和内部字段检查；
- v0.6.012 完成新鲜 Lecture 1–8 回归并记录失败分析；
- 模板课程与未知私有资料各完成一次端到端验收；
- 清小搭生产能力、安全边界和资料删除策略有实测记录。
