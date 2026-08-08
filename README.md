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

- 主动学习画像：从用户明确陈述中识别学习方向、目标、基础、每周时间和讲解偏好；使用匿名 `user` 标识时可保存到本地 SQLite，并支持查看、纠正和删除。
- 意图路由：规则优先、结构化模型兜底；当前执行画像分析、Python 优先的静态代码辅导和澄清，未接入能力会透明说明。
- 代码辅导：提供静态诊断、假设、验证步骤和下一次尝试；不运行用户代码，也不代写可提交作业。
- 已审核 StudyKit 读取：在线辅导可以读取 Lecture 2/8 黄金 StudyKit 的目标、概念和页码引用，不暴露内部评分字段。
- 离线 StudyKit 生成：生成包含目标、前置知识、提纲、术语、练习、引用和限制说明的中文学习包。
- 规划中：完整课程导航、MaterialSet 权限、在线检索、材料答疑、练习反馈和学习复盘。

## 技术路线

项目采用“清小搭平台入口 + 自研 Agent 后端”的架构：

```text
清小搭智能体广场
        ↓ OpenAI 兼容协议
协议适配层：鉴权、JSON、SSE、错误处理、文件 URL
        ↓
Agent 编排：意图路由、主动画像、静态代码辅导、安全校验
        ↓
已审核 StudyKit 读取；后续接入 Manifest、RAG、答疑与复盘
```

当前已实现的接入契约包括：

- `POST /v1/chat/completions`；
- `GET /v1/models`；
- Bearer Token 鉴权；
- 非流式 OpenAI 兼容 JSON；
- 流式 SSE：role、content、stop、`data: [DONE]`；
- `usage`、`finish_reason`、脱敏服务错误和流式错误处理；
- 可选 OpenAI `user` 字段，用于本地/受信网关下的画像逻辑隔离。

清小搭文件 URL、音频输入和 PDF/PPT/Word 等附件尚未接入，不阻塞文本版 MVP。

## 当前阶段

截至 2026-08-08，项目处于“离线 StudyKit 生成内核完成、首批在线 Agent 能力已接入、等待检索和清小搭生产验证”阶段：

| 项目 | 状态 |
| --- | --- |
| 产品目标与 MVP 边界 | 已完成 |
| 用户流程与验收场景 | 已完成 |
| 清小搭接入协议调研 | 已完成 |
| 自研后端架构与仓库结构 | 已完成最小实现 |
| OpenAI 兼容 API 实现 | 已完成 |
| Bearer、JSON、SSE 和错误契约测试 | 已完成；全量 187 项测试通过 |
| 意图路由、主动画像和静态代码辅导 | 已完成首版 |
| 本地聊天测试界面 | 已接入匿名用户 ID、画像和代码辅导入口 |
| 云端部署方式 | 已确认，等待生产版本部署 |
| 首个模板课程与核心讲次冻结 | 已完成：MIT 6.7960，Lecture 2 和 8 为核心 Demo |
| CourseManifest 与来源审核 | 已完成初稿 |
| Lecture 2 黄金 StudyKit | v0.1 已通过 Schema、引用、术语、公式方向复核和人工批准 |
| Lecture 8 StudyKit | v0.1 已完成 Schema、引用、术语、公式方向、练习事实性复核和人工批准 |
| SourceChunk Schema 与 PDF 页级解析 | 已完成；Lecture 2、8 的 chunks 已在本地生成并通过校验，未随公开仓库上传 |
| 黄金 StudyKit 在线读取 | 已完成：Lecture 2、8，只读人工批准版本 |
| 线上 SourceChunk 检索与 RAG | 尚未开始 |
| 清小搭接入探测与试聊 | 尚未开始 |
| 端到端 Demo、评测和用户试用 | 尚未开始 |

当前关键路径是：

1. 冻结 MaterialSet、权限和正式 Catalog 接口；
2. 建立带 owner/session/course/version/unit 过滤的关键词检索；
3. 接入材料答疑、练习反馈和学习复盘能力；
4. 验证清小搭稳定用户身份、消息历史、文件输入、状态和日志能力；
5. 将通过测试的后端部署到生产环境并完成端到端评测。

## 本地运行

创建并启用虚拟环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

设置本地接入密钥。配置 `DEEPSEEK_API_KEY` 后会启用低置信路由、画像候选和语义代码辅导；不配置时仍可使用规则路由、显式画像识别和 Python AST 静态诊断：

```bash
export COURSEPILOT_API_KEY="$(openssl rand -hex 32)"
# 可选：export DEEPSEEK_API_KEY="..."
# 可选：export COURSEPILOT_DB_PATH="/absolute/path/coursepilot.sqlite3"
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

浏览器打开 `http://127.0.0.1:8000/`，在接入设置中填写同一个密钥，即可使用本地聊天测试界面。

OpenAI 请求可带匿名逻辑用户标识：

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer $COURSEPILOT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"coursepilot-probe","user":"local-demo-user","messages":[{"role":"user","content":"我想学系统方向，每周 6 小时，而且有 Python 基础。"}]}'
```

运行全部测试：

```bash
.venv/bin/pytest -q
```

当前测试基线为 `187 passed`，覆盖协议、路由、画像 SQLite 生命周期、并发隔离、静态代码诊断、学术诚信、StudyKit 引用白名单、生成管线和真实本地 HTTP/SSE。

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
- `user` 是客户端提供的匿名逻辑标识，不是授权凭据；在清小搭稳定身份完成验证前，持久画像只适用于本地或受信网关。
- 画像不保存完整对话或代码；模型推断只作为 7 天待确认候选，确认前不参与正式建议。

## 文档

- [文档索引](docs/README.md)
- [GitHub 上传选择与发布前检查](GITHUB_UPLOAD.md)
- [项目状态（开发者入口）](PROJECT_STATUS.md)
- [全局进度](docs/project_status.md)
- [Developers Guide：StudyKit 离线生成与 Agent 接入](docs/developers_guide.md)
- [StudyKit v0.1 冻结标准](docs/studykit_standard.md)
- [StudyKit 分阶段生成与恢复](docs/studykit_generation.md)
- [项目 Proposal](proposal_agent.md)
- [完整实施计划](implementation_plan.md)
- [平台验证记录](docs/platform_validation.md)
- [平台发布记录](docs/platform_release.md)

## 开发状态说明

仓库已经包含 OpenAI 兼容服务、规则优先的意图路由、可撤回 SQLite 学习画像、Python AST 静态代码辅导、只读黄金 StudyKit 上下文，以及完整的分阶段 StudyKit 生成内核。Lecture 2/8 的原始 PDF 和抽取 chunks 仅保留在本地；线上 SourceChunk 检索、未收录资料入口、材料答疑、练习反馈和学习复盘仍属于后续阶段。
