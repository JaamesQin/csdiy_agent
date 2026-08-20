# 六课 Practice Repair 循环进度

更新时间：`2026-08-12 22:38 +08:00`

权威输入为各课程最新 `repair-plan.json`、unit validators、fresh independent audit 与 build-level `result.json`。本文仅是确定性人类可读投影，不替代 registry 或 build records。

## 当前总览

| 指标 | 当前值 |
| --- | ---: |
| 六课 source-supported units | 161 |
| portable validated | 161 / 161 |
| 已在完整成功 build 中闭环 | 161 / 161 |
| 完整成功课程 | 6 / 6 |
| 当前 residual gate units | 0 |
| 当前成功 build 的 failed / pending | 0 / 0 |
| 离线 targeted tests | 50 passed |
| 最近完整要求测试 | 326 passed |

## 当前最终/活动 build

| 课程 | build ID | 单元 | 状态 | residual / next action |
| --- | --- | ---: | --- | --- |
| UCB CS168 | `5a5845d06392380ddb75c75279c52cb9154f6e0e2ebedafcccf0007c681db104` | 26 | succeeded | 0 |
| UCB CS61A | `c24fc9db0a8b098c4656ede6f8efe74eafac9335c6f315b23a61fed929a9fbe2` | 28 | succeeded | 0 |
| UCB CS61C | `3aa107ff8c441c733af11b2dead8a08344a629e05db0ffed30df152aa39054c8` | 35 | succeeded | 0 |
| UCB CS188 | `8ae49b80fe5b56b9d43b575a50ed70dcc89b9b217ab988f691e0c446cd23f169` | 28 | succeeded | 0 |
| UCB CS186 | `07a4426e48eae39ad61b2b09122cbb72f4a04896a0fd715e2cc1e4c478327939` | 20 | succeeded | 0 |
| MIT 6.042J | `33598b2ae46119080dfbf1bd71df11c55e911d8658188adf781286d93ff65f77` | 24 | succeeded | 0 |

## 本轮状态变化

- 修复审计选择器：显式审计时间优先于 `post-final` 文件名；repair unit 中当前 build + 当前 plan + `fresh_repair_audit=true` 的记录具有最高 authority。
- 新增回归测试，防止旧 `post-final` blocker 遮蔽后续 passing re-audit，也防止无 fresh marker 的 sidecar 遮蔽当前 canonical fresh audit。
- CS168、CS61A、CS61C 已经重新 reconcile 为全量 succeeded。
- CS188 lecture-10、CS186 note-10/note-15 只需当前 build 的 fresh audit 和 review metadata，不重写学习内容。
- MIT residual 以新 fingerprint build 处理；lecture-01/03 的 parent mismatch 报告已由仓库权威 digest 复算证明为审计算法误差，原审计保留，新审计必须使用仓库实现。
- CS188 lecture-10、CS186 note-10/note-15 与 MIT 10 个 residual units 已完成 fresh/re-audit、deterministic finalization 和 validators；六课 build-level reconcile 均为 succeeded。
- 全局 registry 已绑定上述最新 active build，六课显示 `161/161 validated`、`161/161 audited`、无 missing audit；其中五课仍因本轮明确暂缓的 course-level visual-review 状态保持 `authoring`，CS61A 为 `complete`。这不会回退六课 repair build 的 succeeded 状态，也避免将未关闭的视觉门禁误报为 catalog complete。

## 放行条件

- 所有 repair units 都有当前 build/plan 绑定、作者不同的 fresh per-practice audit。
- 每道题具体、自包含或明确复述必要条件、检验可迁移概念、结果可判定，hint 不泄露最终答案。
- 03/candidate/final JSON/YAML/Markdown 语义一致；citation、portable validation、review validation 与 unit verify 全部通过。
- direct-parent snapshot digest 与声明和实际 parent 一致；旧 audit 只作 provenance，不能冒充本轮 fresh audit。
- 每个最终 build 的 `result.json.status` 为 `succeeded`，且 failed/pending 都为 0。
