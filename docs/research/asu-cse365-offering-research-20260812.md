# ASU CSE365 offering research

研究日期：2026-08-12
canonical candidate：`asu-cse365`
指南：`data/raw/catalog-sources/cs-self-learning/81d874ee0fb37b2289839847026ba7651f3725d5/docs/系统安全/CSE365.md`（上游文档路径为 `docs/系统安全/CSE365.md`）

## 结论

官方身份已确认，且存在可公开浏览的官方 pwn.college offering。当前最适合作为后续 offering anchor 的是 `CSE 365 - Spring 2025`，因为仓库指南明确指向 `https://pwn.college/cse365-s2025/`；最新已完成的可见版本是 `CSE 365 - Summer 2026`，可作为版本演化与模块证据，但不应把它反向替换为指南指定版本。

本轮不生成 StudyKit。研究结论为：

- `public_access`：`partial`。课程主页、模块 HTML、lecture 条目和 challenge 元数据可公开浏览；启动 dojo/challenge、提交 flag、查看课程 Discord/ASU graded work 仍需要账号或身份绑定，部分 graded assignments 仅 ASU 学生可见。
- `notes_kind`：`interactive-challenge-narrative + embedded-video-lecture`。不是可独立解析的 lecture-note/教材包。
- `notes_completeness`：对 challenge inventory 为 `substantial`；对可用于 StudyKit 的连续、可引用 lecture notes 为 `insufficient`。
- `license_scope`：课程 syllabus、lectures 与 course-related written materials 明示为 2025/2026 copyright；未发现允许复制、再发布或改编整套课程材料的开放许可证。pwncollege GitHub 组织中若单个代码仓库标有 BSD 2-Clause，只能约束该仓库/代码范围，不能推导 lecture、网页叙述、视频或 challenge solution 的许可。
- `blocker`：目前只有公开 recordings/embedded lectures、challenge pages 和少量页内教学叙述，没有可确认授权且连续的 substantive lecture notes。不能把视频正文、challenge solution、flag、提示性解题资料下载或 ingest 来填补该缺口。

因此，本 candidate 可保留为“官方公开挑战型课程”的 offering research 记录，但暂不具备建立面向学习内容的 StudyKit source inventory 的充分材料条件。

## 官方身份与版本证据

Spring 2025 官方主页明确写出：University = Arizona State University，Course = CSE 365 — Introduction to Cybersecurity，Term = Spring 2025；这与指南标题及 canonical candidate 一致：

- Official course home: <https://pwn.college/cse365-s2025/>
- Official Spring 2025 syllabus: <https://pwn.college/dojo/cse365-s2025/course/setup>
- 指南指定链接：`https://pwn.college/cse365-s2025/`

最新版本检查：

- Spring 2026 页面仍明确写出同一 ASU 课程身份，并将课程组织为 8 modules：<https://pwn.college/cse365-s2026/>；其 syllabus 为 <https://pwn.college/dojo/cse365-s2026/course/syllabus>。
- Summer 2026 页面显示 `CSE 365 - Summer 2026`、`Official`、8 个核心模块及一个 `Extra Credit` 模块；日程最后的核心课程 assessment/challenge 日期为 2026-07-11，因此截至本研究日可视为最新已完成版本的公开 evidence：<https://pwn.college/cse365-2026-summer/>。

## Ordered modules

### Guide-targeted Spring 2025

Spring 2025 syllabus 的官方顺序是 9 个主题模块加 1 个 final cumulative module：

| order | official module | scope | public metadata evidence |
|---:|---|---|---|
| 1 | Introduction and Using Linux | Linux、平台入门、access control | <https://pwn.college/cse365-s2025/module-1/> |
| 2 | Dealing with Data and Access Control | data、web、SQL playground | <https://pwn.college/cse365-s2025/module-2/> |
| 3 | Talking Web and SQL Playground | web security groundwork | <https://pwn.college/cse365-s2025/module-3/> |
| 4 | Web Security | web vulnerabilities | <https://pwn.college/cse365-s2025/module-4/> |
| 5 | Computing 101 | architecture、assembly、systems basics | <https://pwn.college/cse365-s2025/module-5/> |
| 6 | Network Security | network/security communication | <https://pwn.college/cse365-s2025/module-6/> |
| 7 | Cryptography | symmetric/asymmetric crypto、hashing、trust | <https://pwn.college/cse365-s2025/module-7/> |
| 8 | Reverse Engineering | binary files、process loading/execution、tools | <https://pwn.college/cse365-s2025/module-8/> |
| 9 | Binary Security | binary exploitation | <https://pwn.college/cse365-s2025/module-9/> |
| 10 | Integrated Security | final cumulative module | <https://pwn.college/cse365-s2025/module-10/> |

注意：Spring 2025 主页的公开计数为 10 个模块、495 challenges，并列出各模块 lecture/challenge counts；指南中的“8 modules / 444 challenges”是旧的课程快照，不应作为当前 offering 的事实覆盖官方页面。

### Latest completed Summer 2026

Summer 2026 的公开 dojo inventory 为 545 challenges：Module 1–8 分别为 150、79、29、108、48、32、34、41，另有 24 个 Extra Credit challenges。其核心顺序与 Spring 2026 syllabus 收敛后的 8-module 顺序一致：

1. Getting Started, Linux Luminarium, and Access Control
2. Dealing with Data, Talking Web, and SQL Playground
3. Web Security
4. Computing 101
5. Reverse Engineering
6. Binary Exploitation
7. Intercepting Communications
8. Cryptography

Evidence：Summer 2026 homepage <https://pwn.college/cse365-2026-summer/>；Spring 2026 syllabus 的 ordered course content <https://pwn.college/dojo/cse365-s2026/course/syllabus>。该版本的 Module 1 页面公开展示 lecture 条目、嵌入式视频播放/观看完成机制和 Linux challenge narrative：<https://pwn.college/cse365-2026-summer/module-1/>；Module 8 页面公开展示 Introduction、Symmetric Encryption、Key Exchange、Asymmetric Encryption、Hashing、Trust 等 lecture 条目及 challenge narrative：<https://pwn.college/cse365-2026-summer/module-8/>。

## Public access and evidence classification

观察到的访问层级：

| resource | public observation | identity/authorization boundary | research treatment |
|---|---|---|---|
| course home / syllabus | 可直接打开并读取身份、学期、顺序、课程规则 | 课程 Discord/grades/setup 有账号或绑定要求 | 可引用 metadata |
| module HTML | 可直接打开；可看到标题、短介绍、lecture labels、challenge labels 和部分正文 | Start、workspace、flag submission 需要 pwn.college account/session | 仅记录 module/lecture/challenge metadata，不抓取运行内容 |
| embedded lecture | 页面声明 lecture video 在点击 Start 后加载 | lecture participation/flag workflow 与 dojo session 绑定 | 只记录存在性与标题，不下载视频、字幕或 transcript |
| challenge pages | 页面和 challenge inventory 可见，部分说明文本公开 | challenge execution、SSH、workspace、flag 需要启动权限 | 只记录数量、顺序、主题和 URL，不记录 solution/flag/hints |
| reflections / quizzes / grades | Spring 2025 reflections 与 Summer 2026 external graded assignments 明确限 ASU 学生 | ASU student verification/课程角色 | 不访问、不复制、不 ingest |

按 StudyKit Generator 的 URL safety 与 scope 规则，本轮没有对受限资源做绕过，也没有把“页面可见”解释为“可再发布”。

## notes_kind / completeness / license scope

### notes_kind

`notes_kind = interactive_challenge_narrative + embedded_video_lecture`。证据显示 lecture card 主要由标题、Start/观看完成机制和 dojo challenge wrapper 构成；模块页可能附带短的概念介绍或 challenge-specific explanation，但这不是一个有稳定页码/章节锚点、能覆盖全课的讲义集合。Summer 2026 Module 8 例如公开了 crypto lecture titles，但正文主要仍嵌在互动 challenge 流程中：<https://pwn.college/cse365-2026-summer/module-8/>。

### completeness

- `challenge_metadata_completeness = high`：Spring 2025 官方主页能列出全课程模块与 challenge counts；Summer 2026 官方页能列出 8 core + Extra Credit 的完整公开 inventory。
- `lecture_metadata_completeness = partial-to-high`：模块页能确认 lecture 的存在、标题和顺序；但未获得可授权的全文 lecture notes/transcripts。
- `substantive_lecture_notes_completeness = insufficient`：公开 recordings/embedded videos 不等于可审计的文本材料；仅靠 challenge 页面不能安全推断 lecture 的完整讲授内容。
- `guide_alignment = stale_snapshot`：指南“8 modules / 444 challenges”与 Spring 2025 当前公开页的 10 modules / 495 challenges 不一致；指南链接和课程身份仍有效，数量需以 offering 页面按版本记录。

### license_scope

Spring 2025 syllabus 明确课程 syllabus、lectures 和 course-related written materials 为 copyright 2025；Summer 2026 syllabus 具有相同性质并标为 copyright 2026。两份 syllabus 还禁止未经书面许可进行课程录音/录像/数字记录或售卖笔记，并对 solution sharing、公开发布 solutions 施加学术诚信限制：

- Spring 2025 syllabus copyright/academic-integrity evidence: <https://pwn.college/dojo/cse365-s2025/course/setup>
- Summer 2026 public course evidence and deadline structure: <https://pwn.college/cse365-2026-summer/>
- pwncollege GitHub organization 可见部分仓库标 BSD 2-Clause（例如 dojo/honors-dojo），但这是 repository-level code metadata，不是 CSE365 全部 lecture/web/video/challenge content 的 blanket license：<https://github.com/orgs/pwncollege/repositories>

记录为：`course_materials = copyright / permission not established`; `challenge_code_repositories = repository-specific license only`; `solutions_and_student_work = do-not-ingest / academic-integrity restricted`。

## Academic-integrity boundary

官方 Spring 2025 syllabus 明确列出：不得使用或引用他人 solution、不得分享任何 solution code/flag、不得使用直接针对 pwn.college/CSE365/assignment challenge 的外部资源，且公开发布 assignment solutions 明确禁止。Summer 2026 syllabus 延续相同的 zero-tolerance 与 solution-sharing 限制。

本研究严格执行以下边界：

- 未下载、运行或 ingest challenge solutions、writeups、flags、学生仓库、Discord 解题讨论、SENSAI 输出或 challenge runtime artifacts。
- challenge 只作为 metadata：版本、模块序号、模块/lecture/challenge 标题、公开 URL、数量、主题标签和访问边界。
- 不把 module page 中用于教学的完整 challenge hints、示例答案或可直接导向 flag 的内容复制进研究文档。
- 后续若要做 StudyKit，必须先获得可处理材料的明确授权，并以新的、独立的 substantive lecture source 作为主 source；不能用 solutions 补齐 lecture gap。

## Source gap / blocker

**BLOCKED_FOR_STUDYKIT_AUTHORING：`substantive_lecture_notes_missing`。**

目前证据足以确认官方身份、版本、模块顺序、公开访问形态和挑战型课程结构；不足以建立“每个 unit 有连续、独立、可引用、许可清楚的 lecture notes”输入。公开 recordings/embedded lectures 可以作为未摄取的外部 metadata link，但不能在本轮转换为 StudyKit source chunks。除非后续获得官方授权的文字讲义、可处理的官方 transcript/notes 或明确允许处理的等价材料，否则应保持 offering research 完成、StudyKit authoring 未启动。

## Evidence log

访问/核查日期：2026-08-12。以下均为官方或官方组织页面；未下载 solution materials。

1. [Spring 2025 course home](https://pwn.college/cse365-s2025/) — ASU identity, term, modules/challenge counts, public course links。
2. [Spring 2025 syllabus](https://pwn.college/dojo/cse365-s2025/course/setup) — ordered modules, asynchronous/public model, lecture/challenge weighting, academic-integrity and copyright restrictions。
3. [Summer 2026 course home](https://pwn.college/cse365-2026-summer/) — latest completed public inventory, 8 core modules + Extra Credit, 545 challenges, calendar through 2026-07-11。
4. [Spring 2026 syllabus](https://pwn.college/dojo/cse365-s2026/course/syllabus) — stable 8-module content order used to interpret the current course shape。
5. [Summer 2026 Module 1](https://pwn.college/cse365-2026-summer/module-1/) — public lecture-card/embedded-video evidence and introductory challenge narrative。
6. [Summer 2026 Module 8](https://pwn.college/cse365-2026-summer/module-8/) — latest-version lecture-card evidence for crypto sequence and interactive challenge narrative。
7. [pwncollege GitHub organization](https://github.com/orgs/pwncollege/repositories) — repository-level public/license metadata only; not used to ingest course content。
