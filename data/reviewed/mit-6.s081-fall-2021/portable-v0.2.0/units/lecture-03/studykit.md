# 操作系统组织、隔离与系统调用

> 课程：mit-6.s081-fall-2021 · 版本：fall-2021 · 单元：lecture-03

## 学习目标

- 辨认弱协作式资源共享方案的调度与内存隔离失败点。
- 用资源映射解释 UNIX 的进程、内存、文件和管道抽象。
- 按职责区分特权级、页表、ecall 与内核参数验证。
- 比较单体内核与微内核的结构性取舍。
- 描述 xv6 在 RISC-V/QEMU 教学平台中的位置。

## 前置知识

- C 程序与函数调用：能读懂函数调用和进程使用系统调用的基本例子。
- CPU、内存与设备：能区分处理器、物理内存和外设的作用。
- UNIX 基础接口：见过 fork、exec、open、read、write 或 pipe 中的若干接口。

## 核心概念

### 多路复用

操作系统要让多个应用共享处理器、内存和设备；仅要求应用主动让出硬件既无法强制进度，也无法防止内存覆盖。

来源：mit-6.s081-f21-lecture-03-material@page:4, mit-6.s081-f21-lecture-03-material@page:6, mit-6.s081-f21-lecture-03-material@page:7

### UNIX 接口抽象

进程替代直接占有核心，私有内存替代共享物理内存，文件替代磁盘块，管道替代共享物理内存通信；这些接口让内核负责分配、隔离和节流。

来源：mit-6.s081-f21-lecture-03-material@page:8, mit-6.s081-f21-lecture-03-material@page:9, mit-6.s081-f21-lecture-03-material@page:10

### 硬件隔离

CPU 特权级限制用户程序执行特权指令，页表限制其可访问的物理内存。本讲的 xv6 路径使用用户态与监管态，并明确不使用 M-mode。

来源：mit-6.s081-f21-lecture-03-material@page:11, mit-6.s081-f21-lecture-03-material@page:12, mit-6.s081-f21-lecture-03-material@page:13

### 系统调用

应用以 ecall 进入预先约定的内核入口；内核再执行服务并验证来自不可信用户程序的参数。

来源：mit-6.s081-f21-lecture-03-material@page:14, mit-6.s081-f21-lecture-03-material@page:15, mit-6.s081-f21-lecture-03-material@page:16

### 可信计算基

内核和模式切换路径必须正确，因为其错误可能破坏应用之间以及应用与内核之间的隔离。

来源：mit-6.s081-f21-lecture-03-material@page:16, mit-6.s081-f21-lecture-03-material@page:17

### 单体内核与微内核

单体内核让文件系统、驱动和内存管理等服务在同一高权限程序内协作；微内核仅保留最小机制，把服务移到用户空间，以更多 IPC 和边界换取故障隔离。

来源：mit-6.s081-f21-lecture-03-material@page:18, mit-6.s081-f21-lecture-03-material@page:19, mit-6.s081-f21-lecture-03-material@page:20

### xv6 教学平台

xv6 是结构可读的单体 UNIX 内核，运行在课程采用的简化 RISC-V 机器模型上；QEMU 通过执行取指、译码和状态更新来仿真该处理器。

来源：mit-6.s081-f21-lecture-03-material@page:21, mit-6.s081-f21-lecture-03-material@page:23, mit-6.s081-f21-lecture-03-material@page:24, mit-6.s081-f21-lecture-03-material@page:25

## 学习顺序

1. 完成两个前置检查，复习 CPU、物理内存、设备与 UNIX 接口的层次。（15 分钟）
2. 阅读第 2–10 页，整理“共享目标—失败方案—UNIX 抽象”的因果链。（25 分钟）
3. 完成失败方案比较与抽象映射，互相检查每项是否对应来源中的具体资源。（20 分钟）
4. 阅读第 11–16 页，按“特权级—页表—ecall—内核验证”制作系统调用进入路径。（30 分钟）
5. 用 write 场景复述受控进入路径，并检查没有越出本讲采用的特权模式范围。（25 分钟）
6. 阅读第 17–25 页，比较内核架构，并标出 xv6、模拟机器和 QEMU 的位置。（25 分钟）
7. 完成架构比较矩阵和平台关系图，使用来源中的优缺点而不扩大结论。（25 分钟）
8. 闭卷画出从裸硬件共享到 xv6 系统调用边界的总图，再回查页码修正遗漏。（15 分钟）

## 练习

### prac-01 · 入门

比较“应用直接使用硬件、操作系统只是库”的方案与由内核强制管理资源的方案。分别指出一个调度失败点和一个内存失败点。

提示：观察应用是否必须主动让出 CPU，以及谁能阻止它写入别人的内存。

提交：两行对照表，每行包含机制、失败场景和所需的内核能力。

来源：mit-6.s081-f21-lecture-03-material@page:5, mit-6.s081-f21-lecture-03-material@page:6, mit-6.s081-f21-lecture-03-material@page:7

### prac-02 · 理解

为进程、私有内存、文件和管道各写出它替代的裸资源，以及内核因此获得的一项管理能力。

提示：按第 8–10 页的“instead of”关系整理。

提交：四行映射表：抽象 → 裸资源 → 内核职责。

来源：mit-6.s081-f21-lecture-03-material@page:8, mit-6.s081-f21-lecture-03-material@page:9, mit-6.s081-f21-lecture-03-material@page:10

### prac-03 · 应用

某用户程序要执行 write。按顺序说明页表、用户态/监管态、ecall 和内核参数验证分别解决什么问题；不要引入本讲未使用的 M-mode。

提示：先分清“限制能做什么”“限制能访问什么”“怎样进入内核”“进入后怎样防御”。

提交：四步路径，每步一句职责说明。

来源：mit-6.s081-f21-lecture-03-material@page:11, mit-6.s081-f21-lecture-03-material@page:12, mit-6.s081-f21-lecture-03-material@page:13, mit-6.s081-f21-lecture-03-material@page:14, mit-6.s081-f21-lecture-03-material@page:16

### prac-04 · 分析

从服务部署位置、内部隔离、跨子系统协作和性能风险四个维度比较单体内核与微内核。

提示：不要把“更多隔离”误写成“没有操作系统服务”。

提交：四维比较矩阵，并用一句话概括核心取舍。

来源：mit-6.s081-f21-lecture-03-material@page:18, mit-6.s081-f21-lecture-03-material@page:19, mit-6.s081-f21-lecture-03-material@page:20

### prac-05 · 迁移

向同伴解释为什么课程既需要 xv6 源码、RISC-V 机器模型，又需要 QEMU。请把三者画成有方向的关系图。

提示：区分“操作系统实现”“被假定的硬件”“运行该硬件模型的软件”。

提交：三节点关系图，加三句边说明。

来源：mit-6.s081-f21-lecture-03-material@page:21, mit-6.s081-f21-lecture-03-material@page:23, mit-6.s081-f21-lecture-03-material@page:24, mit-6.s081-f21-lecture-03-material@page:25

## 限制

- 本学习包仅依据本讲公开幻灯片，不包括视频、读物、实验或作业。
- 这是模型生成的初稿，尚待独立语义审核和人工视觉复核，不替代原始资料。
