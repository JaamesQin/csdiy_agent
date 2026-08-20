# 清小搭平台与本地协议验证记录

> 更新日期：2026-08-20
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
| 用户或会话标识 | 待验证 | 标准协议文档未作确定保证 |
| 长期状态 | 待验证 | 需要平台账号实测 |
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
- 练习反馈要求 practice ID 和当前答案，只允许白名单页码，不保存答案、不累计分数或
  掌握度；模型不可用或返回非法页码时不做关键词粗评；
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
- 当前 catalog 为 119 个课程目标、13 个 manifest 绑定；archive 仍为 0 online-ready。

## 13. 2026-08-20 Web 富文本渲染验证

前端源码已迁入 `frontend/`，通过 Vite/React/TypeScript 构建为同源 `app/static/` 资源；FastAPI
路由、严格 `script-src/style-src 'self'` CSP、Cookie 会话和 CSRF 契约未放宽。助手输出支持
Markdown 标题/列表/表格、Highlight.js 代码和 MathML-only 公式。Markdown 原始 HTML 关闭，
DOMPurify 继续阻断脚本、表单、内联样式、危险链接和模型图片；用户消息、用户名和错误只写入文本节点。
本轮使用项目 `.venv` 的 Python 3.13.14、Node 24.19.0、npm/npx 11.17.0 和已安装的
Google Chrome 151；上方第 2 节保留初次协议验证时的历史环境，不代表本轮版本。

验证结果：

```text
npm run check
17 passed

npm run test:e2e
7 passed (installed Google Chrome, channel=chrome)

.venv/bin/pytest -q
360 passed
```

Chrome 流程覆盖匿名启动与旧浏览器存储清理、注册/刷新恢复/注销、HttpOnly/Strict Cookie、
聊天 CSRF 且无浏览器 Authorization/user 字段、SSE 富文本与主动停止、代码复制、远程图片/XSS 阻断、
过期会话恢复/重复认证与注销竞态、流错误纯文本边界和响应大小上限、
非流式多轮原始 Markdown 历史，以及 `390×844` 下表格/代码/公式无页面级横向溢出。
构建产物不需要 CDN、浏览器下载或系统级依赖安装。

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
