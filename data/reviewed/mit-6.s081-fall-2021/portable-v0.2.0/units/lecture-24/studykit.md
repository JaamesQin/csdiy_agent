# 当前研究：面向辐射故障的软件容错操作系统

> 课程：mit-6.s081-fall-2021 · 版本：fall-2021 · 单元：lecture-24

## 学习目标

- 构建辐射容错的端到端代理评估链。
- 分析冗余多线程的假设、可处理故障和脆弱点。
- 按设备能力选择 I/O 复制或验证路径。
- 解释任务约束如何支持内核最小化。
- 审查不可变调度和仅重启内核的依赖与待验证状态。

## 前置知识

- 进程隔离与上下文切换：知道进程地址空间、寄存器状态和调度器状态的职责。
- 故障模型与冗余：知道容错结论必须说明故障数量、相关性和检测点。
- 实验代理与功能验证：能区分注入故障、检测崩溃和验证系统需求。

## 核心概念

### 评估优先的故障注入

先定义量化成功，再在 QEMU 中用人工位翻转比较防御效果；它不是实际辐照或飞行测试。

来源：mit-6.s081-f21-lecture-24-material@page:10, mit-6.s081-f21-lecture-24-material@page:11, mit-6.s081-f21-lecture-24-material@page:12, mit-6.s081-f21-lecture-24-material@page:13

### 端到端验证平台

代表性软件和时间同步航天器仿真配合自动需求验证与可视化，测量功能影响；该软件不代表真实飞控。

来源：mit-6.s081-f21-lecture-24-material@page:16, mit-6.s081-f21-lecture-24-material@page:17, mit-6.s081-f21-lecture-24-material@page:19, mit-6.s081-f21-lecture-24-material@page:21, mit-6.s081-f21-lecture-24-material@page:24

### 冗余多线程

三副本可绕过一个崩溃/停滞副本，但依赖稀有随机单错假设；投票器和连接点仍脆弱。

来源：mit-6.s081-f21-lecture-24-material@page:30, mit-6.s081-f21-lecture-24-material@page:31, mit-6.s081-f21-lecture-24-material@page:32

### 复制与验证式 I/O

设备能力决定三端口、三消息或主体/校验和分工；校验失败或序列号可使错误包被拒绝。

来源：mit-6.s081-f21-lecture-24-material@page:36, mit-6.s081-f21-lecture-24-material@page:37, mit-6.s081-f21-lecture-24-material@page:39, mit-6.s081-f21-lecture-24-material@page:40

### 约束驱动的内核最小化

固定任务允许静态内存/页表、共享内存 IPC、用户态寄存器恢复和预置代码，把 API 缩到 wake_up；不能直接推广到通用 OS。

来源：mit-6.s081-f21-lecture-24-material@page:46, mit-6.s081-f21-lecture-24-material@page:48, mit-6.s081-f21-lecture-24-material@page:50, mit-6.s081-f21-lecture-24-material@page:52, mit-6.s081-f21-lecture-24-material@page:54

### scrubber 与 watchdog

scrubber 修复代码位但不撤销行为；外部 watchdog 在健康路径未运行时重置计算机。

来源：mit-6.s081-f21-lecture-24-material@page:42, mit-6.s081-f21-lecture-24-material@page:55

### 不可变调度与时间捐赠

固定表替代可变 runqueue，wake_up 可把时间直接交给目标或用户态 scheduler；该提案尚待验证。

来源：mit-6.s081-f21-lecture-24-material@page:55, mit-6.s081-f21-lecture-24-material@page:56, mit-6.s081-f21-lecture-24-material@page:57

### 仅重启内核

若 RAM 保留且编译期布局可定位状态，可重载内核而保留进程；讲者明确整体技术是否有效仍未知。

来源：mit-6.s081-f21-lecture-24-material@page:58, mit-6.s081-f21-lecture-24-material@page:59, mit-6.s081-f21-lecture-24-material@page:60, mit-6.s081-f21-lecture-24-material@page:61

## 学习顺序

1. 复习进程状态、故障模型与代理实验。（15 分钟）
2. 构建问题、故障注入和端到端验证链。（50 分钟）
3. 分析 RMT 故障矩阵和 I/O 防御选择。（55 分钟）
4. 映射内核职责并审查固定调度和仅重启内核。（50 分钟）
5. 总结已构建、候选机制、假设与仍未知。（10 分钟）

## 练习

### prac-01 · 入门

构建七节点评估链并标注代理测试边界。

提示：最终验证功能，不只观察崩溃。

提交：七节点证据链。

来源：mit-6.s081-f21-lecture-24-material@page:10, mit-6.s081-f21-lecture-24-material@page:11, mit-6.s081-f21-lecture-24-material@page:16, mit-6.s081-f21-lecture-24-material@page:21, mit-6.s081-f21-lecture-24-material@page:24

### prac-02 · 理解

填写三副本崩溃、停滞、相关故障、投票器和连接点故障矩阵。

提示：两个健康副本一致才能绕过一个故障。

提交：五行矩阵。

来源：mit-6.s081-f21-lecture-24-material@page:30, mit-6.s081-f21-lecture-24-material@page:31, mit-6.s081-f21-lecture-24-material@page:32

### prac-03 · 应用

为三类设备连接选择三端口、三消息或校验和 I/O 防御。

提示：设备投票能力和接口结构决定选择。

提交：三场景表。

来源：mit-6.s081-f21-lecture-24-material@page:36, mit-6.s081-f21-lecture-24-material@page:37, mit-6.s081-f21-lecture-24-material@page:39, mit-6.s081-f21-lecture-24-material@page:40

### prac-04 · 分析

把六项内核职责映射到静态或用户态替代，并标出 watchdog/scrubber 角色。

提示：固定任务集合是关键边界。

提交：六行职责迁移表。

来源：mit-6.s081-f21-lecture-24-material@page:42, mit-6.s081-f21-lecture-24-material@page:46, mit-6.s081-f21-lecture-24-material@page:48, mit-6.s081-f21-lecture-24-material@page:50, mit-6.s081-f21-lecture-24-material@page:52, mit-6.s081-f21-lecture-24-material@page:54

### prac-05 · 迁移

审查固定调度、时间捐赠和仅重启内核的假设、残余故障与证据缺口。

提示：研究者明确说尚不知道是否工作。

提交：四栏提案审计。

来源：mit-6.s081-f21-lecture-24-material@page:55, mit-6.s081-f21-lecture-24-material@page:56, mit-6.s081-f21-lecture-24-material@page:57, mit-6.s081-f21-lecture-24-material@page:58, mit-6.s081-f21-lecture-24-material@page:59, mit-6.s081-f21-lecture-24-material@page:60, mit-6.s081-f21-lecture-24-material@page:61

## 限制

- 材料明确标为进行中研究和初步结果；候选机制并未在本讲义中被充分验证。
- 评估使用人工位翻转、模拟处理器和简化代表性软件，不等于真实辐照飞行验证。
- RMT 依赖稀有随机单错假设；极小内核、固定调度和仅重启内核依赖固定任务、静态资源、RAM 保留等任务约束。
