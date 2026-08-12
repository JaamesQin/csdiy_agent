# MIT 6.S081 第 19 讲：虚拟机与 Dune

> 课程：mit-6.s081-fall-2021 · 版本：fall-2021 · 单元：lecture-19

## 学习目标

- 解释虚拟机、VMM、host 与 guest 的角色，以及虚拟机的隔离与资源整合动机。
- 追踪 trap-and-emulate 如何虚拟化特权寄存器、模式、页表与设备。
- 说明 VT-x root/non-root、VMCS 与 EPT 如何用硬件降低陷阱开销并保持隔离。
- 分析 Dune 如何把虚拟化硬件能力授予 Linux 进程，并评价沙箱、GC 与性能取舍。

## 前置知识

- 用户态、内核态与特权指令：知道特权状态不能直接交给不可信 guest，受限执行可用 trap 转交监控者。
- 页表地址转换：能区分虚拟地址、物理地址和页表根，便于理解 shadow page table 与 EPT。

## 核心概念

### 虚拟机与 VMM 分层

虚拟机模拟足以运行操作系统的计算机；VMM 位于真实硬件与 guest 之间，可以独立运行或依托 host OS。它让一台物理机运行多个 guest，提供比普通进程更强的隔离，并支持检查点、迁移和内核开发等用途。

来源：mit-6.s081-f21-lecture-19-material@page:1

### trap-and-emulate

guest 普通指令直接在 CPU 上执行以获得速度，guest 内核则运行在受限模式。执行特权指令时陷入 VMM，VMM 更新虚拟寄存器/模式，必要时转换成真实硬件操作。guest 页表可经 shadow page table 转换 guest VA 到 host PA，设备访问也可通过受控陷阱模拟。

来源：mit-6.s081-f21-lecture-19-material@page:1, mit-6.s081-f21-lecture-19-material@page:2

### VT-x 与 EPT 两级翻译

VT-x 提供 root/non-root 模式和 VMCS，使 guest 在 non-root 模式看到一套虚拟控制状态；进入/退出由专门机制管理。EPT 由 VMM 控制，把 guest 物理地址再映射到 host 物理地址，因此 guest 可维护自己的页表，同时仍被限制在 VMM 分配的内存内。

来源：mit-6.s081-f21-lecture-19-material@page:3

### Dune 的用户级特权

Dune 让普通 Linux 进程进入基于 VT-x 的模式，直接管理自己的页表、处理页故障并在 guest user/supervisor 间切换。笔记用浏览器插件沙箱和利用 PTE dirty bit 的并发垃圾回收说明收益，同时指出 VM 进入/退出、内核故障与 EPT TLB miss 带来的开销。

来源：mit-6.s081-f21-lecture-19-material@page:3, mit-6.s081-f21-lecture-19-material@page:4

## 学习顺序

1. 核对前置知识、材料年代与本讲证据边界。（15 分钟）
2. 精读“虚拟机与 VMM 分层”与“trap-and-emulate”，按来源页整理因果链。（35 分钟）
3. 比较“VT-x 与 EPT 两级翻译”与“Dune 的用户级特权”，画出状态或控制流。（35 分钟）
4. 完成基础辨析与逐步追踪练习，并逐项回查页码。（35 分钟）
5. 完成机制分析与设计取舍练习，明确不变量和失败条件。（40 分钟）
6. 完成综合解释，使用来源页自检术语、边界和证据。（20 分钟）

## 练习

### practice-01 · explanation

画出硬件、VMM、两个 guest OS 与各自进程的层次，并分别写出资源整合与隔离的一个理由。

提示：VMM 可独立或运行在 host OS 中；图中只需课程的抽象层。

提交：层次图和两条使用理由。

来源：mit-6.s081-f21-lecture-19-material@page:1

### practice-02 · trace

追踪 guest kernel 执行 sret、guest user 执行 ecall、guest kernel 读取 scause 三个事件：谁陷入 VMM、虚拟状态怎样变化、真实返回位置如何选择？

提示：不要写 VMM 代码，只列虚拟与真实状态转换。

提交：三事件状态表。

来源：mit-6.s081-f21-lecture-19-material@page:2

### practice-03 · analysis

比较 shadow page table 与 EPT：谁维护、翻译链是什么、guest 修改页表时 VMM 是否必须陷入？

提示：分别写 guest VA、guest PA、host PA。

提交：两列翻译链与控制权表。

来源：mit-6.s081-f21-lecture-19-material@page:2, mit-6.s081-f21-lecture-19-material@page:3

### practice-04 · design

用 Dune 插件沙箱案例设计一个权限边界：哪些页面设为 guest-user 可访问、系统调用由谁截获、底层 Linux 保留什么控制？

提示：只做概念沙箱，不提供绕过或攻击代码。

提交：权限图和三条边界规则。

来源：mit-6.s081-f21-lecture-19-material@page:4

### practice-05 · synthesis

为“软件 trap-and-emulate、VT-x 完整 VM、Dune 进程”制作决策矩阵，比较执行路径、隔离控制、所需 guest 修改与主要开销。

提示：结论仅限本课程笔记，不引入产品基准。

提交：四维决策矩阵和 180 字结论。

来源：mit-6.s081-f21-lecture-19-material@page:1, mit-6.s081-f21-lecture-19-material@page:2, mit-6.s081-f21-lecture-19-material@page:3, mit-6.s081-f21-lecture-19-material@page:4

## 限制

- 来源是 Fall 2021 官方课表显式链接的 2020 文本讲义，经确定性分页生成 PDF；页码是派生页码。
- VT-x、EPT 与 Dune 的描述是课程级概览，不是 Intel 手册、Dune 原论文或现代虚拟化系统的完整安全/性能规范。
- Dune 性能观察来自讲义对论文表格的转述；候选不把这些观察推广到其他工作负载。
