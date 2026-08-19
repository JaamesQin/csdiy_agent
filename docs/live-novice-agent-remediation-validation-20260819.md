# 自然语言鲁棒性整改与端到端验证（2026-08-19）

## 结论

在线后端不再把 Markdown、课程 ID、practice ID 或固定命令格式作为普通用户请求的前置条件。
DeepSeek 负责统一理解当前请求、历史指代、纠正、多意图和候选 Artifact；确定性代码只负责身份、
证据、权限、持久化和可执行状态校验。模型候选不能创造课程、讲次、练习、页码或代码字符。

## 整改边界

- 一次 TaskPlan 调用同时输出 `ModelTurnUnderstanding` 与最多 4 个有界任务。
- 当前消息中的代码按字符区间回绑；历史代码不会与新代码拼接，始终保持 `ran_code=false`。
- 课程候选由 Catalog 解析；序号按签名上下文中的真实展示顺序解析。推荐、查询和选择分别使用
  `course_mode`，避免“选第一门”重新生成另一组课程。
- 讲次序号按已审核 StudyKit 的真实顺序解析。例如 CS61C 当前第一份在线 StudyKit 是
  `lecture-02`，不会凭字符串规则写成不存在的 `lecture-01`。
- StudyKit、材料、概念和练习只能进入 Store 校验通过的课程/讲次。方向不明确时先回到 Catalog，
  不执行无边界全库查询。
- 画像操作必须有当前消息中的准确证据。明确陈述使用 add/replace/delete，推断使用 infer；
  课程号或拼写候选不能保存成学习方向，不可用讲次不能保存为 active unit。
- 模型 JSON 的数字 task ID、别名字段、空 Artifact 等表示漂移可以机械修复；事实冲突不会被修复成
  “看起来正确”的事实。
- DeepSeek 对 408/429/5xx/网络错误使用指数退避；空内容、非法 JSON 和长度截断继续在严格解析前
  受控重试，最终失败时透明降级。

## 用户视角验收

重点旅程包括：无围栏 C++/Python、连续换语言、画像+选课+代码多意图、课程拼写容错、课程列表
序号、中文讲次、整讲摘要、自然练习答案、继续提示、画像纠正与删除、缺失上一题上下文。

整改前的典型失败是“请放进 Markdown 围栏”“请重复 practice ID”“这题”误入 authoring 状态、
`cs6lc` 被保存成学习方向，以及“第一门”脱离上一轮列表。整改后，相同输入直接得到能力回答；
上下文确实缺失时，只要求补充缺失对象，并明确无需特定格式。

完整新手探索执行 24 条旅程、60 次真实 DeepSeek 调用；随后对人工审查发现的 5 条残余旅程再次
执行 11 次真实调用并全部闭环。完整回复只写入 `/tmp` 报告，不进入仓库或画像数据库。

## 开发者视角验收

离线门禁：

```bash
.venv/bin/pytest -q
```

真实后端 E2E：

```bash
.venv/bin/python scripts/run_live_backend_e2e.py --suite full \
  --report /tmp/coursepilot-live-remediation-final.json
```

完整新手探索：

```bash
.venv/bin/python scripts/run_live_novice_exploration.py \
  --report /tmp/coursepilot-live-novice-remediation-final.json
```

高风险路径用 `--repeat 3` 重复执行，覆盖代码替换、课程序号、练习连续反馈、画像纠正、概念追问、
课程拼写、操作系统首讲和整讲摘要。pytest 使用 fake `StructuredModel` 且不访问网络；上述两个
credentialed 脚本才使用真实 `DEEPSEEK_API_KEY`。

最终后端报告通过全部 25 个业务场景（另含 provider preflight）：49/49 次真实调用成功，
共 62,856 tokens；报告 SHA-256 为
`8aee1442947d3cb1a0bb603f165bf17601335ec25526331185270a55023ad2f6`。完整 24 旅程报告用于
人工发现残余问题；最后 4 条闭环复测 9/9 次真实调用成功，报告 SHA-256 为
`2337006b6acd866fb81c880eb01e7e6f22a87fff2593394d0b0d9750572d83b4`。

## 仍然保留的限制

- 课程推荐的第一名可能只有目录信息而没有在线 StudyKit；系统会透明说明，不能用模型补材料。
- 完全缺失题面、课程或上一轮签名状态时必须要求补充，鲁棒性不等于猜测事实。
- SourceChunk 私有检索、MaterialSet 权限和学习复盘仍未上线。
