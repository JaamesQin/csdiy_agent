# MIT 6.7960 Lecture 3：近似理论

> 课程：mit-6.7960-fall-2024 · 版本：fall-2024 · 单元：lecture-03

## 学习目标

- 区分近似、优化与泛化，并准确限定本讲结论只回答哪一块拼图。
- 写出一维与多维 Lipschitz 条件、RMS 范数，以及三层逼近定理中的误差与规模。
- 复原“矩形条—超矩形—ReLU 阈值—线性组合”的构造性证明链。
- 用分段线性函数与 kink 计数推导深度分离，并核对浅网宽度的数量级。
- 解释为什么 UFA 与深度分离不能单独决定实践中的宽度/深度选择。

## 前置知识

- 单变量与多变量函数、绝对值与求和记号：能读取函数域/值域和基本不等式；本包会在原页公式中复习所需记号。
- 积分误差与分段线性函数：能把面积理解为积分，并识别斜率发生变化的位置；无需预先掌握证明。
- ReLU 与前馈网络的层/宽度概念：知道 ReLU 是逐点非线性，并能按层追踪线性组合；本讲用图示和 PWL 性补足直觉。

## 核心概念

### 机器学习三块拼图

近似问模型族中是否存在能拟合的网络；优化问能否找到它；泛化问它在未见数据上是否表现良好。本讲主要回答第一问，因此后续存在性定理不能自动推出可训练或可泛化。

来源：mit6-7960-f24-lec3-d7db2ac9fd@page:4, mit6-7960-f24-lec3-d7db2ac9fd@page:34

### L-Lipschitz 函数与 RMS 范数

一维条件用 L 控制输入变化引起的函数变化；多维版本把输入变化用 RMS 范数度量。这里的直觉是函数变化速度受到统一上界约束。

来源：mit6-7960-f24-lec3-d7db2ac9fd@page:8, mit6-7960-f24-lec3-d7db2ac9fd@page:9

公式：$$\|x\|_{\mathrm{RMS}}=\sqrt{\frac{1}{d}\sum_{i=1}^{d}x_i^2},\qquad |g(x+\Delta x)-g(x)|\le L\|\Delta x\|_{\mathrm{RMS}}$$

### 三层 ReLU 逼近定理

对 [0,1]^d 上任意 L-Lipschitz 函数与任意 epsilon>0，幻灯片给出一个三层 ReLU 网络，其单元数为 N=4d(L/epsilon)^d，并使积分绝对误差小于 2epsilon。指数来自 (L/epsilon)^d，而 4d 是线性前因子。

来源：mit6-7960-f24-lec3-d7db2ac9fd@page:10

公式：$$N=4d\left(\frac{L}{\varepsilon}\right)^d,\qquad \int_{[0,1]^d}|f(x)-g(x)|\,dx<2\varepsilon$$

### 矩形条误差

在一维中把区间分成 N 个宽 1/N 的条。Lipschitz 性把每条的误差帽控制为三角形；N 条相加得到 L/(2N)，所以要达到 epsilon 误差，只需令 N 至少为 L/(2epsilon)（幻灯片后续常忽略常数讨论数量级）。

来源：mit6-7960-f24-lec3-d7db2ac9fd@page:12, mit6-7960-f24-lec3-d7db2ac9fd@page:13

公式：$$\int|f(x)-g(x)|\,dx\le N\cdot\frac12\cdot\frac1N\cdot\frac LN=\frac{L}{2N}$$

### 高维超矩形与维度灾难

高维把矩形条替换为边长 1/N^(1/d) 的超矩形。幻灯片给出的 epsilon 级误差需要 (L/epsilon)^d 个超矩形，因此需求随维度指数增长。

来源：mit6-7960-f24-lec3-d7db2ac9fd@page:14, mit6-7960-f24-lec3-d7db2ac9fd@page:18

公式：$$N=\left(\frac{L}{\varepsilon}\right)^d$$

### ReLU 超矩形阈值

每个坐标先由一维近似矩形给出是否“开启”的值；把 d 个值相加并在 d-1 处阈值化，只有各坐标矩形同时开启时才保留。再对平移后的超矩形做线性组合以逼近曲面。

来源：mit6-7960-f24-lec3-d7db2ac9fd@page:16, mit6-7960-f24-lec3-d7db2ac9fd@page:17

公式：$$h_c(x)=\operatorname{ReLU}\!\left(\sum_{i=1}^{d}f_c(x_i)-(d-1)\right)$$

### UFA 不等于学习成功

幻灯片指出矩形表示在训练点处可能只学到局部矩形，权重衰减还会压低其他矩形，因而不泛化；同时 Fourier 级数、多项式和 Python 程序空间都可作为 UFA 例子，但并非因此就是常用学习模型。

来源：mit6-7960-f24-lec3-d7db2ac9fd@page:19, mit6-7960-f24-lec3-d7db2ac9fd@page:21

### PWL、kink 与层间上界

kink 是梯度改变的位置。ReLU 是 PWL，PWL 对加法、复合与数乘封闭，所以 ReLU 网络也是 PWL。加宽时 kinks 至多相加；施加 ReLU 时每个线性段至多被零点再切一次，因此层间至多乘 2n。

来源：mit6-7960-f24-lec3-d7db2ac9fd@page:27, mit6-7960-f24-lec3-d7db2ac9fd@page:28, mit6-7960-f24-lec3-d7db2ac9fd@page:29, mit6-7960-f24-lec3-d7db2ac9fd@page:30, mit6-7960-f24-lec3-d7db2ac9fd@page:31

公式：$$\operatorname{KINKS}_{\ell+1}\le2n\,\operatorname{KINKS}_{\ell},\qquad \operatorname{KINKS}_L\le(2n)^L$$

### tent map 深度分离

页面 32 的 tent map 每自复合一次就把线性区域数翻倍。复合 500 次得到 1000 层、宽 2 的网络和 2^500-1 个 kinks；若三层网络要达到相同数量，页面 33 给出的宽度约为 7×10^49。该结果仍只说明近似表达效率。

来源：mit6-7960-f24-lec3-d7db2ac9fd@page:32, mit6-7960-f24-lec3-d7db2ac9fd@page:33, mit6-7960-f24-lec3-d7db2ac9fd@page:34

公式：$$n\ge\frac12(2^{500}-1)^{1/3}\approx7\times10^{49}$$

### 实践宽深比与混杂因素

宽度便于并行而深度是顺序的；深度可能导致复合问题，但也可能带来表达效率。缩放律结果还会受学习率等训练流水线细节影响，所以最优宽深比不能只由近似定理决定。

来源：mit6-7960-f24-lec3-d7db2ac9fd@page:24, mit6-7960-f24-lec3-d7db2ac9fd@page:37, mit6-7960-f24-lec3-d7db2ac9fd@page:39, mit6-7960-f24-lec3-d7db2ac9fd@page:41

## 学习顺序

1. 建立三块拼图与本讲边界；完成 ex-1 的先验分类。（15 分钟）
2. 形式化函数族、网络族、误差与 Lipschitz/RMS 条件。（20 分钟）
3. 精读三层定理，逐符号核对网络规模与积分误差。（30 分钟）
4. 按矩形条、高维超矩形、ReLU 阈值、线性组合重建证明。（35 分钟）
5. 分析矩形构造的训练/泛化缺陷与 UFA 的非充分性。（15 分钟）
6. 从 PWL 闭包和 kink 操作推导层间递推与总上界。（30 分钟）
7. 分析 tent map 迭代与深浅网络数量分离，完成数值审计。（20 分钟）
8. 用混杂因素和总结页写宽深决策边界备忘录。（15 分钟）

## 练习

### ex-1 · 基础

把下列问题分别归入 approximation、optimization、generalization：(a) 模型族中是否存在拟合训练数据的网络；(b) 若存在，能否找到它；(c) 在未见数据上是否表现良好。再说明本讲主要回答哪一项。

提示：逐条对应页面 4 的三个问句，不要把“存在”写成“能训练出来”。

提交：三行分类表，以及一句本讲范围说明。

来源：mit6-7960-f24-lec3-d7db2ac9fd@page:4

### ex-2 · 基础

从幻灯片复写一维 Lipschitz 条件、多维 Lipschitz 条件和 RMS 范数；逐一解释 L、Delta x、d 与求和下标的含义。

提示：一维见页面 8，多维与 RMS 定义见页面 9。

提交：三条公式和四项符号解释。

来源：mit6-7960-f24-lec3-d7db2ac9fd@page:8, mit6-7960-f24-lec3-d7db2ac9fd@page:9

### ex-3 · 中等

令 d=3、L/epsilon=10。依据页面 10 的公式计算三层网络单元数 N，并指出哪个因子造成对 d 的指数依赖。最后解释为什么不能把 4d 写成 4^d。

提示：先代入 N=4d(L/epsilon)^d，再分别标记前因子与幂。

提交：带代入步骤的计算、指数依赖说明和误读纠正。

来源：mit6-7960-f24-lec3-d7db2ac9fd@page:10, mit6-7960-f24-lec3-d7db2ac9fd@page:18

### ex-4 · 中等

先用每条宽 1/N、高度帽 L/N 的三角形推导 N 条矩形条的总误差 L/(2N)。再把证明步骤排序：一维矩形条、推广到高维超矩形、把 d 个一维矩形相加并在 d-1 阈值化、线性组合平移后的超矩形。

提示：单条面积是 1/2×底×高；高维阈值只有全部坐标都“开”时才通过。

提交：误差推导、达到 epsilon 的 N 下界，以及四步证明链。

来源：mit6-7960-f24-lec3-d7db2ac9fd@page:12, mit6-7960-f24-lec3-d7db2ac9fd@page:13, mit6-7960-f24-lec3-d7db2ac9fd@page:14, mit6-7960-f24-lec3-d7db2ac9fd@page:16, mit6-7960-f24-lec3-d7db2ac9fd@page:17

### ex-5 · 中等

解释为什么 ReLU 网络是 PWL；然后分别用“加法至多相加 kinks”和“ReLU 至多把每个线性段再切一次”推导 KINKS_{l+1}<=2n KINKS_l，最后迭代得到 KINKS_L<=(2n)^L。

提示：先列出 PWL 对加法、复合、数乘的封闭性，再分别处理宽度和非线性。

提交：一段封闭性证明、两步层间推导和最终上界。

来源：mit6-7960-f24-lec3-d7db2ac9fd@page:27, mit6-7960-f24-lec3-d7db2ac9fd@page:28, mit6-7960-f24-lec3-d7db2ac9fd@page:29, mit6-7960-f24-lec3-d7db2ac9fd@page:30, mit6-7960-f24-lec3-d7db2ac9fd@page:31

### ex-6 · 综合

页面 32 的 tent map 自复合 500 次得到 2^500-1 个 kinks 与一个 1000 层、宽 2 的网络。用三层上界反解浅网宽度 n，并检查为什么数量级是约 7×10^49，而不是 10^149。

提示：从 (2n)^3 >= 2^500-1 解 n；注意最后取的是立方根。

提交：完整不等式变形、科学计数法估算和对错误数量级的诊断。

来源：mit6-7960-f24-lec3-d7db2ac9fd@page:32, mit6-7960-f24-lec3-d7db2ac9fd@page:33

### ex-7 · 综合

写一份不超过 250 字的“宽还是深”决策备忘录：必须分别说明 UFA、深度分离、矩形构造的训练缺陷和训练流水线混杂因素能与不能告诉你什么，并给出下一步实验需要控制的变量类别。

提示：用 approximation/optimization/generalization 三栏组织，不要把表达能力结论当成训练或泛化结论。

提交：带三栏边界和实验控制项的短备忘录。

来源：mit6-7960-f24-lec3-d7db2ac9fd@page:19, mit6-7960-f24-lec3-d7db2ac9fd@page:21, mit6-7960-f24-lec3-d7db2ac9fd@page:24, mit6-7960-f24-lec3-d7db2ac9fd@page:34, mit6-7960-f24-lec3-d7db2ac9fd@page:37, mit6-7960-f24-lec3-d7db2ac9fd@page:39, mit6-7960-f24-lec3-d7db2ac9fd@page:41

## 限制

- PDF 原生文本层噪声较大；本包以逐页可见渲染核验为准。
- 第 15、17 页的一维矩形子网络含有难以无歧义辨认的手写上标/向量项，因此不提供其精确 LaTeX；仅保留可见且清楚的构造意图与高维阈值公式。
- 第 20、35、38、39 页提到的外部论文没有在本次离线构建中查阅；本包不把幻灯片的一句简介扩写为完整外部定理。
- 第 22、36、40 页是章节分隔页，第 23 页是宽深示意图；其低文本提取量不是缺页。
- 本包只覆盖 Lecture 3，不延伸到 Lecture 1-2、4-8，也不把第 42 页的下讲预告发展为本讲内容。
