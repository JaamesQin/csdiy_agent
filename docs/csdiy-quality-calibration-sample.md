# 六门课程 StudyKit 校准样本

更新时间：2026-08-11

本表是批量生成前的样本选择。当前已开始执行：CS61A Summer 2026 校准 build 已完成
Lecture 10、13 的最终验证，Lecture 14、15 已完成作者 checkpoint，正在独立审计；其余
课程样本仍按下表推进。全部样本完成独立审计并通过
[质量校准协议](studykit-quality-calibration-protocol.md) 后，才可推广到六门课程的其余单元。

| 课程 | 样本单元 | 资料形态 | 选择理由 |
| --- | --- | --- | --- |
| `ucb-cs61a-spring-2026` | `lecture-10` — Iterators and Generators | 官方 PDF slides，39 页，`pdf-page-v0.2` | 直接覆盖此前暴露的“围绕概念设计例子”空壳问题；检查代码/迭代器内容能否生成给定输入、状态和可观察输出。 |
| `ucb-cs188-spring-2026` | `lecture-03` — A* Search and Heuristics | 官方 PDF slides，67 页，`pdf-page-v0.2` | 检查算法状态、优先队列/启发式条件和可计算结果是否被具体化，而非只复述标题。 |
| `mit-6-042j-spring-2024` | `lecture-02` — Contradiction and Induction | MIT 官方 PDF，10 页，`pdf-page-v0.2` | 检查数学证明材料中的条件、推理步骤和结论是否形成可验证练习，并对比 `data/golden/` 的形式严谨性。 |
| `ucb-cs168-spring-2026` | `lecture-11` — Transport 1: TCP I | 官方公开 PDF，78 页，`pdf-page-v0.2` | 检查网络协议/状态转换类长 slides 的内容覆盖、页锚和条件变化题。 |
| `ucb-cs186-spring-2026` | `note-01` — SQL Part 1 - Basic Queries | 官方在线 textbook/Markdown，15 个 heading chunks | 检查非 PDF、heading anchor 和 online textbook 的具体 SQL 输入/结果练习；验证不能把教材章节标题当内容。 |
| `ucb-cs61c-spring-2026` | `lecture-10` — RISC-V Data Transfer | staff-authored Markdown，35 个 heading chunks | 检查架构代码/寄存器/内存状态的可解设置，以及非 PDF 内容的引用和视觉审查边界。 |

## 样本放行规则

- 六个单元都必须完成同一个 standard fingerprinted build 的 `01`–`05` checkpoint、确定性
  验证、最终 JSON/YAML/Markdown 和 review-plan；不得拿当前旧 build 的成功状态替代新审计。
- 每道练习由作者绑定到 EvidencePlan/Content 的具体 requirement、concept 或 opportunity，
  给出学习者可直接求解的设置、可观察结果、具体 hint 和匹配的 expected evidence。
- 独立 Luna xhigh 审计者逐题阅读 source chunks、三阶段 checkpoint、最终包和实际审阅页；
  同一 Luna medium 顺序完成 `01`–`03` 不构成独立审计。
- 任一样本出现 generic shell、无法从题面开始求解、预期结果不可验证或引用无关，六门课程
  暂停推广；只对问题阶段做一次定向修复，再由不同审计者复核。
- 通过后，校准记录必须逐项对比昨日 CMU 15-213/UCB CS61B 代表单元和
  `data/golden/`，并明确记录实际审阅的练习 ID、页码、问题和结论。

当前状态：`in_progress_hybrid`。校准执行恢复昨天验证过的 standard/fast unit-level
混合调度：复杂或高风险单元走 standard，低风险常规单元走 fast；同一单元不重复生成，
失败单元升级到 standard。作者使用 Luna medium，独立审计和异常复核使用 Luna xhigh。
