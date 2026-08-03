# Lecture 8 StudyKit v0.1 自查记录

自查日期：2026-08-03

对象：`data/golden/mit-6.7960-fall-2024-lecture-08-studykit.yaml`

## 检查结果

- StudyKit Schema：通过。
- Lecture 8 SourceChunk Schema：55/55 通过（由分页构建脚本完成）。
- 引用可解析性：全部引用均解析到 `mit-6.7960-f24-lecture-08-slides` 的现有页码。
- PDF 视觉页码核对：覆盖第 2–54 页的引用范围，主题与页面一致。
- 来源边界：只使用官方下载包中的 Lecture 8 PDF；未使用字幕、视频文字稿、第三方阅读正文或外部网页正文。
- 练习可见性：学习者渲染版不显示 `expected_evidence`、`evaluation` 和默认 `hint`。
- `code_reading` 一致性：`practice-causal-01` 现在包含可执行的 PyTorch 风格 causal-mask 代码，不再只有文字设定。
- 单题反馈：采用 `current_answer_only`，不保存累计答题记录，不统计正确率或总体掌握度。
- 学习时长一致性：学习顺序合计 220 分钟，与 `estimated_study_time_minutes: 220` 一致。

## 公式与形状抽检

| 主题 | 核对内容 | 结果 |
| --- | --- | --- |
| Token 矩阵 | 每个 token 作为一行，`T∈R^(N×d)` | 一致 |
| QKV | `Q=T W_q`、`K=T W_k`、`V=T W_v`，`A` 为 query×key | 一致 |
| Attention 输出 | `Z_out=A V` | 一致 |
| MSA | 多头并行、拼接、再投影 | 一致 |
| 置换性质 | permutation equivariance 不等于 permutation invariance | 一致 |
| Causal mask | 位置 i 不读取未来位置 | 一致 |
| Cross-attention | text query 读取 image key/value | 一致 |

## 发布结果

人类维护者已于 2026-08-03 完成术语、公式、练习和渲染复核并确认通过；StudyKit 状态提升为 `reviewed`。
