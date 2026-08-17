# StudyKit Generator

StudyKit Generator 是一个面向 Codex 的离线课程内容编排 Skill。它可以把经过授权的 PDF、扫描页、图片、Office 文档、网页、Markdown、文本、表格、结构化数据和源代码整理成带来源引用、可审查且可验证的中文自学包（StudyKit）。

本 README 面向使用者和维护者，提供快速入口。Codex 的完整执行流程、质量门槛与安全约束以 [SKILL.md](SKILL.md) 为准。

## 适用场景

- 将一门课程的讲义、网页和补充材料整理成若干学习单元。
- 从扫描版或数学内容较多的 PDF 生成保留页码和公式出处的 StudyKit。
- 批量处理多门课程，并为每个单元生成独立、可验证的构建产物。
- 恢复中断的构建，或验证已有的 StudyKit 候选产物。

它不适合即时课程问答、绕过访问控制、生成可直接提交的作业答案，或在在线聊天接口中同步运行。

## 快速开始

在 Codex 中提供课程材料、输出位置和必要的偏好，例如：

```text
使用 $studykit-generator 处理 syllabus.html、lectures/ 和 labs/，
识别课程与单元，并在 outputs/course-build 中生成中文 StudyKit。
```

如果没有显式指定，Skill 默认使用：

- 语言：`zh-CN`
- 每单元目标学习时间：180 分钟
- 交付策略：`draft`
- 资料范围：`private`
- 质量模式：`standard`

输入材料必须由使用者拥有处理权限。Skill 不会绕过登录、付费墙、DRM、robots 规则、加密或网络限制。

## 工作流程

一次完整构建通常包含以下阶段：

1. 检查本地解析与渲染环境。
2. 清点并摄取全部输入材料，生成带锚点的来源分块。
3. 识别课程、版本与有序单元，并建立可复现的构建指纹。
4. 为每个单元依次生成证据计划、学习内容和练习流程。
5. 独立审查引用、事实、公式、练习质量和学术诚信。
6. 执行有限的定向修复，组装候选 StudyKit。
7. 完成 Schema、引用锚点、语义一致性及人工审查门槛验证。
8. 输出 JSON、YAML、Markdown 和验证报告。

确定性脚本负责摄取、校验、最终组装和产物核对；内容编写及语义审查由 Codex 按 [SKILL.md](SKILL.md) 中的契约完成。

## 质量模式

- `fast`：减少编排轮次，但仍保留独立审查和全部必要检查点。
- `standard`：经过离线评估的默认模式，在质量与成本之间取平衡。
- `strict`：使用更严格的独立审查；未解决的阻断项不得交付成功结果。

质量模式只影响执行策略，不会放宽来源引用、公式核对或练习语义审查要求。详细规则见 [references/quality-modes.md](references/quality-modes.md)。

## 主要产物

每个成功单元包含：

```text
01-evidence-plan.json
02-learning-content.json
03-practice-flow.json
04-quality-audit.json
05-studykit.candidate.json
05-studykit.json
studykit.yaml
studykit.md
validation.json
review-validation.json
review-plan.json
metrics.json
```

只有引用锚点有效、候选与最终格式语义一致、验证报告成功，并满足对应质量模式的审查要求时，单元才可标记为成功。

## 工具与依赖

核心流程使用 Python。以下工具是可选增强项，不是运行前提：

- PyMuPDF：PDF 文本提取与页面渲染。
- Tesseract：扫描页 OCR。
- LibreOffice：Office 文档转换。
- MinerU：复杂 PDF 布局解析。

检查当前环境：

```bash
python scripts/check_environment.py
```

常用的确定性操作示例：

```bash
python scripts/ingest_materials.py \
  --material /path/to/lecture.pdf \
  --material /path/to/notes.md \
  --output-dir /path/to/build/ingestion \
  --scope private \
  --owner-id local-user \
  --render-pdf auto

python scripts/validate_artifacts.py \
  --chunks /path/to/build/ingestion/chunks.jsonl \
  --studykit /path/to/build/units/unit-01/05-studykit.candidate.json \
  --report /path/to/build/units/unit-01/validation.candidate.json
```

这些脚本不能单独替代内容编写、逐项练习审查或视觉公式核对。更多调用示例见 [references/examples.md](references/examples.md)。

## 目录结构

```text
studykit-generator/
├── SKILL.md          # Codex 的权威执行规范
├── README.md         # 面向人类的使用与维护入口
├── agents/           # Skill 的界面元数据
├── assets/           # Schema、模板和图标
├── references/       # 按需读取的详细契约与说明
├── scripts/          # 摄取、规划、校验及打包工具
└── tests/            # Skill 脚本与策略测试
```

## 开发与验证

在仓库根目录运行：

```bash
.venv/bin/pytest -q skills/studykit-generator/tests
```

修改工作流时，应同步检查 [SKILL.md](SKILL.md)、相关模板、Schema、引用文档及测试。不要在 README 中复制完整的执行规则；README 负责导航和概览，`SKILL.md` 始终是行为契约的权威来源。

## 进一步阅读

- [执行契约](references/contract.md)
- [输入格式与解析策略](references/formats.md)
- [质量模式](references/quality-modes.md)
- [并行执行规则](references/parallelism.md)
- [使用示例](references/examples.md)
