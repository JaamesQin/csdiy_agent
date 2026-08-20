# MIT 6.824 / 6.5840 offering research

研究日期：2026-08-12
canonical candidate：`mit-6-824`
官方身份：MIT 6.5840 Distributed Systems；课程页面说明该课程在 2023 年以前称为 6.824。
研究范围：只核验官方 MIT/CSAIL/PDOS 页面及其直接链接；不生成 StudyKit，不下载或使用学生 lab/project solutions。

## 结论

推荐选择 **MIT 6.5840 Spring 2026**，canonical record 继续使用 `mit-6-824`，并保留 `6.5840`、`6.824` 作为官方编号/URL 别名。它是截至研究日最新、已经结束且仍公开的官方学期：课程主页标为 Spring 2026，schedule 覆盖 2026-02-03 至 2026-05-12 的课程活动，final exam 在 2026-05-15；主页还明确说明 6.5840 是原 6.824 的更名课程。[课程主页](https://pdos.csail.mit.edu/6.5840/)、[General Information](https://pdos.csail.mit.edu/6.5840/general.html)、[Spring 2026 schedule](https://pdos.csail.mit.edu/6.824/schedule.html)

该 offering 的教学证据覆盖强：21 个编号 lecture 均有官方 staff-authored per-lecture notes 或 slides 链接；schedule 还列出按讲次安排的论文/阅读、paper questions、labs、考试及 project metadata。没有在官方主页和 schedule 中找到录播入口；因此 recordings 不计入 coverage，也不以第三方视频替代官方证据。

推荐为 **research-ready / later authoring candidate**，但不是可直接公开再分发的素材包：课程页、notes、slides、paper questions 和 PDF 未发现明确的课程材料许可证或统一 Creative Commons 声明，故 license scope 为 `unknown_artifact_scope`，`redistribution_allowed: false`。若后续 authoring，只允许在授权的本地处理范围内使用官方材料，并将外部论文作为阅读链接/metadata；labs、project、exam 及任何学生解答均不作为教学证据。

## 指南与身份核验

用户指定指南 `docs/并行与分布式系统/MIT6.824.md`，但该文件在本次工作树中不存在（已用文件清单和全文检索核验）。因此本报告不从缺失指南推断学期、教师或材料覆盖；身份以 MIT 官方 Spring 2026 页面为准。

官方 General Information 给出课程为 12-unit core graduate subject，包含 lectures、readings、programming labs、optional project、midterm 和 final；主要主题为 fault tolerance、replication、consistency，并要求具备系统课程及较强编程/调试基础。[General Information](https://pdos.csail.mit.edu/6.5840/general.html)

该页列出的 Spring 2026 lecturer 为 Frans Kaashoek、Robert Morris，且明确写出“课程在 2023 年以前称为 6.824”。这足以支持 `mit-6-824` 与当前 `6.5840` 的同一课程身份映射；不把旧 6.824 archive 当作不同课程。[身份与 staff](https://pdos.csail.mit.edu/6.5840/general.html)

## Candidate URL / probe 记录

Probe 日期为 2026-08-12；“公开”表示无需登录、付费、DRM 或绕过访问控制即可由官方页面访问。对 PDF/text 的内容类型判断来自官方页面链接和页面响应展示，不把 HTTP 200 单独当作内容有效性的充分证明。

| candidate / purpose | URL | probe / access | coverage / notes_kind | completeness | license | 处理结论 |
| --- | --- | --- | --- | --- | --- | --- |
| selected home | [6.5840 Spring 2026](https://pdos.csail.mit.edu/6.5840/) | 公开，HTML 可读；未见 login/auth redirect | identity、overview、archive links | complete | 未声明 | 选定 offering |
| selected schedule | [schedule](https://pdos.csail.mit.edu/6.824/schedule.html) | 公开，HTML 可读 | 21 numbered lectures、project demos、dates、readings、labs、exams | complete for published schedule | 未声明 | 规范 unit order |
| selected general | [general.html](https://pdos.csail.mit.edu/6.5840/general.html) | 公开，HTML 可读 | structure、prerequisites、staff、academic-integrity/collaboration policy | complete | 未声明 | 身份及边界证据 |
| lecture notes | [notes/](https://pdos.csail.mit.edu/6.824/notes/) 及 schedule 直接链接的 `l*.txt` | 公开；示例 [L1](https://pdos.csail.mit.edu/6.824/notes/l01.txt)、[L3](https://pdos.csail.mit.edu/6.824/notes/l-gfs.txt)、[L4](https://pdos.csail.mit.edu/6.824/notes/l-paxos.txt) 可读 text/plain | L1–L4、L6–L16、L18–L20 为 per-lecture text notes；L10 为 lab Q&A note | substantial；21/21 lecture 有官方教学 artifact，但非统一 full textbook | 未声明 | primary evidence；后续须保留每个 source URL/vintage |
| lecture slides | [Go patterns PDF](https://pdos.csail.mit.edu/6.824/notes/Go-MIT6824-2026.pdf)、[AWS Lambda PDF](https://pdos.csail.mit.edu/6.824/notes/mbrooker_cs_slides_2026.pdf)、[BFT slides](https://pdos.csail.mit.edu/6.824/notes/65840-pbft.pdf) | 公开；官方响应识别为 application/pdf，分别 73、57、23 页 | L5、L17、L21；覆盖 3/21 lecture artifacts | supplementary to text-note corpus | 未声明 | slides 作为对应 lecture evidence，不重命名为 notes |
| paper questions | [questions](https://pdos.csail.mit.edu/6.5840/questions.html?lec=8&q=q-raft2) 及 schedule 每讲 Question 链接 | 公开 HTML/text；部分问题按讲次参数化 | 论文/阅读讨论问题；与 19 个有 preparation reading 的 lecture 对应，L2 是 Go tutorial，L10 无 paper reading | substantial metadata + question prompts；不是论文正文 corpus | 未声明；外部论文权利各自独立 | 记录 reading metadata；不抓取/再分发第三方论文正文 |
| labs | [Lab 1](https://pdos.csail.mit.edu/6.824/labs/lab-mr.html)（schedule 还链接 [Labs 2–5](https://pdos.csail.mit.edu/6.824/labs/lab-kvsrv1.html)） | 官方页面公开；课程 general 明确 labs 为 individually submitted programming assignments | 5 个 lab（Lab 3 分 A–D、Lab 4 分 A–C、Lab 5 分 A–D）及 deadlines/主题 | metadata-only | 未声明；课程 policy 要求不要公开学生代码 | 不进入教学证据；不读取学生 solutions |
| project | [Spring 2026 project](https://pdos.csail.mit.edu/6.824/project.html) | 官方页面公开；写明 proposal、code/write-up、presentation dates | optional final project 或 Lab 5 replacement；只保留 metadata | metadata-only | 未声明；页面说课程 staff 会发布 project write-ups/code，但未给统一 license | 不进入教学证据；不读取学生 solutions |
| recordings | 选定 home/schedule/general 未提供 recordings URL；[Spring 2025 exam feedback](https://pdos.csail.mit.edu/6.824/quizzes/q25-1-sol.pdf) 仍把 “Record lectures” 列为反馈项 | 未发现官方录播入口；无 auth bypass | 0 个可验证 official recording source | none / unknown | n/a | 不用第三方视频补 coverage |
| archived Spring 2025 | home 的官方 archive link 指向 [nil.csail.mit.edu/6.5840/2025/](https://nil.csail.mit.edu/6.5840/2025/) | archive link 存在，但本次 probe 返回 502 Bad Gateway | 未采用；不能以不可达 archive 替代已公开 2026 offering | unknown | unknown | 记录为 attempted candidate / not selected |
| archived Spring 2024 | home 的官方 archive link 指向 [nil.csail.mit.edu/6.5840/2024/](https://nil.csail.mit.edu/6.5840/2024/) | archive link 存在，但本次 probe 返回 502 Bad Gateway | 未采用 | unknown | unknown | 记录为 attempted candidate / not selected |
| archived Spring 2023 | home 的官方 archive link 指向 [nil.csail.mit.edu/6.5840/2023/](https://nil.csail.mit.edu/6.5840/2023/) | archive link 存在，但本次 probe 返回 502 Bad Gateway | 未采用 | unknown | unknown | 记录为 attempted candidate / not selected |

## Spring 2026 schedule 与 coverage

| 范围 | 官方安排 | 可核验教学证据 | coverage 结论 |
| --- | --- | --- | --- |
| L1–L4 | Introduction；RPC/Threads；GFS；Paxos | text notes 均由 schedule 直接链接 | 4/4 |
| L5–L10 | Go patterns；Raft 1–2；Consistency/Linearizability；ZooKeeper；Q&A Lab 3A+B | L5 PDF slides；L6–L10 官方 text notes/Q&A | 6/6 |
| L11–L15 | Distributed Transactions；Spanner；Chain Replication；Optimistic Concurrency Control；Verification | 官方 text notes | 5/5 |
| L16–L21 | Memcached；AWS Lambda；Ray；SUNDR；Bitcoin；BFT | L16、L18–L20 text notes；L17、L21 PDF slides | 6/6 |
| L22 | Project demos | schedule/project page only | metadata-only；不创建 lecture unit |
| no-class dates | holidays、snow day、spring break、hacking days | schedule only | 不创建 unit |

因此，按“编号 lecture”计为 **21/21 public substantive lecture artifacts**；按“包含 full lecture notes 的统一 corpus”不能称 complete，因为课程是混合的 per-lecture text notes、slides 和 Q&A，且 schedule 自己说明未来日期的 notes/questions 可能是往年副本并可能变化。对已结束学期，报告保留该 vintage caveat，不把旧材料重标成 Spring 2026 原创。

### 论文/阅读覆盖

Schedule 为 L1、L3–L9、L11–L21 安排了论文或指定阅读（共 19 个 reading-preparation slots）；L2 使用 Online Go tutorial，L10 是 lab Q&A，无独立 paper reading。主题覆盖 MapReduce、GFS、Paxos、Go、Raft、linearizability、ZooKeeper、6.033 transaction chapter、Spanner、Chain Replication、FaRM、IronFleet、Memcached、container loading、Ray、SUNDR、Bitcoin、Practical BFT。论文正文大多链接到外部站点或出版物，不作为可再分发教学材料；这里只记录 schedule/question metadata。[Spring 2026 schedule](https://pdos.csail.mit.edu/6.824/schedule.html)

## Access、身份与 license scope

- **公开身份**：官方页面给出课程编号、标题、学期、教师、12-unit graduate structure、prerequisites 和 6.824→6.5840 renaming；身份证据充分。
- **访问**：selected home/schedule/general/notes/slides/questions/project 可不登录访问；Gradescope/Piazza 仅作为课程运营入口，不作为本研究的教学材料来源，也未尝试访问受限内容。
- **许可证**：在 home、general、schedule、代表性 text notes、代表性 PDF slides 和 project 页面未发现明确 license/copyright grant。不能因 MIT/CSAIL 官方托管或公开可下载就推定 CC 或可再分发。
- **记录值**：课程网页与课程 artifact `license_status: unknown_artifact_scope`；外部论文 `license_status: per_external_publisher_or_author`；`redistribution_allowed: false`，除非后续逐项取得明确授权。
- **学术诚信**：General Information 要求学生个人完成 lab，并明确要求不要公开学生代码；project 页面涉及学生提交的 code/write-up。labs、project、exam solutions 只记录标题、链接、时间和主题等 metadata，不作为 lesson evidence，不下载学生答案。

## Recommendation / next action

1. 以 `mit-6-824` 选择 **Spring 2026**，版本标识建议为 `spring-2026`，别名记录 `6.5840` 与 `6.824`。
2. 后续若进入 authoring，以 schedule 的 21 个 numbered lectures 作为 ordered units；L22 project demos、labs、project、exams 和 paper questions 保持 metadata-only。
3. 以官方 per-lecture text notes 为主，三组官方 slides 为对应 lecture 的 primary/supplementary evidence；保留每个文件的 final URL、resource vintage、content type、hash 和 license scope。
4. 不把外部论文正文、学生 lab solutions、project code/write-ups 或任何 exam solutions 纳入 StudyKit source evidence；不声称存在录播。
5. 在取得逐项许可前，所有 raw/derived material 仅限授权的本地处理，禁止把 `unknown_artifact_scope` 素材作为公开可下载 StudyKit 或复制品发布。
