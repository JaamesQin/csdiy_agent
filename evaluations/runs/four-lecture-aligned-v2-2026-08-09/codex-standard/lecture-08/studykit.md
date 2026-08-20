# Lecture 8：Transformers

> 课程：mit-6.7960-fall-2024 · 版本：fall-2024 · 单元：lecture-08

## 学习目标

- 诊断浅层局部 CNN 在长距离 patch 比较上的信息路径限制。
- 用矩阵形状描述 tokenization、跨 token 混合和逐 token 非线性。
- 从 Q/K/V 投影推导 scaled dot-product self-attention 的数据流。
- 追踪多头输出如何合并，并复原含 norm、residual 和 MLP 的 ViT 块。
- 用置换实验解释 transformer 的等变性以及位置码的作用。
- 在自回归和图像到文本系统中正确配置 causal self-attention 与 cross-attention。

## 前置知识

- 线性代数与矩阵形状：能做矩阵乘法和转置并解释行/列。
- MLP、卷积、残差连接：理解共享变换、感受野和跳跃相加。
- softmax：能把一组分数解释为归一化权重。

## 核心概念

### Transformer 的动机

小核 CNN 依赖逐层扩大的感受野；浅层网络中相距很远的 patch 可能没有共同接收二者的节点。Transformer 用 attention 在 token 间混合信息。

来源：mit-6.7960-f24-lecture-08-slides@page:4, mit-6.7960-f24-lecture-08-slides@page:5

### Token

本讲把 token 视为一组神经元形成的向量，是模型各层访问和修改信息的基本单位。

来源：mit-6.7960-f24-lecture-08-slides@page:11

### 图像 tokenization

把图像裁成 patches，向量化后经可学习线性投影得到 d 维 tokens；N 个 token 作为 T 的 N 行。

来源：mit-6.7960-f24-lecture-08-slides@page:14

公式：$$t\in\mathbb{R}^{d},\qquad T\in\mathbb{R}^{N\times d}$$

### 跨 token 线性组合

标量权重作用于整条 token 向量，因而左乘 W 改变 token 轴而保留代码维度。

来源：mit-6.7960-f24-lecture-08-slides@page:17

公式：$$T_{out}[i,:]=\sum_{j=1}^{N}w_{ij}T_{in}[j,:],\qquad T_{out}=WT_{in}$$

### Token-wise nonlinearity

共享函数 F_θ 分别变换每一行，不与其他 token 通信；通常 F_θ 是 MLP。

来源：mit-6.7960-f24-lecture-08-slides@page:18

公式：$$T_{out}=\begin{bmatrix}F_\theta(T_{in}[0,:])\\\vdots\\F_\theta(T_{in}[N-1,:])\end{bmatrix}$$

### Token net 与图视角

token net 交替执行节点混合与逐节点更新；课件把 GNN 的 AGGREGATE/UPDATE 对应到这两步，并把 Transformer 看作完全图上的 GNN。

来源：mit-6.7960-f24-lecture-08-slides@page:20, mit-6.7960-f24-lecture-08-slides@page:23, mit-6.7960-f24-lecture-08-slides@page:24

### 数据依赖注意力矩阵

普通线性层的 W 是自由参数，而注意力矩阵 A 由输入数据经过函数 f 构造，因此是动态加权汇聚。

来源：mit-6.7960-f24-lecture-08-slides@page:20, mit-6.7960-f24-lecture-08-slides@page:32

### QKV self-attention

每个输入 token 投影出 query、key、value；每个 query 与所有 keys 匹配，归一化权重随后混合 values，产生相同数量的输出 tokens。

来源：mit-6.7960-f24-lecture-08-slides@page:29, mit-6.7960-f24-lecture-08-slides@page:30, mit-6.7960-f24-lecture-08-slides@page:34

公式：$$Q=T_{in}W_q^T,\;K=T_{in}W_k^T,\;V=T_{in}W_v^T,\quad A=\operatorname{softmax}\left(\frac{QK^T}{\sqrt m}\right),\quad T_{out}=AV$$

### Multihead self-attention

k 个 head 使用各自的 Q/K/V 函数并行产生表示，按 token 对齐拼接成 N×kv，再由 W_MSA 投影至 d 维。

来源：mit-6.7960-f24-lecture-08-slides@page:37

公式：$$T_{out}^{i}=\operatorname{attn}^{i}(T_{in}),\quad \bar T_{out}\in\mathbb{R}^{N\times kv},\quad T_{out}=\bar T_{out}W_{MSA},\;W_{MSA}\in\mathbb{R}^{kv\times d}$$

### ViT block

一个块采用 token norm→MSA→残差，再 token norm→逐 token MLP→残差；灰色块重复 L 次。

来源：mit-6.7960-f24-lecture-08-slides@page:38, mit-6.7960-f24-lecture-08-slides@page:39

### Permutation equivariance

若输入 token 行被置换，token-wise 层和 attention 的输出行随之作同一置换；组合后的 transformer 仍保持该性质。等变不是输出不变。

来源：mit-6.7960-f24-lecture-08-slides@page:35, mit-6.7960-f24-lecture-08-slides@page:41

公式：$$\operatorname{transformer}(\operatorname{permute}(T_{in}))=\operatorname{permute}(\operatorname{transformer}(T_{in}))$$

### Fourier positional encoding

为每个图像 token 编码 x、y 坐标在一组不同尺度正弦波上的取值，再把位置代码附加到 token 表示；第44页正文给出的方式是拼接，从而使位置可区分。

来源：mit-6.7960-f24-lecture-08-slides@page:43, mit-6.7960-f24-lecture-08-slides@page:44

公式：$$p_x=[\sin(x),\sin(x/B),\sin(x/B^2),\ldots,\sin(x/B^P)]^T,\quad p_y=[\sin(y),\sin(y/B),\ldots,\sin(y/B^P)]^T,\quad p=[p_x;p_y]$$

### Causal attention

causal mask 令某位置只能依赖允许的过去位置；同一次矩阵计算可监督多个 next-token 目标，多层连接仍保持因果路径。

来源：mit-6.7960-f24-lecture-08-slides@page:48, mit-6.7960-f24-lecture-08-slides@page:51, mit-6.7960-f24-lecture-08-slides@page:52

### Cross-attention

在图像到文本架构中，文本 token 发出 queries，图像 tokens 提供 keys/values；文本解码器本身同时使用 causal self-attention。

来源：mit-6.7960-f24-lecture-08-slides@page:54

## 学习顺序

1. 用第4–5页画出浅层 CNN 中两个远距 patch 的信息路径，写下 attention 要解决的问题。（20 分钟）
2. 从 patch tokenization 开始，完成 T、W 和逐 token MLP 的形状追踪。（30 分钟）
3. 对照第20、29、34页，逐步构造 A 并解释 query/key/value 的职责。（40 分钟）
4. 复原多头拼接与 ViT block，标注每条残差路径。（30 分钟）
5. 做一次 token 置换实验，再添加 Fourier 位置码比较结果。（25 分钟）
6. 分析 causal mask 和图像到文本架构，完成综合练习与自检。（35 分钟）

## 练习

### P1 · 入门

一幅图被分为 6 个 patches，每个投影到 16 维。写出 T 的形状，并说明行与列分别表示什么。

提示：课件把 token 向量放在行。

提交：形状和两句解释。

来源：mit-6.7960-f24-lecture-08-slides@page:14

### P2 · 基础

若 W∈R^{3×6}，计算 WT 的输出形状；说明该操作与 F_θ(T[i,:]) 的信息流差异。

提示：前者在 j 上求和，后者一次只读一行。

提交：形状推导和对照表。

来源：mit-6.7960-f24-lecture-08-slides@page:17, mit-6.7960-f24-lecture-08-slides@page:18

### P3 · 中级

用“普通线性层 vs attention”解释为什么 A 被称为数据依赖；对两个不同输入，哪些量会改变？

提示：比较自由参数 W 与 A=f(input)。

提交：不超过150字解释并画两个数据流框图。

来源：mit-6.7960-f24-lecture-08-slides@page:20, mit-6.7960-f24-lecture-08-slides@page:29

### P4 · 中级

设 T∈R^{5×8}，Q、K 的维度均为 4，V 的维度为 6。写出 Q、K、V、QK^T、A、AV 的形状。

提示：五个 queries 分别与五个 keys 匹配。

提交：逐步形状表。

来源：mit-6.7960-f24-lecture-08-slides@page:34

### P5 · 中高级

把输入 (t1,t2,t3) 置换成 (t3,t1,t2)。无位置码时写出输出关系；再说明给每个 patch 固定空间位置码后，若只移动 token 内容而不移动位置码，为什么不再是同一实验。

提示：区分“整行一起置换”和“内容换位但位置代码固定”。

提交：等式和一段反例分析。

来源：mit-6.7960-f24-lecture-08-slides@page:41, mit-6.7960-f24-lecture-08-slides@page:43, mit-6.7960-f24-lecture-08-slides@page:44

### P6 · 高级

画长度4的 causal attention 允许矩阵，并用跨两层的所有可达路径论证位置2不能读取位置4；指出为何训练仍可并行。

提示：每层都删除通向未来的边，但不同输出位置仍可同批计算。

提交：矩阵、两层图和100字论证。

来源：mit-6.7960-f24-lecture-08-slides@page:51, mit-6.7960-f24-lecture-08-slides@page:52

### P7 · 综合

依据第54页设计一个图像描述 transformer：分别标注三种 attention 的 Q 来源与 K/V 来源，并指出训练和采样中保持文本因果性的模块。

提示：文本 queries 跨注意图像 tokens；文本内部还需要 causal self-attention。

提交：模块图、Q/K/V 来源表和验收清单。

来源：mit-6.7960-f24-lecture-08-slides@page:54

## 限制

- 只依据 Lecture 8 幻灯片，不补写第45–47页所引论文的完整算法与实验结论。
- 注意力矩阵的 softmax 轴随行列约定变化；学习包保留课件的数学关系而不绑定具体框架 API。
- 第44页位置编码公式只保留可见的 sine 分量，不假设未显示的 cosine 设计。
