"""Single source of truth for learner-facing CoursePilot capabilities and help."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from app.agent.contracts import CapabilityId, Intent
from app.code_tutor.languages import grouped_languages


@dataclass(frozen=True, slots=True)
class CapabilitySpec:
    capability_id: CapabilityId
    intent: Intent
    title: str
    availability: Literal["available", "unavailable"]
    aliases: tuple[str, ...]
    summary: str
    usage: tuple[str, ...]
    examples: tuple[str, ...]
    limitations: tuple[str, ...]
    alternative: str | None = None


@dataclass(frozen=True, slots=True)
class CapabilityHelpMatch:
    handled: bool
    capability: CapabilitySpec | None = None
    unknown_topic: str | None = None


CAPABILITIES: tuple[CapabilitySpec, ...] = (
    CapabilitySpec(
        capability_id=CapabilityId.PROFILE_ANALYSIS,
        intent=Intent.PROFILE_ANALYSIS,
        title="学习画像",
        availability="available",
        aliases=("学习画像", "用户画像", "画像", "profile", "learner profile"),
        summary="记录用户明确提供的学习方向、目标、每周时间、技术基础和讲解偏好。",
        usage=(
            "直接陈述方向、时间或基础即可建立和更新画像。",
            "使用“查看我的学习画像”检查记录。",
            "使用“删除我的画像”清除当前身份下的画像事实。",
        ),
        examples=(
            "我想学习系统方向，每周可以投入 6 小时，而且有 C++ 基础。",
            "查看我的学习画像",
            "删除我的画像",
        ),
        limitations=(
            "只保存最小学习事实和短证据摘录，不保存完整对话、代码或 traceback。",
            "网页登录按账号隔离；API Key 客户端只使用 legacy 逻辑身份。",
        ),
    ),
    CapabilitySpec(
        capability_id=CapabilityId.CODE_TUTORING,
        intent=Intent.CODE_TUTORING,
        title="多语言静态代码辅导",
        availability="available",
        aliases=(
            "多语言代码辅导",
            "静态代码辅导",
            "代码辅导",
            "代码诊断",
            "代码分析",
            "code tutoring",
            "code tutor",
            "debug",
            "code",
        ),
        summary="从自然语言或常见代码块中识别代码，做确定性语法检查并给出验证步骤。",
        usage=(
            "直接粘贴能复现问题的最小代码即可；Markdown 围栏和语言标签是可选的。",
            "同时提供期望行为、实际行为和原始工具链错误输出。",
            "根据“确定性静态诊断 → 诊断假设 → 验证步骤”逐层缩小问题。",
        ),
        examples=(
            "请分析：\n```cpp\nint main( { return 0; }\n```",
            "请分析这个 CUDA kernel，并结合 nvcc 的第一条 error 给验证步骤。",
        ),
        limitations=(
            "只做静态分析，不编译、不执行代码，ran_code 始终为 false。",
            "不会代写可直接提交的完整课程作业答案。",
        ),
    ),
    CapabilitySpec(
        CapabilityId.COURSE_NAVIGATION,
        Intent.COURSE_NAVIGATION,
        "课程导航",
        "available",
        ("课程导航", "课程推荐", "选课", "学习路线", "course"),
        "检索现有 CSDIY 课程表，并分别标明目录、离线制作和在线 StudyKit 状态。",
        (
            "给出学习方向，获取最多 3 门确定性排序的候选课程。",
            "输入学校名、课程号或课程名进行精确查询。",
            "输入“有哪些课程”查看最多 5 门目录候选。",
        ),
        (
            "推荐一门操作系统课程。",
            "查看 MIT 6.7960。",
        ),
        (
            "多数目录课程尚未完成独立分类审核或在线 StudyKit 导入。",
            "目录收录不代表课程内容已经可以在线问答。",
        ),
    ),
    CapabilitySpec(
        CapabilityId.STUDYKIT_LOOKUP,
        Intent.STUDYKIT_LOOKUP,
        "StudyKit 查询",
        "available",
        ("studykit 查询", "studykit", "学习包", "学习包查询", "studykit lookup"),
        "查询已经审核的课程学习包。",
        (
            "指定课程、版本和讲次查看学习目标、概念、练习和官方来源。",
            "只指定课程时会列出当前在线可用讲次。",
        ),
        ("查看 MIT 6.7960 第 2 讲的 StudyKit。",),
        (
            "当前在线覆盖 9 个 approved build、220 份 archive StudyKit；MIT 6.7960 "
            "Lecture 2/8 golden 仍作为重复身份的安全回退。",
            "未通过完整 build、逐题审计或身份一致性门禁的归档记录不会上线。",
            "其余离线产物仍需修复门禁问题并重新人工批准。",
        ),
    ),
    CapabilitySpec(
        CapabilityId.MATERIAL_QUESTION,
        Intent.MATERIAL_QUESTION,
        "材料问答",
        "available",
        ("材料问答", "讲义问答", "材料查询", "material"),
        "基于当前已审核 StudyKit 的公开摘要回答问题并附页码依据。",
        (
            "先指定在线可用的课程和讲次，再询问材料中的概念或页码。",
            "回答只使用 StudyKit 中带页码的概念、提纲和误区说明。",
        ),
        ("MIT 6.7960 第 2 讲的讲义里，反向传播和梯度下降有什么区别？",),
        (
            "SourceChunk 检索尚未上线，不能回答 StudyKit 未覆盖的任意原文细节。",
            "证据不足时会明确拒绝猜测。",
        ),
    ),
    CapabilitySpec(
        CapabilityId.CONCEPT_EXPLANATION,
        Intent.CONCEPT_EXPLANATION,
        "课程概念解释",
        "available",
        ("课程概念解释", "概念解释", "concept"),
        "结合课程上下文分层解释概念。",
        (
            "指定课程讲次和概念名称。",
            "结果按定义、直觉、公式或说明、常见误区和来源组织。",
        ),
        ("解释 MIT 6.7960 第 2 讲的反向传播。",),
        ("只解释当前 StudyKit 已覆盖且有可核查页码的概念。",),
    ),
    CapabilitySpec(
        CapabilityId.PRACTICE_SELECTION,
        Intent.PRACTICE_SELECTION,
        "练习选择",
        "available",
        ("练习选择", "推荐练习", "practice"),
        "选择已审核练习，并用一次受控模型调用把题面整理得更明确。",
        (
            "指定在线可用课程讲次，并可选择概念、推导、代码阅读、调试或迁移题。",
            "当前对话默认不重复展示同一道题，也可以用 practice ID 指定重看。",
            "模型会明确已知条件、问题、约束和交付格式；失败时自动回退已审核原题。",
        ),
        ("给我一道 MIT 6.7960 第 2 讲的调试练习。",),
        (
            "首次展示不包含提示、预期证据或评分标准。",
            "当前只允许不改变考查目标的结构化重写；证据型变式尚未启用。",
            "练习历史不跨会话保存。",
        ),
    ),
    CapabilitySpec(
        CapabilityId.PRACTICE_FEEDBACK,
        Intent.PRACTICE_FEEDBACK,
        "练习反馈",
        "available",
        ("练习反馈", "答案反馈", "作业反馈", "feedback"),
        "评价当前练习回答并提供分层提示。",
        (
            "直接提交当前答案即可；客户端未回传上下文时再补充 practice ID。",
            "结果只指出正确点、一个关键遗漏、下一层提示和相关页码。",
        ),
        ("点评 practice-concept-01。我的答案是……",),
        (
            "不保存答案，不累计分数、正确率或整体掌握度。",
            "模型不可用时不做粗略判分，只返回原题提示和补充要求。",
            "不会提供可直接提交的完整作业答案。",
        ),
    ),
    CapabilitySpec(
        CapabilityId.GENERAL_ASSISTANCE,
        Intent.GENERAL_ASSISTANCE,
        "通用学习问答",
        "available",
        ("通用学习问答", "通用问答", "学习建议", "general assistance"),
        "回答未被专用能力覆盖的计算机学习、学习方法、目标梳理和一般学习沟通问题。",
        (
            "直接用自然语言描述学习困惑，无需先选择功能或使用固定格式。",
            "CoursePilot 会优先使用更合适的课程、材料、练习或代码专用能力。",
        ),
        (
            "我最近同时学很多内容，有点乱，应该怎么调整？",
            "怎样安排一周的复习和练习？",
        ),
        (
            "通用回答只属于一般知识，不会冒充课程材料或给出虚构页码。",
            "明显无关学习的问题会被引导回学习场景。",
            "不会提供可直接提交的完整课程作业答案，也不会声称运行代码。",
        ),
    ),
    CapabilitySpec(
        CapabilityId.LEARNING_REVIEW,
        Intent.LEARNING_REVIEW,
        "学习复盘",
        "unavailable",
        ("学习复盘", "学习总结"),
        "根据经过确认的学习信息生成复盘和下一步建议。",
        (),
        (),
        ("学习活动记录与复盘编排尚未接入。",),
        "当前可以查看学习画像中的已确认目标和基础。",
    ),
    CapabilitySpec(
        CapabilityId.GENERATION_STATUS,
        Intent.GENERATION_STATUS,
        "生成状态查询",
        "unavailable",
        ("生成状态查询", "生成状态", "任务状态"),
        "查询受控 StudyKit authoring 任务状态。",
        (),
        (),
        ("普通对话没有后台 authoring 任务访问权。",),
        "生成任务必须通过受控开发者或后台入口管理。",
    ),
)


_BY_ID = {item.capability_id: item for item in CAPABILITIES}
_BY_INTENT = {item.intent: item for item in CAPABILITIES}
_ALIASES = sorted(
    ((alias.casefold(), item) for item in CAPABILITIES for alias in item.aliases),
    key=lambda pair: len(pair[0]),
    reverse=True,
)
_HELP_SIGNAL = re.compile(
    r"是什么|什么意思|怎么用|如何使用|如何用|用法|使用方式|"
    r"支持(?:什么|哪些).{0,6}(?:语言|输入|功能)?|有哪些(?:功能|能力)|"
    r"介绍(?:一下)?|说明(?:一下)?|\bhelp\b",
    re.IGNORECASE,
)
_GENERAL_HELP = re.compile(
    r"有哪些.{0,6}(?:功能|能力)|有什么.{0,6}(?:功能|能力)|"
    r"(?:列出|查看).{0,4}(?:功能|能力)|功能列表|能力列表|"
    r"(?:你|coursepilot).{0,8}(?:能.{0,6}做什么|支持什么功能|提供什么功能)|"
    r"what can you do|capabilit",
    re.IGNORECASE,
)
_CAPABILITY_AVAILABILITY_QUESTION = re.compile(
    r"^(?:请问)?(?:你|coursepilot)?\s*"
    r"(?:可以|可不可以|能|能不能|能够|会|会不会|是否|可否|支持)"
    r".{0,32}(?:吗|么|呢|\?|？)$",
    re.IGNORECASE,
)
_CODE_LIKE_INPUT = re.compile(r"```|[{};]|\n|traceback|\berror\b", re.IGNORECASE)


def available_capabilities() -> list[CapabilitySpec]:
    return [item for item in CAPABILITIES if item.availability == "available"]


def match_unavailable_capability_request(text: str) -> CapabilitySpec | None:
    """Match an explicit unavailable capability request, excluding help/status questions."""

    if match_capability_help(text).handled:
        return None
    normalized = text.strip().casefold().replace("_", " ").replace("-", " ")
    aliases = sorted(
        (
            (alias.casefold().replace("_", " ").replace("-", " "), capability)
            for capability in CAPABILITIES
            if capability.availability == "unavailable"
            for alias in (capability.capability_id.value, *capability.aliases)
        ),
        key=lambda item: len(item[0]),
        reverse=True,
    )
    return next(
        (capability for alias, capability in aliases if alias in normalized),
        None,
    )


def capability_by_id(capability_id: CapabilityId) -> CapabilitySpec:
    return _BY_ID[capability_id]


def capability_for_intent(intent: Intent) -> CapabilitySpec | None:
    return _BY_INTENT.get(intent)


def match_capability_help(text: str) -> CapabilityHelpMatch:
    normalized = text.strip().casefold()
    if normalized in {"--help", "/help", "help", "帮助", "功能", "功能列表", "能力列表"}:
        return CapabilityHelpMatch(handled=True)

    command = re.fullmatch(r"(?:/help|help)\s+(.+)", normalized, re.IGNORECASE)
    if command:
        topic = command.group(1).strip()[:64]
        capability = _find_topic(topic)
        return CapabilityHelpMatch(True, capability, None if capability else topic)

    suffix = re.fullmatch(r"(.+?)\s+--help", normalized, re.IGNORECASE)
    if suffix:
        topic = suffix.group(1).strip()[:64]
        capability = _find_topic(topic)
        return CapabilityHelpMatch(True, capability, None if capability else topic)

    if (
        len(normalized) <= 80
        and not _CODE_LIKE_INPUT.search(normalized)
        and _CAPABILITY_AVAILABILITY_QUESTION.fullmatch(normalized)
    ):
        capability = _find_in_text(normalized)
        if capability is not None:
            return CapabilityHelpMatch(True, capability)

    if _HELP_SIGNAL.search(normalized):
        capability = _find_in_text(normalized)
        if capability is not None:
            return CapabilityHelpMatch(True, capability)

    if _GENERAL_HELP.search(normalized):
        return CapabilityHelpMatch(handled=True)
    return CapabilityHelpMatch(handled=False)


def render_capability_help(
    capability_id: CapabilityId | None = None,
    *,
    unknown_topic: str | None = None,
) -> str:
    if capability_id is None:
        return _render_overview(unknown_topic)
    capability = capability_by_id(capability_id)
    lines = [f"## {capability.title}"]
    if capability.availability == "unavailable":
        lines.extend(
            [
                "",
                "**状态：尚未接入在线能力。**",
                "",
                capability.summary,
                "",
                "### 当前限制",
                *[f"- {item}" for item in capability.limitations],
            ]
        )
        if capability.alternative:
            lines.extend(["", "### 当前替代方式", capability.alternative])
        lines.extend(["", "输入 `/help` 查看当前已经上线的功能。"])
        return "\n".join(lines)

    lines.extend(["", capability.summary, "", "### 怎么用"])
    lines.extend(f"- {item}" for item in capability.usage)
    if capability.capability_id is CapabilityId.CODE_TUTORING:
        lines.extend(["", "### 支持语言"])
        for group, languages in grouped_languages():
            names = "、".join(item.display_name for item in languages)
            suffix = "（模型静态建议）" if group == "课程专用 DSL" else ""
            lines.append(f"- **{group}**：{names}{suffix}")
        lines.extend(
            [
                "",
                "### 输入示例",
                "",
                "请分析下面的代码，并说明诊断与验证步骤：",
                "",
                "```cpp",
                "int main( { return 0; }",
                "```",
                "",
                "同时附上期望行为、实际行为和编译器/解释器的原始错误输出。",
            ]
        )
    elif capability.examples:
        lines.extend(["", "### 示例"])
        lines.extend(f"- {item}" for item in capability.examples)
    lines.extend(["", "### 限制"])
    lines.extend(f"- {item}" for item in capability.limitations)
    lines.extend(["", "输入 `/help` 返回当前功能总览。"])
    return "\n".join(lines)


def _render_overview(unknown_topic: str | None) -> str:
    lines: list[str] = []
    if unknown_topic:
        safe_topic = unknown_topic.replace("`", "'")
        lines.extend([f"没有找到帮助主题 `{safe_topic}`。", ""])
    lines.extend(["## CoursePilot 当前功能", ""])
    for index, item in enumerate(available_capabilities(), start=1):
        command = {
            CapabilityId.PROFILE_ANALYSIS: "profile",
            CapabilityId.CODE_TUTORING: "code",
            CapabilityId.COURSE_NAVIGATION: "course",
            CapabilityId.STUDYKIT_LOOKUP: "studykit",
            CapabilityId.MATERIAL_QUESTION: "material",
            CapabilityId.CONCEPT_EXPLANATION: "concept",
            CapabilityId.PRACTICE_SELECTION: "practice",
            CapabilityId.PRACTICE_FEEDBACK: "feedback",
            CapabilityId.GENERAL_ASSISTANCE: "general",
        }.get(item.capability_id, item.capability_id.value)
        lines.extend(
            [
                f"{index}. **{item.title}**",
                f"   {item.summary}",
                f"   详细用法：`/help {command}`",
            ]
        )
    lines.extend(
        [
            "",
            "这里只列出已经上线的学习能力。SourceChunk 检索、私有材料和学习复盘仍在建设中。",
            "也可以直接问“材料问答怎么用”“代码辅导支持什么语言”或“学习画像怎么用”。",
        ]
    )
    return "\n".join(lines)


def _find_topic(topic: str) -> CapabilitySpec | None:
    normalized = topic.strip().casefold().replace("_", " ").replace("-", " ")
    for alias, capability in _ALIASES:
        alias_normalized = alias.replace("_", " ").replace("-", " ")
        if normalized in {alias_normalized, capability.capability_id.value.replace("_", " ")}:
            return capability
    return None


def _find_in_text(text: str) -> CapabilitySpec | None:
    return next((capability for alias, capability in _ALIASES if alias in text), None)
