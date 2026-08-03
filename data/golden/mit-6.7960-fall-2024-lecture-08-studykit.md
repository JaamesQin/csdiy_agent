# Lecture 8: Transformers

> 版本：fall-2024 · 状态：reviewed

## 学习目标

- 解释 token 如何把输入数据组织为可操作的向量表示。
- 区分固定参数的 token mixing 与数据依赖的 attention mixing。
- 用 query、key、value 解释 self-attention 的计算路径。
- 描述 multihead self-attention 和 Transformer block 的组成。
- 解释 permutation equivariance、位置编码和 autoregressive mask 的关系。
- 识别 self-attention、causal self-attention 和 cross-attention 的应用差异。

## 前置知识

- MLP 与 token-wise 线性层：能读懂线性层、非线性层以及对一组向量逐项应用同一函数。
- 向量、矩阵与点积：能判断矩阵乘法、转置和 dot product 的基本形状。
- 卷积网络与局部感受野：理解小卷积核带来的局部连接，以及堆叠层扩大感受野的方式。
- 基础张量形状操作：能读懂 token 维度、序列长度和批量维度的区别。
- 张量计算与 PyTorch 入门：能阅读 token 张量、形状操作和基本 attention 代码。

## 学习提纲

1. **Transformer 动机与三项创新**（第 2–9 页）：理解 CNN 局部感受野难以高效建模远距离关系，以及 token、attention、位置编码的总体角色。
2. **Token 与 tokenization**（第 10–16 页）：建立 token 作为向量化信息单元的表示和矩阵记号。
3. **Token mixing 与 token-wise nonlinearity**（第 17–24 页）：把 Transformer 的两类基本操作与普通神经网络的线性层、逐元素非线性对应起来。
4. **Attention 与 query-key-value**（第 25–34 页）：理解数据依赖的 attention matrix、QKV 投影、softmax 权重和 self-attention。
5. **Multihead self-attention 与 ViT block**（第 35–39 页）：理解多头并行、输出合并、token norm、token-wise MLP 和 residual connection。
6. **Permutation equivariance 与 positional encoding**（第 40–47 页）：解释 token 操作为什么保留置换等变，以及如何加入位置或坐标信息。
7. **Autoregressive modeling 与 causal attention**（第 48–53 页）：理解训练时的并行预测、因果 mask 和 GPT 类模型的时间依赖。
8. **Cross-attention 与图像到文本**（第 54–55 页）：理解不同 token 集合之间的 attention，以及图像编码器与文本解码器的连接。

## 核心概念

### token（令牌/向量化信息单元）（token）

本讲把 token 定义为封装了一组信息的向量化神经元集合；在后续 Transformer 层中，token 是主要操作对象，而不是单个标量神经元。

来源：讲义第 11、15 页。

### token 矩阵（token matrix）

若有 N 个 token、每个 token 的 code vector 维度为 d，本讲将每个 token 转置后作为一行，组成 T∈R^(N×d)。

来源：讲义第 11、16 页。

### tokenization（切分/标记化）（tokenization）

Tokenization 把原始输入切分或投影为一组 token；例如将图像分成 patch，并用可学习的线性投影把每个 patch 映射到 token code vector。

来源：讲义第 14、15 页。

### token mixing（token 混合）（token mixing）

Token mixing 用权重对多个向量化 token 做线性组合；若输入为 T_in∈R^(N_in×d)，固定混合矩阵 W 可产生 T_out=W T_in。

来源：讲义第 17、20 页。

### token-wise 非线性（逐 token 非线性）（token-wise nonlinearity）

Token-wise nonlinearity 对每个 token 独立应用同一个非线性函数 Fθ；Fθ 常可取一个 MLP，因此它不会直接混合不同 token。

来源：讲义第 18、19 页。

### attention（注意力）（attention）

Attention 是一种数据依赖的 token 线性组合：attention matrix A 不是固定自由参数，而是由输入数据经过函数计算得到，因此不同输入或问题可以选择不同的 token 权重。

来源：讲义第 20、27 页。

### query-key-value（QKV）注意力（query-key-value attention）

QKV attention 将 token code vector z 分别投影为 query q、key k 和 value v；query 与 key 的相似度决定 attention 权重，value 则被按这些权重混合。

来源：讲义第 29、32、34 页。

### self-attention（自注意力）（self-attention）

Self-attention 让同一组输入 token 同时产生 query、key 和 value；每个 token 都可以根据对其他 token 的匹配结果，聚合整组 token 的信息。

来源：讲义第 30、32 页。

### multihead self-attention（多头自注意力，MSA）（multihead self-attention）

MSA 并行运行多个带独立 QKV 投影的 attention head，拼接各 head 的输出，再用可学习矩阵投影回目标 token 维度。

来源：讲义第 36、37 页。

### Transformer block（Transformer 模块）（Transformer block）

本讲展示的 Transformer block 以 self-attention 和 token-wise MLP 为核心，并可加入 token normalization 与 residual connection；多个 block 可以堆叠形成 ViT 等架构。

来源：讲义第 36、38、39 页。

### 置换等变性（permutation equivariance）

对 token 顺序做置换后，Transformer 的输出会按同样置换重新排列；这称为 permutation equivariance，而不是输出完全不变的 permutation invariance。

来源：讲义第 35、41 页。

### positional encoding（位置编码）（positional encoding）

由于 token mixing 和 token-wise 操作本身不携带 token 的绝对位置，位置编码把位置或坐标信息加入 token code vector，使模型能够利用空间或序列位置。

来源：讲义第 42、43、44 页。

### causal attention（因果注意力）（causal attention）

Causal attention 用 mask 阻止当前位置访问未来 token，使第 n 个输出只能依赖允许的当前或过去 token，从而支持 autoregressive prediction。

来源：讲义第 48、50、52 页。

### cross-attention（交叉注意力）（cross-attention）

Cross-attention 让一组 token 产生 query，另一组 token 产生 key 和 value；在图像到文本架构中，文本 decoder 可以通过它读取 image encoder 输出的 token。

来源：讲义第 54 页。

## 学习顺序

1. 完成三个前置检查题。（约 15 分钟）
2. 阅读第 2–16 页，理解 CNN 的局部性限制、tokenization 和 token 矩阵。（约 35 分钟）
   - Transformer 首先改变处理对象：把输入组织成 token 集合，并用 T∈R^(N×d) 表示 N 个向量化 token。
3. 阅读第 17–24 页，比较 token mixing、token-wise nonlinearity 和普通神经网络层。（约 25 分钟）
   - token mixing 在 token 之间交换信息，token-wise 非线性独立变换每个 token；二者分别对应普通网络中的线性混合和逐神经元非线性。
4. 阅读第 25–34 页，按形状推导 QKV attention 和 self-attention。（约 40 分钟）
   - Attention 用输入依赖的权重替代固定混合矩阵；QK^T 产生 query-key 匹配分数，softmax 后对 V 做加权求和。
5. 阅读第 35–39 页，理解 MSA 和 ViT Transformer block 的数据流。（约 25 分钟）
   - 多个 attention head 并行提取不同关系，再拼接并投影；token norm、token-wise MLP 和 residual connection 组成可堆叠的 Transformer block。
6. 阅读第 40–47 页，区分 permutation equivariance、permutation invariance 和 positional encoding。（约 25 分钟）
   - 没有额外位置信息时，token 操作对顺序置换保持等变；位置编码把空间或序列位置重新注入 token 表示。
7. 阅读第 48–54 页，理解 causal attention、GPT 训练和 cross-attention。（约 25 分钟）
   - 因果 mask 让训练时不同位置可以并行计算但不能读取未来；cross-attention 则把一组 token 的信息提供给另一组 token。
8. 按需完成后面的 practice；每次作答后只获取针对本题的即时点评。（约 30 分钟）
   - 练习覆盖 token 形状、attention 计算、QKV 来源、MSA、位置编码、因果 mask 和 cross-attention；系统不累计正确率或生成整套题的掌握度结论。

## 练习

### practice-concept-01

类型：concept

CNN 的局部感受野为什么会使远距离 patch 之间的关系难以建模？Transformer 的 attention 针对这个限制提供了什么思路？

作答要求：用两三句话说明限制和 attention 的基本解决思路。

### practice-shape-01

类型：implementation

- N=5 个 token
- 每个 token 的 code vector 维度 d=8
- query/key 维度 d_q=4
- value 维度 d_v=6

按本讲 T∈R^(N×d) 的行 token 约定，写出 T、Q、K、V、QK^T、A 和 Z_out 的形状，并说明 attention matrix A 中一行对应什么。

作答要求：列出所有形状，并用一句话解释 A 的行列含义。

### practice-attention-01

类型：derivation

```text
有两个 key，某个 query 与它们的 scaled dot-product scores 为 [0, 0]。
对应 value vectors 为 v₁ 和 v₂。
```

不需要计算小数，写出 softmax 后的 attention 权重，以及该 query 的输出向量。解释为什么两个 score 相同时输出是两个 value 的平均。

作答要求：写出权重和输出向量表达式，并说明对称性来源。

### practice-qkv-01

类型：concept

在 self-attention、cross-attention 和普通固定 token mixing 中，分别说明 query、key、value 的来源或权重来源有什么不同。

作答要求：分别写出三种机制的来源关系，并指出哪一种使用数据依赖的 attention matrix。

### practice-architecture-01

类型：implementation

一个 ViT block 按以下结构组织：token normalization → MSA → residual connection → token normalization → token-wise MLP → residual connection。说明 MSA 与 token-wise MLP 各自改变什么，以及为什么两者都需要。

作答要求：分别说明两类操作的信息流范围，并解释它们在 block 中的互补性。

### practice-permutation-01

类型：transfer

如果把输入 token 的行顺序打乱，基础 Transformer 的 token-level 输出会发生什么？为什么图像或序列任务通常还需要 positional encoding？

作答要求：解释 permutation equivariance，并说明位置编码注入了什么信息。

### practice-causal-01

类型：code_reading

```python
import torch

n = 4
scores = torch.zeros(n, n)
future = torch.triu(torch.ones(n, n), diagonal=1).bool()
masked_scores = scores.masked_fill(future, float("-inf"))
allowed = masked_scores.isfinite()
```

写出允许访问的位置模式：第 1、2、3、4 个 query 分别可以读取哪些 key。然后解释为什么训练时仍可并行计算，而生成时通常逐 token 进行。

作答要求：列出四行允许访问的 key 索引，并说明训练/生成的计算差异。

### practice-cross-attention-01

类型：transfer

图像到文本系统中，图像 encoder 输出 image tokens，文本 decoder 当前层输出 text tokens。若使用 cross-attention，哪一组 token 产生 Q，哪一组产生 K/V？这使 decoder 获得了什么信息？

作答要求：写出 Q、K、V 的来源，并说明 cross-attention 在架构中的作用。

## 使用限制

- 这是初稿，不替代原讲义。
- 复杂公式、图形、attention heatmap 和矩阵方向应回看原 PDF；文本提取可能丢失视觉结构。
- ‘token nets’ 是本讲材料中的工作术语，不是所有 Transformer 文献中的标准术语。
- 教学补充不是 MIT 官方表述，已通过 teaching_note、claim_type 或 limitations 标记。
- 不使用字幕、视频文字稿或时间戳引用。
- PDF 中部分图像和外部论文图表带有版权限制；StudyKit 仅做概念说明，不复制这些图像。
- 不包含课程作业答案，也不应被用于生成可直接提交的答案。
