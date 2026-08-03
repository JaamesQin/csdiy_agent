# MIT 6.7960 Fall 2024 材料缺口

更新日期：2026-08-03

## 已解除的索引阻塞

1. 已冻结 StudyKit v0.1，并新增 StudyKit 与 SourceChunk JSON Schema。
2. 已实现 PDF 页级解析、页码锚定、页内重复隐藏文本清理和 JSONL 输出。
3. Lecture 2 已生成 81 个页级 SourceChunk；StudyKit 的 Schema、引用解析和视觉页码核对均通过。
4. Lecture 8 已用同一解析器生成 55 个页级 SourceChunk，验证了核心 Demo 间的解析复用。
5. StudyKit v0.1 冻结标准已记录在 `docs/studykit_standard.md`。

## 已知但不阻塞

- PDF 中公式和图示的视觉结构不能由文本提取完整保留；带警告的页在回答时应优先回看原 PDF。
- 当前产物是页级可检索数据，尚未接入向量数据库或线上 RAG 服务。
- 字幕、VTT、SRT、视频文字稿、视频元数据和时间戳引用超出 MVP 能力范围，原文件保留但不处理。
- 外部阅读正文未随课程下载包完整提供，并且许可各异；当前仅保存 OCW 阅读页中的链接信息。
- 五个讲次的逐讲前置知识和一句话说明不是 MIT 官方结构化元数据，现为依据讲义人工整理的内容。
- CoursePilot 现将 Python/张量计算/PyTorch 入门、数学基础、机器学习与神经网络基础列为整门课程的人工整理建议前置知识；softmax、argmax 等具体概念不再单独列为课程级 prerequisite。这些要求不冒充 MIT 官方课程要求。
- Lecture 2/8 的练习已按课程级前置和讲次特定前置逐题对齐，记录见 `evaluations/lecture_02_08_prerequisite_alignment.md`。
- Lecture 2 和 Lecture 8 已确定为核心 Demo；两者的 StudyKit v0.1 均已完成机器校验、Agent 引用/术语/公式/练习复核和人工批准。
- 作业和参考答案不属于当前五讲索引范围；若以后启用，需要单独做许可与学术诚信审核。
- 当前只覆盖 Lecture 1、2、4、8、9，不代表完整覆盖 MIT 6.7960。

## 已完成的用户决定

1. 允许依据讲义人工整理逐讲前置知识。
2. 允许依据讲义人工整理每讲的一句话内容说明。
3. Lecture 2 和 Lecture 8 为核心 Demo。
