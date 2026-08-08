# StudyKit 分阶段生成

本地生成器默认串行执行三个生成阶段、一个独立质量审核阶段，再进行一次不调用模型的确定性组装：

1. `01-evidence-plan.json`：证据规划、候选概念、可评估 requirements、动态 `evidence_controls` 和阶段所需 `chunk_id`。
2. `02-learning-content.json`：目标、requirement 映射、前置知识、提纲、核心概念、术语和误区。
3. `03-practice-flow.json`：5–8 道轻量练习、requirement 覆盖、内部评价依据和学习顺序。
4. `04-quality-audit.json`：来源控制、来源风险、事实、答案一致性、覆盖、术语和格式的独立审核。
5. `05-studykit.json`：确定性组装并通过完整 StudyKit Schema、引用和渲染检查的草稿。

`run.json` 保存输入指纹、Manifest hash、Schema 与 prompt 版本、模型、逐阶段状态、耗时、用量和请求 ID。若供应商返回 `completion_tokens_details.reasoning_tokens`，它会作为用量统计记录。模型返回的原始 `reasoning_content` 不会被读取或写入任何产物。

Evidence、Content、Practice 和 Audit 默认启用思考模式并使用 `reasoning_effort=high`；这是 DeepSeek V4 当前最低的有效思考档。单阶段输出上限为 65,536 tokens、单次请求 timeout 为 600 秒、普通网络重试为 0。每阶段最多执行一次定向修复；纯 Schema/格式修复关闭思考，引用或其他语义修复保持开启。Audit 最多执行一次语义审核。它发现 blocker 时，会把包含 observed、expected、证据和修复要求的完整 issue 返回 Content/Practice，各执行一次语义修复；修复后只重新执行 Schema、引用、controls、chunk 边界和组装等确定性校验，不再次调用 Audit。Evidence blocker、无法确定性裁决的 Assembly blocker或修复所需证据越出阶段边界时停止；warning 只记录，不触发修复。

生成器只执行领域无关的关系校验：requirements、concepts、controls、opportunities、objectives 和 practices 必须闭合映射。`content_chunk_ids` 是概念、requirements 和 controls 所需 chunks 的确定性并集；`practice_chunk_ids` 是 opportunities 自身 chunks 与其 controls 所需 chunks 的确定性并集。

`evidence_controls` 由模型从本讲资料发现，可表达约定、假设、过程顺序、术语、表示方式、单位、来源质量和范围边界，并指定下游应遵循、显式声明、限定表述、核对原始资料或在未解决时省略。定理、界、推导、收敛、因果、普遍性、不可能性和精确公式等高风险声明必须提取其来源条件或声明证据不足。课程事实和课程约束不得由固定 prompt 或下游阶段补造。

Assessment requirement 必须保持原子化：可以独立评估或补救的学习成果应拆成不同 requirements，每个练习机会的证据必须覆盖其关联 requirement。每题聚焦一个主要学习成果和少数紧邻动作，不强制固定交付项数量。

Evidence 只保留来源术语，不负责翻译；Learning Content 是唯一生成中文译名的阶段，Practice 必须复用其名称，Audit 检查中英文语义是否对应。无法确认可靠中文译名时保留英文。Content 和 Practice 中的数学表达统一使用 Markdown LaTeX：行内 `$...$`、独立公式 `$$...$$`，渲染器原样保留这些分隔符和命令。

Audit 修复失败时会分别保存 `*.audit-repair.candidate.json` 和对应 validation。修复成功时，原始失败报告仍保存在 `04-quality-audit.json`，并另存 `04-quality-audit.resolution.json`，明确记录修复目标、确定性校验结果以及未执行语义复审；最终 StudyKit 的 `generator_review_status` 标记为 `audit_repairs_applied_unverified`。`run.json` 中 Audit 调用归属 Audit，定向修复调用归属被修复的 Content/Practice。

模型以 `finish_reason=length` 截断或在重试后仍返回无效 JSON 时，生成器会在读取错误前保留面向用户的 `message.content`，并写入对应的 `*.candidate.txt`；validation 文件记录文件名和字符数。该文本只用于诊断，不被视为通过 Schema 的阶段 JSON，也不会被续跑流程复用。

若供应商返回 `finish_reason=stop` 但 `message.content` 为空，模型适配层保持同一 thinking 配置最多重试三次。若正文非空但不是严格 JSON，则保持同一 thinking 配置最多重试两次，并追加通用 JSON 转义提醒；不会猜测性修改坏正文。若 `finish_reason=length`，保持同一 thinking 配置和 65K 上限精简重试一次，不回传截断正文。三种重试分别计数，均保留 request ID、finish reason 和 token usage 诊断，但不会保存或回传 `reasoning_content`。Schema、语义失败和 Audit blocker 不属于传输重试。

Prompt 仍要求生成 5–8 道练习，以控制默认工作量；Schema/validator 对模型偶发越界保留容错，Evidence opportunities 与 Practice 最多接受 12 道，但不会因此放松 requirements、controls、opportunities、引用或题型覆盖校验。Audit 按实际工作量判断 `excessive_workload`，不只根据题目数量判错。`numeric_complexity=simple` 的数量不设上限，但每一道都必须是短步骤、低负担的计算；不得出现复杂数值计算，也不得把复杂题误标为 `simple`。

生成器以 CS 课程为主要使用场景：资料支持时可以采用代码阅读、调试、实现、算法追踪、系统行为或形式化推理。但这些是条件性能力，不是所有课程的固定模板；非 CS 资料不得产生编程前置、API、代码题或计算机系统设定。

Prompt 版本为 `studykit-staged-v0.5-007`，流水线版本为 `studykit-pipeline-v0.6-010`。System Prompt、初始阶段 Prompt 和 repair Prompt 的真正末尾都要求思考结束后必须在 `message.content` 写入非空、完整的 JSON object，并给出该阶段必须使用的首个顶层键。Audit 只接收模型生成的学习者语义内容；manifest 提供的 URL、路径、哈希和代码生成的 review/feedback metadata 由确定性管线校验。跨阶段缺陷必须拆成独立 issue；一次 Audit 后按 Evidence→Content→Practice 各最多修复一次，不执行第二次 Audit。stage-internal limitation 不要求复制到最终学习者材料。旧输出目录中的 Markdown 可继续查看，但旧 `run.json` 和阶段 JSON 不能通过 `--resume` 或 `--from-stage` 复用，必须使用新目录开始生成。

## 运行

```bash
export DEEPSEEK_API_KEY="..."
python scripts/generate_studykit.py \
  --chunks path/to/chunks.jsonl \
  --manifest data/manifests/mit-6.7960-fall-2024.yaml \
  --unit-id lecture-02 \
  --output-dir output/lecture-02
```

生成器默认直接调用 DeepSeek 官方 OpenAI 兼容 API：
`base_url=https://api.deepseek.com`、`model=deepseek-v4-flash`。该模型 ID
自动路由到当前的 DeepSeek-V4-Flash-0731。Evidence、Content、Practice、Audit 和语义修复显式发送
`reasoning_effort=high` 和 `thinking.type=enabled`；纯 Schema 修复可关闭 thinking。为避免把第三方平台凭证发送到 DeepSeek 官方域名，
生成器只接受 `DEEPSEEK_API_KEY`，不再读取旧的
`COURSEPILOT_LLM_API_KEY`。

失败或中断后续跑：

```bash
python scripts/generate_studykit.py ... --resume
```

从指定阶段重新生成该阶段及其下游产物：

```bash
python scripts/generate_studykit.py ... --from-stage content
```

可选阶段为 `evidence`、`content`、`practice`、`audit` 和 `assemble`。复用前会重新校验中间 JSON；只有输入、Manifest、生成模型、审核模型、生成选项、Schema 和 prompt 版本的指纹完全一致时才允许恢复。

Lecture 2 的离线黄金质量检查：

```bash
python scripts/evaluate_studykit_quality.py output/lecture-02/studykit.yaml \
  --profile data/golden/mit-6.7960-fall-2024-lecture-02-quality.json
```
