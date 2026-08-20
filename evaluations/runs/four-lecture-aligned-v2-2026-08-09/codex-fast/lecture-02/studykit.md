# Lecture 2：如何训练神经网络

> 课程：mit-6.7960-fall-2024 · 版本：fall-2024 · 单元：lecture-02

## 学习目标

- 比较梯度下降、SGD、动量以及梯度裁剪的更新信息和适用问题。
- 把多层网络表示成计算图，并按前向、反向、更新三个阶段解释训练。
- 用 Jacobian 维度检查链式法则，并推导通用层与线性层的局部反向规则。
- 处理 DAG 分支与参数共享中的梯度累加。
- 说明反向传播如何用于优化输入，并完成讲义中的一次数值反向传播。

## 前置知识

- 标量链式法则：能对复合函数求一阶导数
- 向量和矩阵乘法：能追踪向量、矩阵与转置的形状
- 神经网络基本元素：知道层、参数、激活和标量损失

## 核心概念

### 训练目标

样本损失汇总为目标函数，训练寻找使该目标较小的参数。

来源：mit-6.7960-f24-lecture-02-slides@page:5

公式：$$\theta^*=\arg\min_\theta\sum_{i=1}^N\mathcal L(f_\theta(x^{(i)}),y^{(i)})$$

### 梯度下降

一次更新沿目标函数对参数的负梯度方向移动，学习率控制步长。

来源：mit-6.7960-f24-lecture-02-slides@page:8

公式：$$\theta^{k+1}=\theta^k-\eta\nabla_\theta J(\theta^k)$$

### SGD 与批量

SGD 在数据子集上计算梯度；批大小为 1 时逐样本更新，批大小为 N 时是标准梯度下降。

来源：mit-6.7960-f24-lecture-02-slides@page:9

### 动量

动量使当前步倾向延续先前更新方向；动量强度是超参数，并非总能改善优化。

来源：mit-6.7960-f24-lecture-02-slides@page:10

公式：$$\theta^{t+1}=\theta^t-\eta\nabla f(\theta^t)-\alpha m^t$$

### 优化困难与裁剪

局部极小值、梯度消失、零梯度和梯度爆炸会妨碍优化；裁剪把过大梯度限制到阈值范围。

来源：mit-6.7960-f24-lecture-02-slides@page:22

公式：$$v=\nabla_\theta J(\theta^k)$$

### ReLU 的可微性

讲义用 ReLU 说明实践中的损失或节点不必处处光滑；ReLU 在零点以外可微。

来源：mit-6.7960-f24-lecture-02-slides@page:24

公式：$$\operatorname{ReLU}(z)=\max(0,z)$$

### 计算图

深度学习计算可表示为由可微函数节点构成的有向无环图。

来源：mit-6.7960-f24-lecture-02-slides@page:26

### 矩阵链式法则

复合向量函数的 Jacobian 按依赖顺序相乘；矩阵形状提供重要的正确性检查。

来源：mit-6.7960-f24-lecture-02-slides@page:34

公式：$$\frac{\partial z}{\partial x}=\frac{\partial z}{\partial u}\frac{\partial u}{\partial x}$$

### 反向传播

反向传播从损失端逆向传递共享导数项，避免为每个参数重复计算整条链。

来源：mit-6.7960-f24-lecture-02-slides@page:36

### 通用层反向规则

输出侧梯度与层对输入、参数的局部 Jacobian 相乘，得到输入侧梯度和参数梯度。

来源：mit-6.7960-f24-lecture-02-slides@page:41

公式：$$g_{in}=g_{out}L^x,\quad \partial J/\partial\theta=g_{out}L^\theta$$

### 批量梯度

平均损失的梯度等于各数据点损失梯度的平均。

来源：mit-6.7960-f24-lecture-02-slides@page:45

公式：$$\frac{\partial J}{\partial\theta}=\frac1N\sum_{i=1}^N\frac{\partial J_i(x^i,\theta)}{\partial\theta}$$

### 线性层

在讲义的行向量梯度约定下，线性层把输出梯度乘以权重矩阵以传回输入。

来源：mit-6.7960-f24-lecture-02-slides@page:46

公式：$$x_{out}=Wx_{in},\quad g_{in}=g_{out}W$$

### 分支与参数共享

一个变量影响多条下游路径时，反向贡献求和；共享参数的各次使用同样需要累加梯度。

来源：mit-6.7960-f24-lecture-02-slides@page:55

公式：$$\frac{\partial J}{\partial x}=\sum_i\frac{\partial J}{\partial x^i}$$

### 优化输入

反向传播也可计算标量代价对输入的梯度；单元可视化沿输入梯度上升并可加入正则项。

来源：mit-6.7960-f24-lecture-02-slides@page:66

公式：$$x^{k+1}=x^k+\eta\left.\frac{\partial(y_j(x)+\lambda R(x))}{\partial x}\right|_{x=x^k}$$

## 学习顺序

1. 阅读训练目标、GD、SGD 与动量，制作更新规则比较表。（25 分钟）
2. 分析损失地形中的局部极小、消失/零/爆炸梯度与裁剪。（20 分钟）
3. 把两层 MLP 重画为计算图，标出参数、激活和损失。（20 分钟）
4. 用矩阵形状复核向量链式法则。（25 分钟）
5. 追踪通用层的 forward、backward、update，并说明共享计算。（30 分钟）
6. 推导批量、线性层、DAG 分支和共享参数的反向规则。（25 分钟）
7. 比较优化参数和优化输入，解释单元可视化目标。（15 分钟）
8. 独立完成讲义第 72 页的一次反向传播，再对照第 75–80 页自检。（20 分钟）

## 练习

### p1 · 基础

比较 batch=1、一般小批量与 batch=N 时一次更新使用的数据。

提示：从第 9 页的两个边界情形开始。

提交：三行比较表。

来源：mit-6.7960-f24-lecture-02-slides@page:9

### p2 · 基础

为第 29 页计算图列出一次训练迭代的 forward、backward、update 顺序。

提示：先得到标量损失，再逆序传播。

提交：有向流程图。

来源：mit-6.7960-f24-lecture-02-slides@page:29, mit-6.7960-f24-lecture-02-slides@page:42

### p3 · 进阶

若 x、u、z 的长度分别为 n、p、m，写出链式法则中两个 Jacobian 及乘积的形状。

提示：参考第 34 页标注。

提交：三项形状推导。

来源：mit-6.7960-f24-lecture-02-slides@page:34

### p4 · 进阶

对 x_out=W x_in 画出输入梯度与权重梯度所需的局部量并标形状。

提示：沿用讲义的行向量 g 约定。

提交：局部反向传播卡片。

来源：mit-6.7960-f24-lecture-02-slides@page:46, mit-6.7960-f24-lecture-02-slides@page:48

### p5 · 挑战

变量 x 分支到两条路径时推导回到 x 的梯度，并类比共享参数。

提示：每条路径贡献都要保留。

提交：两条求和规则和解释。

来源：mit-6.7960-f24-lecture-02-slides@page:53, mit-6.7960-f24-lecture-02-slides@page:55

### p6 · 挑战

遮住讲义答案，只用第 72 页数据完成一次反向传播；报告中间激活、两个权重梯度与更新后权重。

提示：先按第 75 页模块化，再逆序应用链式法则。

提交：完整计算记录，注明舍入。

来源：mit-6.7960-f24-lecture-02-slides@page:72, mit-6.7960-f24-lecture-02-slides@page:75, mit-6.7960-f24-lecture-02-slides@page:80

## 限制

- 仅使用固定 lecture-02 chunks 与原始本地 PDF。
- 第 48、72、76、80 页采用“正增量配合负学习率”的符号约定，本包保留讲义约定。
- 低文本过渡页不承担实质主张；外链内容未被访问或用作证据。
