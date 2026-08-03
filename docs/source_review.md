# MIT 6.7960 Fall 2024 来源审核

审核日期：2026-08-01  
审核范围：Lecture 1、2、4、8、9  
结论：五份讲义可作为模板课程的候选索引来源，但必须在分块后进行人工抽检。

## 1. 来源与版本

用户确认原始 ZIP 来自 MIT OCW 的课程下载页：

<https://ocw.mit.edu/courses/6-7960-deep-learning-fall-2024/download/>

官方页面将课程标识为 MIT 6.7960、Deep Learning、Fall 2024，列出的教师为 Phillip Isola、Sara Beery 和 Jeremy Bernstein。下载页说明下载包与在线课程内容相同，但音视频材料需要另行下载；课程 PDF 位于解压包的 `static_resources` 目录。

本地 `site/data.json` 与官方页面的课程编号、标题、学期和教师一致。五份选定讲义的本地资源元数据均位于同一个离线课程包，文件名包含 `f24`，未发现其他学期的同名讲义进入选定范围。

## 2. 规范来源

| 讲次 | 官方资源标题 | 规范本地文件 | 页数 | 处理结论 |
| ---: | --- | --- | ---: | --- |
| 1 | Lecture 1: Introduction to Deep Learning | `site/static_resources/mit6_7960_f24_lec1.pdf` | 81 | 可处理，需人工抽检 |
| 2 | Lecture 2: How to Train a Neural Net | `site/static_resources/mit6_7960_f24_lec2.pdf` | 81 | 可处理，需人工抽检 |
| 4 | Lecture 4: Architectures for Grids | `site/static_resources/mit6_7960_f24_lec4.pdf` | 84 | 可处理，需人工抽检 |
| 8 | Lecture 8: Transformers | `site/static_resources/mit6_7960_f24_lec8.pdf` | 55 | 可处理，需人工抽检 |
| 9 | Lecture 9: Hacker's Guide to Deep Learning | `site/static_resources/mit6_7960_f24_lec9.pdf` | 72 | 可处理，需人工抽检 |

`site/resources/.../index.html` 和 `data.json` 是资源展示与元数据页面，不应与对应 PDF 重复索引。`site/pages/readings/data.json` 可以按 Session 标题切分，用于记录官方阅读要求；其中指向第三方网站的正文不属于本地课程包的已批准索引内容。

## 3. 完整性与可解析性

- 原始 ZIP 已通过 `unzip -tq` 完整性检查。
- ZIP SHA-256 为 `7a5e955d2dd633ec7160a1d581cc8c368566147e93dd9fad2cc923db912de56e`。
- 五份 PDF 均未加密，`pdfinfo` 可以读取页数和页面尺寸。
- `pdftotext` 对五份 PDF 均能输出文本，因此它们不是完全不可提取的纯图片扫描件。
- 能输出文本不等于解析质量合格。幻灯片可能包含隐藏文本、重复对象、公式、图表和非线性阅读顺序，必须在构建索引后按页人工抽检。

各文件的大小、页数和 SHA-256 已写入 CourseManifest。

## 4. 许可审核

五份讲义各自的 OCW 资源元数据均声明：

```text
https://creativecommons.org/licenses/by-nc-sa/4.0/
```

因此 Manifest 将这些讲义的许可状态记录为 `confirmed`。Syllabus、Readings 和课程元数据也在本地 OCW 元数据中声明同一许可。

这一结论只适用于对应的 OCW 页面或资源元数据所覆盖的内容。阅读页链接的外部教材、论文、博客及第三方网站可能采用不同许可，只登记链接，不抓取或索引第三方正文。讲义内嵌的第三方图片或引文仍需遵守其署名和权利说明；当前审核不推定这些元素可被独立重新分发。

## 5. 入库规则

允许进入首轮索引：

- 五份选定的讲义 PDF；
- Syllabus 页面；
- Readings 页面中与五个 Session 对应的 OCW 自有页面内容。

不进入首轮索引：

- 字幕、VTT、SRT；
- 视频文字稿和视频元数据；
- 音视频文件；
- 第三方阅读正文；
- 作业、附加文件和 Homework 5 Solutions；
- 其他未选讲次。

引用仅允许使用 PDF 页码或网页标题。不得生成时间戳引用。

## 6. 人工整理结论

- MIT 官方材料没有提供五个讲次各自的结构化前置知识；现已根据讲义内容人工整理，并以 `manually_curated_from_slides` 标记，避免误认为官方元数据。
- MIT 官方材料没有为五讲分别提供独立的一句话内容说明；现已根据讲义提纲人工整理，并以 `manually_curated_from_slides` 标记。
- Lecture 2 和 Lecture 8 已由用户确定为核心 Demo。
- PDF 的逐页文本质量、公式保真度和图表上下文尚未完成人工抽检。
