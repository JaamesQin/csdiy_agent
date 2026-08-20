# 六门课程 StudyKit 校准执行 Runbook

更新时间：2026-08-12

本文件定义当前执行方式；当前状态是 `in_progress_hybrid`，校准 build 已开始运行。它配合
[校准样本计划](csdiy-quality-calibration-sample.md) 和
[质量校准协议](studykit-quality-calibration-protocol.md) 使用。

> **⚠️ AGENT 数量硬门槛（每次调度前必须核对）**
>
> - `.codex/config.toml` 的 `32` 只是 session 并发上限，不是本批次应启动的数量，也不代表当前已有 32 个 agent。
> - 本批次目标/上限是 **16 个实际活动槽位**：`1 global coordinator + 15 个隔离 subagents`；subagents 可按当前瓶颈拆为 build/root coordinator、unit worker 和只读审计员。
> - `global coordinator` 计入 16；每个 build 最多 **4 个 unit worker**，绝不启动第五个；build coordinator 不得兼任另一个 build。
> - 已完成、停止或失败的 thread 必须先关闭并从活动计数中移除，才能补位；静态 execution plan、历史 agent 记录和“计划 worker”都不算实际活动 agent。
> - 每次 spawn/close 都要更新本表或批次状态；如果实际活动数无法确认，**停止新增 spawn，先清点再继续**。
> - 当前协调员不把“使用 16 个”当作自动扩容许可：可用槽位不足时宁可少于 16，也不能突破每 build 四个 worker 或重复写入同一 unit。

**最近一次 live 清点已于 2026-08-12 的 WSL 意外重启后失效。**

> **当前可验证结论：`1 global coordinator + 0 个已存活 subagent = 1/16`。**
> 旧表中的 thread ID 在重启后均已不可查询，不能继续冒充活动 agent；`.codex/config.toml`
> 的 `32` 仍只是配置上限。磁盘 checkpoint 仍有效，但 thread 状态必须重新分配、重新核验。

恢复调度前，先读取 registry 和每个 build 的 root summary，再登记真实启动的 thread ID；
完成、停止或失败的 thread 必须从活动计数移除后才能补位。旧的 execution plan、历史
coordinator 记录和磁盘 unit 目录都不计入活动 agent。单个 build 仍最多 4 个 unit worker，
global coordinator 始终保留一个槽位。

**Namespace gate：** 每个 unit worker 在第一次写入前必须验证绝对 `BUILD_ROOT`、绝对
`UNIT_DIR` 和该 build `manifest.yaml.course_id` 三者一致；禁止从仓库根目录的
`execution-plan.json`、旧 build hash 或相似课程名推断输出路径。若验证失败，线程必须停止并
保留孤立检查点，不得复制、删除或合并到正确 build。

## 角色与挡位

| 角色 | Luna 挡位 | 写入范围 | 责任 |
| --- | --- | --- | --- |
| Global coordinator | xhigh | registry、全局 status、aggregate audit | 冻结分配、校验 handoff hash、合并状态；不写任何课程 build 或 unit。 |
| Build coordinator | medium | 一个且仅一个 build root 及其课程 namespace | ingestion/grouping/fingerprint、调度 unit、写 root summaries；不替 unit 作者内容。 |
| Unit author | medium（已完成的高风险校准样本保留 xhigh provenance） | 分配的 unit 目录 | 顺序完成 `01`–`03`，同一 agent 可顺序 checkpoint 这三阶段；随后完成 author-side `04`。 |
| Independent auditor | medium（普通单元）；xhigh（高风险、失败复审） | 只写对应 unit 的 independent-audit/review sidecars | 必须不同于作者；普通单元仍阅读 chunks、01–04、最终包和实际审阅页，逐题检查练习内容关联；高风险单元追加公式、图表、低文本/隐藏文本和跨阶段语义检查。 |

`01`、`02`、`03` 可以由同一个 Luna medium agent 顺序完成，但文件仍必须分别 checkpoint，
不能因此省略任一阶段。作者不得给自己的 unit 充当 independent auditor。

## Audit-ready checkpoint gate

`01`–`04` 仅表示 author checkpoint 完成，**不表示 unit 已可交给 independent auditor**。
作者在交接前必须在同一个、且仅同一个 unit 目录中留下：

- `05-studykit.candidate.json`，并由当前 unit 的 `02`/`03` 语义和真实 source anchors 生成；
- `review-plan.json`，其中 `actual_reviewed_pages` 精确记录真实检查过的页面/heading anchors；
- `metrics.json`，与 candidate 的 citation、chunk、practice 和 review 事实一致；
- candidate 必须通过仓库 portable skill 的权威 `validate_artifacts.py`，不能以作者自定义
  的弱校验或审计摘要替代；同时 candidate 与 YAML/Markdown 的语义一致性必须可验证。

缺少任一项时，unit 状态只能是 `authoring`/`failed_recoverable`，不能启动或通过独立审计。
审计器必须把缺失 checkpoint 记录为 blocker；协调员应派 repair author 补齐后再派不同
身份的 auditor。不得用其他 build 的 candidate，也不得把 finalization 或“练习本身看起来
不错”当作缺失 checkpoint 的替代证据。

若 auditor 的结论与 coordinator 直接运行的 portable validator 冲突，以 portable
validator 的可复现报告为 hard gate；不得把冲突记为 pass，必须保留冲突审计并重新修复/复审。

## 引用审计的最低充分标准

引用审计可以降低冗余要求，但不能降低 StudyKit 合约规定的证据门槛。以下规则适用于新
单元和修复单元：

- 每个实质性学习目标、前置知识、核心概念、误区、练习任务及其关键评价要求，至少有一个
  真实且相关的 source anchor；练习必须能从题面直接开始，并能由引用材料支持其求解。
- 同一页或同一 heading 明确支撑的一组紧密相关陈述，可以共享一个 citation；不要求为同一
  事实重复挂多个相邻页码，也不要求把一个段落机械拆成逐句 citation。
- citation 审计重点检查缺失、错配、越界、虚构 chunk、标题/无关页和隐藏文本证据；普通单元
  使用 Luna medium，不再为已经充分支撑的陈述追求引用数量最大化。
- 公式、图表、低文本页、来源缺失、历史 blocker 或修复后争议仍使用 Luna xhigh，并检查
  公式 provenance、实际可见证据和页级风险。
- 已存在的 citation blocker 必须修复并复审；“减少冗余引用”不能把缺失或不相关引用改判
  为通过。

该调整只改变审计深度和冗余判断，不改变 `SKILL.md` 中“每个实质性陈述必须有相关锚点”及
`validate_review.py` 对锚点存在性的硬门槛。

## 昨日 proven standard/fast hybrid

本次恢复昨天已经验证过的 unit-level 混合调度，而不是把同一单元重复生成两遍：

- `standard`：公式/证明、复杂算法状态、寄存器或代码状态、长页高密度 slides、online
  textbook/heading anchors、解析风险或既有审计暴露问题的单元；
- `fast`：结构稳定、低解析风险、无保留公式且不依赖隐藏层的常规 slides 单元；
- fast 单元仍必须完成 content-grounded practice、portable validation、页选择和风险
  检查；发现语义、引用、公式、视觉或练习 blocker 时，单元升级到 standard；
- 只有输入 hash、manifest、chunks、schema、prompt 和 pipeline fingerprint 完全一致时
  才能复用 checkpoint，否则创建新的 build ID。

昨日 canonical 结果为：CMU 15-213 使用 17 个 standard / 7 个 fast 单元，UCB CS61B
使用 10 个 standard / 30 个 fast 单元。当前 CS61A 已完成的校准样本保留其 standard
质量证据，后续常规单元由 Luna medium author 和 Luna medium auditor 处理。Luna xhigh
仅用于公式/证明、复杂算法状态、低文本或隐藏文本风险、来源缺失、此前失败以及修复后的
争议复审；审计挡位降低不改变审计覆盖范围。

## 16-slot 分配

完整批量阶段按 skill 的并行安全上限规划：

```text
1 global coordinator
+ 3 build coordinators
+ 3 × 4 unit workers
= 16 slots
```

三个 build coordinator 各自只拥有一个课程 build；不得把两个课程放入同一 build root。六门
课程按两波三门执行。项目 `.codex/config.toml` 当前将 session cap 设为 32；16-slot 是
本批次的安全分配规模，而不是单个 build 的 worker 数。实际调度必须以真实启动的 agent
thread 为准，禁止把静态分配冒充已启动 worker：

- Wave A：`ucb-cs61a`、`ucb-cs188`、`mit-6-042j`；
- Wave B：`ucb-cs168`、`ucb-cs186`、`ucb-cs61c`。

独立审计是每波的后续阶段：审计者替换已完成的 unit-worker 槽位或由下一波调度，不能在同一
build 中增加第五个 worker。每个 unit 的审计者必须与作者身份不同；global coordinator
始终保留一个槽位。

校准样本先按相同两波生成六个 unit。样本阶段不为方便而创建 fast/standard 双 build；
只创建一个新的 hybrid fingerprinted build。build 根级 fingerprint 保留默认挡位（当前为
`fast`），每个 unit 在自己的 `metrics.json`、`review-plan.json`、audit 和 finalization
records 中记录有效挡位；因此同一 build 可以有显式 `standard` unit override，但不得把
root default 当成该 unit 的有效 authoring mode。样本未通过前，不开始其余 unit。

## 获准后的单 course 流程

Build coordinator 对其唯一课程执行：

1. 用 `scripts/prepare_studykit_build.py` 创建新的 hybrid/draft fingerprint；若输入、
   skill/pipeline/schema 版本或质量挡位改变，创建新 build ID，不编辑旧 build。
2. 运行 `skills/studykit-generator/scripts/plan_execution.py`，传入该 build 的 unit
   列表和每 build 不超过四个 worker；plan 只写隔离 build 目录。
3. 每个 Unit author 读取 source chunks 和 skill contract，依次写入 `01`、`02`、`03`。
   在接受 `03` 前，coordinator 检查每一道题是否有具体设置、可观察结果、匹配 hint/
   expected evidence/evaluation 和相关 page/heading anchor。
4. 作者完成 `04-quality-audit.json` 后，安排不同的 auditor。普通单元使用 Luna medium；
   若 unit 命中公式/证明、图表或低文本/隐藏文本风险、来源缺失、历史 blocker，或属于
   修复后的争议复审，则使用 Luna xhigh。两种挡位都必须写入
   `independent-audit.json`，包括作者/审计者身份、结果、blockers、实际审阅页码和逐题
   练习检查记录。medium 只降低推理深度，不减少 unit、练习或关键引用的审计覆盖。
5. 只有 independent audit 通过，才运行 `finalize_studykit.py`、`validate_review.py`、
   `verify_unit_outputs.py` 和 candidate/final/YAML 语义相等性检查。
6. coordinator 写 batch summary、course index 和 handoff；global coordinator 检查
   build fingerprint、manifest/source hashes、unit counts 和 handoff hash 后才合并 registry。

## 校准放行

六个样本都要完成上述流程。global coordinator 与独立审计者将它们和昨日 CMU 15-213、
UCB CS61B 代表单元及 `data/golden/` 比较，记录实际练习 ID、引用页、风险页和结论。
以下任一项失败即暂停推广并回到对应 checkpoint：

- 存在 generic exercise shell 或学习者必须先发明完整场景；
- 练习不能从题面直接开始求解，或没有可验证的预期结果；
- hint、expected evidence、evaluation 与题目不是同一任务；
- citation 只指向标题/无关页，或使用隐藏文字；
- independent auditor 缺失、与作者相同、没有实际审阅页，或未逐题检查。

校准通过后才将六门课程的 `practice_quality_review` 更新为 `passed`，再恢复全课程队列。
在此之前，registry 中的六个 `needs_repair` 状态不得被任何结构验证结果覆盖。
