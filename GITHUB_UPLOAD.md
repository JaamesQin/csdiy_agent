# GitHub 上传选择

本文档定义当前工作区中哪些文件适合进入公开 GitHub 仓库。它是一次上传前的人工检查清单，不会自动执行 `git add`、提交或推送。

## 建议上传

这些文件构成可复现的代码、规范和经过审核的最小课程样例：

- 项目说明与决策：`README.md`、`PROJECT_STATUS.md`、`implementation_plan.md`、`plan_agent.md`、`proposal_agent.md`、`requirements.txt`、`pytest.ini`、`.env.example`、`.gitignore`。
- 应用代码：`app/` 中的源代码和静态页面；特别是 `app/retrieval/` 的解析、引用校验、练习点评和 StudyKit 渲染组件。
- 契约与工具：`schemas/`、`scripts/`、`tests/`、`evaluations/`。
- 公共文档：`docs/README.md`、`docs/platform_release.md`、`docs/platform_validation.md`、`docs/project_status.md`、`docs/material_gaps.md`、`docs/material_source_strategy.md`、`docs/source_review.md`、`docs/studykit_standard.md`、`docs/template_course_scope.md`。
- 课程元数据：`data/manifests/mit-6.7960-fall-2024.yaml`。它记录官方来源、课程版本、讲次范围和许可状态，不包含原始讲义。
- 已批准的黄金样例：`data/golden/` 下 Lecture 2 和 Lecture 8 的 YAML 及渲染版 Markdown。它们是经过人工审核的 StudyKit 示例，不是原始 PDF 的替代副本。

一个不含本地课程资料的最小候选集可以这样列出（命令只读取文件系统，不会修改 Git 索引）：

```bash
find app schemas scripts tests evaluations docs data/manifests data/golden \
  -type f ! -path '*/__pycache__/*' | sort
```

如果只希望先发布代码和规范，可以暂时省略 `data/golden`，但这会失去目前最重要的两个端到端教学样例。

## 默认不上传

以下内容应留在本地或私有存储中：

- `data/raw/`：从 MIT OCW 下载的 ZIP、PDF、HTML 和其他原始资源；其中包含约 235 MB 的课程下载包。
- `data/sources/`：从讲义抽取的页级 `chunks.jsonl`。它是可重建的派生索引，并且仍包含大量课程正文；公开仓库默认不保存。
- `.venv/`、`__pycache__/`、`.pytest_cache/`、覆盖率文件、运行时生成目录、`.env` 和任何密钥。
- 未来的 `data/private/`、`data/uploads/`、`storage/`、`artifacts/`：用户上传资料、私有派生索引、会话数据和临时产物。
- 根目录下的本地平台资料：`0720线上说明会.pptx`、`openai-compatible-agent-integration-guide.md`、`多模态附件对端接口文档.md`。这些文件已加入 `.gitignore`，不属于课程项目的公开输入。

`.gitignore` 已覆盖上述新生成目录；如果某个文件曾经被跟踪，忽略规则不会自动将它从 Git 索引移除。

## 需要发布前人工确认

1. `docs/references/智能共创平台-帮助文档.zip` 已经存在于历史 Git 索引中。它不是本次新增的公开项目资料；如果仓库要公开，必须先确认该平台文档的再分发权限。未获得确认前，不要把它视为本次上传白名单的一部分，也不要在本次操作中擅自删除历史文件。
2. MIT OCW 课程资源在当前 CourseManifest 中记录为 CC BY-NC-SA 4.0。公开发布 `data/golden/` 和相关说明时，应保留 MIT/OCW 来源链接、课程版本和许可声明，并避免把第三方图片、外部阅读材料或原始讲义重新打包进仓库。许可标记不自动覆盖讲义中的第三方内容。
3. `data/golden/` 是本项目制作的结构化教学样例；发布前应再次确认其中只有必要的短引用、页码引用和原创讲解，没有整页复制的讲义正文。

## 上传前检查

```bash
# 查看将被忽略的本地资料
git status --short --ignored

# 确认原始包和抽取文本不会被加入
git check-ignore -v data/raw/mit-6.7960/fall-2024/6.7960-fall-2024.zip \
  data/sources/mit-6.7960-fall-2024/lecture-02/chunks.jsonl

# 检查待发布文本中是否意外出现密钥或本地路径
rg -n --hidden -g '!data/raw/**' -g '!data/sources/**' \
  '(OPENAI_API_KEY|api[_-]?key|secret|password|/home/|/Users/)' .

# 检查空白和常见补丁错误
git diff --check
```

本清单只说明“适合进入 GitHub 的候选文件”，不等同于已经完成版权、隐私或安全审查；最终公开前仍需由仓库维护者确认上述人工检查项。
