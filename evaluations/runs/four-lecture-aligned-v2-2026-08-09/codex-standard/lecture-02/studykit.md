# Lecture 2：如何训练神经网络

> 课程：mit-6.7960-fall-2024 · 版本：fall-2024 · 单元：lecture-02

## 学习目标

- 从目标函数出发，比较全批量梯度下降、SGD、动量和梯度裁剪。
- 识别损失地形中的局部极小值、梯度消失、零梯度和梯度爆炸，并解释它们为何阻碍优化。
- 把多层网络表达为计算图，使用 Jacobian 链式法则说明前向传播和反向传播。
- 推导通用层、线性层、数据批次、DAG 分支和参数共享的反向规则。
- 区分优化模型参数与优化输入，并独立完成讲义给出的数值反向传播案例。

## 前置知识

- 一阶微积分：能应用标量链式法则
- 线性代数：能完成矩阵乘法并检查维度
- 神经网络组件：理解层、参数、激活、预测和标量损失

## 核心概念

### 经验损失目标

训练目标把每个样本经过模型后的损失汇总，并在参数空间中寻找极小值。

来源：mit-6.7960-f24-lecture-02-slides@page:5

公式：$$\theta^*=\arg\min_\theta\sum_{i=1}^{N}\mathcal L(f_\theta(x^{(i)}),y^{(i)})$$

### 梯度下降更新

梯度下降使用一阶导数；每步从当前参数沿负梯度方向移动，η 是学习率。

来源：mit-6.7960-f24-lecture-02-slides@page:8

公式：$$\theta^{k+1}=\theta^k-\eta\nabla_\theta J(\theta^k)$$

### SGD 与 batch

SGD 用一个数据子集估计总体梯度。batch=1 时逐样本更新，batch=N 时等于标准梯度下降；小批量更快但方向噪声更大。

来源：mit-6.7960-f24-lecture-02-slides@page:9

### 动量

动量把上一更新方向带入当前步；其强度是超参数，讲义明确说明它可能有帮助也可能有害。

来源：mit-6.7960-f24-lecture-02-slides@page:10

公式：$$\theta^{t+1}=\theta^t-\eta\nabla f(\theta^t)-\alpha m^t$$

### 优化故障模式

局部极小值影响终点；梯度消失或为零使进展停滞；梯度爆炸导致不稳定和越界。

来源：mit-6.7960-f24-lecture-02-slides@page:14

### 梯度裁剪

若梯度分量超过阈值 m，讲义用 clip 把它限制在区间内，以缓解爆炸梯度造成的不稳定。

来源：mit-6.7960-f24-lecture-02-slides@page:22

公式：$$\theta^{k+1}=\theta^k-\eta[\operatorname{clip}(v_1,-m,m),\ldots,\operatorname{clip}(v_M,-m,m)]^\top$$

### ReLU 与可微要求

ReLU 连续但在零点并非通常意义下可微，也不处处光滑；讲义以它说明实用节点不必满足“处处光滑”。

来源：mit-6.7960-f24-lecture-02-slides@page:24

公式：$$\operatorname{ReLU}(z)=\max(0,z)$$

### 计算图

深度学习主要使用由可微函数节点组成的有向无环计算图；多层网络的前向过程沿依赖方向计算到标量损失。

来源：mit-6.7960-f24-lecture-02-slides@page:26

### Jacobian 链式法则

讲义把标量对列向量的导数写作行向量、向量对向量的导数写作 Jacobian；复合映射按维度匹配的顺序相乘。

来源：mit-6.7960-f24-lecture-02-slides@page:34

公式：$$\frac{\partial z}{\partial x}=\frac{\partial z}{\partial u}\frac{\partial u}{\partial x}$$

### 反向传播复用

不同参数的链式展开共享靠近损失端的导数项；反向传播只计算共享项一次，再从输出向输入传播。

来源：mit-6.7960-f24-lecture-02-slides@page:36

### 通用层局部反向

对层 x_out=f(x_in,θ)，输出侧梯度分别与输入 Jacobian 和参数 Jacobian 组合，得到输入梯度与参数梯度。

来源：mit-6.7960-f24-lecture-02-slides@page:41

公式：$$g_{in}=g_{out}L^x,\qquad \frac{\partial J}{\partial\theta}=g_{out}L^\theta$$

### 批次平均梯度

平均数据损失对参数的梯度，就是各数据点损失梯度的平均。

来源：mit-6.7960-f24-lecture-02-slides@page:45

公式：$$\frac{\partial J}{\partial\theta}=\frac1N\sum_{i=1}^N\frac{\partial J_i(x^i,\theta)}{\partial\theta}$$

### 线性层反向

对 x_out=W x_in，在讲义的行梯度约定下，输入梯度是 g_out W；权重梯度由输入列向量与输出侧行梯度组成外积。

来源：mit-6.7960-f24-lecture-02-slides@page:46

公式：$$x_{out}=Wx_{in},\qquad g_{in}=g_{out}W$$

### DAG 分支与共享参数

同一上游量沿多个分支影响损失时，各路径梯度在回到该量时相加；同一参数多次使用时也汇总全部使用点的贡献。

来源：mit-6.7960-f24-lecture-02-slides@page:55

公式：$$\frac{\partial J}{\partial x}=\sum_i\frac{\partial J}{\partial x^i}$$

### 对输入求梯度

反向传播可对计算图中的节点或边相对于任意标量代价求导。单元可视化固定网络，沿输入梯度上升并加入正则项。

来源：mit-6.7960-f24-lecture-02-slides@page:66

公式：$$x^{k+1}=x^k+\eta\left.\frac{\partial(y_j(x)+\lambda R(x))}{\partial x}\right|_{x=x^k}$$

## 学习顺序

1. 从目标函数出发，建立 GD、SGD 和动量的更新比较表。（25 分钟）
2. 逐图判断可微性和优化难点，归纳梯度故障与裁剪的作用边界。（20 分钟）
3. 把 MLP 改写为带参数、激活和损失的计算图。（20 分钟）
4. 按讲义约定复习向量导数和 Jacobian，并用形状检查链式法则。（25 分钟）
5. 沿链式图执行 forward、backward、update，说明反向传播的共享计算。（30 分钟）
6. 推导批次平均、线性层、DAG 分支和参数共享规则。（25 分钟）
7. 比较优化参数与优化输入，解释单元可视化的目标与正则项。（15 分钟）
8. 独立完成数值反向传播，再逐页对照讲义解答检查中间量和更新。（20 分钟）

## 练习

### ex-1 · 基础

分别说明 batch=1、小批量和 batch=N 时一次 SGD 更新使用什么数据。

提示：先找第 9 页明确给出的两个边界。

提交：三行比较表。

来源：mit-6.7960-f24-lecture-02-slides@page:9

### ex-2 · 基础

为第 29 页的链式图写出一次训练迭代的前向、反向、更新顺序，并说明为什么不能先更新。

提示：参数梯度依赖已计算的损失和激活。

提交：步骤图和两句解释。

来源：mit-6.7960-f24-lecture-02-slides@page:29, mit-6.7960-f24-lecture-02-slides@page:42

### ex-3 · 进阶

设 |x|=n、|u|=p、|z|=m，标出 ∂z/∂u、∂u/∂x 和乘积的形状。

提示：使用第 34 页的 Jacobian 排布。

提交：带形状的链式法则。

来源：mit-6.7960-f24-lecture-02-slides@page:34

### ex-4 · 进阶

对 x_out=W x_in，推导 g_in，并用分量关系解释权重梯度为何是外积形状。

提示：先使用 ∂x_out_i/∂x_in_j=W_ij。

提交：公式、分量推导、形状表。

来源：mit-6.7960-f24-lecture-02-slides@page:46, mit-6.7960-f24-lecture-02-slides@page:48

### ex-5 · 挑战

一个变量分成两条路径，又有同一参数在三处使用。分别写回到变量与参数的梯度汇总规则。

提示：把每个下游使用点视为独立贡献，再相加。

提交：两条求和公式与路径图。

来源：mit-6.7960-f24-lecture-02-slides@page:53, mit-6.7960-f24-lecture-02-slides@page:55

### ex-6 · 挑战

仅看第 72 页，完成一次前向和反向传播，给出两个权重梯度及更新后权重；完成后再用第 75–80 页核对。

提示：先重画成线性—tanh—线性—平方损失模块。

提交：完整计算表，注明矩阵形状和舍入。

来源：mit-6.7960-f24-lecture-02-slides@page:72, mit-6.7960-f24-lecture-02-slides@page:75, mit-6.7960-f24-lecture-02-slides@page:80

## 限制

- 仅依据指定 chunks 和本地原始 PDF；没有访问讲义中的外部链接。
- 第 48、72、76、80 页用正增量写更新，并在数值题中令 η=-0.2；本包保留该符号约定。
- 第 31、35、74 页是低文本过渡页，不承担实质性结论。
