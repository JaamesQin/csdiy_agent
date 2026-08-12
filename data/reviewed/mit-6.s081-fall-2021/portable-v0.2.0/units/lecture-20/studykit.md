# Kernels and high-level languages

> 课程：mit-6.s081-fall-2021 · 版本：fall-2021 · 单元：lecture-20

## 学习目标

- 能够把 C 与 HLL 的内核开发优势和成本分解为安全、控制、性能、内存和可编程性维度。
- 能够解释 Biscuit 为何需要系统调用级堆预留以及静态分析如何支持它。
- 能够区分“漏洞不再可执行恶意代码”“变为 panic”和“逻辑错误仍存在”等安全结果。
- 能够审查内核语言性能实验的工作负载、基线、成本分解和外推限制。
- 能够根据安全、延迟、吞吐和内存约束给出条件化的内核语言选择。

## 前置知识

- C 内存管理：理解手工分配、释放和内存安全错误。
- 垃圾回收：理解 live data、heap headroom、并发 GC 与暂停。
- 操作系统内核路径：理解系统调用、上下文切换、文件系统和网络栈是内核密集工作。
- 性能实验：能区分吞吐、延迟、CPU profile 和扩展性。

## 核心概念

### 语言权衡而非单一胜负

C 提供直接内存控制和少量隐式代码，但内存安全难；HLL 提供类型/内存安全和抽象，同时引入检查、GC 与运行时约束。

来源：mit-6.s081-f21-lecture-20-material@page:4, mit-6.s081-f21-lecture-20-material@page:5, mit-6.s081-f21-lecture-20-material@page:7, mit-6.s081-f21-lecture-20-material@page:8

### Biscuit

Biscuit 是使用 Go 与少量汇编实现的单体 UNIX 内核，提供多核、线程、日志文件系统、虚拟内存、网络和驱动等功能。

来源：mit-6.s081-f21-lecture-20-material@page:14, mit-6.s081-f21-lecture-20-material@page:15, mit-6.s081-f21-lecture-20-material@page:16, mit-6.s081-f21-lecture-20-material@page:17

### 堆耗尽预留

Go 可能隐式分配且不暴露普通分配失败；Biscuit 在执行系统调用前预留其最坏内存需求以避免中途死锁或失败处理。

来源：mit-6.s081-f21-lecture-20-material@page:20, mit-6.s081-f21-lecture-20-material@page:25, mit-6.s081-f21-lecture-20-material@page:26, mit-6.s081-f21-lecture-20-material@page:27

### 静态内存边界分析

工具借助 Go 静态分析和逃逸分析估计每个系统调用的最大内存需求，困难路径用标注补充。

来源：mit-6.s081-f21-lecture-20-material@page:28, mit-6.s081-f21-lecture-20-material@page:29

### HLL 安全结果分类

内存安全可让部分越界或 use-after-free 漏洞消失或转为 panic，但未知逻辑错误不自动消失。

来源：mit-6.s081-f21-lecture-20-material@page:42, mit-6.s081-f21-lecture-20-material@page:43

### HLL tax

评估把成本拆分为 GC、函数 prologue、写屏障和安全检查，避免把所有差异笼统归因于垃圾回收。

来源：mit-6.s081-f21-lecture-20-material@page:50, mit-6.s081-f21-lecture-20-material@page:51

### GC 内存-时间权衡

live data 相对空闲 heap 越多，GC 越频繁或每轮成本越高；增加 headroom 可降低 GC 占比但增加内存预算。

来源：mit-6.s081-f21-lecture-20-material@page:52, mit-6.s081-f21-lecture-20-material@page:53, mit-6.s081-f21-lecture-20-material@page:54

### 条件化工程结论

材料的结论是按约束选择：极致性能或最小内存倾向 C，安全优先且可接受成本时 HLL 更有吸引力。

来源：mit-6.s081-f21-lecture-20-material@page:62, mit-6.s081-f21-lecture-20-material@page:65, mit-6.s081-f21-lecture-20-material@page:66

## 学习顺序

1. 复习 C 内存安全、GC 和内核性能指标。（20 分钟）
2. 理解 Biscuit 的目标、方法和系统范围。（30 分钟）
3. 分析裸机 Go 的堆耗尽、预留和静态分析方案。（35 分钟）
4. 评估 HLL 的可编程性和漏洞结果。（30 分钟）
5. 解读 HLL tax、GC 内存/暂停和代码路径实验。（35 分钟）
6. 完成多核扩展与语言选择综合决策。（30 分钟）

## 练习

### p1 · 基础

建立 C 与 HLL 内核开发的五维对照表：内存控制、安全、并发、隐式运行时和依赖。

提示：每个维度都写收益和代价。

提交：五维权衡表。

来源：mit-6.s081-f21-lecture-20-material@page:4, mit-6.s081-f21-lecture-20-material@page:5, mit-6.s081-f21-lecture-20-material@page:7, mit-6.s081-f21-lecture-20-material@page:8

### p2 · 设计

某系统调用可能在执行中隐式分配。比较 panic、在分配器等待、逐次检查失败和预先预留四种策略，解释死锁/可实现性问题。

提示：关注“已经持有资源后再等待内存”这一风险。

提交：策略比较与推荐。

来源：mit-6.s081-f21-lecture-20-material@page:20, mit-6.s081-f21-lecture-20-material@page:25, mit-6.s081-f21-lecture-20-material@page:26, mit-6.s081-f21-lecture-20-material@page:27

### p3 · 安全分析

把四个假想内核缺陷分类为越界、use-after-free、逻辑错误或未知，并预测在内存安全语言中是消失、panic 还是仍可能存在。

提示：不要把 panic 等同于正确执行。

提交：分类矩阵与理由。

来源：mit-6.s081-f21-lecture-20-material@page:42, mit-6.s081-f21-lecture-20-material@page:43

### p4 · 数据解读

根据 live/free heap 与 GC 占比的表格，解释为何增加 headroom 会降低 GC 比例，并列出无法从三行数据推出的结论。

提示：区分相关的观察与跨工作负载因果外推。

提交：趋势解释和外推限制清单。

来源：mit-6.s081-f21-lecture-20-material@page:52, mit-6.s081-f21-lecture-20-material@page:53, mit-6.s081-f21-lecture-20-material@page:54

### p5 · 实验审查

为“Go 内核和 C 内核性能差异”设计复现实验清单，涵盖功能对齐、硬件、工作负载、吞吐、延迟、profile 和多核扩展。

提示：先保证比较对象做相同工作。

提交：复现实验协议。

来源：mit-6.s081-f21-lecture-20-material@page:44, mit-6.s081-f21-lecture-20-material@page:45, mit-6.s081-f21-lecture-20-material@page:46, mit-6.s081-f21-lecture-20-material@page:50, mit-6.s081-f21-lecture-20-material@page:60, mit-6.s081-f21-lecture-20-material@page:63

### p6 · 综合决策

为安全关键控制器、内存极小设备和通用服务内核三个场景分别选择 C/HLL/混合方案，并明确会改变结论的假设。

提示：使用材料最后的条件化结论，而非一次基准排名。

提交：三份简短决策记录。

来源：mit-6.s081-f21-lecture-20-material@page:58, mit-6.s081-f21-lecture-20-material@page:62, mit-6.s081-f21-lecture-20-material@page:65, mit-6.s081-f21-lecture-20-material@page:66

## 限制

- 材料是官方 2021 日程链接的 2020 Biscuit 幻灯片，研究结论应保留其系统、硬件、应用与时间背景。
- Biscuit 与 Linux 的功能和配置不是完全 apples-to-apples；本包将实验结果作为有条件证据而非普遍排名。
- 第 49 页比率抽取不完整，未用于任何精确数值结论；第 21–24 页低文本动画也未用于主张。
- 百分比、比率与复杂度均作为文字证据保留，未创建结构化公式。
