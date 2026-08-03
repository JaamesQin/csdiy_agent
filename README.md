# CoursePilot

CoursePilot 是一个面向中文计算机科学自学者的循证学习 Agent。项目以 [CSDIY](https://csdiy.wiki/) 等公开学习路线为入口，帮助学习者从可信、可追溯的海外 CS 课程资料出发，完成选课、逐讲学习、材料答疑、代码辅导和学习复盘。

项目计划接入清华大学“清小搭”智能体广场，并使用自研代码后端承载核心业务。清小搭负责广场入口、对话展示、文件上传和附件转存；后端通过 OpenAI 兼容协议提供 Agent 能力。

## 项目背景

海外优质 CS 课程数量丰富，但中文学习者在实际使用中经常遇到以下问题：

- 课程官网、讲义、视频、作业和代码仓库分散；
- 不同学期的资料容易混用，课程版本难以确认；
- 通用问答工具通常缺少页码或章节等可核查依据；
- 学习规划、材料理解、代码实践和复盘相互割裂；
- 直接提供完整作业答案会带来学术诚信和学习效果问题。

CoursePilot 不以收集最多课程为目标，而是优先完成一个小规模、可验证的学习闭环：

```text
了解目标
  → 选择课程与版本
  → 选择讲次
  → 生成带来源的 StudyKit
  → 材料答疑或代码辅导
  → 提交学习证据
  → 复盘并生成下一步计划
```

用户既可以从多个经过审核的模板课程中获得推荐、官方下载链接和按讲学习，也可以处理项目未预先收录的自有课程资料。两类入口共享学习能力；未经用户确认，私有资料不会与模板课程混合。

## 核心能力

- 课程导航：从受控模板目录中推荐课程，展示课程版本、前置要求、官方课程页、整课下载页和已支持讲次。
- Manifest 体系：CourseManifest 管理公共模板课程；MaterialManifest 管理未收录的用户私有资料，课程身份无法确认时允许保持未知。
- 资料解析与检索：处理公开或用户有权使用的 PDF、网页和 Markdown，保留页码或标题锚点。
- StudyKit：生成包含目标、前置知识、提纲、术语、练习、引用和限制说明的中文学习包。
- 课程内答疑：在确定的课程版本和讲次范围内回答，材料不足时明确说明。
- 代码辅导：提供问题拆解、诊断假设、验证步骤、测试建议和代码审阅，不直接代写可提交作业。
- 学习复盘：依据小测、自评、笔记或代码结果更新学习状态，并生成下一步任务。

## 技术路线

项目采用“清小搭平台入口 + 自研 Agent 后端”的架构：

```text
清小搭智能体广场
        ↓ OpenAI 兼容协议
协议适配层：鉴权、JSON、SSE、错误处理、文件 URL
        ↓
Agent 编排：意图路由、上下文检查、安全校验
        ↓
课程 Manifest、资料解析、RAG、StudyKit、答疑与复盘
```

P0 接入契约包括：

- `POST /v1/chat/completions`；
- `GET /v1/models`；
- Bearer Token 鉴权；
- 非流式 OpenAI 兼容 JSON；
- 流式 SSE：role、content、stop、`data: [DONE]`；
- `usage`、`finish_reason` 和流式错误处理；
- 清小搭文件 URL 的域名、类型、大小和超时校验。

音频输入和 PDF/PPT/Word 等附件产物属于条件性增强，不阻塞文本版 MVP。

## 当前阶段

截至 2026-08-03，项目处于“阶段 1 本地协议实现完成、StudyKit 验证切片完成、等待清小搭生产接入验证”阶段：

| 项目 | 状态 |
| --- | --- |
| 产品目标与 MVP 边界 | 已完成 |
| 用户流程与验收场景 | 已完成 |
| 清小搭接入协议调研 | 已完成 |
| 自研后端架构与仓库结构 | 已完成最小实现 |
| OpenAI 兼容 API 实现 | 已完成 |
| Bearer、JSON、SSE 和错误契约测试 | 已完成；全量 45 项测试通过 |
| 本地聊天测试界面 | 已完成 |
| 云端部署方式 | 已确认，等待生产版本部署 |
| 首个模板课程与核心讲次冻结 | 已完成：MIT 6.7960，Lecture 2 和 8 为核心 Demo |
| CourseManifest 与来源审核 | 已完成初稿 |
| Lecture 2 黄金 StudyKit | v0.1 已通过 Schema、引用、术语、公式方向复核和人工批准 |
| Lecture 8 StudyKit | v0.1 已完成 Schema、引用、术语、公式方向、练习事实性复核和人工批准 |
| SourceChunk Schema 与 PDF 页级解析 | 已完成；Lecture 2、8 的 chunks 已在本地生成并通过校验，未随公开仓库上传 |
| 线上检索与 RAG 接入 | 尚未开始 |
| 清小搭接入探测与试聊 | 尚未开始 |
| 端到端 Demo、评测和用户试用 | 尚未开始 |

当前关键路径是：

1. 建立多模板课程目录和 Catalog/Supported/Demo 准入级别；
2. 将已通过本地测试的 OpenAI 兼容后端部署到生产环境；
3. 通过清小搭的连通性、凭证、最小对话和响应格式探测；
4. 实测消息历史、系统提示、文件输入、会话标识、状态和日志能力；
5. 补齐 CourseManifest、MaterialManifest 和 MaterialSet Schema；
6. 将已验证的按讲解析接入未收录资料处理和公共/私有索引；
7. 实现 StudyKit、答疑、代码辅导和复盘；
8. 完成端到端评测、试用和上线。

## 本地运行

创建并启用虚拟环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

设置本地接入密钥并启动服务：

```bash
export COURSEPILOT_API_KEY="$(openssl rand -hex 32)"
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

浏览器打开 `http://127.0.0.1:8000/`，在接入设置中填写同一个密钥，即可使用本地聊天测试界面。

运行全部测试：

```bash
pytest -q
```

当前测试基线为 `45 passed`，覆盖鉴权、非流式 JSON、SSE 帧顺序、流式错误、严格参数校验、启动安全、静态界面、真实本地 HTTP 并发请求，以及 SourceChunk/StudyKit 解析、Schema、引用和渲染。

## 本地运行

创建并启用虚拟环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

设置本地接入密钥并启动服务：

```bash
export COURSEPILOT_API_KEY="$(openssl rand -hex 32)"
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

浏览器打开 `http://127.0.0.1:8000/`，在接入设置中填写同一个密钥，即可使用本地聊天测试界面。

运行全部测试：

```bash
pytest -q
```

当前测试基线为 `36 passed`，覆盖鉴权、非流式 JSON、SSE 帧顺序、流式错误、严格参数校验、启动安全、静态界面和真实本地 HTTP 并发请求。

## MVP 范围

最低可交付版本覆盖：

- 1 门经过审核的课程；
- 3–5 个讲次；
- 1 个可重复演示的核心讲次；
- 带来源锚点的 StudyKit；
- 至少一个材料答疑、代码辅导和学习复盘场景；
- 至少三个可以绕过完整向导的直接功能入口。

大规模课程收集、真实代码沙箱、完整知识图谱、复杂长期记忆、音频输入和高级附件输出均不阻塞 MVP。

## 安全与合规

- 只索引公开、开放许可或用户有权使用的材料；
- 不绕过登录、付费、地域或技术访问限制；
- 不镜像和重新分发无授权的整套课程资料；
- 不生成可替代原材料的整份受保护内容；
- 不直接提供可提交的完整作业答案；
- 公共模板课程、用户私有资料和用户学习状态相互隔离；
- 未收录资料无需匹配模板课程；不能确认的课程身份保持未知；
- 用户文件 URL 仅允许受信任的清小搭 OSS 域名，防止 SSRF；
- 没有可靠沙箱时只进行静态代码分析，不声称已经运行代码。

## 文档

- [文档索引](docs/README.md)
- [GitHub 上传选择与发布前检查](GITHUB_UPLOAD.md)
- [项目状态（开发者入口）](PROJECT_STATUS.md)
- [全局进度](docs/project_status.md)
- [StudyKit v0.1 冻结标准](docs/studykit_standard.md)
- [项目 Proposal](proposal_agent.md)
- [完整实施计划](implementation_plan.md)
- [平台验证记录](docs/platform_validation.md)
- [平台发布记录](docs/platform_release.md)

## 开发状态说明

仓库已经包含阶段 1 的最小 OpenAI 兼容服务、课程 Manifest 初稿、StudyKit/SourceChunk Schema、PDF 页级解析器、Lecture 2/8 的黄金 StudyKit 与无状态单题点评组件。Lecture 2/8 的原始 PDF 和抽取 chunks 仅保留在本地，用于重新生成和验证；线上 RAG、对话路由、未收录资料入口、答疑、代码辅导和学习复盘仍属于后续阶段。
