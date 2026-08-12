# MIT 6.S081 第 4 讲：页表

> 课程：mit-6.s081-fall-2021 · 版本：fall-2021 · 单元：lecture-04

## 学习目标

- 解释虚拟地址到物理地址的间接层如何支持进程与内核隔离。
- 描述 RISC-V Sv39 地址划分、PTE 权限和三级页表的基本结构。
- 说明 satp、硬件页表遍历、TLB 缓存与失效处理的关系。
- 分析 xv6 进程页表、trampoline 映射和按需内存调整的设计问题。

## 前置知识

- 二进制地址与位字段：能把地址理解为若干索引字段和页内偏移，不要求手算具体页表地址。
- 用户态与内核态：理解用户代码不能直接配置 MMU，内核负责保护边界。

## 核心概念

### 虚拟内存的隔离间接层

每个进程使用自己的虚拟地址空间；软件访问虚拟地址，MMU 按内核配置的页表转换为物理地址，并利用权限限制用户访问内核或其他进程内存。

来源：mit-6.s081-f21-lecture-04-material@page:6, mit-6.s081-f21-lecture-04-material@page:7

### Sv39 三级页表

课程使用 Sv39：虚拟地址按页内偏移和虚拟页号划分，三级页表逐层使用索引查找 PTE。PTE 包含物理页号及有效、用户、读写执行等权限信息；多级结构避免为未使用的地址范围预留完整平面数组。

来源：mit-6.s081-f21-lecture-04-material@page:8, mit-6.s081-f21-lecture-04-material@page:9, mit-6.s081-f21-lecture-04-material@page:10, mit-6.s081-f21-lecture-04-material@page:13, mit-6.s081-f21-lecture-04-material@page:14

### satp、页表遍历与 TLB

satp 指向当前页表根，硬件在需要时遍历页表，TLB 缓存近期翻译。PTE 被移除、权限变化或切换页表根后，旧 TLB 项可能失效，软件必须按架构规则使缓存翻译失效。

来源：mit-6.s081-f21-lecture-04-material@page:16, mit-6.s081-f21-lecture-04-material@page:17, mit-6.s081-f21-lecture-04-material@page:18

### xv6 地址空间实践

xv6 为每个进程维护页表，并在进程切换时更换页表根；trampoline 在各页表的同一位置映射且必须可执行、不可写。分页还为写时复制、惰性分配和进程堆调整提供基础。

来源：mit-6.s081-f21-lecture-04-material@page:20, mit-6.s081-f21-lecture-04-material@page:21, mit-6.s081-f21-lecture-04-material@page:23, mit-6.s081-f21-lecture-04-material@page:25, mit-6.s081-f21-lecture-04-material@page:26

## 学习顺序

1. 核对前置知识、材料年代与本讲证据边界。（15 分钟）
2. 精读“虚拟内存的隔离间接层”与“Sv39 三级页表”，按来源页整理因果链。（35 分钟）
3. 比较“satp、页表遍历与 TLB”与“xv6 地址空间实践”，画出状态或控制流。（35 分钟）
4. 完成基础辨析与逐步追踪练习，并逐项回查页码。（35 分钟）
5. 完成机制分析与设计取舍练习，明确不变量和失败条件。（40 分钟）
6. 完成综合解释，使用来源页自检术语、边界和证据。（20 分钟）

## 练习

### practice-01 · recall

用三句话分别说明 CPU、MMU、页表在一次用户内存访问中的职责。

提示：从“软件只读写虚拟内存”和“只有内核配置 MMU”出发。

提交：三角色职责表。

来源：mit-6.s081-f21-lecture-04-material@page:6, mit-6.s081-f21-lecture-04-material@page:7

### practice-02 · trace

不做数值计算，按顺序描述 Sv39 三级页表查找：地址字段、逐级索引、最终 PTE 与页内偏移如何参与。

提示：用页面中的三级树与 9 位索引描述。

提交：5–7 步的查找流程。

来源：mit-6.s081-f21-lecture-04-material@page:9, mit-6.s081-f21-lecture-04-material@page:13, mit-6.s081-f21-lecture-04-material@page:14

### practice-03 · analysis

分析三种事件为何可能产生陈旧 TLB 项：删除 PTE、改变权限、切换页表根；分别写出若继续使用旧项的风险。

提示：风险可从错误映射或错误权限思考。

提交：三行事件—风险表。

来源：mit-6.s081-f21-lecture-04-material@page:16, mit-6.s081-f21-lecture-04-material@page:17, mit-6.s081-f21-lecture-04-material@page:18

### practice-04 · design

为 trampoline 映射做权限评审：根据材料判断执行与写权限，并解释为何相同虚拟位置对进程切换有用。

提示：不要扩展到材料未提供的完整 trap 实现。

提交：权限结论和两条设计理由。

来源：mit-6.s081-f21-lecture-04-material@page:23, mit-6.s081-f21-lecture-04-material@page:25

### practice-05 · synthesis

画出一个“进程访问—页表查找—TLB 命中/未命中—权限检查—可能页故障”的概念流程，并标出 xv6 切换进程时需改变的状态。

提示：只画概念组件，不写内核代码。

提交：流程图和 150 字说明。

来源：mit-6.s081-f21-lecture-04-material@page:7, mit-6.s081-f21-lecture-04-material@page:10, mit-6.s081-f21-lecture-04-material@page:16, mit-6.s081-f21-lecture-04-material@page:17, mit-6.s081-f21-lecture-04-material@page:23

## 限制

- 本单元只使用课程页表幻灯片，不包含 xv6 源码或页表实验答案。
- 第 22、24 页文本提取过少，不能单独支撑内核布局或 trampoline 主张；相关结论使用相邻的非空页面。
- 地址图的精确视觉布局仍需在独立审阅中核对；本候选不创建结构化公式字段。
