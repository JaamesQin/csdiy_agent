# 系统调用进入与退出：从 ecall 到内核分派

> 课程：mit-6.s081-fall-2021 · 版本：fall-2021 · 单元：lecture-06

## 学习目标

- 比较内联汇编与独立汇编文件中的工具支持和维护责任。
- 识别关键 RISC-V 特权寄存器与返回指令的职责。
- 按四阶段追踪一次 xv6 系统调用进入内核。
- 阅读 trapframe/trampoline 片段并解释状态保存和环境切换。
- 用隔离、透明性、灵活性和性能评估入口机制。

## 前置知识

- RISC-V 调用约定：知道 a0–a7 是参数/返回值相关寄存器，并能读基本汇编。
- 页表与特权级：理解用户页表、内核页表及用户态/监管态的隔离目标。
- xv6 系统调用概览：知道 write 从用户函数进入内核实现，细节将在本讲建立。

## 核心概念

### 内联汇编与独立汇编源文件

内联汇编通过输出、输入和 clobber 约束让编译器继续协助分配与保存寄存器；独立 .S 文件直接指定寄存器，调用约定和保存责任由程序员承担。

来源：mit-6.s081-f21-lecture-06-material@page:3, mit-6.s081-f21-lecture-06-material@page:4, mit-6.s081-f21-lecture-06-material@page:5, mit-6.s081-f21-lecture-06-material@page:7

### RISC-V 特权状态

satp 指向页表根，stvec 指定陷阱入口，sepc 保存用户 PC，sscratch 提供转换临时状态；CSR 指令访问这些寄存器，sret 返回用户空间。

来源：mit-6.s081-f21-lecture-06-material@page:8, mit-6.s081-f21-lecture-06-material@page:9

### 用户态到内核态转换

转换必须保存用户寄存器和 PC，建立内核栈与页表，再进入能区分系统调用、故障和中断的内核 C 代码，同时保证返回后用户状态不被意外扰动。

来源：mit-6.s081-f21-lecture-06-material@page:11, mit-6.s081-f21-lecture-06-material@page:13, mit-6.s081-f21-lecture-06-material@page:14, mit-6.s081-f21-lecture-06-material@page:15

### ecall 包装约定

包装函数把系统调用号放入 a7、参数放入 a0–a6，并从 a0 取返回值。幻灯片限定 ecall 本身只切换到监管态并跳到 stvec，其他转换由软件完成。

来源：mit-6.s081-f21-lecture-06-material@page:16, mit-6.s081-f21-lecture-06-material@page:17, mit-6.s081-f21-lecture-06-material@page:18

### 蹦床页与陷阱帧

trampoline 先借助 sscratch 取得 trapframe，保存用户寄存器，再从 trapframe 恢复内核栈、hart 标识、usertrap 地址和内核页表。

来源：mit-6.s081-f21-lecture-06-material@page:19, mit-6.s081-f21-lecture-06-material@page:20, mit-6.s081-f21-lecture-06-material@page:21, mit-6.s081-f21-lecture-06-material@page:22, mit-6.s081-f21-lecture-06-material@page:23

### 陷阱分派

usertrap 读取 scause 区分陷阱类型；系统调用路径再用 trapframe 中的 a7 值索引内核函数表。

来源：mit-6.s081-f21-lecture-06-material@page:25, mit-6.s081-f21-lecture-06-material@page:26, mit-6.s081-f21-lecture-06-material@page:27

## 学习顺序

1. 完成前置检查，复习调用约定、页表与特权级。（15 分钟）
2. 阅读第 2–9 页，整理两种汇编接口和关键特权状态。（25 分钟）
3. 完成汇编比较和特权寄存器配对。（20 分钟）
4. 阅读第 11–18 页，画出系统调用函数到 ecall 的最小硬件边界。（30 分钟）
5. 对 write 路径进行阶段排序并逐项核查。（25 分钟）
6. 阅读第 19–23、25–27 页，追踪 trapframe、页表切换和分派。（25 分钟）
7. 完成代码注释与硬件/软件权衡题。（25 分钟）
8. 闭卷重画四阶段路径，标注每个状态的保存位置和下一跳，再回看来源页纠错。（15 分钟）

## 练习

### prac-01 · 入门

比较内联汇编 w_satp 示例和 .S 文件中的 csrwsatp, a1：谁选择寄存器、谁负责保存、编译器能否重排？

提示：查看内联汇编的约束列表与 .S 文件说明。

提交：三维对照表。

来源：mit-6.s081-f21-lecture-06-material@page:3, mit-6.s081-f21-lecture-06-material@page:4, mit-6.s081-f21-lecture-06-material@page:5, mit-6.s081-f21-lecture-06-material@page:6, mit-6.s081-f21-lecture-06-material@page:7

### prac-02 · 理解

将 satp、stvec、sepc、sscratch 分别配对到页表根、陷阱入口、被保存的用户 PC 和临时交换空间。

提示：每个寄存器只写本讲给出的主要职责。

提交：四行配对及一句用途。

来源：mit-6.s081-f21-lecture-06-material@page:8, mit-6.s081-f21-lecture-06-material@page:9

### prac-03 · 应用

把 write 系统调用的以下动作排序并归入四阶段：设置 a7、执行 ecall、保存 trapframe、换内核页表、进入 usertrap、用 a7 选择 sys_write。

提示：先按系统调用函数→trampoline→usertrap→具体实现分组。

提交：有编号的阶段表，每个动作只出现一次。

来源：mit-6.s081-f21-lecture-06-material@page:14, mit-6.s081-f21-lecture-06-material@page:15, mit-6.s081-f21-lecture-06-material@page:16, mit-6.s081-f21-lecture-06-material@page:18, mit-6.s081-f21-lecture-06-material@page:19, mit-6.s081-f21-lecture-06-material@page:23, mit-6.s081-f21-lecture-06-material@page:25, mit-6.s081-f21-lecture-06-material@page:26

### prac-04 · 分析

阅读第 21–23 页：为 kernel_sp、kernel_trap、kernel_satp 以及用户 a0 写出“从哪里加载、用于什么”的注释。

提示：区分 trapframe 的内核元数据区与用户寄存器区。

提交：四条伪代码注释。

来源：mit-6.s081-f21-lecture-06-material@page:20, mit-6.s081-f21-lecture-06-material@page:21, mit-6.s081-f21-lecture-06-material@page:22, mit-6.s081-f21-lecture-06-material@page:23

### prac-05 · 迁移

有人建议让 ecall 自动保存所有寄存器并固定内核栈和页表，以缩短软件路径。依据本讲，分别写出一个可能简化点和一个会失去的设计灵活性；不要断言该方案一定更快。

提示：第 18 页给出硬件保持简单的理由和若干软件优化方向。

提交：两栏权衡说明，各不超过三句。

来源：mit-6.s081-f21-lecture-06-material@page:13, mit-6.s081-f21-lecture-06-material@page:18, mit-6.s081-f21-lecture-06-material@page:27

## 限制

- 本学习包仅依据本讲公开幻灯片，不包括视频、读物、实验或作业。
- 第 10 页文本提取量低，第 24 页含重复层清理；两页未用于学习者事实、概念或练习。
- 这是模型生成的初稿，尚待独立语义审核和人工视觉复核，不替代原始资料。
