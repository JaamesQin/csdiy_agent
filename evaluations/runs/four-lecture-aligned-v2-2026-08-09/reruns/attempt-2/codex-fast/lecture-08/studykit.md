# Lecture 8：Transformers

> 课程：mit-6.7960-fall-2024 · 版本：fall-2024 · 单元：lecture-08

## 学习目标

- 解释浅层局部 CNN 处理远距离关系的路径限制。
- 用矩阵形状表达 tokenization、token mixing 与逐 token MLP。
- 从 Q/K/V 投影推演 self-attention 的权重与输出。
- 复原多头 attention 与完整 ViT block。
- 用置换等变性说明为何要提供位置代码。
- 比较 causal self-attention 和 image-to-text cross-attention。

## 前置知识

- 矩阵乘法与转置：可追踪矩阵形状。
- MLP、卷积、残差：理解局部连接、共享变换和跳跃相加。
- softmax：能把分数解释为归一化权重。

## 核心概念

### 局部性限制

小卷积核只连接局部邻域；浅层示例中相距很远的输入节点无法共同影响一个节点。attention 用跨 token 混合来处理此类关系。

来源：mit-6.7960-f24-lecture-08-slides@page:4, mit-6.7960-f24-lecture-08-slides@page:5

### Tokenization

token 是封装信息的向量。图像可切成 patches，每个 patch 经线性投影成为 d 维 token，N 个 tokens 作为矩阵 T 的行。

来源：mit-6.7960-f24-lecture-08-slides@page:14, mit-6.7960-f24-lecture-08-slides@page:14

公式：$$t\in\mathbb{R}^{d},\qquad T\in\mathbb{R}^{N\times d}$$

### Token mixing

标量权重作用于整条 token 向量；左乘 W 对 token 行作线性组合。

来源：mit-6.7960-f24-lecture-08-slides@page:17

公式：$$T_{out}[i,:]=\sum_{j=1}^{N}w_{ij}T_{in}[j,:],\qquad T_{out}=WT_{in}$$

### Token-wise nonlinearity

同一 F_θ 独立作用于各 token；通常 F_θ 是 MLP，此步本身不跨 token 汇聚。

来源：mit-6.7960-f24-lecture-08-slides@page:18

公式：$$T_{out}=\begin{bmatrix}F_\theta(T_{in}[0,:])\\\vdots\\F_\theta(T_{in}[N-1,:])\end{bmatrix}$$

### 数据依赖 attention

普通线性层直接学习 W；attention 则由输入构造 A，使混合权重随当前 tokens 改变。

来源：mit-6.7960-f24-lecture-08-slides@page:20, mit-6.7960-f24-lecture-08-slides@page:34

### Scaled dot-product self-attention

同一输入集产生 Q、K、V；QK^T 给出所有 query-key 匹配，经缩放和 softmax 得 A，随后 AV 汇聚 values。

来源：mit-6.7960-f24-lecture-08-slides@page:34, mit-6.7960-f24-lecture-08-slides@page:30, mit-6.7960-f24-lecture-08-slides@page:34

公式：$$Q=T_{in}W_q^T,\;K=T_{in}W_k^T,\;V=T_{in}W_v^T,\quad A=\operatorname{softmax}\left(\frac{QK^T}{\sqrt m}\right),\quad T_{out}=AV$$

### Multihead self-attention

k 个 heads 分别计算 attention，按 token 行拼接为 N×kv，再用 W_MSA 投影回 d 维。

来源：mit-6.7960-f24-lecture-08-slides@page:37

公式：$$T_{out}^{i}=\operatorname{attn}^{i}(T_{in}),\quad \bar T_{out}\in\mathbb{R}^{N\times kv},\quad T_{out}=\bar T_{out}W_{MSA},\;W_{MSA}\in\mathbb{R}^{kv\times d}$$

### ViT block

课件展示的块依次使用 token norm、MSA、残差，再使用 token norm、逐 token MLP、残差，并重复 L 次。

来源：mit-6.7960-f24-lecture-08-slides@page:39, mit-6.7960-f24-lecture-08-slides@page:39

### Permutation equivariance

输入 token 行被置换时，输出行作相同置换；这不是逐项输出不变。

来源：mit-6.7960-f24-lecture-08-slides@page:41

公式：$$\operatorname{transformer}(\operatorname{permute}(T_{in}))=\operatorname{permute}(\operatorname{transformer}(T_{in}))$$

### Fourier positional codes

把 x、y 坐标在多尺度正弦上的值组织成位置向量并附加到 token 表示，使空间位置可区分。

来源：mit-6.7960-f24-lecture-08-slides@page:43, mit-6.7960-f24-lecture-08-slides@page:43

公式：$$p_x=[\sin(x),\sin(x/B),\sin(x/B^2),\ldots]^T,\quad p_y=[\sin(y),\sin(y/B),\sin(y/B^2),\ldots]^T,\quad p=[p_x;p_y]$$

### Causal attention

causal mask 阻止当前位置依赖未来 tokens；一次前向仍能并行监督多个 next-token 位置，多层连接保持因果。

来源：mit-6.7960-f24-lecture-08-slides@page:51, mit-6.7960-f24-lecture-08-slides@page:51

### Cross-attention

图像到文本架构用 image self-attention 编码视觉 tokens；文本侧用 causal self-attention，并让文本 queries 对图像 keys/values 做 cross-attention。

来源：mit-6.7960-f24-lecture-08-slides@page:54

## 学习顺序

1. 画出浅 CNN 远距节点路径并归纳 Transformer 的三项创新。（20 分钟）
2. 完成 patch→token、WT 和逐 token MLP 的形状追踪。（35 分钟）
3. 逐步构造 Q、K、V、A 和 AV，并解释其语义。（40 分钟）
4. 重画多头输出合并和 ViT 残差块。（25 分钟）
5. 做 token 置换与位置码对照实验。（25 分钟）
6. 分析 causal mask 与图像到文本连接，完成综合练习。（35 分钟）

## 练习

### P1 · 基础

6 个 patches 各映射到 8 维 token。写出 T 的形状；若 W∈R^{4×6}，写出 WT 的形状。

提示：token 放在行。

提交：形状推导。

来源：mit-6.7960-f24-lecture-08-slides@page:14, mit-6.7960-f24-lecture-08-slides@page:17

### P2 · 基础

比较 token mixing 和 token-wise MLP：哪一步跨 token，哪一步独立处理每行？

提示：检查求和下标。

提交：两列表。

来源：mit-6.7960-f24-lecture-08-slides@page:17, mit-6.7960-f24-lecture-08-slides@page:18

### P3 · 中级

设 N=5，Q/K 维4，V维6。列出 Q、K、V、QK^T、A、AV 的形状。

提示：每个 query 对五个 keys。

提交：形状表和 A_ij 含义。

来源：mit-6.7960-f24-lecture-08-slides@page:34

### P4 · 中高级

把 (t1,t2,t3) 置换为 (t3,t1,t2)。写出无位置码输出关系，并说明位置码为何能让空间槽可区分。

提示：等变不等于不变。

提交：等式和解释。

来源：mit-6.7960-f24-lecture-08-slides@page:41, mit-6.7960-f24-lecture-08-slides@page:43, mit-6.7960-f24-lecture-08-slides@page:43

### P5 · 高级

画长度4、两层 causal attention 的允许边，并证明位置2不能读取位置4；说明训练仍如何并行。

提示：每层都删除未来边。

提交：图、路径论证、并行说明。

来源：mit-6.7960-f24-lecture-08-slides@page:51, mit-6.7960-f24-lecture-08-slides@page:51

### P6 · 综合

为图像描述模型列出 image self-attn、text causal self-attn、cross-attn 的 Q/K/V 来源，并标出防未来词泄漏的位置。

提示：文本查询图像。

提交：架构图和来源表。

来源：mit-6.7960-f24-lecture-08-slides@page:54

## 限制

- 仅依据 Lecture 8 幻灯片的可见内容；隐藏提取文本未用作证据。
- 不展开第45–47页外部论文的完整方法。
- 第44页只转录可见 sine 位置代码，不推断未显示分量。
