# 清小搭平台与本地协议验证记录

> 更新日期：2026-08-21
> 当前结论：本地协议验证通过，清小搭生产平台验证待执行

## 1. 验证范围

本轮只验证阶段 1 中可以在本地独立完成的部分：

- FastAPI 服务启动与健康检查；
- `Authorization: Bearer <credential>` 鉴权；
- `GET /v1/models`；
- `POST /v1/chat/completions` 非流式 JSON；
- `POST /v1/chat/completions` 流式 SSE；
- `model` 缺失、空字符串或 `null`；
- `max_tokens: 1`；
- `stream` 严格 JSON 布尔校验；
- 流式中途错误的 stop 帧、独立 `error` 字段和 `[DONE]`；
- 密钥缺失或过短时拒绝启动；
- 密钥不出现在正常或错误响应中；
- 本地聊天界面、Vite 静态资源和安全 Markdown/MathML 学习者渲染；
- 独立 Uvicorn 进程上的真实 HTTP、SSE 和轻量并发请求。

本轮没有验证清小搭账号侧能力、生产网络、文件 URL 或长期状态。

2026-08-12 另完成离线 StudyKit 归档验证：12 builds、286 documents、12,008 text
artifacts；SQLite `quick_check` 和内容/工件 SHA-256 回读均通过，重复课程版本为 0，
online-ready 文档为 0（全部保持 `validated_draft`）。记录见
`evaluations/studykit-archive-import-20260812.json` 与
`evaluations/studykit-outputs-prune-20260812.json`。

## 2. 本地环境（2026-07-31 历史基线）

| 项目 | 值 |
| --- | --- |
| Python | 3.12.3 |
| FastAPI | 0.141.1 |
| Uvicorn | 0.52.0 |
| HTTP 客户端 | HTTPX 0.28.1 |
| 测试框架 | pytest 9.1.1 |
| 服务地址 | `http://127.0.0.1:<临时端口>` |
| 模型调用 | 无，使用固定回显 |

## 3. 自动化结果

执行命令：

```bash
source .venv/bin/activate
pytest -q
```

结果：

```text
36 passed in 2.27s
```

依赖检查：

```text
No broken requirements found.
```

真实 HTTP 测试会启动独立 Uvicorn 子进程，并覆盖：

- 100 次 `/v1/models` 请求；
- 100 次非流式对话请求；
- 20 次流式对话请求；
- SSE 实际增量到达；
- 每个流式响应以 `data: [DONE]` 结束。

上述请求成功率为 100%。

## 4. 能力结论

| 能力 | 状态 | 证据或说明 |
| --- | --- | --- |
| Bearer 鉴权 | 支持 | 正确密钥 200，错误或缺失密钥 401 |
| `/v1/models` | 支持 | 返回 OpenAI 风格模型列表 |
| 非流式 JSON | 支持 | `choices[0].message.content` 与 `usage` 完整 |
| 流式 SSE | 支持 | role、content、stop、`[DONE]` 顺序和唯一性通过 |
| 流式错误收尾 | 支持 | stop + 独立 `error` + `[DONE]` |
| 严格 `stream` | 支持 | 字符串、数字、`null` 等返回 422 |
| 探测字段兼容 | 支持 | `max_tokens: 1` 和空模型通过 |
| 多轮消息输入 | 支持 | 接受 system、user、assistant，使用最后一条用户消息 |
| 本地聊天界面 | 支持 | 流式切换、停止、清空、多轮和会话级密钥 |
| 真实模型生成 | 尚未实现 | 阶段 1 使用固定回显 |
| 清小搭四项探测 | 待验证 | 需要生产部署地址 |
| 清小搭真实试聊 | 待验证 | 需要账号侧操作 |
| `file.url` | 待验证 | 需要平台实际发送文件请求 |
| 用户或会话标识 | 协议已确认，本地已验证 | 清小搭顶层可选 `sessionId`；生产账号侧仍需实测 |
| 长期状态 | 30 天最小连续状态已实现 | 生产持久卷、备份和平台账号侧仍需实测 |
| 平台日志 | 待验证 | 需要生产部署与清小搭后台 |

## 5. 待执行的平台验收

生产部署完成后依次执行：

1. 验证生产域名的 `/health`、`/v1/models` 和 `/v1/chat/completions`；
2. 等待实例闲置后再次验证冷启动；
3. 在清小搭接入向导完成连通性、凭证、最小对话和响应格式四项探测；
4. 从清小搭页面完成一轮真实输入和输出；
5. 验证系统提示和多轮历史；
6. 验证文件 URL、域名、类型、大小和 120 秒总超时；
7. 记录会话标识、状态保存、日志和平台版本；
8. 将每项 P0 平台依赖标记为支持、降级或阻塞。

## 6. 当前判定

本地协议实现满足进入生产部署和清小搭接入探测的条件。由于清小搭账号侧探测与真实试聊尚未完成，阶段 1 暂不能标记为全部完成。

## 7. 2026-08-09 多用户安全验证

本节是新增验证记录，不替代上面的 2026-07-31 协议记录。

实现新增了账号注册/登录/注销、SQLite Schema v2、Argon2id、服务端会话、
CSRF、同源校验、限流和账号画像隔离，同时保留原有 API Key 接口。

执行：

```bash
.venv/bin/pytest -q
```

结果：

```text
163 passed
```

其中 159 项不需要网络或外部模型凭据；4 项真实 HTTP 测试绑定
`127.0.0.1` 临时端口并启动独立 Uvicorn，覆盖：

- API Key 非流式、SSE 顺序和轻量并发兼容；
- 浏览器账号注册和 Cookie 会话；
- CSRF header 下的画像写入与读取；
- 画像数据不依赖客户端 `user` 字段。

安全测试另行确认：

- 密码只以 Argon2id 格式存储；原始会话令牌不出现在 SQLite 文件；
- 账号会话过期、撤销和用户级联删除后不可恢复；
- v1 画像迁移到 `legacy:`，未知数据库版本被拒绝；
- 用户名大小写唯一，并发重复注册只有一个成功；
- 错误用户和错误密码使用相同响应；登录失败触发限流；
- Cookie 包含 HttpOnly、SameSite=Strict、Path=/，无 Domain 和持久 Max-Age；
- Cookie 写请求缺少 CSRF 时拒绝，非 allowlist Origin 被拒绝；
- 账号 A、账号 B、legacy API Key 三者的画像空间互不相交；
- API Key 客户端仍通过原 `/v1/models`、`/v1/chat/completions` 和 SSE 测试。

尚未完成生产 HTTPS、Secure Cookie、共享限流、备份恢复、日志脱敏和清小搭账号侧实测，因此本记录只证明本地候选版本。

另使用真实浏览器完成桌面与 `390×844` 移动视口检查，验证登录门禁、注册后自动
进入聊天、刷新恢复会话、画像写入/读取、用户名展示和注销返回登录页；最终浏览器
控制台无 error。首次交互测试发现异步 submit 后使用失效 `event.currentTarget` 的
前端问题，已改为稳定表单引用并增加静态回归断言。

## 8. 2026-08-10 账号与在线 Agent 合并验证

本节追加记录账号分支与在线 Agent 分支合并后的兼容性验证，不替代前述历史结果。
合并后的请求链路先由 API 层校验 API Key 或 Cookie 会话与 CSRF，再把
`account:<uuid>` 或 `legacy:<user>` 可信 subject 交给 Agent；Agent 执行意图路由、
主动画像和静态代码辅导。账号请求体中的 `user` 仍被忽略。

执行结果：

```text
.venv/bin/pytest -q --ignore=tests/integration/test_local_http.py
206 passed

.venv/bin/pytest -q tests/integration/test_local_http.py
4 passed
```

合计 `210 passed`。新增合并验证确认：

- SQLite Schema v2 同时由账号、会话和增强画像事实使用，不再存在独立 schema version 竞争；
- Cookie 账号、不同账号和 API Key legacy 用户的画像保持隔离；
- OpenAI `user`、模型 ID、非流式 envelope、usage 与 SSE role/content/stop/`[DONE]` 顺序保持兼容；
- 登录后的 Web UI 保留画像查看/删除、意图路由和 Python 静态代码辅导入口，不保存匿名 ID 或 API Key；
- 未配置 DeepSeek 时仍可使用规则路由、明确画像识别和 Python AST 诊断；
- 4 项真实 HTTP/SSE 测试在 `127.0.0.1` 临时端口全部通过。

## 9. 2026-08-10 多语言辅导与能力帮助验证

本节记录当前候选版本的最新验证，前述 36/210 项结果保留为历史基线。新增验证覆盖
能力目录、Help 路由优先级、CSDIY 多语言别名、所有保证的 Tree-sitter grammar、
Python/Triton AST、解析器失败降级和未标语言边界。

```text
.venv/bin/pytest -q --ignore=tests/integration/test_local_http.py
250 passed

.venv/bin/pytest -q tests/integration/test_local_http.py
4 passed
```

合计 `254 passed`。验证确认：

- `/help` 和“你目前有哪些功能”只列学习画像与多语言静态代码辅导；
- `/help code`、“代码辅导支持什么语言”和“课程导航是什么”返回目录中的对应帮助/状态；
- Help 在画像观察前返回，不写入学习画像；“C++ 中什么是 virtual”不会误路由到 Help；
- C/C++、CUDA、ISPC、LaTeX 等错误代码返回结构位置，Triton 使用 Python 宿主语法；
- 所有保证的 grammar 从安装包离线加载，测试过程不需要外部模型或网络；
- 未标语言不会默认按 Python 解析，课程专用 DSL 和解析器异常会透明降级；
- 所有代码辅导路径仍为 `ran_code=false`，OpenAI JSON/SSE 顺序和真实 loopback HTTP 保持兼容。

## 10. 2026-08-12 课程导航与 StudyKit 学习能力验证

本节记录课程导航、StudyKit 查询、材料问答、概念解释、练习选择和练习反馈接入后的
最新候选版本；前述 254 项结果保留为历史基线。

```text
.venv/bin/pytest -q --ignore=tests/integration/test_local_http.py
290 passed

.venv/bin/pytest -q tests/integration/test_local_http.py
4 passed
```

合并数据库 adapter 后，普通测试为 `299 passed`，loopback HTTP/SSE 为 `4 passed`，
合计 `303 passed`。新增验证确认：

- CSDIY registry 的 119 个课程目标通过类型、唯一 ID、导航 provenance、状态和
  Manifest 路径校验；损坏或重复数据失败关闭，不交给模型补全；
- 课程导航的精确匹配、方向推荐和稳定排序分别限制为 5/3 个结果，并把目录分类、
  离线 authoring 和在线 StudyKit 三种状态分开；
- 当前仅 MIT 6.7960 Lecture 2/8 标记为在线 ready；MIT 6.S081 的离线 `authoring`
  不会被误报为在线 StudyKit 可用；
- `第 8 页` 不再被解析为 `lecture-08`，不完整身份只有在 Store 中唯一时才采用；
- StudyKit 学习者投影不包含 `expected_evidence`、evaluation/rubric、审计字段、
  `local_path` 或 `data/raw` 路径；
- 材料模型只能返回引用白名单 ID；未知引用、未知页码、模型失败和未配置模型均进入
  有证据的确定性降级；
- 概念解释只使用带页码的已审核概念；练习首次不泄漏 hint/rubric，并在当前 messages
  中避免重复；
- 练习反馈要求 practice ID 和当前答案；本节当时只验证页码白名单，现已由第 20 节扩展为
  精确 page/heading/chunk 白名单。不保存答案、不累计分数或掌握度；模型不可用或返回非法引用时不做关键词粗评；
- 六项能力的真实 `/v1/chat/completions` 非流式 envelope 和课程概念 SSE
  role/content/单 stop/`[DONE]` 顺序保持兼容。

`COURSEPILOT_DB_PATH` 仍只保存账号、会话和画像事实；SourceChunk、私有 MaterialSet 和
跨会话练习状态仍未上线。

## 11. 2026-08-11 StudyKit 语义质量校准准备

本节记录离线 StudyKit 批量生成的质量门禁准备，不代表新的课程样本已经生成或通过校准。
standard authoring 现在要求每道练习绑定到 EvidencePlan/Content 的具体内容，给出学习者
可以直接求解的设置和可观察结果；独立审计者必须逐题核对内容关联、提示、预期证据、评价
标准和 source anchor。Schema、引用格式或渲染通过本身不能替代该语义审查。

代表性样本随后按照 [StudyKit 质量校准协议](studykit-quality-calibration-protocol.md)
与 CMU 15-213、UCB CS61B 产物及 `data/golden/` 人审样例比较，并演进为六课逐题 repair
循环。最终状态记录在 `evaluations/csdiy-six-course-practice-repair-round2-progress.md`；
本节保留最初校准门禁的形成过程，不再作为当前进度判断。

Selective repair 仅允许作为离线、fingerprinted build 执行：保存 direct-parent snapshot，
并把 rich independent audit 绑定到当前 `build_id` 与 repair-plan digest。审计必须对当前
candidate 的 practice IDs 做 exact coverage（无 missing、duplicate 或 stale IDs）；任一
mismatch 都阻止 completion/false-complete。portable/deterministic Schema pass 不能替代
逐题语义审计。后续六课循环已完成 161/161 validated、161/161 audited 和 6/6 build
`succeeded`；五课仍有课程级 visual-review gate，因此 catalog 全局 release gate 仍未关闭。

## 12. 2026-08-13 私有数据 submodule 与在线 adapter 验证

- 私有仓库 `JaamesQin/csdiy_agent-data` 的 `main` 固定到 `f4b25bb`，GitHub 属性为 private；
- 主仓库 `data` gitlink 固定到同一提交，迁移提交为 `f7cab57`；
- SQLite 为 130,453,504 字节，SHA-256 为
  `76daa4534257434b9e0e005ce20c03c06abed655ff9c4c061d96e30fc752107a`，
  `PRAGMA quick_check = ok`；
- 归档计数为 12 builds、286 documents、12,008 artifacts，review status 全部为
  `validated_draft`；
- 424 个本地 Git LFS 对象通过 `git lfs fsck`，submodule tracked worktree clean；
- `tests/catalog/test_studykit_archive.py` 从真实 archive 抽取 portable v0.1/v0.2.1 行，
  在临时测试库中设为 approved，验证双 review gate、哈希/身份/schema/table 失败关闭、
  archive 优先、golden 回退以及六项在线能力；正式 archive 未被修改；
- 截至 2026-08-13，该历史基线的 catalog 为 119 个课程目标、13 个 manifest 绑定，archive 为
  0 online-ready；后续批准结果见下一节。

## 13. 2026-08-17 StudyKit archive 人工批准与在线接入

- 批量批准工具：`scripts/approve_studykit_archive.py`；默认 dry-run，`--apply` 时强制要求
  SQLite backup 路径；
- 批准依据：archive 零完整性问题、portable v0.2.1 Schema、逐 unit validation 和
  review-validation、requested/completed/validated/audited/document 精确身份集合、匹配 build ID
  的独立审计全覆盖，以及用户明确的人工发布批准。MIT 6.7960 与 MIT 6.S081 采用显式
  reviewed-legacy owner approval，报告逐项保留 waived gates，未伪装为新版门禁通过；
- UCB CS186 从直接父 build `07a442…` 创建新指纹 build `bb2553…`，只在 `note-03` 范围修正
  `lecture-03` 身份字段及其审计引用，不改变学习内容或练习语义；repair plan、父 artifact-tree
  digest、20/20 exact-set 和当前 build 审计绑定全部写入归档与补充审计；
- 批准结果：9 builds、220 documents 为 `approved`；3 个 partial builds、66 documents 保持
  `validated_draft`；
- approved archive Store 与组合 Store 均返回 220 项；MIT 6.7960 Lecture 2/8 golden 与 archive
  身份重复，由 archive 优先覆盖；Catalog 中 9 门课程具有在线 StudyKit；
- 保持 draft 的记录仅包括三个 partial build：CMU 15.213、MIT 6.031、UCB CS61B；
- 更新前数据库 SHA-256：`76daa4534257434b9e0e005ce20c03c06abed655ff9c4c061d96e30fc752107a`；
  最终数据库 SHA-256：`2ecb73198409e55753c0fb3d85f9bb04bd824588e1da6b3b7afe3b2fbc7b585f`；
- 可审计报告：`evaluations/studykit-archive-approval-20260817.json`；更新前 SQLite backup 位于
  `/tmp/studykits.before-approval-20260817.sqlite3`，该临时备份不属于发布产物；
- CS186 修复报告：`evaluations/ucb-cs186-archive-identity-repair-result-20260817.json`；补充审计：
  `evaluations/ucb-cs186-archive-identity-repair-audit-20260817.json`；
- `tests/catalog/test_studykit_archive_approval.py` 验证严格门禁、legacy owner approval、CS186
  补充审计和事务只更新 eligible build/document；在线相关目标测试结果见本节最终验证记录。
# Online Agent P0–P2 validation

Validation covers TaskPlan DAG limits, partial execution, provenance partition degradation, public
SourceChunk filters and hashes, context tamper/expiry behavior, expired profile confirmation,
CodeArtifact line binding/toolchain parsing, and fit/readiness separation. All model paths use fakes;
tests do not execute learner code or require network access.

## Opt-in provider-backed acceptance

`scripts/run_live_agent_acceptance.py` is a manual, credentialed acceptance suite and is intentionally
excluded from pytest. It sends only synthetic learner text and an invented StudyKit/practice to the
configured provider; it does not send repository StudyKit content, persist conversations, or print
model prose or credentials.

```bash
DEEPSEEK_API_KEY=... .venv/bin/python scripts/run_live_agent_acceptance.py
```

The current suite also asserts the online call budget: TaskPlan is separate and profile, material,
practice presentation, practice feedback, general explanation, and code tutoring each use at most one
model call. Practice presentation checks a non-placeholder structured rewrite, original objective/ID
retention, hidden-control safety, and transparent original-question fallback. The provider-backed run
prints only verdict, call-count, usage, presentation kind, and sanitized fallback-code metadata.

The final 2026-08-17 `deepseek-v4-flash` run passed 7/7 checks with 4,310 reported tokens. Planning
used one successful call; profile, material, general explanation, practice feedback, and code tutoring
each reported exactly one capability model call. Practice presentation ran three independent requests,
each used one call, and all 3/3 produced non-fallback `structured_rewrite` results. Check-level latency
was P50 2,221 ms and P95 9,324 ms (the presentation check includes three sequential samples), with
zero presentation fallbacks. No provider prose, credentials, learner data, or repository StudyKit
content was printed or persisted.

## Live backend natural-language E2E

`scripts/run_live_backend_e2e.py` 使用合成学习者消息、临时画像 SQLite、真实受审核
Catalog/StudyKitStore 和配置的 DeepSeek，从 `CoursePilotAgent.handle()` 验证到最终
`AgentReply`。该脚本故意排除在 pytest 之外；运行时不会打印凭据、完整 prompt、模型正文、
代码或画像证据。

```bash
.venv/bin/python scripts/run_live_backend_e2e.py --suite smoke
.venv/bin/python scripts/run_live_backend_e2e.py --suite full \
  --report /tmp/coursepilot-live-e2e-full.json
```

full suite 覆盖内联/压平 C++、画像与课程多意图、中文讲次和页码、材料与概念证据、
练习选择后无 ID连续反馈、签名上下文篡改、课程纠正和帮助短路。结构化事件只记录
capability、task status 和模型调用元数据，不记录学习者内容。

2026-08-19 自然语言整改后的 `deepseek-v4-flash` full suite 覆盖 25 个场景（另含 provider
preflight），包括无格式代码、模型候选回绑、签名课程序号、自然 StudyKit/摘要、画像纠正删除、
课程拼写和缺失练习上下文。完整新手探索另覆盖 24 条多轮旅程；报告写入 `/tmp`，不属于仓库产物。
具体命令和双视角审查见 `docs/live-novice-agent-remediation-validation-20260819.md`。

## 14. 2026-08-20 通用学习问答兜底验证

- TaskPlan 无法归类、模型规划结构失败或错误使用 `generation_status` 时，统一规范化为
  `general_assistance`；明确的生成状态请求仍保留原能力；
- 专用任务和通用任务同时出现时只执行专用任务，并移除对被丢弃通用任务的依赖；
- 通用上下文最多保留最近 30 条消息和 48,000 字符，长消息保留首尾并带截断标记；
- 只传 confirmed 画像值和最小验签连续状态，过滤 plan/code digest、时间戳等内部字段；
- CoursePilot 角色和 available 能力从 `CapabilitySpec` 构建，学习复盘等 unavailable 能力不作为
  已上线功能提供给模型；
- 输出合同固定 `general_knowledge`、空 citation/catalog/diagnostic IDs 和 `ran_code=false`；
  违反合同或模型不可用时透明降级；
- 可提交完整作业请求在通用模型调用前确定性拒绝；Planner 和通用能力分别计数，通用能力每个
  请求最多调用模型一次。

同日使用已配置的真实 `DEEPSEEK_API_KEY` 运行更新后的 full suite。provider preflight 与 26 个
合成业务场景全部通过（27/27 checks）；50/50 次 `deepseek-v4-flash` 调用最终成功，无 provider
error。总 usage 为 53,027 prompt、13,609 completion、66,636 tokens；单次调用延迟 P50 为
2,144 ms、P95 为 3,097.3 ms，范围 590–6,077 ms。49 次调用一次传输成功，1 次调用经过
3 次 transport attempts 后成功。新增 `general_learning_fallback` 场景严格完成
`general_assistance`，只使用 1 次 TaskPlan 调用和 1 次通用能力调用，未降级、未输出课程依据或
`ran_code=true`。测试只使用合成学习者输入与临时画像数据库，控制台未输出凭据、完整 prompt、
模型正文、代码或画像证据。

## 15. 2026-08-20 画像感知课程排序与全课程索引验证

- registry 当前 119 个唯一课程目标全部进入约 27K 字符的极简决策索引；索引上限 64,000 字符，
  相关详情最多 12 门/48,000 字符；本地路径、哈希、candidate offering 和审计诊断均未进入 Prompt；
- `background=没有Python` 作为 confirmed 学习背景原样保存，界面标签改为“学习背景”；导航模型同时
  收到方向、负向背景和完整课程索引，并只可返回 registry 中的唯一 catalog ID；
- 个性化推荐每阶段最多 3 门，分成“现在开始/长期目标”。课程标题、链接、制作状态和在线状态由
  后端重新解析；未记录精确先修时保持 unknown；
- 精确查课、身份纠正和列表不调用模型。排序模型关闭 thinking，业务层每个导航能力最多调用一次；
  非法 JSON 由模型适配器在相同关闭状态下附加修复指令重试，非法 ID、超时或模型不可用时显示
  “未个性化排序”的方向候选；
- `general_assistance` 常驻完整极简索引，课程选择经 catalog-ID 白名单生成独立 metadata claim，
  无效课程分区被丢弃时 general knowledge 仍独立成功。

本次 `.venv/bin/pytest -q` 为 601 passed。真实 DeepSeek full suite 首轮中 provider 56/56 调用成功，
27 个业务场景有 25 个通过；两个失败是旧 E2E 标题断言未接受新的“现在开始/长期目标”或明确降级
契约，不是能力执行失败。修正断言后定向重跑这两个多意图场景，2/2 通过且 provider 6/6 调用成功。
新增负向背景场景实际选择编程基础课程作为当前入口、系统课程作为长期目标，并通过后端 ID、阶段、
先修 unknown 和未降级检查。测试使用真实 `DEEPSEEK_API_KEY`，未输出密钥、完整 prompt 或模型正文。

延迟复核后关闭课程排序 thinking，并将输出预算设为 4,096、单次请求超时设为 60 秒；非法 JSON
仍由统一模型适配器附加修复指令后重试，重试保持 thinking disabled。使用真实 DeepSeek 重跑同一
负向背景场景：场景通过，3/3 provider 调用均为单次传输；课程排序调用约 1,813 ms，整轮 provider
latency 为 780/2,776/1,813 ms，总 completion 556 tokens。模型仍把编程基础课程放入“现在开始”，
把系统核心课程放入“长期目标”，未触发未个性化降级。

能力可用性问句补充确定性短路：短小、无代码痕迹、包含已知能力别名且以“吗/么/呢/？”结尾的
“你可以进行代码辅导吗”等请求，在 Planner 和画像观察前返回对应 `/help` 内容；带真实代码块的
同类措辞仍进入 `code_tutoring`。路由、编排和实际代码反例均有独立回归。

浏览器连续状态修复：Web 客户端从非流式响应顶层或 SSE stop frame 读取短期签名
`coursepilot_context`，在下一轮请求中回传，并在清空会话或请求失败时清除；不写入 localStorage、
sessionStorage 或数据库。“显示/查看/打开 + practice ID/中文序数”以及单独发送的 `ex-N` 在 Planner 前
确定性进入练习展示；当前讲次内把 `ex1`、`ex-1`、`EX 1` 等位置别名绑定到审核过的练习顺序。
只有实际题目呈现标记或签名连续状态才计入已展示集合，StudyKit 目录列表不计入。StudyKit→指定练习多轮、
流式/非流式静态合同和全仓回归共为 601 passed。练习连续交互新增验证：StudyKit 目录中的 ID 列表不会被误算为已展示题目；中文序数、`ex-N` 位置别名及“ex7 是什么”等自然问法均确定性解析到当前讲次的审核练习。

跨能力连续状态进一步收紧：模型在 follow-up 中返回同一课程但省略讲次时，不能把已验签的当前讲次降为课程级；材料问答、概念解释、练习选择和 StudyKit 查询共享该规则。显式换讲覆盖旧讲次，显式换课不继承旧课程讲次，“列出所有讲次”才允许主动降到课程级。问候、能力帮助和 onboarding 响应保留有效 token；浏览器仅在服务返回新 token 时替换，篡改或过期 token 不回显。

## 16. 2026-08-20 清小搭 `sessionId` 会话连续状态验证

- `/v1/chat/completions` 接受可选顶层 `sessionId`；空白值规范为缺失，超长或非字符串值拒绝。JSON 和 SSE 都不回传 `sessionId` 或 `coursepilot_context`。
- Schema v3 以 HMAC(`trusted namespace`, `sessionId`) 摘要作为主键，不存原始会话 ID。账号、不同 legacy user 与无 `user` 网关请求处于不同命名空间。
- 仅存储已验证课程/讲次、当前与已展示练习、提示级别、展示/代码摘要和最小 follow-up 元数据；不存完整消息、代码、答案、分数或 reasoning。
- 默认 30 天滑动有效期，加载和保存时惰性清理过期行；revision CAS 防止并发请求静默覆盖。数据库异常或 CAS 冲突只记录非敏感连续事件，不阻断当轮回答。
- `TurnResolver` 统一课程、讲次和 Catalog 身份解析：显式新引用优先，同课 follow-up 不得因模型省略讲次而降低已验证上下文具体度。

自动化全仓回归为 `619 passed`，包含 schema v2→v3 迁移不重复加 `legacy:`、原始 ID 非明文、命名空间隔离、滑动过期、CAS、故障降级、JSON/SSE 以及独立 Uvicorn 合同。

另使用真实 `DEEPSEEK_API_KEY` 完成本地多轮：同一 `sessionId` 依次查看 MIT 6.7960 Lecture 2、询问梯度下降、索取一道练习；重启 Uvicorn 后只发送“ex7 是什么”，仍正确返回 `### ex-7`，没有要求重新指定课程/讲次，也没有回传签名上下文。SQLite 文件检查确认 `user_version=3`，且不包含测试用原始 `sessionId`。这仍是本地端到端验证，清小搭生产账号侧探测另行进行。

## 17. 2026-08-20 未上线能力路由失败关闭

- `app/agent/capabilities.py` 继续是能力可用性的唯一事实源；`learning_review` 和
  `generation_status` 保留在 `/help` 中用于说明状态，但不再是可执行 Router/TaskPlan 目标。
- Planner 在模型调用前拦截明确未上线能力别名；Prompt 只列已上线 capability ID；
  模型后对任何违规 ID 再做目录驱动归一化。旧 IntentRouter 和编排执行入口各有独立防线。
- 转换后的 `general_assistance` 只收到匹配能力的 title/status/limitations/alternative，
  不获得后台状态、任务记录或其他权限。服务端确定性前缀声明该能力尚未接入，
  通用模型不得暗示 StudyKit 查询等其他在线能力可以读取 authoring 任务状态。
- `/help 生成状态`、“生成状态查询是什么？”仍返回专用状态页，不调用通用模型。

自动化基线为 `623 passed`。使用真实 DeepSeek 与本地 HTTP 复测原失败句
“查看我的 StudyKit 生成任务状态”：不再进入练习反馈或索要 practice ID，而是进入通用回答并明示未上线边界；学习复盘请求同样进入通用学习建议。

## 18. 2026-08-20 Web 富文本渲染与连续状态合并验证

前端源码位于 `frontend/`，通过 Vite/React/TypeScript 构建为同源 `app/static/` 资源；FastAPI
路由、严格 `script-src/style-src 'self'` CSP、Cookie 会话和 CSRF 契约未放宽。助手输出支持
Markdown 标题/列表/表格、Highlight.js 代码和 MathML-only 公式。Markdown 原始 HTML 关闭，
DOMPurify 阻断脚本、表单、内联样式、危险链接和模型图片；用户消息、用户名和错误只写入文本节点。

合并后的 React 客户端从有界 JSON 响应或 SSE stop frame 读取签名 `coursepilot_context`，只保存在
页面内存中，在下一轮请求回传，并在清空会话或请求失败时清除。上下文长度、SSE frame、助手正文、
JSON body 和浏览器内对话总量均有独立上限。

验证结果：

```text
npm run check
18 passed

npm run test:e2e
7 passed (installed Google Chrome, channel=chrome)

.venv/bin/pytest -q
623 passed
```

Chrome 流程覆盖旧浏览器存储清理、注册/刷新恢复/注销、HttpOnly/Strict Cookie、聊天 CSRF、
SSE 富文本与主动停止、连续状态回传与清空、代码复制、远程图片/XSS 阻断、认证与注销竞态、
流错误纯文本边界、响应大小上限、非流式多轮原始 Markdown 历史，以及 `390×844` 下表格/代码/公式
无页面级横向溢出。构建产物不需要 CDN、浏览器下载或系统级依赖安装。

## 19. 2026-08-20 多模式静态代码教练

- `code_tutoring` 新增示例生成、解释、诊断、审阅、修复、重构和测试设计模式；明确的生成请求
  不再把缺少用户 `CodeArtifact` 当成输入错误。
- 目标语言按本轮明确语言、当前代码和可靠语义上下文解析；仍不默认 Python。缺少语言或必需代码时
  在能力模型调用前只询问缺失项。
- 模型生成代码使用结构化 code block 合同，并在可用时经过 Python AST/Tree-sitter 二次语法检查；
  语言错配、缺少必需 block、非法 Schema 或语法失败均失败关闭，不追加第二次能力调用。
- 普通最小完整示例允许生成；课程作业完整解答在空代码分支之前拒绝。所有预期输出均标注“未运行”，
  每条路径继续返回 `ran_code=false`。
- 最近助手示例只有在消息历史仍携带原代码且用户明确指代时才被精确提取；服务端连续状态不保存正文。

## 20. 2026-08-21 Exercise 精确证据与通用反馈降级

- `SourceChunkStore.resolve_exact` 不使用 FTS/BM25；它在 SQL 中先过滤 public scope、
  course/version/unit、succeeded build、approved review 和 index eligibility，再按
  `chunk_id` 或 `source_id + anchor` 精确解析并复核内容 SHA-256。伪造、跨课、歧义、
  未审核和哈希漂移引用均不会进入模型。
- 单题课程证据限定为 16 个引用、16,000 字符；任一引用无效会丢弃整个课程证据分区。
  随后同一次能力调用只接收题面、作答要求和当前答案，并以固定标题
  “通用反馈（未按当前课程材料核验）”标明未按课程材料验证。模型失败不触发第二次调用。
- portable v0.2.2 要求每题声明 `course_grounded` 或 `general_only`。前者必须全部精确解析，
  后者必须无引用；生成 validator 和 archive approval gate 使用同一确定性检查并分别报告
  grounded、general-only、unresolved、declaration mismatch。
- `scripts/build_source_chunk_index.py` 只读取 build/document 双 approved 的归档记录，并复核
  fingerprint 中的 `chunks_path/chunks_sha256` 后原子替换可重建索引。

本次新增的独立、无网络验证结果：SourceChunk/索引/Exercise 回归 `13 passed`，generator skill
与 workflow policy `32 passed`，archive feedback release gate `3 passed`，page-only generator contract
`1 passed`，skill quick validation
和 Python compileall 通过。覆盖了截图对应 CS61C `lecture-02/p1` 的两个 heading chunk、页码证据、
选择优先级、跨课程降级、引用/字符上限、声明冲突和 source hash drift。

当前工作树中的私有 `data` submodule 预先存在用户删除的 golden、catalog 和 manifest 文件；
依赖这些文件的旧全仓测试会以 `FileNotFoundError` 或 ready Store 为空失败。本次没有恢复或修改
这些数据文件，相关失败不作为 Exercise 契约回归通过的证据。实际全量命令
`.venv/bin/pytest -q --tb=no` 得到 `500 passed, 160 failed, 5 errors`；代表性抽查分别落在缺失的
MIT golden fixture 和由此不可用的 `ReviewedFileStudyKitStore`。5 个 error 的 traceback 是受限沙箱
拒绝 `socket.bind(("127.0.0.1", 0))`；获准在本机回环环境运行
`tests/integration/test_local_http.py` 后为 `5 passed`。这些结果与上述 49 项独立回归分开记录。
