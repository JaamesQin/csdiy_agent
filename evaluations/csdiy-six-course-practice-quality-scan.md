# Six-course practice quality scan

更新时间：2026-08-11

本记录是对当前六门旧 standard 输出的静态风险筛查，不是新的 StudyKit 质量通过报告。
它只用于把 registry 中的旧 `complete` 状态降回待校准状态；没有删除或修改任何旧 build。

## Scope

扫描的 build roots：

- `ucb-cs61a-spring-2026/cdcdeec7d13ce7404a8e858bf13ebd99c5b147e44096692a5c8710277c126079`
- `ucb-cs188-spring-2026/d46e9dcb62c47f3132888db581e6b83d9fda8ac4fa6ffbe422be180ac9b00328`
- `mit-6-042j-spring-2024/89a0616b96b49b2060735c20c2ba17616905b29c357aa0d8c4daa42f624ba485`
- `ucb-cs168-spring-2026/af46bdaf7cdaacb8e3953525eaaf44e21af406b6785e5c10c596e330c6c3d04c`
- `ucb-cs186-spring-2026/48e2739450f3054f2eb5afff8681f06f7966bcf5b8e9075f988dfc1e132dd565`
- `ucb-cs61c-spring-2026/680f533e4e516db281471d88598fa24a41d72af7fd45344988a1dfb8a9aab028`

静态扫描结果：161 个 unit、573 道 practice。保守的字符串筛查发现 141 道题包含
“围绕……设计/说明/举例/例子”一类开放模板，503 道题的 question 字符串少于 80
个字符。两项都是风险信号而不是语义证明；它们与人工抽查共同说明旧输出不能作为新
内容对齐合同的通过证据。

人工确认的代表问题包括：

- `ucb-cs61a-spring-2026` Lecture 10 的练习只要求围绕 “Iterators and Generators”
  设计例子，没有给出可直接求解的输入、状态或预期输出；
- `ucb-cs61a-spring-2026` Lecture 13 的 `oop-motivation`、`class-instance` 和
  `lookup` 练习同样把完整题面设计责任交给学习者，和材料页的具体内容没有形成可检查
  的任务闭环。

这些问题不是 PDF/chunk 缺失造成的：上述单元存在可读且有具体内容的 source chunks。
因此旧 build 的 Schema、引用和独立 audit 记录不能关闭 `practice_quality_review`。

## Decision

六门课程的旧输出保留为诊断/比较材料，不作为新 build 的复用 checkpoint：

`practice_quality_review.status = needs_repair`
`practice_quality_review.next_action = rebuild_content_grounded_practice`

下一步必须按 `docs/csdiy-quality-calibration-sample.md` 先生成六个新样本，并由不同作者和
审计者完成校准。该记录没有授权开始生成。
