# MIT 6.S081 第 13 讲：实验问答 II——写时复制机制

> 课程：mit-6.s081-fall-2021 · 版本：fall-2021 · 单元：lecture-13

## 学习目标

- 解释 fork 后立即 exec 的模式为何使完整地址空间复制浪费资源。
- 描述 COW 页从只读共享到写故障私有副本的状态转换。
- 识别 COW 设计涉及的页表复制、故障处理、引用计数与内核写用户页四类责任。
- 比较每进程虚拟内存区域描述与全机物理页元数据/引用计数的作用。

## 前置知识

- fork 与 exec 的地址空间效果：知道 fork 创建子进程地址空间，而 exec 会用新程序替换当前地址空间。
- PTE 权限与页故障：能解释清除写权限会让写访问产生页故障，并能区分故障地址和原因。

## 核心概念

### 写时复制的动机

fork 若立即复制整个地址空间，而子进程随后 exec 丢弃它，会浪费内存与复制工作。COW 先让父子共享页面，把真正的复制推迟到某一方写入；同类思想也可用于保留唯一页面副本。

来源：mit-6.s081-f21-lecture-13-material@page:2, mit-6.s081-f21-lecture-13-material@page:3

### COW 页状态机

共享页先被标为不可写并注明 COW；写访问触发页故障。处理器提供故障地址、原因和指令位置，内核据此分配新页、复制旧内容，并把写入者的映射改为可写私有页。

来源：mit-6.s081-f21-lecture-13-material@page:4, mit-6.s081-f21-lecture-13-material@page:5, mit-6.s081-f21-lecture-13-material@page:6

### COW 跨模块责任

材料把责任分为建立共享只读映射、处理 COW 写故障、维护物理页引用计数，以及在内核向用户页写入前确保页面可写。引用计数用于判断一个物理页仍被多少映射持有。

来源：mit-6.s081-f21-lecture-13-material@page:7, mit-6.s081-f21-lecture-13-material@page:9

### 虚拟区域与物理页元数据

Linux 的虚拟内存区域列表描述每个进程的虚拟地址布局；全机 page 数组描述物理页，并为每页保存引用计数、锁和其他元数据。两者分别回答“这个进程映射什么”和“这个物理页被怎样共享”。

来源：mit-6.s081-f21-lecture-13-material@page:9, mit-6.s081-f21-lecture-13-material@page:10, mit-6.s081-f21-lecture-13-material@page:12

## 学习顺序

1. 核对前置知识、材料年代与本讲证据边界。（15 分钟）
2. 精读“写时复制的动机”与“COW 页状态机”，按来源页整理因果链。（35 分钟）
3. 比较“COW 跨模块责任”与“虚拟区域与物理页元数据”，画出状态或控制流。（35 分钟）
4. 完成基础辨析与逐步追踪练习，并逐项回查页码。（35 分钟）
5. 完成机制分析与设计取舍练习，明确不变量和失败条件。（40 分钟）
6. 完成综合解释，使用来源页自检术语、边界和证据。（20 分钟）

## 练习

### practice-01 · explanation

用 fork 后立即 exec 的事件序列说明：传统复制在哪一步发生、哪些数据随后被丢弃、COW 把成本推迟到什么事件。

提示：只写概念事件，不使用课程实验代码。

提交：五步事件时间线。

来源：mit-6.s081-f21-lecture-13-material@page:3

### practice-02 · trace

追踪父进程和子进程共享一页后，子进程首次写入的 PTE/物理页状态：写前、故障、复制、写后各是什么？

提示：把两边映射和物理页分开画。

提交：四阶段状态表。

来源：mit-6.s081-f21-lecture-13-material@page:4, mit-6.s081-f21-lecture-13-material@page:5, mit-6.s081-f21-lecture-13-material@page:6

### practice-03 · analysis

为建立共享、处理故障、释放页面、内核 copyout 四种场景分别写出引用计数必须防止的错误。

提示：只讨论责任和不变量，不列函数补丁。

提交：场景—风险—所需计数动作表。

来源：mit-6.s081-f21-lecture-13-material@page:7, mit-6.s081-f21-lecture-13-material@page:9

### practice-04 · comparison

比较 vmarea 列表与 page 数组：所有者范围、描述对象、COW 中能回答的问题各是什么？

提示：一个是 per-process，另一个是 per-machine。

提交：三维对照表。

来源：mit-6.s081-f21-lecture-13-material@page:9, mit-6.s081-f21-lecture-13-material@page:10, mit-6.s081-f21-lecture-13-material@page:12

### practice-05 · synthesis

设计一份不含代码的 COW 正确性检查清单：至少覆盖页权限、故障分类、复制后映射、引用计数和释放条件，并为每项标注来源页。

提示：检查清单用于概念评审，不能作为实验提交物。

提交：五项以上检查清单及页码。

来源：mit-6.s081-f21-lecture-13-material@page:3, mit-6.s081-f21-lecture-13-material@page:4, mit-6.s081-f21-lecture-13-material@page:6, mit-6.s081-f21-lecture-13-material@page:7, mit-6.s081-f21-lecture-13-material@page:9, mit-6.s081-f21-lecture-13-material@page:12

## 限制

- 本讲是 COW 实验问答材料；候选刻意省略第 8 页 solution walkthrough，并不提供 uvmcopy、usertrap、kalloc 或 copyout 的可提交实现。
- 第 8、11 页文本提取过少，只进入视觉审阅，不作为主张证据。
- 材料只给出 Linux 内存元数据的高层对照，不足以支持完整 Linux VM 内部结构。
