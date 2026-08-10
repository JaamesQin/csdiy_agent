# C and gdb

> 课程：mit-6.s081-fall-2021 · 版本：fall-2021 · 单元：lecture-02

## 学习目标

- 能够依据存储区和生命周期分析 C 程序中的指针安全问题。
- 能够用数组连续布局和指针算术追踪地址与元素访问。
- 能够说明声明、定义、头文件与源文件的协作边界。
- 能够为一个可复现的故障选择合适的 GDB 运行控制与检查命令。
- 能够把 C 级内存推理与调试器观察结果结合成可验证的故障假设。

## 前置知识

- 基本命令行操作：能够在两个终端中运行构建工具和调试器。
- 一种高级语言的函数与控制流：理解变量、函数调用、条件和循环即可；本单元会突出 C 的差异。
- 十六进制与字节：能把地址视为数值并按字节解释内存。

## 核心概念

### 显式内存生命周期

C 把栈、静态区和堆的生命周期暴露给程序员；局部栈对象在函数返回后不能继续作为有效对象使用。

来源：mit-6.s081-f21-lecture-02-material@page:13, mit-6.s081-f21-lecture-02-material@page:33, mit-6.s081-f21-lecture-02-material@page:34

### 指针与内存安全

指针描述内存位置并允许直接读写；这种能力同时带来 use-after-free、double-free 和越界访问等风险。

来源：mit-6.s081-f21-lecture-02-material@page:14, mit-6.s081-f21-lecture-02-material@page:15

### 数组的连续布局

数组元素在内存中连续排列，索引访问可理解为对首地址做按元素大小缩放的偏移后解引用。

来源：mit-6.s081-f21-lecture-02-material@page:22, mit-6.s081-f21-lecture-02-material@page:23

### 声明与定义

声明告知名称和类型，定义则分配对象或给出函数实现；共享声明通常放在头文件中。

来源：mit-6.s081-f21-lecture-02-material@page:37, mit-6.s081-f21-lecture-02-material@page:47

### C 字符串契约

C 字符串是以空字符结尾的字符数组；缺少终止符会使依赖它的字符串函数越界读取。

来源：mit-6.s081-f21-lecture-02-material@page:45, mit-6.s081-f21-lecture-02-material@page:57

### 断点、条件断点与观察点

断点按位置暂停，条件断点只在谓词成立时暂停，观察点则在表达式或地址内容变化时暂停。

来源：mit-6.s081-f21-lecture-02-material@page:89, mit-6.s081-f21-lecture-02-material@page:92, mit-6.s081-f21-lecture-02-material@page:94

### 状态检查与栈回溯

GDB 可用 print/x 检查有类型表达式或原始内存，并用寄存器、栈帧和 backtrace 重建执行上下文。

来源：mit-6.s081-f21-lecture-02-material@page:99, mit-6.s081-f21-lecture-02-material@page:102

## 学习顺序

1. 完成十六进制、字节和函数调用的前置检查。（20 分钟）
2. 学习 C 的存储区、指针、数组和生命周期。（35 分钟）
3. 梳理声明、头文件、字符串和常用内存接口。（25 分钟）
4. 完成指针追踪与生命周期诊断练习。（30 分钟）
5. 建立 GDB 运行控制、断点、观察点和状态检查工具箱。（35 分钟）
6. 完成综合调试案例并用证据表自评。（35 分钟）

## 练习

### p1 · 基础

给出一个含局部变量、静态变量和 malloc 对象的短函数，画出三类对象的生命周期，并标出函数返回后仍有效的对象。

提示：先按栈、静态区、堆分类，再判断释放责任。

提交：一张带时间轴的内存区域图。

来源：mit-6.s081-f21-lecture-02-material@page:13, mit-6.s081-f21-lecture-02-material@page:14

### p2 · 基础到应用

对一个五元素 int 数组，分别用下标与指针算术表达第三个元素，并解释地址增量为何不是一个字节。

提示：把指针加一解释为移动一个所指类型的大小。

提交：两种等价表达式与三句话解释。

来源：mit-6.s081-f21-lecture-02-material@page:22, mit-6.s081-f21-lecture-02-material@page:23

### p3 · 诊断

审查一个返回局部数组地址的辅助函数，指出失效时刻，并提出不泄漏内存的接口修正方案。

提示：先处理对象所有权，再决定由谁分配、由谁释放。

提交：问题定位、修正后的接口契约和释放责任说明。

来源：mit-6.s081-f21-lecture-02-material@page:33, mit-6.s081-f21-lecture-02-material@page:34, mit-6.s081-f21-lecture-02-material@page:35

### p4 · 应用

为“循环到第 500 次后某字段偶尔被改写”的故障设计 GDB 调试计划。必须说明条件断点、观察点、单步策略和待检查状态。

提示：不要一开始逐行执行；先用条件缩小时间窗口，再监视写入。

提交：按命令类别组织的调试步骤和每步预期证据。

来源：mit-6.s081-f21-lecture-02-material@page:82, mit-6.s081-f21-lecture-02-material@page:89, mit-6.s081-f21-lecture-02-material@page:92, mit-6.s081-f21-lecture-02-material@page:94, mit-6.s081-f21-lecture-02-material@page:99, mit-6.s081-f21-lecture-02-material@page:102

### p5 · 综合

构造一个不依赖课程实验答案的小型 C 内存错误案例，并写出从症状、假设、断点到证据确认的完整调试记录模板。

提示：案例只需十余行；重点是证据链而非复杂代码。

提交：案例代码、假设表、调试命令与判定标准。

来源：mit-6.s081-f21-lecture-02-material@page:14, mit-6.s081-f21-lecture-02-material@page:57, mit-6.s081-f21-lecture-02-material@page:78, mit-6.s081-f21-lecture-02-material@page:89, mit-6.s081-f21-lecture-02-material@page:94, mit-6.s081-f21-lecture-02-material@page:99

## 限制

- 材料由 2021 C 讲义与一份标注为 2018 的 GDB 讲义合并；GDB 命令概念可用，但其中 JOS/x86 示例的历史语境不应当作 2021 xv6/RISC-V 的配置事实。
- 第 69–77 页含旧作业解答，已从内容与练习证据中排除。
- 本单元没有保留结构化公式；所有位运算与地址关系均以可追溯文字和代码概念表达。
