# Lecture 8：Transformers

> 课程：mit-6.7960-fall-2024 · 版本：fall-2024 · 单元：lecture-08

## 学习目标

- 从计算图路径解释浅层 CNN 难以比较远距图像区域的原因。
- 用维度一致的矩阵表达 tokenization、token mixing 和逐 token 非线性。
- 从 Q/K/V 投影到权重矩阵再到 value 汇聚，完整推演 self-attention。
- 复原多头 self-attention 和含归一化、残差、MLP 的 ViT block。
- 用置换等变关系判断何时需要位置编码。
- 在自回归文本与图像描述架构中区分 causal self-attention 和 cross-attention。

## 前置知识

- 矩阵乘法、转置与形状：可验证 QK^T 与 AV 的维度。
- MLP、卷积和残差：理解局部连接、逐点共享函数与跳跃相加。
- softmax：能把相似度分数解释成归一化权重。

## 核心概念

### 局部性限制

小卷积核只连接局部邻域；在示例的浅层网络中，相距很远的 x1 与 x7 没有同时接收二者的节点。attention 提供跨 token 的动态信息混合。

来源：mit-6.7960-f24-lecture-08-slides@page:4, mit-6.7960-f24-lecture-08-slides@page:5

### Token 与 tokenization

token 是封装信息的神经元向量。通用 tokenization 策略是把输入切块，再把每块投影成向量；课件展示了图像 patch、文本 byte pair 和声音片段。

来源：mit-6.7960-f24-lecture-08-slides@page:11, mit-6.7960-f24-lecture-08-slides@page:14, mit-6.7960-f24-lecture-08-slides@page:15

公式：$$t\in\mathbb{R}^{d},\qquad T\in\mathbb{R}^{N\times d}$$

### Token mixing

输出 token 的每个代码位置使用同一组标量权重汇聚输入 tokens；W 左乘 T，因此混合 token 轴。

来源：mit-6.7960-f24-lecture-08-slides@page:17

公式：$$T_{out}[i,:]=\sum_{j=1}^{N}w_{ij}T_{in}[j,:],\qquad T_{out}=WT_{in}$$

### Token-wise nonlinearity

共享非线性 F_θ 独立作用于每个 token；通常它是 MLP，且这一步本身不跨 token 传递信息。

来源：mit-6.7960-f24-lecture-08-slides@page:18, mit-6.7960-f24-lecture-08-slides@page:19

公式：$$T_{out}=\begin{bmatrix}F_\theta(T_{in}[0,:])\\\vdots\\F_\theta(T_{in}[N-1,:])\end{bmatrix}$$

### Token net 的图视角

token net 交替执行线性 token 混合与逐 token 更新；GNN 的 AGGREGATE/UPDATE 提供对应视角，Transformer 可看作完全图上的 GNN。

来源：mit-6.7960-f24-lecture-08-slides@page:20, mit-6.7960-f24-lecture-08-slides@page:22, mit-6.7960-f24-lecture-08-slides@page:23, mit-6.7960-f24-lecture-08-slides@page:24

### 数据依赖 attention

与直接学习固定连接矩阵 W 不同，attention 使用由当前输入构造的矩阵 A，因此可依 query 内容动态选择要汇聚的 tokens。

来源：mit-6.7960-f24-lecture-08-slides@page:20, mit-6.7960-f24-lecture-08-slides@page:29, mit-6.7960-f24-lecture-08-slides@page:32

### Scaled dot-product self-attention

同一输入 token 集产生 Q、K、V；QK^T 给出所有 query-key 匹配，缩放并 softmax 后得到 A，再由 AV 汇聚 values。

来源：mit-6.7960-f24-lecture-08-slides@page:29, mit-6.7960-f24-lecture-08-slides@page:33, mit-6.7960-f24-lecture-08-slides@page:34

公式：$$Q=T_{in}W_q^T,\;K=T_{in}W_k^T,\;V=T_{in}W_v^T,\quad A=\operatorname{softmax}\left(\frac{QK^T}{\sqrt m}\right),\quad T_{out}=AV$$

### Multihead self-attention

k 个 head 分别计算 attention，按同一 token 行拼接成 N×kv 表示，再用 W_MSA 映回 d 维。

来源：mit-6.7960-f24-lecture-08-slides@page:37

公式：$$T_{out}^{i}=\operatorname{attn}^{i}(T_{in}),\quad \bar T_{out}\in\mathbb{R}^{N\times kv},\quad T_{out}=\bar T_{out}W_{MSA},\;W_{MSA}\in\mathbb{R}^{kv\times d}$$

### ViT block

课件图中的 block 依次包含 token norm、MSA、残差加法、token norm、逐 token MLP、残差加法，并重复 L 次。

来源：mit-6.7960-f24-lecture-08-slides@page:38, mit-6.7960-f24-lecture-08-slides@page:39

### Permutation equivariance

逐 token 层和 attention 都对 token 行置换等变，它们的组合也等变：输入重排会导致输出作同一重排，而非输出保持逐项不变。

来源：mit-6.7960-f24-lecture-08-slides@page:35, mit-6.7960-f24-lecture-08-slides@page:41

公式：$$\operatorname{transformer}(\operatorname{permute}(T_{in}))=\operatorname{permute}(\operatorname{transformer}(T_{in}))$$

### Positional encoding

向 token 代码附加位置，使模型能区分相同内容处于不同坐标的情况。图像示例用多尺度正弦值表示 x、y，并拼接成 p。

来源：mit-6.7960-f24-lecture-08-slides@page:42, mit-6.7960-f24-lecture-08-slides@page:43, mit-6.7960-f24-lecture-08-slides@page:44

公式：$$p_x=[\sin(x),\sin(x/B),\sin(x/B^2),\ldots,\sin(x/B^P)]^T,\quad p_y=[\sin(y),\sin(y/B),\ldots,\sin(y/B^P)]^T,\quad p=[p_x;p_y]$$

### Causal attention

causal mask 删除从当前位置通向未来位置的信息边；它允许单次前向同时训练多个 next-token 目标，多层仍保持因果可达性。

来源：mit-6.7960-f24-lecture-08-slides@page:48, mit-6.7960-f24-lecture-08-slides@page:49, mit-6.7960-f24-lecture-08-slides@page:51, mit-6.7960-f24-lecture-08-slides@page:52

### Image-to-text cross-attention

图像编码器以 self-attention 处理视觉 tokens；文本解码器以 causal self-attention 处理文本，并用文本 queries 对图像 keys/values 做 cross-attention。

来源：mit-6.7960-f24-lecture-08-slides@page:54

## 学习顺序

1. 追踪第4–5页局部计算图，写出长距离关系所需的信息路径。（20 分钟）
2. 完成 patch→token→token mixing→token-wise MLP 的矩阵形状练习。（35 分钟）
3. 逐行推演 Q/K/V、QK^T、softmax 与 AV，并解释每个对象的语义。（40 分钟）
4. 重画多头合并与 ViT block，核查两条残差。（25 分钟）
5. 做 token 置换与位置码对照实验。（25 分钟）
6. 分析 causal 两层路径与图像到文本注意力来源，完成综合练习。（35 分钟）

## 练习

### Q1 · 基础

将 8 个图像 patches 投影成 12 维 tokens。写出 T 的形状；若 W∈R^{5×8}，写出 WT 的形状并解释其每一行。

提示：token 是行，W 混合行。

提交：维度推导和行语义。

来源：mit-6.7960-f24-lecture-08-slides@page:14, mit-6.7960-f24-lecture-08-slides@page:17

### Q2 · 基础

比较 token mixing、token-wise MLP 与 GNN 的 AGGREGATE/UPDATE；指出每步是否读取其他节点。

提示：用第22–23页建立对应。

提交：三列表。

来源：mit-6.7960-f24-lecture-08-slides@page:18, mit-6.7960-f24-lecture-08-slides@page:22, mit-6.7960-f24-lecture-08-slides@page:23

### Q3 · 中级

设 N=4、query/key 维 m=3、value 维 v=5。列出 Q、K、V、QK^T、A、AV 的形状，并解释 A 的一个元素。

提示：每个 query 对每个 key 得一个标量。

提交：形状表和元素解释。

来源：mit-6.7960-f24-lecture-08-slides@page:34

### Q4 · 中高级

对输入 token 作置换 π。先写无位置码输出关系，再讨论“token 内容移动但每个空间槽的位置码固定”为什么不是对完整输入行作同一 π。

提示：把内容和位置代码是否一起移动说清楚。

提交：等式和反例。

来源：mit-6.7960-f24-lecture-08-slides@page:41, mit-6.7960-f24-lecture-08-slides@page:43, mit-6.7960-f24-lecture-08-slides@page:44

### Q5 · 高级

画长度4、两层 causal attention 的允许边，证明输出位置2不存在通向输入位置4的路径；再说明训练为何仍可并行产生多个损失。

提示：每层都不允许未来边。

提交：两层图、路径证明、并行训练说明。

来源：mit-6.7960-f24-lecture-08-slides@page:51, mit-6.7960-f24-lecture-08-slides@page:52

### Q6 · 综合

设计图像描述模型的数据流表：对 image self-attn、text causal self-attn、cross-attn 分别填 Q、K、V 来源，并标出防止未来词泄漏的位置。

提示：cross-attn 由文本查询图像。

提交：架构图、来源表、泄漏检查清单。

来源：mit-6.7960-f24-lecture-08-slides@page:54

## 限制

- 只使用 Lecture 8 幻灯片可见内容；不补充第45–47页引用论文的未展示细节。
- 第34页 softmax 的具体轴依矩阵行列约定，本包不绑定实现 API。
- 第44页公式只含可见 sine 分量，不推断未出现的 cosine 分量。
