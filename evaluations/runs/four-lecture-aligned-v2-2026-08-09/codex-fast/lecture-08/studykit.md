# Lecture 8：Transformers

> 课程：mit-6.7960-fall-2024 · 版本：fall-2024 · 单元：lecture-08

## 学习目标

- 能够从局部感受野角度解释 Transformer 引入全局 token 交互的动机。
- 能够写出 token 矩阵的形状，并区分 token 混合与逐 token 非线性。
- 能够按 Q/K/V、相似度、softmax、value 加权和的顺序解释注意力。
- 能够说明多头注意力、残差、归一化与逐 token MLP 如何组成 ViT 块。
- 能够判断置换等变性何时有用，并说明位置编码与因果掩码如何引入顺序信息。
- 能够比较图像编码器、文本解码器中的 self-attention、causal self-attention 与 cross-attention。

## 前置知识

- 矩阵乘法与向量维度：能检查矩阵乘法形状
- MLP、卷积与残差连接：能解释逐点非线性和残差加法
- softmax：知道其把分数归一化为权重

## 核心概念

### 局部性与全局依赖

小卷积核让相距很远的区域在浅层中不能直接交互；注意力允许根据任务动态汇聚远处 token 的信息。

来源：mit-6.7960-f24-lecture-08-slides@page:4, mit-6.7960-f24-lecture-08-slides@page:5, mit-6.7960-f24-lecture-08-slides@page:6

### Token 与 tokenization

token 是封装信息的向量。图像可切成 patches，再用可学习线性投影映射为 d 维 token；N 个 token 组成矩阵 T∈R^{N×d}。

来源：mit-6.7960-f24-lecture-08-slides@page:11, mit-6.7960-f24-lecture-08-slides@page:14, mit-6.7960-f24-lecture-08-slides@page:16

公式：$$T\in\mathbb{R}^{N\times d}$$

### Token 混合

跨 token 的线性组合对整条 token 向量使用同一个标量权重；矩阵形式是 T_out=W T_in。

来源：mit-6.7960-f24-lecture-08-slides@page:17

公式：$$T_{\mathrm{out}}[i,:]=\sum_{j=1}^{N}w_{ij}T_{\mathrm{in}}[j,:],\quad T_{\mathrm{out}}=WT_{\mathrm{in}}$$

### 逐 token 非线性

同一个非线性函数 F_θ 独立作用于每个 token；通常由 MLP 实现，功能上类似沿 token 序列运行的 1×1 卷积。

来源：mit-6.7960-f24-lecture-08-slides@page:18, mit-6.7960-f24-lecture-08-slides@page:19

公式：$$T_{\mathrm{out}}=[F_\theta(T_{\mathrm{in}}[0,:]);\ldots;F_\theta(T_{\mathrm{in}}[N-1,:])]$$

### Query–Key–Value attention

query 表示要寻找什么，key 用于匹配，value 是被汇聚的内容。先由线性投影得到 q、k、v，再把 query 与各 key 的相似度经 softmax 归一化，最后对 value 加权求和。

来源：mit-6.7960-f24-lecture-08-slides@page:29, mit-6.7960-f24-lecture-08-slides@page:32

公式：$$q=W_qt,\;k=W_kt,\;v=W_vt,\quad A=\operatorname{softmax}(s),\quad T_{\mathrm{out}}=AV$$

### Self-attention

self-attention 让同一组输入 token 同时提供 queries、keys 与 values，使每个 token 能根据上下文聚合其他 token。

来源：mit-6.7960-f24-lecture-08-slides@page:30, mit-6.7960-f24-lecture-08-slides@page:32

### Multihead self-attention

k 个 head 各自拥有 Q/K/V 投影并行计算，按 token 位置拼接结果，再以 W_MSA 投影回 d 维。

来源：mit-6.7960-f24-lecture-08-slides@page:37

公式：$$T_{\mathrm{out}}^{i}=\operatorname{attn}^{i}(T_{\mathrm{in}}),\quad \bar T_{\mathrm{out}}\in\mathbb{R}^{N\times kv},\quad T_{\mathrm{out}}=\bar T_{\mathrm{out}}W_{\mathrm{MSA}},\;W_{\mathrm{MSA}}\in\mathbb{R}^{kv\times d}$$

### ViT Transformer block

ViT 块把 token norm、MSA、残差连接、再次 token norm、逐 token MLP 与另一条残差连接组合起来，并重复 L 次。

来源：mit-6.7960-f24-lecture-08-slides@page:38, mit-6.7960-f24-lecture-08-slides@page:39

### 置换等变性

不含位置码的逐 token 层和自注意力对输入 token 的置换作同样置换，因此整个 transformer 是 set-to-set 的置换等变映射，而不是自动感知空间位置。

来源：mit-6.7960-f24-lecture-08-slides@page:35, mit-6.7960-f24-lecture-08-slides@page:41

公式：$$\operatorname{transformer}(\operatorname{permute}(T_{\mathrm{in}}))=\operatorname{permute}(\operatorname{transformer}(T_{\mathrm{in}}))$$

### Fourier positional codes

把坐标在多频率正弦基上编码，并把位置向量加入或拼接到 token 表示，从而让模型区分位置。

来源：mit-6.7960-f24-lecture-08-slides@page:43, mit-6.7960-f24-lecture-08-slides@page:44

公式：$$p_x=[\sin(x),\sin(x/B),\sin(x/B^2),\ldots],\quad p_y=[\sin(y),\sin(y/B),\sin(y/B^2),\ldots]$$

### Causal attention

因果 mask 阻止位置 i 使用未来位置；训练时，多个 next-token 预测可在一次前向传播中并行监督，多层仍保持因果依赖。

来源：mit-6.7960-f24-lecture-08-slides@page:48, mit-6.7960-f24-lecture-08-slides@page:51, mit-6.7960-f24-lecture-08-slides@page:52

### Cross-attention

图像到文本架构先以图像 self-attention 得到视觉 token；文本解码器用 causal self-attention，并让文本 token cross-attend 图像 token。

来源：mit-6.7960-f24-lecture-08-slides@page:54

## 学习顺序

1. 阅读动机、三项创新并做局部/全局对照表。（20 分钟）
2. 手工追踪 patch→token、token 混合与逐 token MLP 的矩阵形状。（30 分钟）
3. 用一个 query 对四个图像 token 计算匹配、softmax 与 value 加权和。（40 分钟）
4. 画出多头输出拼接及 ViT 残差块的数据流。（30 分钟）
5. 完成置换等变性与 Fourier 位置码实验。（25 分钟）
6. 比较自回归文本与图像到文本注意力连接，并完成综合练习。（35 分钟）

## 练习

### P1 · 基础

设 4 个图像 patch 各投影成 8 维 token。写出 T_in 的形状；若 W∈R^{3×4}，写出 T_out=W T_in 的形状，并说明每一行的含义。

提示：token 放在矩阵的行；左乘混合 token 维。

提交：形状推导与一句语义解释。

来源：mit-6.7960-f24-lecture-08-slides@page:16, mit-6.7960-f24-lecture-08-slides@page:17

### P2 · 基础

比较 token mixing 与 token-wise MLP：哪一步跨 token 通信，哪一步独立处理每个 token？

提示：查看求和下标与 F_θ 的输入行。

提交：两列表格。

来源：mit-6.7960-f24-lecture-08-slides@page:17, mit-6.7960-f24-lecture-08-slides@page:18

### P3 · 中级

给定单个 query 与四个 key 的分数 [1,0.2,0.9,0.1]，说明 softmax 后哪些 value 贡献更大，并写出输出的符号表达式。无需计算小数。

提示：softmax 保持分数次序；输出是归一化权重乘 value 的和。

提交：排序与公式。

来源：mit-6.7960-f24-lecture-08-slides@page:29

### P4 · 中级

把三个 token 的顺序从 (t1,t2,t3) 改成 (t2,t3,t1)。对无位置码 transformer，预测输出如何变化；再说明加入位置码后为什么结论可能改变。

提示：先应用第41页等变关系，再考虑代码是否跟 token 内容一起被置换。

提交：一段推理和一个等式。

来源：mit-6.7960-f24-lecture-08-slides@page:41, mit-6.7960-f24-lecture-08-slides@page:43, mit-6.7960-f24-lecture-08-slides@page:44

### P5 · 高级

为长度 4 的 next-token 训练画出 causal attention 允许/禁止矩阵，并解释两层时为何第 i 个输出仍不能依赖未来输入。

提示：每层都只能从当前位置及允许的过去路径取信息。

提交：4×4 mask 与路径论证。

来源：mit-6.7960-f24-lecture-08-slides@page:51, mit-6.7960-f24-lecture-08-slides@page:52

### P6 · 综合

依据第54页设计图像描述器的数据流：标出 image self-attention、text causal self-attention、cross-attention 的 query 来源与 key/value 来源，并指出哪部分保证生成时不看未来词。

提示：跨注意力让文本 token 查询图像 token。

提交：带箭头模块图及 4 句说明。

来源：mit-6.7960-f24-lecture-08-slides@page:54

## 限制

- 本包仅依据课堂幻灯片；不展开第45–47页所引外部论文的实验细节。
- 第29页 QKV 公式按可见单查询示意概括；不同实现的矩阵方向约定可能不同。
- Fourier 位置码按第44页可见 sine 示例呈现，不外推未显示的 cosine 分量。
