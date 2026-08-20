# 六门课程批次进度

更新时间：`2026-08-12T14:42:40+00:00`

本表由 `scripts/update_csdiy_hybrid_progress.py` 从 registry 当前选定的 fingerprinted build 及其 `course-summary.json` 生成。`完成` 是 root reconciler 的完成单元数；portable validation 单独列出，不能替代独立审计或 finalization。

> **Agent 数量硬门槛：** 本批次调度上限为 **16/16**：1 个 global coordinator；每个 build 最多 4 个 unit worker。agent 数量不参与课程进度计算。

## 完成总览

| 课程 build | 完成 / 总单元 | 完成度 | audited | portable validated | failed | pending | root status |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| MIT 6.042J | 24 / 24 | 100.0% | 24 | 24 | 0 | 0 | `succeeded` |
| UCB CS168 | 26 / 26 | 100.0% | 26 | 26 | 0 | 0 | `succeeded` |
| UCB CS186 | 20 / 20 | 100.0% | 20 | 20 | 0 | 0 | `succeeded` |
| UCB CS188 | 28 / 28 | 100.0% | 28 | 28 | 0 | 0 | `succeeded` |
| UCB CS61A | 28 / 28 | 100.0% | 28 | 28 | 0 | 0 | `succeeded` |
| UCB CS61C | 35 / 35 | 100.0% | 35 | 35 | 0 | 0 | `succeeded` |
| **当前合计** | **161 / 161** | **100.0%** | **161** | **161** | **0** | **0** | — |

## 口径与来源

- 课程分母来自 pinned catalog registry；本表不会删除 failed、blocked 或 pending 单元。
- 每一行的数字来自 registry `coverage.build_id` 指向的 root `course-summary.json`；缺少该文件时显示 0 并标记 `not_reconciled`，不会猜测旧 build 数字。
- 新输入或版本必须生成新 fingerprinted build；旧 build 保留为历史证据，不原地覆盖。
- 已存在的 practice 语义问题本轮只登记为延期问题，不在本轮返工或数字投影中处理；这不表示问题已通过，也不表示可以忽略。
- 新生成或修复的单元仍须逐题满足 StudyKit practice 契约：题目必须具体、可作答、真正考查本单元材料，而不是只复述标题；每题须有真实 source_id@page 锚点，并由独立审计检查练习与内容的语义对应关系。
- root、registry 与本表的更新命令：

```bash
.venv/bin/python scripts/audit_csdiy_registry.py --registry data/catalog/csdiy-course-registry.yaml --repository-root . --report evaluations/csdiy-catalog-registry-audit.json --update
.venv/bin/python scripts/update_csdiy_hybrid_progress.py --repository-root . --registry data/catalog/csdiy-course-registry.yaml --output docs/csdiy-hybrid-batch-progress.md
```

全局机器可读状态以 [`data/catalog/csdiy-course-registry.yaml`](../data/catalog/csdiy-course-registry.yaml) 和 [`evaluations/csdiy-catalog-registry-audit.json`](../evaluations/csdiy-catalog-registry-audit.json) 为准；本表是六课 root 数字的人类可读投影。
