# CoursePilot 全局进度

更新时间：2026-08-13

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

本地账号、会话安全和可信 subject 学习画像已经落地，产品运行时也已加入意图路由、
能力帮助、主动学习画像、全目录分级课程导航、golden StudyKit 查询/材料/概念/练习能力
和多语言静态代码辅导。尚未完成的是用户资料接入、MaterialSet 权限、在线 SourceChunk
检索、完整 LearnerState、清小搭生产部署和真实用户验收。

离线成果现有独立 SQLite 归档层：2026-08-12 的整理保留 12 个最新 build、286 个
StudyKit 和 12,008 个文本审计工件，并删除约 4.27 GiB 的重复 `outputs/` checkpoint/
图片缓存。2026-08-13 已把 `data/` 迁移为私有 Git submodule；Git LFS 管理
`archive/studykits.sqlite3` 与 anchored JSONL chunks。归档状态是 `validated_draft`，
在线运行时使用只读 archive adapter 和组合 Store；build/document 双 `approved` 后才优先
读取 archive，否则回退到人工批准的 golden 数据。当前 286 条均为 `validated_draft`，
所以实际在线范围仍为 Lecture 2/8。

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
| CourseManifest / Catalog | 已完成类型化只读 Catalog MVP | 正式 Schema、数据库和独立分类审核 |
| MaterialManifest/MaterialSet | 待完成 | 存储、权限、过期、删除和混合授权 |
| 私有检索数据归档 | 已完成精简快照 | 接入 permission-filtered 在线读取；当前仍为 `validated_draft` |
| 检索 | 待完成 | 元数据过滤、关键词检索、可选向量检索 |
| 本地账号与会话 | 已完成安全 MVP | 邮箱、找回/修改密码和账号删除不在首版 |
| OpenAI 兼容 API | 双身份兼容且已接入八项 Agent 能力 | 扩展权限检索、私有材料与复盘 handler |
| 主动学习画像 | 已完成账号/legacy 隔离的 SQLite MVP | 验证清小搭稳定身份并演进完整 LearnerState |
| 能力帮助 | 已完成可发现能力目录与 `/help` | 新能力接入时同步状态与帮助内容 |
| 代码辅导 | 已完成 Python AST + Tree-sitter 多语言静态 MVP | 接入 SourceChunk 检索；沙箱执行不属于当前范围 |
| StudyKit 查询/概念/练习选择 | 已完成 approved archive + golden 回退 MVP | 人工批准更多课程和端到端评测 |
| 材料答疑/练习反馈 | 已完成页码白名单与透明降级 MVP | SourceChunk 检索、权限过滤和生产模型评测 |
| LearnerState/复盘 | 有账号隔离的画像事实基础 | 练习/代码证据更新、目标映射和复盘状态机 |
| 清小搭接入 | 本地协议已验证 | 账号级文件、会话、超时和生产实测 |
| 自动化测试 | 303 项通过 | MaterialSet 权限、检索和生产测试 |

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
- 新增内容对齐的练习 checkpoint 合同：练习必须从 EvidencePlan/Content 的具体
  requirement、concept 或 opportunity 派生，给出可求解设置、可观察结果和相关引用；
  独立审计必须逐题检查。六课最终 repair builds 已按此合同完成逐题审计。
- selective repair 仅离线可用：每个新 build 保留直接父 snapshot，rich independent audit
  必须绑定当前 build+repair plan，并对当前 practice IDs 做无缺失、无重复、无 stale ID 的
  精确逐题覆盖。任何 mismatch 都阻止 completion/false-complete；deterministic Schema pass
  不能替代语义审查。六课 repair 已达到 161/161 validated、161/161 audited 和
  6/6 build succeeded；五课未关闭课程级视觉复核，故 catalog 仍非全局 complete。

## 四、生成质量与回归状态

2026-08-12 六课集中 practice repair 已闭环 161 个 source-supported units，当前
residual gate units、failed 和 pending 均为 0。最终 build IDs 与逐题审计口径见
`evaluations/csdiy-six-course-practice-repair-round2-progress.md`。这表示 practice repair
build 成功，不替代尚未完成的课程级 visual-review gate。

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
  模型修复，空响应重试 24 次后全部成功。详细机器摘要属于未纳入精简 submodule 的
  历史本地 regression 数据。

2026-08-10 另完成一次 host-authored portable 全课程构建，覆盖官方可用的
Lecture 01–21、23、24 共 23 讲。23/23 均通过 portable schema、引用锚和渲染验证，
并经 Lecture 09、18、21 随机语义抽查。reviewed 重复包未纳入精简 submodule；正式
archive 记录仍为 `validated_draft`，不接入在线查询，也不能直接混入采用另一 Schema
的 `data/golden/`。

同日从协作者离线快照恢复并复核 MIT 6.S081 Fall 2021 的完整 v0.2 构建。
Lecture 01–24 共 24/24 讲重新通过 artifact、review 与输出一致性校验，随机抽查
Lecture 07、15、17 的来源页、主张、练习和限制也通过。reviewed 重复包以及 raw、
chunks、页图和完整作者化 build 继续留在精简远端之外；正式 archive 记录仍为
`validated_draft`，不会因这些离线结果自动成为 online-ready。

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

这些修复、账号安全链路及新增在线运行时已有 303 项自动化测试覆盖，并已通过 v21 新鲜外部全量回归；由于设计
上不进行二次语义 Audit，`repairs_applied_unverified` 结果仍必须人工复核。

仍需关注的语义问题：

- Lecture 2 当前离线质量 profile 仍报告缺少规范 `forward pass` 概念和
  `transfer` 题型；正文已有前向传播内容，但元数据/题型未完全对齐。
- Lecture 3 的精确宽度公式和 Lecture 7 的 RMS/谱范数细节受 OCR 限制，
  需要对照原始幻灯片。
- Lecture 8 对 LayerNorm 是否包含可学习仿射参数的表述需要核对来源。
- 所有修复后的产物必须进入人工语义复核队列；结构验证通过不等于语义二次审核通过。

## 五、下一阶段工作

1. 为 archive 文档完成独立人工批准流程，并冻结 MaterialSet、完整 LearnerState 和
   TaskPlan 的最小接口；复用可信 `account:<uuid>` 身份。
2. 完成公共课程和私有用户资料的统一解析、存储、授权与删除。
3. 建立带 owner/session/course/version/unit 过滤的检索层。
4. 将已完成的 approved archive + golden 回退材料答疑和练习反馈接入 SourceChunk，继续实现复盘和后台生成状态。
5. 修复 Lecture 2 离线 profile 对齐问题，核对 Lecture 8 LayerNorm 表述，
   并完成 v21 产物的人工语义复核。
6. 实现基于用户确认证据的最小学习状态与复盘。
7. 完成清小搭实测、生产部署、日志脱敏和安全测试。
8. 验收模板课程与未知私有资料两条端到端流程，开展用户试用。

## 六、并行开发建议

在当前只读接口基础上，可分为四条并行工作流：

- Agent/API：意图路由、上下文管理和对话编排；
- Material/Retrieval：资料输入、MaterialSet、权限和检索；
- Quality/Evaluation：生成回归、语义审核、离线评测和红队；
- Platform/Product：清小搭实测、部署、前端、Demo 和用户试用。

MaterialSet 与检索接口是下一阶段 Agent 扩展的主要前置依赖；端到端和平台验收必须在
各工作流集成后串行关闭。

当前在线 Agent 的约束：StudyKitGenerator 只在离线流程运行；Cookie 会话只使用
服务端验证的 `account:<uuid>`，API Key 请求的 `user` 只映射为 `legacy:<user>`、
不能替代生产授权；能力总览只展示已经上线的能力；代码辅导始终为静态分析并返回
`ran_code=false`，语言解析不调用编译器或执行用户代码；课程目录事实来自已校验 registry/
Manifest，课程页码只来自 Lecture 2/8 人工批准的黄金 StudyKit。练习答案不持久化。

## 七、下一阶段完成定义

- 模板和私有资料都能映射到授权 MaterialSet；
- 检索结果按权限和课程范围过滤，并保留来源锚点；
- 对话入口能执行 StudyKit、材料答疑、练习反馈、代码辅导和复盘；
- 每个 StudyKit 通过 Schema、引用、渲染和内部字段检查；
- v0.11-019/v21 完成新鲜 Lecture 1–8 回归并达到 8/8，记录每讲修复轨迹和质量评分；
- 模板课程与未知私有资料各完成一次端到端验收；
- 清小搭生产能力、安全边界和资料删除策略有实测记录。
# Online Agent P0–P2 status (2026-08-17)

See [`online-agent-p0-p2.md`](online-agent-p0-p2.md) for the enabled contracts and explicit deferred
boundaries. This status does not claim private retrieval, vector retrieval, or globally complete
StudyKit repair.

Online practice selection now automatically clarifies approved questions with one model call and
falls back to the original on any contract violation. TaskPlan is separate; concrete capabilities are
limited to one online model call, while independent semantic review remains an offline authoring gate.
Context-token v2 adds only a presentation kind/digest and continues to accept v1.
