# MIT 6.S081 第 10 讲：多处理器与锁

> 课程：mit-6.s081-fall-2021 · 版本：fall-2021 · 单元：lecture-10

## 学习目标

- 用哈希表交错执行解释竞态条件与丢失更新。
- 说明临界区、数据结构不变量和锁保护范围之间的关系。
- 识别死锁的循环等待并使用一致加锁顺序规避它。
- 比较锁粒度、原子操作、内存顺序、spin lock 与其他并发设计选项。

## 前置知识

- 指针链表与哈希桶：能读懂 bucket 头指针和链式冲突结构，以便追踪两个 put 的交错。
- 多核共享内存：知道多个 CPU 可并发访问同一 RAM 位置，并且执行顺序不固定。

## 核心概念

### 竞态条件与丢失更新

多核让多个系统调用并行访问共享数据。哈希表中两个 put 若同时读取同一 bucket 头并随后写回，最后写入者可能覆盖另一更新；只要某种合法交错会破坏结果，就存在竞态。

来源：mit-6.s081-f21-lecture-10-material@page:4, mit-6.s081-f21-lecture-10-material@page:7, mit-6.s081-f21-lecture-10-material@page:8, mit-6.s081-f21-lecture-10-material@page:9

### 临界区与不变量

acquire/release 把一段多步操作变为其他线程不可见的临界区。锁不自动绑定数据；程序员必须识别共享写入和跨字段不变量，并在释放前恢复不变量，从而隐藏暂时不一致状态。

来源：mit-6.s081-f21-lecture-10-material@page:12, mit-6.s081-f21-lecture-10-material@page:13, mit-6.s081-f21-lecture-10-material@page:14, mit-6.s081-f21-lecture-10-material@page:15

### 死锁与全局加锁顺序

两个执行流若以相反顺序各持一个锁再等待另一个，会永久等待。统一锁获取顺序可打破这种循环，但要求模块间暴露部分锁依赖，因此会牺牲封装与模块化。

来源：mit-6.s081-f21-lecture-10-material@page:16, mit-6.s081-f21-lecture-10-material@page:17, mit-6.s081-f21-lecture-10-material@page:18

### 锁实现与粒度取舍

粗粒度锁易推理但限制并行，细粒度锁提高并行度却增加不变量和死锁复杂度。真实锁需要原子读改写及获取/释放顺序保证；短临界区适合自旋，长等待通常需要可阻塞方案，而每核数据、RCU 或无锁算法可减少共享。

来源：mit-6.s081-f21-lecture-10-material@page:19, mit-6.s081-f21-lecture-10-material@page:20, mit-6.s081-f21-lecture-10-material@page:22, mit-6.s081-f21-lecture-10-material@page:23, mit-6.s081-f21-lecture-10-material@page:24, mit-6.s081-f21-lecture-10-material@page:25, mit-6.s081-f21-lecture-10-material@page:26, mit-6.s081-f21-lecture-10-material@page:27, mit-6.s081-f21-lecture-10-material@page:28, mit-6.s081-f21-lecture-10-material@page:29, mit-6.s081-f21-lecture-10-material@page:31, mit-6.s081-f21-lecture-10-material@page:32, mit-6.s081-f21-lecture-10-material@page:33

## 学习顺序

1. 核对前置知识、材料年代与本讲证据边界。（15 分钟）
2. 精读“竞态条件与丢失更新”与“临界区与不变量”，按来源页整理因果链。（35 分钟）
3. 比较“死锁与全局加锁顺序”与“锁实现与粒度取舍”，画出状态或控制流。（35 分钟）
4. 完成基础辨析与逐步追踪练习，并逐项回查页码。（35 分钟）
5. 完成机制分析与设计取舍练习，明确不变量和失败条件。（40 分钟）
6. 完成综合解释，使用来源页自检术语、边界和证据。（20 分钟）

## 练习

### practice-01 · trace

逐行交错两个对同一 bucket 执行的 put：两者先读取旧头，再分别链接并写回。指出哪一步让一个 key 消失。

提示：把每次 READ/WRITE 写成时间线，不假定线程连续执行。

提交：两列时间线和丢失更新说明。

来源：mit-6.s081-f21-lecture-10-material@page:7, mit-6.s081-f21-lecture-10-material@page:8, mit-6.s081-f21-lecture-10-material@page:9

### practice-02 · explanation

为“把节点从目录 d1 移到 d2”的抽象操作写出一个不变量，并说明为何分别锁住两次单步修改会暴露中间状态。

提示：材料用 rename 说明自动逐对象加锁的局限。

提交：不变量、坏中间状态和所需临界区边界。

来源：mit-6.s081-f21-lecture-10-material@page:14, mit-6.s081-f21-lecture-10-material@page:15

### practice-03 · analysis

画出两个相反方向 rename 的等待图，并用一个全局顺序改写锁获取顺序。

提示：节点是 CPU/线程和锁，边表示持有或等待。

提交：等待图和一致顺序规则。

来源：mit-6.s081-f21-lecture-10-material@page:16, mit-6.s081-f21-lecture-10-material@page:17

### practice-04 · design

给共享哈希表设计两个锁粒度方案：整表锁与每桶锁。比较正确性推理、潜在并行度和死锁风险，并提出何时值得细化。

提示：遵循“先粗锁、再测量”的材料建议。

提交：三维对照表和一个测量触发条件。

来源：mit-6.s081-f21-lecture-10-material@page:10, mit-6.s081-f21-lecture-10-material@page:11, mit-6.s081-f21-lecture-10-material@page:22, mit-6.s081-f21-lecture-10-material@page:23

### practice-05 · synthesis

评审一个短临界区 spin lock：从原子获取、失败重试、获取顺序、临界区、释放顺序到存零，写出机制链；再说明它为何不适合长等待。

提示：只解释幻灯片中的 AMO/fence/acquire-release 概念，不复制为课程提交代码。

提交：6 步机制链和一段适用性判断。

来源：mit-6.s081-f21-lecture-10-material@page:24, mit-6.s081-f21-lecture-10-material@page:25, mit-6.s081-f21-lecture-10-material@page:26, mit-6.s081-f21-lecture-10-material@page:27, mit-6.s081-f21-lecture-10-material@page:28, mit-6.s081-f21-lecture-10-material@page:29, mit-6.s081-f21-lecture-10-material@page:31

## 限制

- 本单元仅使用锁与多处理器幻灯片；不包含 xv6 kfree 或 spinlock 源码全文。
- 第 3、10、30 页文本提取过少，仅作为视觉审阅页，不能单独支撑机制主张。
- 材料中的汇编是解释原子与顺序语义的证据；本 StudyKit 不提供可提交实验实现，也不创建结构化公式字段。
