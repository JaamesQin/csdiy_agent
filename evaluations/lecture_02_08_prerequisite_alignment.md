# Lecture 2/8 前置知识与练习对齐记录

审核日期：2026-08-03

## 课程级建议前置

CoursePilot 在保留 MIT 官方课程要求的基础上，新增三类人工整理的通用建议前置：Python、张量计算与 PyTorch 入门；数学基础；机器学习与神经网络基础。它们位于 CourseManifest 的 `recommended_prerequisites`，不冒充 MIT 官方元数据。softmax、argmax、位置编码和 causal mask 等具体概念由课程内容或前置检查引入。

## 讲次对齐

| 讲次 | 练习直接使用的知识 | 讲次 StudyKit 是否补充 |
| --- | --- | --- |
| Lecture 2 | 链式法则、矩阵形状、自动微分、softmax/argmax | 是；继承课程级前置，并补充本讲所需的微积分、MLP 和张量概念 |
| Lecture 8 | token 矩阵、点积、softmax、QKV、MSA、位置编码、causal mask | 是；继承课程级前置，并补充本讲所需的 token、矩阵和局部性概念 |

## 结论

`code_reading` 题不再把具体 API 名称或单个概念倒推成整门课的前置知识。课程目录负责表达三类共同能力要求，StudyKit 负责表达当前讲次的概念差异；题目中的具体 API 和新概念由代码上下文、提示或学习过程解释。本讲的新概念（例如 cross-attention 和 positional encoding）仍作为学习目标，不倒置为 prerequisite。
