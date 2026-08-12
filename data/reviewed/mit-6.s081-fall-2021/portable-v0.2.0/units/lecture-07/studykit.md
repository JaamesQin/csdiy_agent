# MIT 6.S081 第 7 讲：页故障与虚拟内存应用

> 课程：mit-6.s081-fall-2021 · 版本：fall-2021 · 单元：lecture-07

## 学习目标

- 说明 RISC-V 页故障处理需要收集的故障地址、原因、指令位置与特权级信息。
- 解释惰性分配如何把物理页分配推迟到首次访问，并识别基本边界检查。
- 比较零页、写时复制、按需分页和换页如何利用页故障改变资源成本。
- 说明 guard page、mmap 与 TLB 管理如何把虚拟内存用于保护、接口和性能。

## 前置知识

- 页表与 PTE 权限：能解释有效、用户、读、写、执行位对访问许可的影响。
- RISC-V 陷阱基本概念：知道异常会把控制转移到内核，并保存故障相关状态。

## 核心概念

### 页故障证据三元组

处理页故障需要知道故障虚拟地址、访问类型和故障发生位置/特权级。材料把地址放在 STVAL，把页故障类别编码在 SCAUSE，并通过保存的程序计数器与状态判断发生位置和模式。

来源：mit-6.s081-f21-lecture-07-material@page:5, mit-6.s081-f21-lecture-07-material@page:6, mit-6.s081-f21-lecture-07-material@page:7, mit-6.s081-f21-lecture-07-material@page:8

### 惰性物理页分配

传统 sbrk 可能提前分配永不访问的内存；惰性分配先扩展可用地址范围，在首次访问产生页故障时再安装物理页。处理器还必须拒绝越过用户栈或侵入内核范围的无效故障。

来源：mit-6.s081-f21-lecture-07-material@page:10, mit-6.s081-f21-lecture-07-material@page:12

### 页故障驱动的内存优化

只读零页让多个映射共享同一已清零物理页，写入时再复制；写时复制 fork 先共享只读页，写故障时复制；按需分页在故障时从文件装入；当工作集适合时，页表还可协助在磁盘与 RAM 间换页。

来源：mit-6.s081-f21-lecture-07-material@page:13, mit-6.s081-f21-lecture-07-material@page:15, mit-6.s081-f21-lecture-07-material@page:16, mit-6.s081-f21-lecture-07-material@page:17

### 虚拟内存作为可编程间接层

无效 guard page 可捕获栈越界；mmap 把文件块映射为可用 load/store 访问的地址；ASID、全局项、局部失效和大页等机制用于减少 TLB 管理成本。虚拟内存因此既是隔离工具，也是功能与性能接口。

来源：mit-6.s081-f21-lecture-07-material@page:14, mit-6.s081-f21-lecture-07-material@page:19, mit-6.s081-f21-lecture-07-material@page:21, mit-6.s081-f21-lecture-07-material@page:22, mit-6.s081-f21-lecture-07-material@page:23

## 学习顺序

1. 核对前置知识、材料年代与本讲证据边界。（15 分钟）
2. 精读“页故障证据三元组”与“惰性物理页分配”，按来源页整理因果链。（35 分钟）
3. 比较“页故障驱动的内存优化”与“虚拟内存作为可编程间接层”，画出状态或控制流。（35 分钟）
4. 完成基础辨析与逐步追踪练习，并逐项回查页码。（35 分钟）
5. 完成机制分析与设计取舍练习，明确不变量和失败条件。（40 分钟）
6. 完成综合解释，使用来源页自检术语、边界和证据。（20 分钟）

## 练习

### practice-01 · recall

制作页故障诊断卡：故障地址、访问类型、故障指令位置/模式分别从哪里获得？

提示：查找 STVAL、SCAUSE、epc 与状态寄存器。

提交：四列诊断表。

来源：mit-6.s081-f21-lecture-07-material@page:5, mit-6.s081-f21-lecture-07-material@page:7, mit-6.s081-f21-lecture-07-material@page:8

### practice-02 · trace

追踪一次合法但尚未分配的堆地址首次写入：从页故障到安装物理页，再到指令重试；同时标出两个必须拒绝的地址边界。

提示：不要写代码，只写状态变化。

提交：6–8 步事件序列。

来源：mit-6.s081-f21-lecture-07-material@page:10, mit-6.s081-f21-lecture-07-material@page:12

### practice-03 · analysis

比较零页与写时复制：初始共享条件、触发复制的事件以及复制后权限各是什么？

提示：两者都依赖只读映射与写故障，但共享内容和使用场景不同。

提交：两机制对照表。

来源：mit-6.s081-f21-lecture-07-material@page:13, mit-6.s081-f21-lecture-07-material@page:15

### practice-04 · design

为一个有限大小用户栈设计一条概念保护规则：guard page 放在哪里、PTE 状态如何、故障处理器应如何区分越界与可增长情况？

提示：材料只给概念，不要求 xv6 实现。

提交：一张内存布局草图和三条规则。

来源：mit-6.s081-f21-lecture-07-material@page:14

### practice-05 · synthesis

选择惰性分配、COW、需求分页或 mmap 之一，画出“PTE 初态—访问—故障证据—内核动作—PTE 终态”的完整链，并说明一个性能收益和一个正确性风险。

提示：每一步都标出来源页，不写可提交代码。

提交：状态机图、收益/风险各一条。

来源：mit-6.s081-f21-lecture-07-material@page:8, mit-6.s081-f21-lecture-07-material@page:10, mit-6.s081-f21-lecture-07-material@page:15, mit-6.s081-f21-lecture-07-material@page:16, mit-6.s081-f21-lecture-07-material@page:19

## 限制

- 本单元只使用页故障与虚拟内存应用幻灯片，不包含 xv6 源码、实验说明或 COW/mmap 可提交实现。
- 第 9、11 页文本提取过少，分别是布局图和演示标题，不单独支撑主张。
- 页面中的地址布局与 PTE 图仍待独立视觉审阅；候选未创建结构化公式字段。
