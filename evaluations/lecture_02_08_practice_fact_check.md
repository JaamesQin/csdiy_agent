# Lecture 2/8 练习题事实核对

核对日期：2026-08-03

## 结果摘要

- Lecture 2：7/7 题的数学关系、张量形状、训练流程和题目范围正确。
- Lecture 8：8/8 题的 QKV 关系、张量形状、mask 访问模式和架构概念正确；其中 1 题的 ViT block 顺序已修正，1 题补充了 token-level 输出限定。
- 所有题目的 `source_pages` 均能解析到对应讲次的 SourceChunk。

## 重点核对

| 题目 | 核对内容 | 结果 |
| --- | --- | --- |
| L2 `practice-derivation-01` | `u=ax, v=u², J=v+b`，因此 `dJ/da=2ux=2ax²` | 正确 |
| L2 `practice-shape-01` | 讲义 Jacobian 行布局下，`∂J/∂W₂` 为 `3×2`、`∂J/∂W₁` 为 `4×3`；更新时取转置 | 正确 |
| L2 `practice-code-reading-01` | 首次梯度为 36，第二次 `backward()` 后 `.grad` 累加为 72；清空 `.grad` 后只保留第二次梯度 | 正确；属于 PyTorch 教学迁移，不声称讲义直接给出 API 行为 |
| L2 `practice-differentiable-programming-01` | 硬 `argmax`/离散索引不能向 `scores` 提供有用的连续梯度；softmax 加权替代保留梯度路径 | 正确 |
| L8 `practice-shape-01` | `T:5×8, Q/K:5×4, V:5×6, A:5×5, Z_out:5×6` | 正确 |
| L8 `practice-qkv-01` | self-attention 的 Q/K/V 来自同组；cross-attention 的 Q 与 K/V 来自不同组 | 正确 |
| L8 `practice-architecture-01` | `token norm → MSA → residual → token norm → token-wise MLP → residual` | 已修正并与第 38–39 页一致 |
| L8 `practice-permutation-01` | token-level 输出按同样置换排列；后续 pooling 可能另有不变性 | 已补充范围限定 |
| L8 `practice-causal-01` | `triu(diagonal=1)` 标记未来位置；第 i 行只能访问 1…i | 正确 |
| L8 `practice-cross-attention-01` | 图像到文本中 text query 读取 image key/value | 正确 |

结论：当前练习没有未修正的事实性错误。代码题中的具体 PyTorch API 是教学迁移，课程材料引用支持其概念依据，不应被表述为 MIT 讲义直接规定的 API 行为。
