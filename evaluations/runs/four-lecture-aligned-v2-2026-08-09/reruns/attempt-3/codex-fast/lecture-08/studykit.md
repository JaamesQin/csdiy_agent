# Lecture 8：Transformers

> 课程：mit-6.7960-fall-2024 · 版本：fall-2024 · 单元：lecture-08

## 学习目标

- 解释浅层 CNN 中远距离输入缺少共同信息路径的原因。
- 推导 tokenization、token mixing 与 token-wise MLP 的矩阵形状。
- 从 Q/K/V 到 A 和 AV 完整解释 self-attention。
- 复原 multihead attention 的合并与 ViT block 的数据流。
- 用置换等变公式解释位置编码的需求。
- 比较 causal self-attention 和图像到文本 cross-attention。

## 前置知识

- 矩阵乘法与转置：能检查乘法维度。
- MLP、卷积、残差：理解局部连接、共享函数和残差相加。
- softmax：能把分数解释为归一化权重。

## 核心概念

### 局部性与远距离依赖

小卷积核只提供局部连接；浅层示例中相距很远的输入没有共同接收二者的节点，因此跨区域比较需要更长路径或另一种混合机制。

来源：mit-6.7960-f24-lecture-08-slides@page:4, mit-6.7960-f24-lecture-08-slides@page:5

### 图像 tokenization

把图像裁成 patches，再用可学习线性投影把每块变成 d 维向量；这些向量作为 Transformer 的 tokens。

来源：mit-6.7960-f24-lecture-08-slides@page:14

公式：$$t\in\mathbb{R}^{d}$$

### Token mixing

每个输出 token 是输入 token 向量的标量加权和；W 左乘 token 矩阵，混合行而不直接混合代码坐标。

来源：mit-6.7960-f24-lecture-08-slides@page:17

公式：$$T_{out}[i,:]=\sum_{j=1}^{N}w_{ij}T_{in}[j,:],\qquad T_{out}=WT_{in}$$

### 逐 token 非线性

共享函数 F_θ 独立作用于每个 token，通常由 MLP 实现；这一步不读取其他 token。

来源：mit-6.7960-f24-lecture-08-slides@page:18

公式：$$T_{out}=\begin{bmatrix}F_\theta(T_{in}[0,:])\\\vdots\\F_\theta(T_{in}[N-1,:])\end{bmatrix}$$

### Attention matrix

attention 使用由输入产生的矩阵 A 来混合 tokens，因此权重可以随当前输入变化。

来源：mit-6.7960-f24-lecture-08-slides@page:20, mit-6.7960-f24-lecture-08-slides@page:30

### Self-attention 的矩阵过程

同一 token 集产生 Q、K、V；所有 query-key 点积构成匹配矩阵，经缩放和 softmax 得 A，随后 A 加权汇聚 V。

来源：mit-6.7960-f24-lecture-08-slides@page:30, mit-6.7960-f24-lecture-08-slides@page:34

公式：$$Q=T_{in}W_q^T,\;K=T_{in}W_k^T,\;V=T_{in}W_v^T,\quad A=\operatorname{softmax}\left(\frac{QK^T}{\sqrt m}\right),\quad T_{out}=AV$$

### Multihead self-attention

k 个 heads 各自计算 attention，输出按 token 位置拼接成 N×kv，再由 W_MSA 投影到 d 维。

来源：mit-6.7960-f24-lecture-08-slides@page:37

公式：$$T_{out}^{i}=\operatorname{attn}^{i}(T_{in}),\quad \bar T_{out}\in\mathbb{R}^{N\times kv},\quad T_{out}=\bar T_{out}W_{MSA}$$

### ViT block

ViT 伪代码先归一化 tokens 后计算 attention 并加残差，再归一化后通过逐 token MLP 并加第二条残差；这一过程重复 L 层。

来源：mit-6.7960-f24-lecture-08-slides@page:39

### 置换等变性

若输入 token 行按某置换重排，Transformer 输出也按同一置换重排；等变不表示每个输出位置保持不动。

来源：mit-6.7960-f24-lecture-08-slides@page:41

公式：$$\operatorname{transformer}(\operatorname{permute}(T_{in}))=\operatorname{permute}(\operatorname{transformer}(T_{in}))$$

### 位置编码

当任务需要位置敏感性时，可向 token code vectors 添加位置信息；本包不保留 flagged chunk 中的具体位置公式。

来源：mit-6.7960-f24-lecture-08-slides@page:43

### Causal attention

causal mask 使当前输出只能使用允许的先前 tokens；一次矩阵运算仍能同时为多个时间位置产生训练预测。

来源：mit-6.7960-f24-lecture-08-slides@page:51

### Image-to-text attention

图像编码器在视觉 tokens 内做 self-attention；文本解码器使用 causal self-attention，并通过 cross-attention 读取图像 tokens。

来源：mit-6.7960-f24-lecture-08-slides@page:54

## 学习顺序

1. 分析浅层 CNN 的远距连接并整理三项创新。（20 分钟）
2. 追踪 patch→token、WT 和逐 token MLP 的形状。（35 分钟）
3. 推演 Q、K、V、A、AV 的形状和语义。（40 分钟）
4. 画出 multihead 合并和 ViT 残差数据流。（25 分钟）
5. 做 token 置换与位置代码对照实验。（25 分钟）
6. 分析 causal 训练和图像到文本架构并完成综合练习。（35 分钟）

## 练习

### p1 · 基础

将 5 个 patches 投影成 12 维 tokens。写出 T 的形状；若 W∈R^{3×5}，写出 WT 的形状并解释每个输出行。

提示：tokens 是行。

提交：形状和一句解释。

来源：mit-6.7960-f24-lecture-08-slides@page:14, mit-6.7960-f24-lecture-08-slides@page:17

### p2 · 基础

对照 token mixing 与 token-wise MLP，指出哪一步跨 token 读取，哪一步只读取单行。

提示：观察求和下标和 F_θ 输入。

提交：两列表。

来源：mit-6.7960-f24-lecture-08-slides@page:17, mit-6.7960-f24-lecture-08-slides@page:18

### p3 · 中级

若 N=4、Q/K 维3、V维6，写出 Q、K、V、QK^T、A、AV 的形状并解释 A_ij。

提示：每个 query 匹配四个 keys。

提交：形状表。

来源：mit-6.7960-f24-lecture-08-slides@page:34

### p4 · 中高级

把输入 tokens 做置换 π。写出输出关系，并解释添加固定空间槽的位置代码后，为何“只移动内容”不再等于对完整 token 行作 π。

提示：区分 token 内容与完整输入表示。

提交：等式和反例。

来源：mit-6.7960-f24-lecture-08-slides@page:41, mit-6.7960-f24-lecture-08-slides@page:43

### p5 · 高级

为长度4的 next-token 训练画 causal mask，说明哪些连接被遮住以及为何各位置损失仍可并行计算。

提示：未来 token 不可见，但各行仍能同批计算。

提交：4×4 mask 与说明。

来源：mit-6.7960-f24-lecture-08-slides@page:51

### p6 · 综合

在图像描述器中列出 image self-attention、text causal self-attention、cross-attention 的 Q/K/V 来源，并标出防未来词泄漏的模块。

提示：文本 queries 读取图像 keys/values。

提交：来源表和架构图。

来源：mit-6.7960-f24-lecture-08-slides@page:54

## 限制

- 仅使用 Lecture 8 幻灯片中具有 clean chunk 锚点的可见内容。
- 不保留 flagged hidden-text chunk 中的公式或陈述，即使对应页已视觉检查。
- 不展开第45–47页外部论文截图的技术细节。
