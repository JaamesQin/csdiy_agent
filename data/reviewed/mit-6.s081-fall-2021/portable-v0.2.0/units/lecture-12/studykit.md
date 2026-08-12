# 调度协调、丢失唤醒与安全终止

> 课程：mit-6.s081-fall-2021 · 版本：fall-2021 · 单元：lecture-12

## 学习目标

- 解释 p->lock 为何跨 swtch 持有并由调度器释放。
- 诊断持有普通自旋锁时重调度造成的死锁。
- 比较忙等、阻塞和 channel 唤醒。
- 定位并修复丢失唤醒窗口。
- 解释 xv6 延迟终止和资源回收协议。

## 前置知识

- xv6 调度与 swtch：知道进程状态、内核线程栈和调度器栈会在切换时交接。
- 锁与竞态：理解检查条件和改变状态之间可被其他执行流插入。
- 进程生命周期：知道运行进程占用栈、上下文和退出状态。

## 核心概念

### 跨 swtch 的 p->lock

内核线程设置 RUNNABLE 后仍需保存上下文并离开自己的栈，所以 p->lock 跨 swtch 保持，直到调度器栈一侧释放。

来源：mit-6.s081-f21-lecture-12-material@page:3, mit-6.s081-f21-lecture-12-material@page:4

### 重调度时不得持有其他自旋锁

若线程持有普通锁进入 sched，之后运行的线程可能等待该锁，而原线程已无法继续释放它，形成死锁。

来源：mit-6.s081-f21-lecture-12-material@page:5, mit-6.s081-f21-lecture-12-material@page:6

### 阻塞式协调

等待磁盘、管道、超时或子进程等事件时，阻塞进入调度器可让 CPU 处理其他工作，优于持续空转。

来源：mit-6.s081-f21-lecture-12-material@page:7, mit-6.s081-f21-lecture-12-material@page:8, mit-6.s081-f21-lecture-12-material@page:9, mit-6.s081-f21-lecture-12-material@page:10

### sleep/wakeup 通道

sleep 在不透明 channel 上阻塞并接收保护条件的锁；wakeup 唤醒同 channel 的等待者，可能一次唤醒多个线程。

来源：mit-6.s081-f21-lecture-12-material@page:11, mit-6.s081-f21-lecture-12-material@page:16, mit-6.s081-f21-lecture-12-material@page:21, mit-6.s081-f21-lecture-12-material@page:22

### 丢失唤醒

若事件在等待者检查条件之后、标记 SLEEPING 之前发生，wakeup 看不到睡眠者。条件锁必须覆盖该窗口，sleep 内部原子地释放锁并睡眠，返回时再重获。

来源：mit-6.s081-f21-lecture-12-material@page:17, mit-6.s081-f21-lecture-12-material@page:18, mit-6.s081-f21-lecture-12-material@page:19, mit-6.s081-f21-lecture-12-material@page:20

### 协作式进程终止

kill 先设置标志，让目标在安全点自行停止；exit 留下 ZOMBIE 和退出状态，wait 读取状态后才释放 proc 资源。

来源：mit-6.s081-f21-lecture-12-material@page:23, mit-6.s081-f21-lecture-12-material@page:24

## 学习顺序

1. 复习调度上下文、锁和进程生命周期。（15 分钟）
2. 阅读第 2–6 页，画出 p->lock 交接和持锁重调度死锁。（25 分钟）
3. 完成锁交接图和死锁调试题。（25 分钟）
4. 阅读第 7–12、15–22 页，建立 sleep/wakeup 和条件锁协议。（35 分钟）
5. 比较忙等与阻塞，并调试 UART 丢失唤醒。（35 分钟）
6. 阅读第 23–24、26 页，整理延迟终止和回收。（15 分钟）
7. 完成跨核目标的终止时间线。（15 分钟）
8. 闭卷复述两条不变量：切换锁交接与条件锁防丢失唤醒，再核对终止顺序。（15 分钟）

## 练习

### prac-01 · 入门

在“内核线程→swtch→调度器线程”图上标出 p->lock 的获得、持续持有和释放位置，并写出每段保护的对象。

提示：RUNNABLE 状态先改变，但上下文和栈交接尚未结束。

提交：三节点时序图。

来源：mit-6.s081-f21-lecture-12-material@page:3, mit-6.s081-f21-lecture-12-material@page:4

### prac-02 · 理解

P1 获得锁 l 后调用 sched，P2 随后尝试获得 l。写出系统为什么挂起，并给出来源中的修复规则。

提示：谁还能释放 l？

提交：三步死锁链和一条规则。

来源：mit-6.s081-f21-lecture-12-material@page:5, mit-6.s081-f21-lecture-12-material@page:6

### prac-03 · 应用

比较管道为空时忙等与 sleep(chan, lock)：CPU 是否可做其他工作、事件如何标识、谁负责唤醒？

提示：channel 只标识条件，不解释条件。

提交：三维对照表。

来源：mit-6.s081-f21-lecture-12-material@page:7, mit-6.s081-f21-lecture-12-material@page:8, mit-6.s081-f21-lecture-12-material@page:9, mit-6.s081-f21-lecture-12-material@page:10, mit-6.s081-f21-lecture-12-material@page:11

### prac-04 · 分析

在 UART done 示例中指出中断触发会造成永久睡眠的精确窗口，并重写成使用条件锁的步骤顺序。

提示：窗口在 while 检查之后、p->state=SLEEPING 之前。

提交：错误交错和修复交错各一条。

来源：mit-6.s081-f21-lecture-12-material@page:16, mit-6.s081-f21-lecture-12-material@page:17, mit-6.s081-f21-lecture-12-material@page:18, mit-6.s081-f21-lecture-12-material@page:19, mit-6.s081-f21-lecture-12-material@page:20

### prac-05 · 迁移

目标进程可能在另一核心运行并持锁。设计一个只使用本讲机制的终止时间线，说明何时能读退出状态和释放 proc。

提示：外部请求、目标自停、父进程回收是三个阶段。

提交：三阶段时间线。

来源：mit-6.s081-f21-lecture-12-material@page:23, mit-6.s081-f21-lecture-12-material@page:24

## 限制

- 本学习包仅依据本讲公开幻灯片，不包括视频、读物、实验或作业。
- 第 13、14、25 页文本提取量低，未用于学习者事实、概念或练习。
- 这是模型生成的初稿，尚待独立语义审核和人工视觉复核，不替代原始资料。
