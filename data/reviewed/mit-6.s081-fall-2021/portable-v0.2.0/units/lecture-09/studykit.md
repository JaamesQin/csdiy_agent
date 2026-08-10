# 中断、设备并发与轮询

> 课程：mit-6.s081-fall-2021 · 版本：fall-2021 · 单元：lecture-09

## 学习目标

- 构建中断来源、控制器与 CPU 控制状态的分层模型。
- 追踪一次控制台字符输出与 UART 完成中断。
- 用生产者—消费者模型解释环形缓冲区。
- 识别中断竞态并选择范围正确的同步手段。
- 比较中断与轮询在不同事件频率下的成本。

## 前置知识

- 系统调用与陷阱入口：知道用户或内核执行可被统一陷阱机制打断。
- 基本并发：能理解两段代码交错访问共享状态会产生不同结果。
- 缓冲区与队列：知道生产者和消费者可通过有限缓冲解耦速度。

## 核心概念

### 异步中断

设备、计时器或其他核心可以在软件运行期间请求处理；UART 以中断通知内核收发进展。

来源：mit-6.s081-f21-lecture-09-material@page:2, mit-6.s081-f21-lecture-09-material@page:4, mit-6.s081-f21-lecture-09-material@page:6

### PLIC 与核心本地中断控制器

PLIC 接收外部设备中断并分发到核心；核心本地控制器处理每核计时器和核间相关事件。

来源：mit-6.s081-f21-lecture-09-material@page:3, mit-6.s081-f21-lecture-09-material@page:6

### 中断控制状态

sie 选择中断类型，sstatus.SIE 总体开关监管态中断，sip 表示等待类型，scause 记录原因，stvec 指向处理入口。

来源：mit-6.s081-f21-lecture-09-material@page:7, mit-6.s081-f21-lecture-09-material@page:8

### UART 中断路径

shell 的 write 经 sys_write、filewrite、uartputc 和 uartstart 把字符交给 UART；设备完成后经 PLIC 触发 CPU 保存状态并跳到 stvec。

来源：mit-6.s081-f21-lecture-09-material@page:9, mit-6.s081-f21-lecture-09-material@page:10, mit-6.s081-f21-lecture-09-material@page:11, mit-6.s081-f21-lecture-09-material@page:12

### 生产者—消费者环形缓冲区

shell 产生字符、UART 消费字符；环形缓冲区吸收速度差，底半部中断处理唤醒等待空间的上半部。

来源：mit-6.s081-f21-lecture-09-material@page:14, mit-6.s081-f21-lecture-09-material@page:15

### 中断竞态与本地原子性

中断可发生在相邻指令之间。intr_off 可让当前核心的一段代码不被中断，但另一核心仍可能并发访问，所以跨核共享数据需要锁。

来源：mit-6.s081-f21-lecture-09-material@page:17, mit-6.s081-f21-lecture-09-material@page:18, mit-6.s081-f21-lecture-09-material@page:19, mit-6.s081-f21-lecture-09-material@page:20

### 中断与轮询

事件稀少时轮询浪费周期；事件高频时每次中断的固定开销可能过大，现代系统常结合中断、批量工作和轮询。

来源：mit-6.s081-f21-lecture-09-material@page:21, mit-6.s081-f21-lecture-09-material@page:22

## 学习顺序

1. 完成并发与陷阱入口前置检查。（15 分钟）
2. 阅读第 2–8 页，画出中断来源、控制器和寄存器层次。（25 分钟）
3. 完成来源—控制—入口链。（15 分钟）
4. 阅读第 9–15 页，追踪“$”输出和生产者—消费者缓冲。（30 分钟）
5. 完成三泳道时序图和缓冲角色表。（30 分钟）
6. 阅读第 17–22 页，分析竞态、原子区和轮询取舍。（25 分钟）
7. 完成竞态调试与两种负载决策题。（25 分钟）
8. 闭卷复述从 UART 事件到处理完成的全链，并回查每个同步边界。（15 分钟）

## 练习

### prac-01 · 入门

把 UART 外部中断、PLIC、sie/sstatus、scause 和 stvec 排成“来源→允许→原因→入口”链。

提示：PLIC 是设备与核心之间的分发层。

提交：一条带箭头的五节点链。

来源：mit-6.s081-f21-lecture-09-material@page:3, mit-6.s081-f21-lecture-09-material@page:4, mit-6.s081-f21-lecture-09-material@page:6, mit-6.s081-f21-lecture-09-material@page:7, mit-6.s081-f21-lecture-09-material@page:8

### prac-02 · 理解

从 printf 输出“$”开始，排序到 CPU 跳入 stvec 的关键动作，并标出用户、内核、设备三方。

提示：先走 write 路径，再让 UART 并发完成发送。

提交：三泳道时序图。

来源：mit-6.s081-f21-lecture-09-material@page:9, mit-6.s081-f21-lecture-09-material@page:10, mit-6.s081-f21-lecture-09-material@page:11, mit-6.s081-f21-lecture-09-material@page:12

### prac-03 · 应用

在控制台输出环形缓冲区中标注生产者、消费者、缓冲区满时等待者以及唤醒者。

提示：上半部运行在调用进程上下文；下半部由中断触发。

提交：角色表和一条唤醒关系。

来源：mit-6.s081-f21-lecture-09-material@page:14, mit-6.s081-f21-lecture-09-material@page:15

### prac-04 · 分析

共享变量 x 的普通代码先判断 x==0 再调用 f，中断代码把 x 设为 1。指出竞态窗口，并分别说明单核中断与另一核心并发时该用什么保护。

提示：“检查”和“使用”之间可以被打断。

提交：竞态说明加两种保护选择。

来源：mit-6.s081-f21-lecture-09-material@page:17, mit-6.s081-f21-lecture-09-material@page:18, mit-6.s081-f21-lecture-09-material@page:19, mit-6.s081-f21-lecture-09-material@page:20

### prac-05 · 迁移

为“每秒偶发一次的键盘事件”和“每微秒可产生一次事件的高速设备”分别选择以中断或轮询为主，并说明固定开销。

提示：比较空闲时是否白白检查，以及每次事件是否都承担陷阱成本。

提交：两个场景各三句决策说明。

来源：mit-6.s081-f21-lecture-09-material@page:21, mit-6.s081-f21-lecture-09-material@page:22

## 限制

- 本学习包仅依据本讲公开幻灯片，不包括视频、读物、实验或作业。
- 第 16 页文本提取量低，未用于学习者事实、概念或练习。
- 这是模型生成的初稿，尚待独立语义审核和人工视觉复核，不替代原始资料。
