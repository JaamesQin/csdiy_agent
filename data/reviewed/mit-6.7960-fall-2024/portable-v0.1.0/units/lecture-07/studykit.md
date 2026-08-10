# Lecture 7：优化的缩放规则

> 课程：mit-6.7960-fall-2024 · 版本：fall-2024 · 单元：lecture-07

## 学习目标

- 把监督学习训练写成经验损失的全批次最小化问题，并说清本讲的范围边界。
- 从二阶 Taylor 模型推出 Newton 步，并辨认 Hessian 计算与存储的尺度障碍。
- 解释复合目标的 Gauss–Newton 分解、平方损失下的近似步，以及忽略模型曲率的风险。
- 用所选范数及其对偶范数统一解释梯度下降、符号梯度下降和一般最速下降。
- 计算并比较谱范数与 RMS–RMS 算子范数，说明它们怎样量化矩阵对向量尺度的放大。
- 把宽度缩放规则、深度残差参数化与模块化理论区分为启发式、研究问题和理论构建提案。

## 前置知识

- 多元微积分：能读梯度、Hessian、Jacobian 与二阶 Taylor 展开；本单元会复核符号但不从头教授求导。
- 线性代数：理解矩阵乘法、奇异值、向量二范数和可逆矩阵。
- 神经网络训练记号：能区分模型 f(x;w)、目标 y、误差函数与经验损失。

## 核心概念

### 经验损失最小化

幻灯片把神经网络预测写成 f(x;w)，以误差函数 ℓ 比较预测与目标，并对 N 个训练样本取平均得到损失；目标是寻找使该损失最小的 w。本讲随后明确只研究 full-batch optimization。

来源：mit6-7960-f24-lec7-d9137f6191@page:4, mit6-7960-f24-lec7-d9137f6191@page:6

公式：$$\mathcal{L}(w)=\frac{1}{N}\sum_{i=1}^{N}\ell\!\left(f(x^{(i)};w),y^{(i)}\right)$$

### 二阶 Taylor 局部模型

多种经典优化方法以损失在 w 附近的 Taylor 展开为共同起点；g 是 d 维梯度，H 是 d×d Hessian。后续方法的差别来自保留的阶数、曲率近似和给更新施加的几何。

来源：mit6-7960-f24-lec7-d9137f6191@page:10

公式：$$\mathcal{L}(w+\Delta w)=\mathcal{L}(w)+g^T\Delta w+\frac{1}{2}\Delta w^T H\Delta w+\cdots$$

### Newton 步

最小化二阶局部模型并令其对 Δw 的导数为零，得到用逆 Hessian 预条件梯度的 Newton 步。幻灯片同时提醒：方法可能走向局部极大值，且 d 个参数产生 d×d Hessian，即使小网络也可能过于昂贵。

来源：mit6-7960-f24-lec7-d9137f6191@page:11, mit6-7960-f24-lec7-d9137f6191@page:12

公式：$$g+H\Delta w=0\quad\Longrightarrow\quad\Delta w=-H^{-1}g$$

### Gauss–Newton 分解与近似

对复合目标 L=ℓ∘f，Hessian 可分为由误差函数曲率经模型 Jacobian 拉回的项，以及由模型自身二阶导数产生的项。平方损失使误差曲率为单位阵；忽略模型曲率便得到幻灯片所示的 Gauss–Newton 步。其代价是额外求导，而且忽略模型曲率是否安全并无保证。

来源：mit6-7960-f24-lec7-d9137f6191@page:13, mit6-7960-f24-lec7-d9137f6191@page:14, mit6-7960-f24-lec7-d9137f6191@page:15

公式：$$H=J_f^T H_{\ell}J_f+\sum_k\frac{\partial\ell}{\partial f_k}\nabla_w^2 f_k;\qquad \Delta w_{GN}=-(J_f^TJ_f)^{-1}g\;\text{（平方损失）}$$

### 一般最速下降

把二阶非线性部分换成 λ/2·||Δw||² 后，更新取决于所选范数。二范数给出普通梯度下降，无穷范数给出符号梯度下降；一般情形的步长由梯度的对偶范数决定，方向是在单位范数球上使 gᵀt 最大的方向的反向。

来源：mit6-7960-f24-lec7-d9137f6191@page:16, mit6-7960-f24-lec7-d9137f6191@page:17, mit6-7960-f24-lec7-d9137f6191@page:18, mit6-7960-f24-lec7-d9137f6191@page:19

公式：$$\arg\min_{\Delta w}\left[g^T\Delta w+\frac{\lambda}{2}\lVert\Delta w\rVert^2\right]=-\frac{\lVert g\rVert_*}{\lambda}\arg\max_{\lVert t\rVert=1}g^Tt$$

### 谱范数

谱范数回答矩阵最多能把向量的欧氏范数放大多少；幻灯片指出它等于最大奇异值。这提供了从神经计算转向矩阵尺度控制的接口。

来源：mit6-7960-f24-lec7-d9137f6191@page:21, mit6-7960-f24-lec7-d9137f6191@page:23

公式：$$\lVert M\rVert_*=\max_{v\ne0}\frac{\lVert Mv\rVert_2}{\lVert v\rVert_2}=\sigma_{\max}(M)$$

### RMS–RMS 算子范数

向量 RMS 范数把二范数除以维数平方根。对应的 RMS–RMS 算子范数衡量矩阵对输入 RMS 的最大放大；对从 d_in 维映射到 d_out 维的矩阵，它与谱范数相差 √(d_in/d_out)。

来源：mit6-7960-f24-lec7-d9137f6191@page:24

公式：$$\lVert v\rVert_{RMS}=\frac{1}{\sqrt d}\lVert v\rVert_2,\qquad \lVert M\rVert_{RMS\to RMS}=\sqrt{\frac{d_{in}}{d_{out}}}\lVert M\rVert_*$$

### 谱控制的宽度缩放启发式

幻灯片把“宽度改变时移除最优学习率漂移”明确标为 claim，并建议每层初始化满足 ||W_l||_{RMS→RMS}≈1、更新满足 ||ΔW_l||_{RMS→RMS}≈1。本 StudyKit 将它保留为讲者给出的启发式主张，而不是已证明的普适定理。

来源：mit6-7960-f24-lec7-d9137f6191@page:25

公式：$$\lVert W_l\rVert_{RMS\to RMS}\sim1,\qquad\lVert\Delta W_l\rVert_{RMS\to RMS}\sim1$$

### 深度缩放的残差参数化

深度缩放页以“the trick seems to be”作限定，回顾 (1+x/L)^L 的指数极限，并建议把残差块写成 x↦x+(1/L)·layer(x)；页末同时标注仍需更多研究。因此这里把它当作研究启发，而非性能保证。

来源：mit6-7960-f24-lec7-d9137f6191@page:26

公式：$$\lim_{L\to\infty}\left(1+\frac{x}{L}\right)^L=e^x,\qquad x\mapsto x+\frac{1}{L}\operatorname{layer}(x)$$

### 模块化优化理论提案

讲者明确提醒“my research, so be skeptical”。提案是让优化理论随神经网络结构一起构建：每个原子模块提供 forward、backward 和 norm，再为模块复合写组合规则；前向与反向可用复合和链式法则，而范数如何组合仍是开放问题。

来源：mit6-7960-f24-lec7-d9137f6191@page:27, mit6-7960-f24-lec7-d9137f6191@page:28, mit6-7960-f24-lec7-d9137f6191@page:29, mit6-7960-f24-lec7-d9137f6191@page:30

## 学习顺序

1. 阅读问题形式与 full-batch 边界，自己重写符号表。（15 分钟）
2. 从二阶 Taylor 模型手推 Newton 步并做维度检查。（25 分钟）
3. 列出 Newton 法的计算与优化风险。（15 分钟）
4. 用链式法则标注 Gauss–Newton 分解中两类曲率。（25 分钟）
5. 比较 L2、L∞ 与一般范数下的最速下降更新。（30 分钟）
6. 验证谱范数与 RMS–RMS 范数定义和维度换算。（30 分钟）
7. 把宽度、深度缩放陈述按“定义/启发式/开放问题”分类。（20 分钟）
8. 设计一个原子模块接口和一次复合规则，完成总复盘。（20 分钟）

## 练习

### p1-objective · 基础

用你自己的符号写出 N 个训练样本的经验损失，并逐项说明 f、ℓ、w、x^(i)、y^(i) 的角色；最后加一句说明本讲研究哪种批处理范围。

提示：先画出“输入—模型—预测—误差”的箭头，再把样本索引放进平均式。

提交：一条带维度/角色注释的损失公式和一句范围声明。

来源：mit6-7960-f24-lec7-d9137f6191@page:4, mit6-7960-f24-lec7-d9137f6191@page:6

### p2-newton · 基础推导

从二阶 Taylor 局部模型出发，对 Δw 求导并写出驻点方程；再用一句话解释为什么参数数目 d 会造成计算问题。

提示：常数项消失，线性项给 g，二次型给 HΔw；先不要直接写最终更新。

提交：不超过六行的推导和一条 d×d 尺度说明。

来源：mit6-7960-f24-lec7-d9137f6191@page:11, mit6-7960-f24-lec7-d9137f6191@page:12

### p3-gn-ledger · 中等

为复合目标 L=ℓ∘f 做一张“两类曲率账本”：每行写曲率来源、对应 Hessian 项、Gauss–Newton 是否保留，以及舍弃它可能带来的问题。

提示：区分误差函数 ℓ 的曲率和模型 f 的曲率；平方损失只简化前者。

提交：四列两行的曲率账本，外加一条限制说明。

来源：mit6-7960-f24-lec7-d9137f6191@page:13, mit6-7960-f24-lec7-d9137f6191@page:14, mit6-7960-f24-lec7-d9137f6191@page:15

### p4-steepest-geometry · 中等推导

取一个二维非零梯度 g，自选具体数值。分别画出 L2 与 L∞ 单位球，标出使 g^Tt 最大的 t，并说明对应下降更新为何分别呈现梯度方向与符号方向。

提示：先求线性函数在单位球边界上的支撑点，再取反向；把步长和方向分开讨论。

提交：两幅小图、两个方向表达式和三句比较。

来源：mit6-7960-f24-lec7-d9137f6191@page:17, mit6-7960-f24-lec7-d9137f6191@page:18, mit6-7960-f24-lec7-d9137f6191@page:19

### p5-rms-dimensions · 进阶

设 M:R^{d_in}→R^{d_out}。仅由 RMS 向量范数和谱范数定义，推导 ||M||_{RMS→RMS} 与 ||M||_* 的维度因子；随后用 d_in=d_out 做一次一致性检查。

提示：把分子与分母中的 RMS 都替换成二范数除以相应维数平方根，再把常数提出最大化。

提交：逐步换元推导、最终比例式和一个方阵特例检查。

来源：mit6-7960-f24-lec7-d9137f6191@page:23, mit6-7960-f24-lec7-d9137f6191@page:24

### p6-claim-calibration · 进阶审辨

把下列三类陈述各写一个“可安全保留版本”：谱范数定义、宽度缩放规则、深度残差参数化。每条标注为定义/讲者 claim/研究启发，并指出不能从幻灯片推出什么。

提示：留意第 25 页的“Claim”、第 26 页的“seems”和“needs more research”；不要读取第三方图中的曲线作定量结论。

提交：三行证据等级表，每行含保留陈述、限定词、不可推出项和页码。

来源：mit6-7960-f24-lec7-d9137f6191@page:23, mit6-7960-f24-lec7-d9137f6191@page:25, mit6-7960-f24-lec7-d9137f6191@page:26

### p7-module-design · 综合设计

为两个可复合的原子模块 M1、M2 设计最小接口：列出 forward、backward、norm 的输入输出，再写 M=M2∘M1 的前向和反向组合规则。最后把“组合后的 norm 如何定义”保留为一个带约束的开放问题。

提示：前向用函数复合，反向用链式法则；不要凭空给出幻灯片没有证明的 norm 组合定理。

提交：接口表、两条组合伪代码和一个开放问题陈述。

来源：mit6-7960-f24-lec7-d9137f6191@page:27, mit6-7960-f24-lec7-d9137f6191@page:29, mit6-7960-f24-lec7-d9137f6191@page:30

## 限制

- 仅依据 32 页讲义，没有课堂音频或讲稿；手写数学主要依靠渲染页核对。
- 第 7、25、26 页第三方图片未复用，且未保留只能从图片或叠加/隐藏文本得到的主张。
- 第 14 页唯一 U+FFFD 对应可见 emoji，不影响公式；仍记录为摄取修复痕迹。
- 本讲只研究 full-batch；不得把结论自动外推到 mini-batch 或随机优化。
- 第 25 页宽度规则是 claim，第 26 页深度规则仍需研究，第 27—30 页是讲者明确要求保持怀疑的个人研究提案。
