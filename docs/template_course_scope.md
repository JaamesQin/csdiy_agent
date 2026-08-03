# 模板课程范围

## 课程版本

- 课程：MIT 6.7960 Deep Learning
- 学期：Fall 2024
- `course_id`：`mit-6.7960-fall-2024`
- 原始资料：`data/raw/mit-6.7960/fall-2024/`
- 范围状态：已冻结

## 选定讲次

| unit_id | 讲次 | 主题 | 当前主要输入 |
| --- | ---: | --- | --- |
| `lecture-01` | 1 | Introduction to Deep Learning | `mit6_7960_f24_lec1.pdf`、课程阅读页面 |
| `lecture-02` | 2 | How to Train a Neural Net（核心 Demo） | `mit6_7960_f24_lec2.pdf`、课程阅读页面 |
| `lecture-04` | 4 | Architectures: Grids | `mit6_7960_f24_lec4.pdf`、课程阅读页面 |
| `lecture-08` | 8 | Architectures: Transformers（核心 Demo） | `mit6_7960_f24_lec8.pdf`、课程阅读页面 |
| `lecture-09` | 9 | Hacker's Guide to Deep Learning | `mit6_7960_f24_lec9.pdf`、课程阅读页面 |

第 2、8 讲已确定为核心 Demo。第 2 讲用于展示带页码引用的训练过程解释、反向传播答疑和代码诊断；第 8 讲用于展示 Transformer 架构讲解、概念关联和结构比较。其余三讲用于验证同一资料处理流程能否复用。

## 课程级建议前置知识

除 MIT 官方列出的课程要求外，CoursePilot 为材料答疑、代码阅读和练习统一采用三类人工整理建议：Python、张量计算与 PyTorch 入门；数学基础；机器学习与神经网络基础。它们标记为 CoursePilot 建议，不冒充 MIT 官方元数据；softmax、argmax、位置编码等具体概念由课程内容或前置检查引入，不作为整门课的 prerequisite。

## 处理边界

- 支持文本型 PDF、课程 HTML 页面以及后续确认可用的 Markdown、纯文本和代码文件。
- 引用锚点仅使用 PDF 页码或网页标题。
- 字幕、VTT、SRT、视频文字稿和视频元数据不进入解析或检索索引。
- 外部阅读只登记链接、版本、访问状态和许可状态；完成来源审核前不抓取正文。
- 作业材料不作为首轮五讲知识索引的默认组成部分；若用于代码辅导，必须单独审核许可并执行学术诚信限制。

## 下一步产物

1. `data/manifests/mit-6.7960-fall-2024.yaml`（已完成）
2. `docs/source_review.md`（已完成）
3. `docs/material_gaps.md`（持续维护）
4. Lecture 2、8 的 `chunks.jsonl`（已完成）；Lecture 1、4、9 待生成
5. `data/golden/mit-6.7960-fall-2024-lecture-02-studykit.yaml`（v0.1 已完成 Schema、引用、术语、公式方向复核及人工批准）
6. `data/golden/mit-6.7960-fall-2024-lecture-08-studykit.yaml`（v0.1 已完成 Schema、引用、术语、公式方向、练习事实性复核及人工批准）
