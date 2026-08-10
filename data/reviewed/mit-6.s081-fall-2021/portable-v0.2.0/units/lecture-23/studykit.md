# Multi-core scalability and RCU

> 课程：mit-6.s081-fall-2021 · 版本：fall-2021 · 单元：lecture-23

## 学习目标

- 能够解释读写锁的读路径为何仍可能在多核上形成写热点。
- 能够用复制、单指针发布和内存屏障解释 RCU 读者为何可无锁。
- 能够画出删除对象、等待 grace period、最终释放的安全时序。
- 能够根据读写比、引用生命周期和数据结构更新方式判断 RCU 是否适用。
- 能够比较 RCU 与 per-core 分区对读热点和写热点的不同取舍。

## 前置知识

- 缓存一致性：理解一个核心写共享缓存行会使其他核心副本失效。
- 原子操作与锁：理解 CAS、spinlock 和 read/write lock 的基本语义。
- 内存顺序：知道编译器和 CPU 可能重排独立读写，需要屏障建立 happens-before。
- 调度与 context switch：理解线程在切换后不再继续使用先前栈上的临时引用。

## 核心概念

### 读写锁的缓存行争用

读锁也会递增共享读者计数，导致每个读者执行写和缓存失效；高核心数下成本会急剧放大。

来源：mit-6.s081-f21-lecture-23-material@page:1

### 复制后单写提交

RCU 写者不原地修改读者可见对象，而是准备新副本并以一次指针更新作为提交点。

来源：mit-6.s081-f21-lecture-23-material@page:2

### 发布与解引用屏障

写屏障保证对象初始化先于发布，读屏障保证获取指针先于读取对象内容。

来源：mit-6.s081-f21-lecture-23-material@page:2

### grace period

删除可见指针后，写者等待所有可能持旧引用的 CPU 经过 context switch，再安全释放旧对象。

来源：mit-6.s081-f21-lecture-23-material@page:2, mit-6.s081-f21-lecture-23-material@page:3

### 读侧临界区

rcu_read_lock/unlock 限定指针可用区间；引用不能跨 yield/sleep 或被返回给区间外代码。

来源：mit-6.s081-f21-lecture-23-material@page:3, mit-6.s081-f21-lecture-23-material@page:4

### 读优化、写变慢

RCU 让读路径接近零写入并可与写并发，但写者需要复制、同步和延迟回收，适合读远多于写的结构。

来源：mit-6.s081-f21-lecture-23-material@page:3, mit-6.s081-f21-lecture-23-material@page:4

### per-core 分区

写频繁时可把状态拆为每核私有/半私有分区，使本地写便宜，并把昂贵聚合移到稀少的读操作。

来源：mit-6.s081-f21-lecture-23-material@page:4

## 学习顺序

1. 复习缓存一致性、CAS、内存屏障与 context switch。（20 分钟）
2. 分析读写锁读路径的共享写成本。（30 分钟）
3. 推导复制后发布与读写内存屏障。（35 分钟）
4. 学习 grace period、读侧临界区和延迟释放 API。（35 分钟）
5. 分析 NMI/IP options 用例和 RCU 的适用边界。（30 分钟）
6. 完成数据结构适用性与 per-core 分区综合练习。（30 分钟）

## 练习

### p1 · 基础

用四个核心同时获取读锁的例子，画出共享读者计数所在缓存行的失效与重试过程。

提示：每次成功 CAS 都是一次共享写。

提交：缓存行时间线。

来源：mit-6.s081-f21-lecture-23-material@page:1

### p2 · 交错推理

写者要修改单链表中间节点。分别列出读者在提交指针写之前和之后读取时看到的版本，并解释为何不会看到半初始化节点。

提示：把初始化和发布之间放置顺序边界。

提交：两种合法交错和禁止的乱序。

来源：mit-6.s081-f21-lecture-23-material@page:2

### p3 · 内存安全

构造一个读者仍指向已摘除节点的场景，说明立即 free 的后果，并画出 synchronize_rcu 后释放的安全时序。

提示：读者是否跨 context switch 是判断 grace period 的关键。

提交：错误时序与修正时序。

来源：mit-6.s081-f21-lecture-23-material@page:2, mit-6.s081-f21-lecture-23-material@page:3

### p4 · 适用性判断

对进程列表、双向链表、频繁更新计数器和偶尔更新配置四种结构判断 RCU 适用性，列出关键假设。

提示：检查读写比例、提交写、陈旧读取和引用是否跨 sleep。

提交：决策表。

来源：mit-6.s081-f21-lecture-23-material@page:3, mit-6.s081-f21-lecture-23-material@page:4

### p5 · 综合设计

为一个写频繁、读聚合稀少的统计计数器比较全局锁、RCU 和 per-core 计数，设计更新与汇总路径。

提示：材料建议把昂贵工作移到少见操作。

提交：三个方案的成本模型与推荐。

来源：mit-6.s081-f21-lecture-23-material@page:4

## 限制

- 准备材料是官方 2021 日程明确链接的 2020 文本讲义，经确定性分页生成 4 页 PDF。
- 讲义给出的是简化 RCU 说明；真实 Linux RCU 变体、内存模型和实现细节远超本单元范围。
- 读写锁工作量增长与性能数字按讲义定性/文字描述，不创建结构化复杂度公式。
- 是否允许陈旧读是应用语义问题；本包不会默认所有 RCU 场景都可接受陈旧值。
