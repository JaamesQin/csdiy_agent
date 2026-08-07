from app.generation.evidence import build_evidence_bundle
from app.generation.prompts import (
    FINAL_OUTPUT_PROTOCOLS,
    OUTPUT_PREFIXES,
    PROMPT_VERSION,
    STAGE_TASKS,
    SYSTEM_PROMPT,
    build_stage_repair_prompt,
    build_stage_prompt,
)
from app.generation.result import GenerationIssue, GenerationStage
from tests.generation.helpers import generation_request, source_chunks


def test_stage_prompts_assign_translation_to_content_only() -> None:
    evidence = STAGE_TASKS[GenerationStage.EVIDENCE]
    content = STAGE_TASKS[GenerationStage.CONTENT]
    practice = STAGE_TASKS[GenerationStage.PRACTICE]
    audit = STAGE_TASKS[GenerationStage.AUDIT]

    assert "不负责翻译" in evidence
    assert "本阶段唯一负责" in content
    assert "概念范围和抽象层级" in content
    assert "复用 LearningContent" in practice
    assert "term_en、term_zh" in audit
    assert "含义不对应" in audit


def test_prompts_are_subject_agnostic_and_use_dynamic_controls() -> None:
    evidence = STAGE_TASKS[GenerationStage.EVIDENCE]
    content = STAGE_TASKS[GenerationStage.CONTENT]
    practice = STAGE_TASKS[GenerationStage.PRACTICE]
    audit = STAGE_TASKS[GenerationStage.AUDIT]
    combined = SYSTEM_PROMPT + "\n".join(STAGE_TASKS.values())

    assert PROMPT_VERSION == "studykit-staged-v0.5-007"
    assert "行内公式写成 $...$" in content
    assert "行内 $...$、独立公式 $$...$$" in practice
    assert "evidence control" in evidence
    assert "required_action" in content
    assert "复制其 opportunity 的 control_ids" in practice
    assert "动态审核清单" in audit
    for course_specific_term in (
        "Jacobian",
        "行向量",
        "列向量",
        "转置",
        "forward pass",
        "QKV",
        "ReLU",
        "VC dimension",
        "Transformer",
        "Gauss-Newton",
    ):
        assert course_specific_term not in combined
    assert "高风险声明" in evidence
    assert "符号角色" in content
    assert "logical_error" in audit
    assert "unanswerable_practice" in audit
    assert "可信管线" in audit
    assert "拆成两个不同 ID" in audit
    assert "scope=stage_internal" in audit
    assert "不存在的新 concept" in audit


def test_evidence_and_practice_prompts_enforce_atomic_lightweight_assessment() -> None:
    evidence = STAGE_TASKS[GenerationStage.EVIDENCE]
    practice = STAGE_TASKS[GenerationStage.PRACTICE]

    assert "原子性" in evidence
    assert "能否独立评估或独立补救" in evidence
    assert "至少使用两种有证据支持的题型" in evidence
    assert "一个主要学习成果和少数紧邻动作" in practice
    assert "最多要求三个独立的学习者动作" not in practice


def test_prompts_allow_cs_when_supported_without_forcing_it_on_other_domains() -> None:
    evidence = STAGE_TASKS[GenerationStage.EVIDENCE]
    content = STAGE_TASKS[GenerationStage.CONTENT]
    practice = STAGE_TASKS[GenerationStage.PRACTICE]
    audit = STAGE_TASKS[GenerationStage.AUDIT]

    assert "CS 资料可优先发现" in evidence
    assert "非 CS 课程不得沿用" in content
    assert "CS 课程可使用有来源依据" in practice
    assert "非 CS 资料中凭空出现" in audit
    assert "simple 的题目数量不设上限" in practice
    assert "不要按 simple 题目数量判错" in audit
    assert "complex_numeric_practice" in audit
    assert "仅凭 LearningContent" in practice
    assert "完整多阶段前后向" not in practice


def test_all_stage_prompts_end_with_nonempty_final_json_protocol() -> None:
    request = generation_request()
    evidence = build_evidence_bundle(request, source_chunks(count=1))
    issue = GenerationIssue(
        stage="test",
        code="test",
        message="repair the candidate",
    )

    assert "只有 reasoning_content" in SYSTEM_PROMPT
    assert set(OUTPUT_PREFIXES) == {
        GenerationStage.EVIDENCE,
        GenerationStage.CONTENT,
        GenerationStage.PRACTICE,
        GenerationStage.AUDIT,
    }
    for stage, prefix in OUTPUT_PREFIXES.items():
        prompt = build_stage_prompt(stage, request, evidence, {})
        repair_prompt = build_stage_repair_prompt(
            stage,
            request,
            evidence,
            {},
            {},
            (issue,),
        )
        protocol = FINAL_OUTPUT_PROTOCOLS[stage]
        assert prompt.endswith(protocol)
        assert repair_prompt.endswith(protocol)
        assert repair_prompt.index("上一版候选 JSON") < repair_prompt.index(
            "最终输出协议"
        )
        assert f"message.content 必须直接以 {prefix} 开始" in prompt
        assert "输出结构示例" not in prompt
