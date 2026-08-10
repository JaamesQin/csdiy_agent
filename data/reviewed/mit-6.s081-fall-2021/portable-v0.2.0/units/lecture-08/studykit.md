# Q&A labs I

> 课程：mit-6.s081-fall-2021 · 版本：fall-2021 · 单元：lecture-08

## 学习目标

- 能够为只读共享页选择适合与不适合加速的系统调用结果。
- 能够阅读页表输出并把层级、物理地址和权限位转化为调试问题。
- 能够区分访问位、脏位及页故障式访问检测的语义和成本。
- 能够解释代际 GC 中跨代引用为何需要额外跟踪。
- 能够在不复述实验实现答案的前提下评估虚拟内存机制的设计权衡。

## 前置知识

- 多级页表：理解虚拟地址经页表映射到物理页，并知道 PTE 包含权限/状态位。
- 系统调用：理解用户态进入内核态存在固定开销。
- 垃圾回收基础：知道根集合、可达性和对象分代的基本含义。

## 核心概念

### USYSCALL 共享页

对进程生命周期内稳定、无副作用的查询，内核可把数据放在用户可读但不可写的共享页中以避免切换。

来源：mit-6.s081-f21-lecture-08-material@page:4, mit-6.s081-f21-lecture-08-material@page:6, mit-6.s081-f21-lecture-08-material@page:7

### VDSO

更完整的做法是在用户地址空间同时提供只读共享数据和解释数据的用户态代码。

来源：mit-6.s081-f21-lecture-08-material@page:9, mit-6.s081-f21-lecture-08-material@page:10

### 页表可观测性

递归打印页表可揭示映射层次、物理页和权限，是后续虚拟内存故障的诊断工具。

来源：mit-6.s081-f21-lecture-08-material@page:11, mit-6.s081-f21-lecture-08-material@page:13

### 访问位与脏位

硬件在页表遍历时设置访问位表示读或写过，并设置脏位表示发生写入。

来源：mit-6.s081-f21-lecture-08-material@page:15

### 故障驱动的访问检测

缺少访问位时可暂时清除有效映射并在页故障中记录访问，但每次首次访问要支付陷入成本。

来源：mit-6.s081-f21-lecture-08-material@page:18, mit-6.s081-f21-lecture-08-material@page:19

### 代际 GC 的跨代引用

只扫描年轻代时，老年代指向年轻代的引用会成为遗漏风险；脏页信息可缩小需要检查的老年代区域。

来源：mit-6.s081-f21-lecture-08-material@page:20, mit-6.s081-f21-lecture-08-material@page:22, mit-6.s081-f21-lecture-08-material@page:23, mit-6.s081-f21-lecture-08-material@page:24

## 学习顺序

1. 复习系统调用开销、多级页表和 PTE 状态位。（20 分钟）
2. 分析只读共享页与 VDSO 的数据发布路径。（30 分钟）
3. 学习页表打印输出作为可观测性工具。（25 分钟）
4. 比较访问位、脏位和故障式访问跟踪。（30 分钟）
5. 推导代际 GC 的跨代引用与脏页方案。（35 分钟）
6. 完成概念设计练习并检查是否越过实验答案边界。（40 分钟）

## 练习

### p1 · 基础

把 getpid、uptime 和一个会修改内核状态的调用分类为“适合只读共享页”“需要额外更新时间机制”或“不适合”，并说明理由。

提示：检查副作用、值的稳定期和用户写权限。

提交：分类表和每项两句理由。

来源：mit-6.s081-f21-lecture-08-material@page:4, mit-6.s081-f21-lecture-08-material@page:6, mit-6.s081-f21-lecture-08-material@page:7

### p2 · 应用

给出一段简化页表打印输出，设计检查顺序来确认某用户页是否映射、是否用户可访问、对应哪个物理页。

提示：从层级缩进到叶子 PTE，再看权限。

提交：逐步检查清单。

来源：mit-6.s081-f21-lecture-08-material@page:11, mit-6.s081-f21-lecture-08-material@page:13

### p3 · 比较

比较“读取 PTE_A”与“清除 PTE_V 后等待页故障”两种访问检测方案的准确性、开销和恢复动作。

提示：后者必须在故障处理后恢复有效映射。

提交：三维比较表。

来源：mit-6.s081-f21-lecture-08-material@page:15, mit-6.s081-f21-lecture-08-material@page:18, mit-6.s081-f21-lecture-08-material@page:19

### p4 · 推理

画出年轻代与老年代，并构造一个老对象指向年轻对象的例子；说明只扫描年轻代为何会漏标以及脏页怎样缩小检查范围。

提示：把写入发生的页与对象引用分开标注。

提交：对象图、脏页标记和扫描步骤。

来源：mit-6.s081-f21-lecture-08-material@page:20, mit-6.s081-f21-lecture-08-material@page:22, mit-6.s081-f21-lecture-08-material@page:23, mit-6.s081-f21-lecture-08-material@page:24

### p5 · 综合

设计一个不涉及课程实验代码的“高频只读内核数据发布”方案，说明共享页权限、更新时机、用户读取路径和失效边界。

提示：可选时间戳或统计计数器，但要写清楚一致性要求。

提交：一页设计说明与威胁/失效分析。

来源：mit-6.s081-f21-lecture-08-material@page:4, mit-6.s081-f21-lecture-08-material@page:7, mit-6.s081-f21-lecture-08-material@page:9, mit-6.s081-f21-lecture-08-material@page:15

## 限制

- 原讲义是课程实验问答材料；本包只提取通用虚拟内存概念，不提供或重建任何实验代码答案。
- 第 8、14、16 页的 Code walkthrough 因文本证据稀少且涉及实验实现而排除。
- 页表图和代际 GC 图的空间细节需要独立视觉审核；当前候选不保留结构化公式。
