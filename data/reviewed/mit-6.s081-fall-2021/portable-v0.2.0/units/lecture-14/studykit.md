# File systems

> 课程：mit-6.s081-fall-2021 · 版本：fall-2021 · 单元：lecture-14

## 学习目标

- 能够从 link/unlink/open 语义解释 inode、nlink 和打开引用计数的必要性。
- 能够标注 xv6 on-disk 布局并按 inode/bitmap/数据块定位元数据。
- 能够追踪一次创建、写入或删除触发的主要磁盘块更新。
- 能够说明块缓存唯一副本不变量及两级锁分工。
- 能够分析 pathname lookup 与 unlink 并发时引用和锁的生命周期。

## 前置知识

- UNIX 文件描述符：知道 open/read/write/close 的基本接口语义。
- 持久存储与块：理解磁盘按固定大小块读写。
- 锁与引用计数：理解锁保护共享状态、引用计数延迟释放对象。

## 核心概念

### inode 身份

目录名不是文件的唯一身份；inode 保存独立于目录项的文件信息，使多个硬链接与打开后 unlink 成为可能。

来源：mit-6.s081-f21-lecture-14-material@page:1

### 链接与打开引用

inode 只有在最后一个目录链接和最后一个打开引用都消失后才能安全释放。

来源：mit-6.s081-f21-lecture-14-material@page:1

### xv6 磁盘布局

xv6 把磁盘视为块数组，固定区域存放 superblock、日志、inode、分配 bitmap 和文件/目录内容。

来源：mit-6.s081-f21-lecture-14-material@page:2

### 元数据更新路径

创建、写入和删除会更新不同的 inode、目录块、bitmap 与数据块；调用图把系统调用连接到这些物理更新。

来源：mit-6.s081-f21-lecture-14-material@page:3

### 块缓存唯一副本

缓存保证同一磁盘块在内存中只有一个缓存副本，避免并发调用者对不同副本做冲突修改。

来源：mit-6.s081-f21-lecture-14-material@page:4

### 两级锁

bcache.lock 保护缓存目录/替换元数据，单个 buffer 的锁保护该块内容并允许其他块并行访问。

来源：mit-6.s081-f21-lecture-14-material@page:4

### 引用先于锁

路径查找在解锁当前目录后仍持有下一 inode 的引用，因此并发 unlink 不会立刻回收该 inode。

来源：mit-6.s081-f21-lecture-14-material@page:4

## 学习顺序

1. 复习文件描述符、目录与磁盘块。（20 分钟）
2. 从 API 语义推导 inode、链接与延迟回收。（30 分钟）
3. 建立 xv6 磁盘布局和 inode/目录/bitmap 数据结构图。（35 分钟）
4. 追踪创建、写入与删除的块更新路径。（35 分钟）
5. 分析块缓存两级锁和并发 inode 分配。（35 分钟）
6. 完成并发路径查找综合练习与自评。（25 分钟）

## 练习

### p1 · 基础

对 open、link、unlink、仍通过旧 fd 写入的序列，画出目录项、inode nlink 和打开引用的变化。

提示：文件名变化与 inode 身份分开记录。

提交：逐步状态表。

来源：mit-6.s081-f21-lecture-14-material@page:1

### p2 · 基础到应用

依据讲义布局标注 superblock、log、inode、bitmap 与内容块，并说明查找文件第 8000 字节的大致步骤。

提示：先算逻辑块，再通过 inode 的地址项定位。

提交：布局图与查找步骤。

来源：mit-6.s081-f21-lecture-14-material@page:2

### p3 · 追踪

为“创建空文件后写入 hi”建立块写入账本，按 inode、目录、bitmap、数据块分类每次更新的目的。

提示：使用调用图，而不是背诵块号。

提交：分类账本和调用链。

来源：mit-6.s081-f21-lecture-14-material@page:3

### p4 · 并发

两个线程同时 ialloc 时，说明缓存唯一副本与 buffer lock 怎样阻止它们分配同一 inode。

提示：区分缓存目录锁和块内容锁。

提交：并发时间线与不变量。

来源：mit-6.s081-f21-lecture-14-material@page:4

### p5 · 综合

构造 pathname lookup 与 unlink 的交错，展示为什么“获取引用后解锁”仍安全，以及如果没有引用计数会发生什么。

提示：追踪当前 inode、下一 inode 的 refcnt 与锁。

提交：交错表、失败反例和安全条件。

来源：mit-6.s081-f21-lecture-14-material@page:4

## 限制

- 准备材料是官方 2021 日程明确链接的 2020 文本讲义，经确定性分页生成 4 页 PDF；不是原生 2021 幻灯片。
- 每页信息密度很高，页级引用无法进一步定位到原文本行；审核时应结合对应页面全文。
- 讲义在崩溃恢复与日志方面只列出层次，本单元不扩展到下一讲的事务恢复算法。
