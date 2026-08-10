# GDB, calling conventions and stack frames RISC-V

> 课程：mit-6.s081-fall-2021 · 版本：fall-2021 · 单元：lecture-05

## 学习目标

- 能够启动并组织一个 QEMU/GDB 双终端调试会话。
- 能够根据问题选择源码级或指令级单步以及合适的运行终点。
- 能够组合普通断点、条件断点与观察点定位首次异常状态变化。
- 能够用 print、x、寄存器、栈帧和 backtrace 收集可复核证据。
- 能够识别本材料对 RISC-V 调用约定覆盖不足并避免无来源扩写。

## 前置知识

- 命令行与 make：能够在不同终端启动进程并阅读构建输出。
- C 函数调用：理解函数、局部变量和返回的基本概念。
- 源码与机器指令的区别：知道一行源码可能对应多条指令即可。

## 核心概念

### 调试会话编排

课程环境通过 .gdbinit 连接 QEMU；QEMU 与 GDB 分别运行在两个终端中。

来源：mit-6.s081-f21-lecture-05-material@page:11

### 源码级与指令级单步

step/next 按源码行前进并在是否进入调用上不同；stepi/nexti 在机器指令粒度工作。

来源：mit-6.s081-f21-lecture-05-material@page:15

### 运行终点

continue 等待断点或中断，finish 等待当前函数返回，advance 前进到指定位置。

来源：mit-6.s081-f21-lecture-05-material@page:19

### 条件化停止

条件断点只在谓词满足时停下，适合跳过大量无关迭代。

来源：mit-6.s081-f21-lecture-05-material@page:22, mit-6.s081-f21-lecture-05-material@page:25

### 观察点

观察点把停止条件绑定到表达式值变化或具体地址内容变化，可用于捕获首次写坏状态。

来源：mit-6.s081-f21-lecture-05-material@page:27

### 类型化与原始检查

print 计算 C 表达式并按类型展示，x 按格式读取原始内存；二者回答不同问题。

来源：mit-6.s081-f21-lecture-05-material@page:32

### 调用上下文

寄存器、当前栈帧和 backtrace 共同描述程序为何到达当前执行位置。

来源：mit-6.s081-f21-lecture-05-material@page:35

## 学习顺序

1. 建立双终端 QEMU/GDB 环境与命令自助入口。（20 分钟）
2. 比较源码级/指令级单步与三种运行终点。（30 分钟）
3. 练习普通断点、条件断点和观察点。（35 分钟）
4. 学习 print、x、寄存器、栈帧和回溯。（30 分钟）
5. 了解 TUI、set、符号切换与手册查询。（25 分钟）
6. 完成独立调试剧本并按证据链自评。（40 分钟）

## 练习

### p1 · 基础

给出“进入函数内部”和“跳过函数调用”两个目标，分别选择 GDB 命令并解释选择。

提示：在 step 与 next 之间比较，再考虑是否需要指令级版本。

提交：命令选择表。

来源：mit-6.s081-f21-lecture-05-material@page:15

### p2 · 基础到应用

为一个执行很久但最终会返回的函数设计最少命令数的运行方案，比较 continue、finish 和 advance。

提示：先写清楚希望在哪个语义事件停下。

提交：三个候选命令的适用条件与最终选择。

来源：mit-6.s081-f21-lecture-05-material@page:19

### p3 · 诊断

某变量只在第 1000 次循环后变坏。设计条件断点与观察点组合，说明每一步怎样缩小范围。

提示：条件断点定位时间窗口，观察点定位写入者。

提交：可执行的调试步骤和预期证据。

来源：mit-6.s081-f21-lecture-05-material@page:22, mit-6.s081-f21-lecture-05-material@page:25, mit-6.s081-f21-lecture-05-material@page:27

### p4 · 应用

面对一个未知指针，分别设计 print 与 x 的检查，并说明何时还要查看寄存器、栈帧和回溯。

提示：先问“我要类型化值还是原始字节”。

提交：检查清单及每项可能排除的假设。

来源：mit-6.s081-f21-lecture-05-material@page:32, mit-6.s081-f21-lecture-05-material@page:35

### p5 · 综合

编写一个与任何课程实验无关的调试剧本：从可复现症状开始，使用断点、观察点、状态检查和回溯建立证据链。

提示：可用自编十行 C 程序；不要复述讲义中的 Homework solution。

提交：症状、假设、命令日志、证据和结论。

来源：mit-6.s081-f21-lecture-05-material@page:13, mit-6.s081-f21-lecture-05-material@page:22, mit-6.s081-f21-lecture-05-material@page:27, mit-6.s081-f21-lecture-05-material@page:32, mit-6.s081-f21-lecture-05-material@page:35, mit-6.s081-f21-lecture-05-material@page:42

## 限制

- 准备 PDF 标注为 6.828 Fall 2018，且主要内容是 GDB；它不足以支持官方 2021 单元标题中的 RISC-V 调用约定与栈帧细节。
- 第 2–10 页含旧 Homework solution 展开，已从学习内容和练习中排除。
- 示例中的 JOS、x86 地址和 symbol-file 路径只说明 GDB 机制，不应视为 2021 xv6/RISC-V 的配置事实。
