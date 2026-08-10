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
        summary="对带语言标签的代码做确定性语法检查，并给出假设、验证步骤和下一次尝试。",
        usage=(
            "粘贴能复现问题的最小代码，并给 Markdown 围栏写明语言。",
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
        "unavailable",
        ("课程导航", "课程推荐", "选课", "学习路线"),
        "根据目标、基础和时间推荐课程与学习顺序。",
        (),
        (),
        ("正式 Catalog 与完整课程覆盖尚未接入在线编排。",),
        "当前可以先通过学习画像记录方向和时间。",
    ),
    CapabilitySpec(
        CapabilityId.STUDYKIT_LOOKUP,
        Intent.STUDYKIT_LOOKUP,
        "StudyKit 查询",
        "unavailable",
        ("studykit 查询", "studykit", "学习包", "学习包查询"),
        "查询已经审核的课程学习包。",
        (),
        (),
        ("当前黄金 StudyKit 只作为代码辅导的受控上下文读取。",),
        "可以在关联课程的代码问题中请求基于已审核材料的解释。",
    ),
    CapabilitySpec(
        CapabilityId.MATERIAL_QUESTION,
        Intent.MATERIAL_QUESTION,
        "材料问答",
        "unavailable",
        ("材料问答", "讲义问答", "材料查询"),
        "基于课程讲义和用户有权使用的材料回答问题并附来源。",
        (),
        (),
        ("权限过滤的 SourceChunk 检索尚未接入。",),
        "当前不要依赖 CoursePilot 回答尚未进入已审核 StudyKit 的课程事实。",
    ),
    CapabilitySpec(
        CapabilityId.CONCEPT_EXPLANATION,
        Intent.CONCEPT_EXPLANATION,
        "课程概念解释",
        "unavailable",
        ("课程概念解释", "概念解释"),
        "结合课程上下文分层解释概念。",
        (),
        (),
        ("通用概念解释尚未接入在线执行路径。",),
        "可以把相关代码与具体疑问交给静态代码辅导。",
    ),
    CapabilitySpec(
        CapabilityId.PRACTICE_SELECTION,
        Intent.PRACTICE_SELECTION,
        "练习选择",
        "unavailable",
        ("练习选择", "推荐练习"),
        "根据目标和当前进度选择已审核练习。",
        (),
        (),
        ("在线练习选择器尚未接入。",),
        "当前可记录学习目标，等待练习能力接入。",
    ),
    CapabilitySpec(
        CapabilityId.PRACTICE_FEEDBACK,
        Intent.PRACTICE_FEEDBACK,
        "练习反馈",
        "unavailable",
        ("练习反馈", "答案反馈", "作业反馈"),
        "评价当前练习回答并提供分层提示。",
        (),
        (),
        ("受控练习评估器尚未接入在线编排。",),
        "代码类尝试可以使用静态代码辅导，但不会获得完整答案。",
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
    r"(?:你|coursepilot).{0,8}(?:能做什么|支持什么功能|提供什么功能)|"
    r"what can you do|capabilit",
    re.IGNORECASE,
)


def available_capabilities() -> list[CapabilitySpec]:
    return [item for item in CAPABILITIES if item.availability == "available"]


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
                "````text",
                "请分析下面的代码，并说明诊断与验证步骤：",
                "```cpp",
                "int main( { return 0; }",
                "```",
                "````",
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
        command = "profile" if item.capability_id is CapabilityId.PROFILE_ANALYSIS else "code"
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
            "这里只列出已经上线的学习能力。课程导航、材料问答、练习反馈和学习复盘仍在建设中。",
            "也可以直接问“代码辅导支持什么语言”或“学习画像怎么用”。",
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
