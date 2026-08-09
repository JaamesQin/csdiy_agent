# CoursePilot 全局进度

更新时间：2026-08-08

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

产品运行时已经加入意图路由、主动学习画像和静态代码辅导。尚未完成的是
用户资料接入、MaterialSet 权限、在线 SourceChunk 检索、材料答疑、完整学习状态、
清小搭生产部署和真实用户验收。

## 二、能力状态矩阵

| 能力 | 当前状态 | 发布前缺口 |
| --- | --- | --- |
| StudyKit 标准 | 已完成 | 根据端到端使用情况做兼容性演进 |
| SourceChunk/PDF 解析 | 已完成基础能力 | HTML、Markdown、纯文本和用户文件统一入口 |
| 分阶段 StudyKitGenerator | 已完成 | v0.11-019 已完成 v21 新鲜全量模型回归；仍需人工语义复核 |
| Evidence controls | 已完成 | 扩大非 CS 和来源冲突评测 |
| DeepSeek 调用可靠性 | 已完成基础机制 | 生产速率、超时和成本监控 |
| 单次 Audit 回修 | 已完成 | 已加入字段所有权归一化、去重、ID 身份保护和依赖传播 |
| Schema/引用/渲染 | 已完成 | 加入在线权限与检索边界检查 |
| CourseManifest | 有 YAML manifest | 正式 Schema、Catalog 和运行时 API |
| MaterialManifest/MaterialSet | 待完成 | 存储、权限、过期、删除和混合授权 |
| 检索 | 待完成 | 元数据过滤、关键词检索、可选向量检索 |
| OpenAI 兼容 API | 已接入首批 Agent 路由 | 扩展检索、答疑、练习与复盘 handler |
| 主动学习画像 | 已完成本地 SQLite MVP | 验证清小搭稳定身份并演进完整 LearnerState |
| 代码辅导 | 已完成 Python 静态优先 MVP | 接入 SourceChunk 检索；沙箱执行不属于当前范围 |
| 材料答疑 | 待完成 | 权限过滤、检索、引用和端到端测试 |
| LearnerState/复盘 | 有画像事实基础 | 练习/代码证据更新、目标映射和复盘状态机 |
| 清小搭接入 | 本地协议已验证 | 账号级文件、会话、超时和生产实测 |
| 自动化测试 | 187 项通过 | MaterialSet 权限、检索和生产测试 |

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
- Audit blocker 在修复前按字段所有权归一化和规范位置去重；真实 assembly
  问题不会提前阻断 Evidence、Content、Practice 模型修复。
- Audit 修复保护原有 concept、requirement、control、opportunity ID；模型
  擅自新增或删除身份字段时由代码恢复或拒绝，保留有效字段修改。
- PracticeFlow/StudyKit 的学习顺序强制使用 `practice_ids`，所有练习至少出现
  一次；非 practice 步骤使用空数组，review 可以重复引用。

## 四、生成质量与回归状态

Prompt 固定为 `studykit-staged-v0.8-010`，当前 Pipeline 为
`studykit-pipeline-v0.11-019`，运行版本为 `21`。

最近一次使用冻结 Prompt 的 Lecture 1–8 八路并发回归（v21，concurrency=8）：

| 讲次 | 结果 | 初次 Audit | 最终状态 | 质量分 |
| --- | --- | --- | --- | ---: |
| Lecture 1 | 成功，8 题 | pass | repairs_applied_unverified | 93 |
| Lecture 2 | 成功，8 题 | fail | repairs_applied_unverified | 85 |
| Lecture 3 | 成功，9 题 | fail | repairs_applied_unverified | 90 |
| Lecture 4 | 成功，8 题 | fail | repairs_applied_unverified | 91 |
| Lecture 5 | 成功，8 题 | fail | repairs_applied_unverified | 94 |
| Lecture 6 | 成功，8 题 | fail | repairs_applied_unverified | 91 |
| Lecture 7 | 成功，8 题 | fail | repairs_applied_unverified | 93 |
| Lecture 8 | 成功，8 题 | pass | repairs_applied_unverified | 91 |

总结果为 `8/8`，平均人工质量分为 `91/100`。回归耗时约 26 分 42 秒，
每讲学习时间均为 180 分钟，未解决 blocker 为 0；8 个 warning 全部由对应阶段
模型修复，空响应重试 24 次后全部成功。详细机器摘要见
`data/regression/studykit-v21-lectures-01-08/regression-summary.json`。

本轮完成的流程改进包括：

- 所有 blocker 先按字段所有权归一化和规范位置去重，再路由到 Evidence、
  Content、Practice 或 Assembly；真实 assembly 问题不会提前阻断模型阶段。
- Evidence → Content → Practice 依赖修复会自动传播；每阶段最多回修一次，
  Audit 仍只执行一次。
- Audit 修复保护原有 concept、requirement、control、opportunity ID；模型
  擅自新增或删除身份字段时由代码恢复或拒绝，保留有效字段修改。
- PracticeFlow/StudyKit 的学习顺序强制使用 `practice_ids`，所有练习必须至少
  在学习路径出现一次；非 practice 步骤使用空数组，review 可以重复引用。
- 标题优先使用 manifest/unit 的可信标题，内部 `EvidencePlan` 等标签不进入
  学习者文本；外部回归 8 讲均未发现内部标签泄漏。

这些修复及新增在线运行时已有 187 项自动化测试覆盖，并已通过 v21 新鲜外部全量回归；由于设计
上不进行二次语义 Audit，`repairs_applied_unverified` 结果仍必须人工复核。

仍需关注的语义问题：

- Lecture 2 当前离线质量 profile 仍报告缺少规范 `forward pass` 概念和
  `transfer` 题型；正文已有前向传播内容，但元数据/题型未完全对齐。
- Lecture 3 的精确宽度公式和 Lecture 7 的 RMS/谱范数细节受 OCR 限制，
  需要对照原始幻灯片。
- Lecture 8 对 LayerNorm 是否包含可学习仿射参数的表述需要核对来源。
- 所有修复后的产物必须进入人工语义复核队列；结构验证通过不等于语义二次审核通过。

## 五、下一阶段工作

1. 冻结 Manifest、MaterialSet、完整 LearnerState 和 TaskPlan 的最小接口。
2. 完成公共课程和私有用户资料的统一解析、存储、授权与删除。
3. 建立带 owner/session/course/version/unit 过滤的检索层。
4. 在已完成的画像、路由和代码辅导上接入 StudyKit 查询、材料答疑、
   练习反馈、复盘和后台生成状态。
5. 修复 Lecture 2 离线 profile 对齐问题，核对 Lecture 8 LayerNorm 表述，
   并完成 v21 产物的人工语义复核。
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

当前在线 Agent 的约束：StudyKitGenerator 只在离线流程运行；`user` 只是客户端
提供的匿名逻辑标识，不能替代生产授权；代码辅导始终为静态分析并返回
`ran_code=false`；课程页码只来自 Lecture 2/8 人工批准的黄金 StudyKit。

## 七、下一阶段完成定义

- 模板和私有资料都能映射到授权 MaterialSet；
- 检索结果按权限和课程范围过滤，并保留来源锚点；
- 对话入口能执行 StudyKit、材料答疑、练习反馈、代码辅导和复盘；
- 每个 StudyKit 通过 Schema、引用、渲染和内部字段检查；
- v0.11-019/v21 完成新鲜 Lecture 1–8 回归并达到 8/8，记录每讲修复轨迹和质量评分；
- 模板课程与未知私有资料各完成一次端到端验收；
- 清小搭生产能力、安全边界和资料删除策略有实测记录。
