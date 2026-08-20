# 六门课程 practice 语义复核汇总

更新时间：`2026-08-12`
范围：六门课程当前选定 offering 的全部 `161/161` 个单元、`790` 个 practice item。
方法：先由 Luna medium 分片审计，再由独立 Luna xhigh 课程级审计复核；仅离线读取当前 StudyKit、`03-practice-flow.json`、`05-studykit.json` 与 source chunks，未调用网络、provider 或模型 endpoint。旧 build 未被修改。

## 当前结果

| 课程 | 单元 | practice | 分片直接标记需修复 | 课程级确认 blocker | 说明 |
| --- | ---: | ---: | ---: | ---: | --- |
| MIT 6.042J | 24/24 | 71 | 70 | 70 | 主要是 generic exercise shell 与未给定可作答实例 |
| UCB CS168 | 26/26 | 137 | 7 | 7 | 网络拓扑、可靠性与设计比较题缺少固定输入/事件 |
| UCB CS186 | 20/20 | 113 | 2 | 8 | 课程级复核从抽查的原“pass”中又确认 6 条 blocker；与分片计数有重叠，不能相加为总数 |
| UCB CS188 | 28/28 | 139 | 4 | 18 | 课程级复核发现额外 lecture-replay/self-containment 问题 |
| UCB CS61A Summer 2026 | 28/28 | 139 | 1 | 1 | Lecture 28 AMA 题目未在 prompt 中重述可选问题 |
| UCB CS61C | 35/35 | 191 | 13 | 13 | 包含 lecture-specific dependency、citation mismatch 与 worked-example replay |
| **合计** | **161/161** | **790** | **96** | **至少 117** | 课程级数字是确认的 blocker；不能把未被抽查的其余项目自动宣称为通过 |

`96` 是分片报告直接标记的 item-level 非通过数（MIT 70、CS168 6、CS186 2、CS188 4、CS61A 1、CS61C 13）。课程级审计新增并确认了 CS168 的 1 条、CS186 的 6 条和 CS188 的 14 条，因此当前修复清单至少为 `117` 条；CS186 的 8 条中包含原分片的 2 条，禁止重复相加。

这不是“其余 673 条已经证明没有问题”：课程级复核对原本 pass 的项目采用了定向抽样。执行阶段仍要求 worker 扫描全部 `161/161` 单元和 `790` 道题；扫描通过的题只记录，不重写。

执行后校正：全量 worker 扫描确认 `118/790` 个 blocker、`52/161` 个 repair unit；CS186 新增的 `note-07/p3` 位于原已修复单元内，没有增加 unit 分母。随后由不同 agent 对这 52 个单元的全部 practice 做独立门禁，结果为 `8 pass / 44 block`，另有 129 条 blocker 记录（其中包含 checkpoint 一致性、引用、题面自洽性和 baseline 遗留问题）。因此 `portable validated` 不能作为 practice 质量放行条件。

## 质量判断

结构性门槛已经闭合：每个单元均有 portable validation、独立结构审计和最终输出。但 practice 语义门槛尚未闭合，原因不是数字漂移，而是初稿中的题目常把讲义中的变量、示例、题号或隐含上下文留给学习者自行恢复，导致题目不能独立作答；另有少量 citation mismatch、evidence misalignment 和逐字复现讲义 quick check 的情况。

修复时必须在题目中重述完成作答所需的输入、状态、约束、操作、目标和可观察结果；允许保留讲义概念、变量或示例作为证据/提示，但不能让学习者必须回看讲义才能知道题目到底给了什么。每个修复 item 仍需真实 source anchor、提示、预期证据和评价标准一致，并由非作者独立复核。

## 证据文件

- 分片报告：`evaluations/practice-scan-20260812/<course>/range-*.json`
- 课程级报告：`evaluations/practice-scan-20260812/<course>/course-review.json`
- 质量协议：[`docs/studykit-quality-calibration-protocol.md`](../docs/studykit-quality-calibration-protocol.md)
- 六课结构进度：[`docs/csdiy-hybrid-batch-progress.md`](../docs/csdiy-hybrid-batch-progress.md)

## 下一步

1. 以当前 build 为只读基线，按课程生成新的 fingerprinted 修复 build，不原地修改旧 build。
2. 优先修复 MIT 6.042J，其次 CS61C、CS188、CS168、CS186，最后处理 CS61A 的单项 blocker；修复范围以课程级 blocker 清单为准。
3. 每个修复单元重新完成 evidence/content/practice/audit/finalize/portable validation，并由不同 agent 做独立 practice 复核。
4. 所有课程修复后再次汇总；在 practice 语义复核通过前，registry 的课程状态保持 `authoring`/`partial`，不能将六课批次宣称为质量完成。
