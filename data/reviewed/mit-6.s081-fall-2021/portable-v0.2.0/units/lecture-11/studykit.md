# Scheduling I

> 课程：mit-6.s081-fall-2021 · 版本：fall-2021 · 单元：lecture-11

## 学习目标

- 能够说明线程抽象、抢占和调度器共同解决的多任务问题。
- 能够画出 xv6 用户线程到内核、调度器再到另一线程的状态保存链。
- 能够区分 trapframe、context、kernel stack 和进程状态各自保存的信息。
- 能够用原子状态转移解释 p->lock 跨 swtch 的必要性。
- 能够识别持锁 yield 的死锁路径并评价替代调度结构。

## 前置知识

- 中断与陷入：理解定时器中断可把控制权交回内核。
- 寄存器与调用栈：知道暂停执行需要保存 PC、寄存器和栈状态。
- 自旋锁：理解锁保护共享状态以及持锁等待可能造成死锁。

## 核心概念

### 线程

线程是独立的串行执行，包含栈、寄存器和 PC；多个线程向操作系统暴露可并发安排的工作。

来源：mit-6.s081-f21-lecture-11-material@page:4

### 抢占式调度

每核定时器周期性触发中断，让内核从不主动让出的线程夺回控制并切换执行。

来源：mit-6.s081-f21-lecture-11-material@page:11

### 调度状态机

Running 表示正在占用核心，Runnable 表示可运行但未占用核心，Sleeping 表示当前不能运行。

来源：mit-6.s081-f21-lecture-11-material@page:12

### trapframe 与 context

trapframe 保存用户寄存器，context 保存内核寄存器；它们支持用户/内核与内核/调度器两层切换。

来源：mit-6.s081-f21-lecture-11-material@page:15, mit-6.s081-f21-lecture-11-material@page:16, mit-6.s081-f21-lecture-11-material@page:19

### 每核调度器线程

每个核心有独立调度器栈和 context，使退出线程可以离开自己的内核栈并允许其他核心安全接管。

来源：mit-6.s081-f21-lecture-11-material@page:17, mit-6.s081-f21-lecture-11-material@page:18

### 跨 swtch 的 p->lock

把状态标记、context 保存和停止使用内核栈作为原子步骤，防止另一调度器过早运行同一进程。

来源：mit-6.s081-f21-lecture-11-material@page:21, mit-6.s081-f21-lecture-11-material@page:23

### 持锁 yield 死锁

若线程持普通锁让出 CPU，另一线程可能在关闭中断时自旋等待该锁，使原拥有者无法重新运行释放锁。

来源：mit-6.s081-f21-lecture-11-material@page:26, mit-6.s081-f21-lecture-11-material@page:27

## 学习顺序

1. 复习中断、寄存器、内核栈和锁。（20 分钟）
2. 学习线程抽象、设计空间与调度目标。（30 分钟）
3. 建立抢占和线程状态机。（25 分钟）
4. 逐步追踪 xv6 的 trapframe/context 切换链。（40 分钟）
5. 分析 p->lock 跨切换不变量与持锁 yield 死锁。（30 分钟）
6. 完成替代调度结构比较和综合自评。（35 分钟）

## 练习

### p1 · 基础

把三个线程分别分类为 Running、Runnable、Sleeping，并为每个状态写出能发生的下一次转换。

提示：先区分“能运行”和“正在运行”。

提交：状态表与转换触发条件。

来源：mit-6.s081-f21-lecture-11-material@page:11, mit-6.s081-f21-lecture-11-material@page:12

### p2 · 结构化推理

画出一次从用户线程 A 切换到用户线程 B 的四段路径，标注每段保存或恢复 trapframe/context 的动作。

提示：按用户→内核→调度器→内核→用户排列。

提交：带结构名和栈归属的序列图。

来源：mit-6.s081-f21-lecture-11-material@page:15, mit-6.s081-f21-lecture-11-material@page:16, mit-6.s081-f21-lecture-11-material@page:17, mit-6.s081-f21-lecture-11-material@page:19

### p3 · 不变量分析

假设在 swtch 前释放 p->lock，构造另一核心过早选择同一进程的交错，并指出可能被同时使用的状态。

提示：围绕 state、context 与 kernel stack 三步分析。

提交：交错表和被破坏的不变量。

来源：mit-6.s081-f21-lecture-11-material@page:21, mit-6.s081-f21-lecture-11-material@page:22, mit-6.s081-f21-lecture-11-material@page:23

### p4 · 诊断

重建“P1 持 L1 后 yield，P2 获取 L1”的死锁等待图，并提出两种避免方式。

提示：注意 P2 自旋时中断关闭。

提交：等待图、必要条件和修正策略。

来源：mit-6.s081-f21-lecture-11-material@page:26, mit-6.s081-f21-lecture-11-material@page:27

### p5 · 综合设计

比较 xv6 的每核调度器线程与“直接在进程内核栈上运行调度循环”两种设计，列出退出、跨核接管、栈所有权和性能权衡。

提示：先列必须保持的不变量，再评价性能。

提交：设计对照表与推荐条件。

来源：mit-6.s081-f21-lecture-11-material@page:17, mit-6.s081-f21-lecture-11-material@page:18, mit-6.s081-f21-lecture-11-material@page:25, mit-6.s081-f21-lecture-11-material@page:28, mit-6.s081-f21-lecture-11-material@page:29, mit-6.s081-f21-lecture-11-material@page:30

## 限制

- 本包聚焦讲义中的 xv6 调度机制，不把其简单扫描策略泛化为生产操作系统的调度策略。
- 第 20 页抽取文本极少，保留为视觉审核风险页但不作为内容证据。
- 讲义中的讨论问题在练习中改写为全新推理任务，不提供课程作业或实验答案。
