# 六课 practice-only repair 结果（2026-08-12）

本记录是 `evaluations/csdiy-six-course-practice-repair-plan-20260812.json` 的执行结果。它只描述本轮六个新 fingerprinted builds，不替换六门课程原有的 baseline build。

## 数量口径

以每个 unit 的最终 candidate practice 列表为准，而不是假定所有 `03-practice-flow.json` 使用同一种顶层字段：

| 课程 | units 扫描 | practices 扫描 | scan-time blocker | repair units | 实际修改 practices | 独立门禁 pass/block |
|---|---:|---:|---:|---:|---:|---:|
| MIT 6.042J | 24 | 71 | 70 | 24 | 70 | 0 / 24 |
| UCB CS168 | 26 | 137 | 7 | 3 | 7 | 0 / 3 |
| UCB CS186 | 20 | 113 | 9 | 8 | 9 | 2 / 6 |
| UCB CS188 | 28 | 139 | 18 | 10 | 18 | 4 / 6 |
| UCB CS61A | 28 | 139 | 1 | 1 | 1 | 0 / 1 |
| UCB CS61C | 35 | 191 | 13 | 6 | 13 | 2 / 4 |
| **合计** | **161** | **790** | **118** | **52** | **118** | **8 / 44** |

CS186 的 `note-07/p3` 是全量 worker 扫描中新确认的 blocker，但 `note-07` 已经在修复单元集合中，所以没有增加 unit 分母。CS168 的旧 `03` 简表曾得到 125；lecture-05/lecture-10 等结构例外使这个数字不完整，最终 candidate 核对为 137。

## 独立门禁结果

不同于作者的 Luna xhigh agent 复核了 52 个修复 unit 的全部 practice，写入每个 unit 的 `independent-audit.xhigh.json` 和 canonical `independent-audit.json`。结果为 8 个通过、44 个阻塞，共 129 条 blocker 记录。

典型 blocker 包括：

- MIT 6.042J：70/71 道题的 `expected_evidence` 与 `evaluation` 仍是跨题通用模板；另有状态、概率、递推边界和算术题面不自洽。
- CS168：修复后的题面与 evaluation 仍使用旧变量，hint 泄露完整答案，或 repair 记录无法满足一次修复约束。
- CS186：引用为空/占位、复用讲义原题并泄露解法、提示值与 expected evidence 不一致。
- CS188：缺条件、转移数值错误、数学期望分支错误，以及本轮修复项仍未定义必要权衡。
- CS61A：`lecture-28/p2` 的“至少 8 行”与给出的 7 个选择不相容；`p3` 没有在题面列出资源候选集合。
- CS61C：旧 validator 仍检查修复前题面，且多个 unit 存在 03→05 漂移或错误 AMAT 期望值。

这些 blocker 均保留在独立审计文件中；本轮没有第二次偷偷修复，也没有用成功的 portable validator 覆盖语义失败。

## build 与 false-complete 校正

当前 practice-repair build 路径：

- [MIT 6.042J build](../outputs/mit-6-042j-spring-2024/1db4a3a7fee047565818f331b9bc809fd00b9036ce97826a0cafcf29049c53ce/)
- [UCB CS168 build](../outputs/ucb-cs168-spring-2026/d194c537857777cc12747610d694519d43545a1928ff50daa93f66051deaa8d0/)
- [UCB CS186 build](../outputs/ucb-cs186-spring-2026/7e26cbe86e81324985a46ea0d9cfd694ce0d077351605da080d4eecd612c2fe0/)
- [UCB CS188 build](../outputs/ucb-cs188-spring-2026/132fad020d624070614235f6b2378fd5d9d5cd412a9acf00c4a6be8d6987c0f4/)
- [UCB CS61A build](../outputs/ucb-cs61a-summer-2026/09e38a57a95cfa256b6c3270013dc6fb6bf4dcba08d2191d11a7879b43a9b933/)
- [UCB CS61C build](../outputs/ucb-cs61c-spring-2026/12b1704ea45e2daca9b589b480185850638ca311835eede3f1cfc6ecffc82fd5/)

本轮还修复了一个 build-level false-complete 根因：旧 baseline 的 `independent-audit.post-final.*` sidecar 会覆盖当前 canonical blocker。`reconcile_studykit_unit.py` 现在写入当前 release-stage sidecar，并记录 `reconciled_at`；build reconcile 按当前 reconciliation 时间选择权威证据。回放后六个 build 的状态为：MIT failed；CS168/CS186/CS188/CS61A/CS61C 均 partial，CS61A 不再错误显示 succeeded。

## 结论与下一步

本轮没有任何课程达到 semantic release gate，不能更新为 `complete`，也不能发布到 StudyKitStore。下一轮应单独建立新的 fingerprinted repair build，并针对本记录中的 blocker 做内容级修复；至少必须同步修改题面、hint、expected evidence、evaluation、citations 和 candidate projection，再重新执行 portable validators 与不同 agent 的独立门禁。

Tracked plan: [`csdiy-six-course-practice-repair-plan-20260812.json`](csdiy-six-course-practice-repair-plan-20260812.json)。原始 raw/chunks/outputs 仍是 ignored local checkpoints；本记录、计划、脚本和测试是 tracked reproducibility metadata。当前未 stage、未 commit。
