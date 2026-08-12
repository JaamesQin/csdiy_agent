# 操作系统组织：单体内核、微内核与 L4/Linux

> 课程：mit-6.s081-fall-2021 · 版本：fall-2021 · 单元：lecture-18

## 学习目标

- 比较单体内核与微内核的组织取舍。
- 用 L4 最小原语解释用户态内存服务。
- 解释快速 IPC 如何削减 RPC 路径成本。
- 追踪 L4/Linux OS server 的系统调用或 fork。
- 限定性解释历史微基准与整机基准。

## 前置知识

- 内核/用户权限边界：知道高权限内核代码和用户态进程的隔离差异。
- 地址空间、线程与缺页：知道页表映射、线程切换和 page fault 的基本角色。
- IPC 与 RPC：知道请求—响应需要在两个执行主体间传递控制和数据。

## 核心概念

### 单体内核

强抽象和内核内协作带来便利，也扩大高权限代码、复杂度和固化选择；不存在脱离应用的单一最佳组织。

来源：mit-6.s081-f21-lecture-18-material@page:1

### 微内核

微内核把多数 OS 功能移到用户态服务，内核主要保留地址空间、线程和 IPC。

来源：mit-6.s081-f21-lecture-18-material@page:1, mit-6.s081-f21-lecture-18-material@page:2

### L4 原语与 pager

task、thread、IPC 和页映射组合出用户态内存管理；缺页被 IPC 给外部 pager。

来源：mit-6.s081-f21-lecture-18-material@page:2

### 快速同步 IPC

同步无缓冲会合、寄存器消息、页授权和组合 RPC 调用减少队列、复制、调度及穿越；性能倍数限于历史实现。

来源：mit-6.s081-f21-lecture-18-material@page:3

### L4/Linux OS server

修改后的 Linux 内核作为用户态服务器，通过 IPC 提供语义，并借 L4 创建 task/thread、映射页和接收事件。

来源：mit-6.s081-f21-lecture-18-material@page:3, mit-6.s081-f21-lecture-18-material@page:4

### 微基准与整机基准

历史 getpid 和 AIM 结果削弱因性能否决 L4 的理由，但不证明应采用 L4。

来源：mit-6.s081-f21-lecture-18-material@page:4, mit-6.s081-f21-lecture-18-material@page:5

## 学习顺序

1. 复习权限边界、地址空间、线程、缺页和 RPC。（15 分钟）
2. 比较单体内核与微内核并完成对照。（45 分钟）
3. 学习 L4 pager 与快速 IPC，完成两条路径练习。（65 分钟）
4. 追踪 L4/Linux fork 和评估方法。（50 分钟）
5. 汇总机制、代价、证据和限制。（5 分钟）

## 练习

### prac-01 · 入门

按四个维度比较单体与微内核，并说明为何没有普遍赢家。

提示：观察边界带来的双向影响。

提交：四行对照表。

来源：mit-6.s081-f21-lecture-18-material@page:1

### prac-02 · 理解

画出外部 pager 的缺页 IPC 与页映射路径。

提示：目标先暂停，pager 回复映射。

提交：六节点图。

来源：mit-6.s081-f21-lecture-18-material@page:2

### prac-03 · 应用

比较异步队列 RPC 与 L4 快速同步 RPC 的队列、复制、调度和调用。

提示：接收者常已等待。

提交：四维路径表。

来源：mit-6.s081-f21-lecture-18-material@page:2, mit-6.s081-f21-lecture-18-material@page:3

### prac-04 · 分析

追踪 L4/Linux fork，并区分 P1、Linux server 与 L4 的职责。

提示：语义在 server，原语在 L4。

提交：跨组件时间线。

来源：mit-6.s081-f21-lecture-18-material@page:4

### prac-05 · 迁移

说明历史 getpid 与 AIM 结果能反驳什么、不能证明什么。

提示：可接受性能不等于架构选择充分。

提交：四句边界陈述。

来源：mit-6.s081-f21-lecture-18-material@page:4, mit-6.s081-f21-lecture-18-material@page:5

## 限制

- 证据为官方 Fall 2021 日程链接的 2020 文本讲义转换稿。
- 数值与性能结论仅归属于讲义讨论的历史实现和论文。
- 本单元不把任一内核组织描述为普遍最佳；第 2、3 页去除了少量重复行。
