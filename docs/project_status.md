# CoursePilot 全局进度

更新时间：2026-08-03

状态口径：

- 已完成：已有可复查产物和验证记录。
- 进行中：已有部分实现，但尚未达到发布门槛。
- 待完成：设计或计划已确定，尚无完整可运行实现。
- 阻塞：存在外部能力或未解决问题，当前路径不能直接关闭。

## 一、总体判断

项目已经完成了“课程资料治理 + StudyKit 标准验证”的纵向切片，但还没有完成“最终 Agent 自动生成和对话服务”的端到端闭环。

当前最成熟的链路是：

```text
MIT 6.7960 Fall 2024 PDF
  → 页级 SourceChunk
  → StudyKit YAML
  → Schema/引用/术语/公式/练习检查
  → 学习者 Markdown
  → 无状态单题点评组件
```

其中 Lecture 2 和 Lecture 8 均已人工批准为 `reviewed`。目前的 StudyKit 是人工制作的黄金样例，不是由运行时 Teaching Designer 自动生成的结果。

## 二、已完成部分

### 1. 产品和范围

- 已确定 CoursePilot 的目标、MVP 边界和清小搭 OpenAI 兼容接入方向。
- 已确定模板课程和用户上传资料是两个平级入口。
- 已确定支持“模板推荐 → 官方下载链接 → 选择讲次 → 解析/学习”，同时支持未收录资料直接进入。
- 已确定公共模板资料、用户私有资料和用户学习状态必须隔离。

### 2. 首个模板课程

- 已冻结 MIT 6.7960 Deep Learning Fall 2024。
- 已选定 Lecture 1、2、4、8、9。
- 已确定 Lecture 2 和 Lecture 8 为核心 Demo。
- 已保存 CourseManifest 初稿、官方来源、下载页、版本和 checksum。
- 已完成来源审核、版权边界和字幕/VTT/SRT 不支持范围记录。

### 3. StudyKit 和资料标准

- 已冻结 [StudyKit v0.1 标准](studykit_standard.md)。
- 已实现 StudyKit JSON Schema。
- 已实现 SourceChunk JSON Schema。
- 已确定页码引用、claim_type、教学解释、练习内部评分字段和学习者可见性规则。
- 已确定前置知识采用课程级三类能力要求，避免按单题 API 过拟合。
- 已确定 practice 采用具体问题、作答要求、隐藏证据和隐藏评价规则。
- 已确定 `code_reading` 必须包含代码或明确伪代码。
- 已确定单题反馈只针对当前答案，不保存累计正确率或掌握度。

### 4. 已实现的资料处理组件

- PDF 页级解析器已实现。
- 页内重复隐藏文本清理已实现。
- 一页一个 SourceChunk，使用一基页码锚点。
- Lecture 2 已生成 81 个 chunks。
- Lecture 8 已生成 55 个 chunks。
- Lecture 8 已用于验证解析器复用，并修复了隐藏文本重复导致的单页文本膨胀问题。
- StudyKit 引用存在性检查已实现。
- 学习者 Markdown 渲染已实现。
- practice prompt 和无状态当前答案点评组件已实现。

### 5. 两个核心 Demo

- Lecture 2 StudyKit 已完成：
  - Schema 校验；
  - 页码引用校验；
  - 术语一致性审核；
  - Jacobian/梯度方向审核；
  - 练习事实性审核；
  - 学习者版渲染；
  - 人工批准并标记 `reviewed`。
- Lecture 8 StudyKit v0.1 已完成并批准：
  - token、attention、QKV、MSA、位置编码、causal attention、cross-attention；
  - Schema 校验；
  - 页码引用校验；
  - PDF 视觉页码核对；
  - 练习事实性核对；
  - code-reading causal mask 题；
  - 学习者版渲染；
  - 已人工批准并标记 `reviewed`。

### 6. 当前质量记录

- [Lecture 2 数学复核](../evaluations/lecture_02_math_review.md)
- [Lecture 2 术语复核](../evaluations/lecture_02_terminology_review.md)
- [Lecture 2/8 练习事实核对](../evaluations/lecture_02_08_practice_fact_check.md)
- [Lecture 2/8 前置知识对齐](../evaluations/lecture_02_08_prerequisite_alignment.md)
- [Lecture 8 StudyKit 自查](../evaluations/lecture_08_studykit_self_check.md)
- [PDF 解析复用报告](../evaluations/parser_results.md)

## 三、进行中或部分完成

| 能力 | 当前状态 | 缺口 |
| --- | --- | --- |
| CourseManifest | 有 YAML 初稿 | 尚无正式 CourseManifest Schema 和自动校验 |
| StudyKit | 两个黄金样例可校验、可渲染 | 尚无运行时自动生成器 |
| PDF 解析 | Lecture 2/8 已完成 | Lecture 1/4/9 尚未生成 chunks；HTML/Markdown 尚未支持 |
| 引用 | 页码引用与存在性检查已完成 | 尚未接入线上检索和问答路由 |
| 前置知识 | 课程级和讲次级规则已冻结 | 尚未在课程推荐界面展示前置差距 |
| API 服务 | OpenAI 兼容协议本地实现已有 | 尚未接入真实课程 Agent 路由 |
| 测试 | retrieval 相关测试通过 | Web UI 测试曾出现长时间不返回，需单独修复/定位 |

## 四、尚未完成部分

### 1. 数据协议

- CourseManifest JSON Schema；
- MaterialManifest JSON Schema；
- LearnerState JSON Schema；
- 负例 fixtures：缺来源、错版本、缺引用、越权资料；
- Manifest 自动校验和 Catalog 目录。

### 2. 运行时资料管线

- 用户文件 URL 下载和安全校验；
- session/owner/material_set 的存储和授权过滤；
- 私有原文、chunks、索引的保留和删除策略；
- HTML、Markdown、纯文本和扫描 PDF 的处理边界；
- 向量或关键词检索索引；
- 公共/私有/混合 MaterialSet 的检索器。

### 3. StudyKit 自动生成

- Teaching Designer 生成提示和结构化输出接口；
- 根据 SourceChunk 生成 StudyKit 草稿；
- 自动补充或修正引用；
- 失败时返回资料不足和限制，而不是编造；
- 生成后自动 Schema/引用/安全检查；
- 与 Lecture 2 黄金样例和 Lecture 8 人工样例的自动评测。

### 4. Agent 对话闭环

- 意图路由：推荐、解析、StudyKit、答疑、代码辅导、复盘；
- 课程/版本/讲次上下文管理；
- 当前任务所需字段检查和最小追问；
- 模板资料和用户资料入口的统一编排；
- 材料范围内答疑；
- 代码辅导和不伪称运行的诊断流程；
- 学习复盘和后续任务生成。

### 5. 课程覆盖和发布

- Lecture 8 StudyKit 已完成；
- Lecture 1、4、9 chunks；
- Lecture 1、4、9 StudyKit 或至少可复用生成验证；
- 端到端核心 Demo；
- 清小搭真实连通性、文件输入、会话和状态能力实测；
- 生产部署、试用和错误分析。

## 五、主要风险

1. 当前黄金 StudyKit 是人工样例，不能证明运行时模型已经能够稳定生成同等质量的 StudyKit。
2. CourseManifest 和私有 MaterialManifest 尚无统一 Schema，上传资料链路容易出现身份或权限边界不一致。
3. PDF 文本层可能丢失公式、图表和阅读顺序；视觉审核不能完全自动化。
4. 清小搭文件输入、会话标识和文件保留能力仍需要账号级实测。
5. 现有 OpenAI 兼容 API 测试通过不代表课程 Agent 已接入真实对话链路。
6. 如果过早扩展 Lecture 1/4/9，而不先完成生成器和权限检索，课程数量会增加但产品闭环不会增加。

## 六、下一步优先级

### P0：把已验证样例变成可运行生成链路

1. 定义 CourseManifest、MaterialManifest、LearnerState Schema 的最小版本。
2. 实现 `MaterialSet` 过滤和页级检索接口。
3. 实现 `StudyKitGenerator`：输入课程上下文和检索 chunks，输出结构化 StudyKit 草稿。
4. 接入 Schema、引用、权限和学习者渲染检查。
5. 用 Lecture 2 黄金样例做回归，用 Lecture 8 做第二个生成验证。

### P1：关闭核心 Demo

1. 建立核心 Demo 端到端脚本：选择讲次 → 解析/读取 chunks → 生成 StudyKit → 提问 → 单题点评。
2. 修复或隔离现有 Web UI 长时间不返回的测试问题。

### P2：支持未收录用户资料

1. 实现安全的文件输入和临时私有存储。
2. 生成 MaterialManifest，课程身份允许 unknown。
3. 建立 owner/session/material_set 授权过滤。
4. 用一份未收录 PDF 完成私有资料 StudyKit 验收。

### P3：扩展课程覆盖

在 P0/P1 通过评测后，再生成 Lecture 1、4、9 chunks，并用同一 StudyKit 标准扩展模板课程。

## 七、下一阶段完成定义

“核心生成链路完成”必须同时满足：

- 模板和私有资料都能映射到 MaterialSet；
- 检索结果带来源锚点且按权限过滤；
- StudyKit 由生成器产生，不依赖手工复制黄金 YAML；
- 每个输出通过 StudyKit Schema 和引用检查；
- 学习者版不泄漏评分内部字段；
- 至少 Lecture 2 和 Lecture 8 各完成一次端到端生成；
- 用户可以对任意一道 practice 获得当前答案点评，且没有累计正确率统计；
- 资料不足、身份未知和解析失败时有明确降级结果。
