from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from typing import Any

from app.generation.generator import StudyKitGenerator, _studykit_title
from app.generation.model import (
    ModelAPIError,
    ModelResponse,
    ModelResponseError,
)
from app.generation.result import GenerationStage, GenerationStatus
from app.retrieval.render import render_studykit_markdown
from tests.generation.helpers import (
    evidence_plan,
    generation_request,
    learning_content,
    model_response,
    practice_flow,
    quality_audit,
    source_chunks,
)


class FakeModel:
    def __init__(self, responses: list[ModelResponse | Exception]) -> None:
        self.responses = list(responses)
        self.prompts: list[tuple[str, str]] = []
        self.options: list[dict[str, Any]] = []

    async def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        thinking_enabled: bool | None = None,
        max_tokens: int | None = None,
        timeout_seconds: float | None = None,
    ) -> ModelResponse:
        self.prompts.append((system_prompt, user_prompt))
        self.options.append(
            {
                "thinking_enabled": thinking_enabled,
                "max_tokens": max_tokens,
                "timeout_seconds": timeout_seconds,
            }
        )
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def successful_responses() -> list[ModelResponse]:
    return [
        model_response(evidence_plan()),
        model_response(learning_content()),
        model_response(practice_flow()),
        model_response(quality_audit()),
    ]


def audit_issue(
    *,
    target_stage: str,
    category: str = "answer_inconsistency",
    description: str = "候选答案与独立核算不一致。",
) -> dict[str, Any]:
    locations = {
        "evidence": "EvidencePlan.evidence_controls[0].statement",
        "content": "LearningContent.core_concepts[0].explanation",
        "practice": "PracticeFlow.practice[0].expected_evidence",
        "assembly": "StudyKit.title",
    }
    return {
        "id": "audit-issue-01",
        "severity": "blocker",
        "category": category,
        "target_stage": target_stage,
        "location": locations[target_stage],
        "description": description,
        "evidence_chunk_ids": [
            "mit-6.7960-f24-lecture-02-slides-p034"
        ],
        "observed": "候选符号为正。",
        "expected": "根据链式法则应为负。",
        "repair_instruction": "重新核算符号并保持答案与更新方向一致。",
    }


async def test_generator_runs_stages_audit_and_assembles_trusted_draft() -> None:
    model = FakeModel(successful_responses())
    request = generation_request()

    result = await StudyKitGenerator(model).generate(request, source_chunks())

    assert result.status is GenerationStatus.SUCCEEDED
    assert result.studykit is not None
    assert result.studykit["status"] == "draft"
    assert result.studykit["course_id"] == request.course_id
    assert result.studykit["review"]["human_review_status"] == "pending"
    assert result.studykit["practice_feedback_policy"]["persistence"] == "none"
    assert result.attempts == 4
    assert [stage.stage for stage in result.stages] == list(GenerationStage)
    assert [
        option["thinking_enabled"] for option in model.options
    ] == [True, True, True, True]
    assert "EvidencePlan JSON" in model.prompts[1][1]
    assert "LearningContent JSON" in model.prompts[2][1]
    assert "预组装 StudyKit JSON" in model.prompts[3][1]
    assert "official_url" not in model.prompts[3][1]
    assert "local_path" not in model.prompts[3][1]
    assert "sha256" not in model.prompts[3][1]


async def test_generator_repairs_invalid_content_citation_with_thinking() -> None:
    invalid = learning_content()
    invalid["core_concepts"][0]["citations"][0]["page"] = 999
    model = FakeModel(
        [
            model_response(evidence_plan()),
            model_response(invalid),
            model_response(learning_content()),
            model_response(practice_flow()),
            model_response(quality_audit()),
        ]
    )

    result = await StudyKitGenerator(model).generate(
        generation_request(), source_chunks()
    )

    assert result.status is GenerationStatus.SUCCEEDED
    assert result.attempts == 5
    assert "page_not_selected" in model.prompts[2][1]
    assert model.options[2]["thinking_enabled"] is True


async def test_content_outline_may_span_unselected_pages_in_plan_segments() -> None:
    plan = evidence_plan()
    unselected = "mit-6.7960-f24-lecture-02-slides-p007"
    for concept in plan["core_concept_candidates"]:
        concept["chunk_ids"] = [
            item for item in concept["chunk_ids"] if item != unselected
        ]
    plan["content_chunk_ids"].remove(unselected)
    content = learning_content()
    assert content["outline"][0]["pages"] == "5–11"

    responses = successful_responses()
    responses[0] = model_response(plan)
    responses[1] = model_response(content)
    result = await StudyKitGenerator(FakeModel(responses)).generate(
        generation_request(), source_chunks()
    )

    assert result.succeeded


async def test_content_outline_rejects_page_outside_plan_segments() -> None:
    content = learning_content()
    content["outline"][0]["pages"] = "82"
    result = await StudyKitGenerator(
        FakeModel(
            [
                model_response(evidence_plan()),
                model_response(content),
            ]
        ),
        max_repairs=0,
    ).generate(generation_request(), source_chunks())

    assert result.failed_stage is GenerationStage.CONTENT
    assert result.issues[0].code == "page_not_selected"
    assert "outside input SourceChunks" in result.issues[0].message


async def test_schema_only_repair_disables_thinking() -> None:
    invalid = evidence_plan()
    invalid.pop("lecture_summary")
    model = FakeModel(
        [
            model_response(invalid),
            model_response(evidence_plan()),
            model_response(learning_content()),
            model_response(practice_flow()),
            model_response(quality_audit()),
        ]
    )

    result = await StudyKitGenerator(model).generate(
        generation_request(), source_chunks()
    )

    assert result.succeeded
    assert model.options[0]["thinking_enabled"] is True
    assert model.options[1]["thinking_enabled"] is False


async def test_generator_stops_downstream_after_stage_failure() -> None:
    invalid = evidence_plan()
    invalid["content_chunk_ids"] = ["missing"]
    model = FakeModel(
        [
            model_response(invalid),
            model_response(invalid),
            model_response(invalid),
        ]
    )

    result = await StudyKitGenerator(model).generate(
        generation_request(), source_chunks()
    )

    assert result.status is GenerationStatus.FAILED_VALIDATION
    assert result.failed_stage is GenerationStage.EVIDENCE
    assert result.attempts == 3
    assert {issue.code for issue in result.issues} == {
        "unknown_chunk_id",
        "content_chunk_selection",
    }
    assert len(model.prompts) == 3


async def test_evidence_expands_unambiguous_page_chunk_aliases() -> None:
    plan = evidence_plan()
    full_id = plan["content_chunk_ids"][0]
    page = int(full_id.rsplit("-p", 1)[1])

    def replace_alias(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: replace_alias(item) for key, item in value.items()}
        if isinstance(value, list):
            return [replace_alias(item) for item in value]
        return f"p{page:03d}" if value == full_id else value

    model = FakeModel(
        [
            model_response(replace_alias(plan)),
            model_response(learning_content()),
            model_response(practice_flow()),
            model_response(quality_audit()),
        ]
    )

    result = await StudyKitGenerator(model).generate(
        generation_request(), source_chunks()
    )

    assert result.succeeded
    assert len(model.prompts) == 4


async def test_evidence_retries_after_model_error() -> None:
    model = FakeModel(
        [
            ModelAPIError("temporary evidence failure", status_code=503),
            model_response(evidence_plan()),
            model_response(learning_content()),
            model_response(practice_flow()),
            model_response(quality_audit()),
        ]
    )

    result = await StudyKitGenerator(model).generate(
        generation_request(), source_chunks()
    )

    assert result.succeeded
    assert len(model.prompts) == 5
    assert model.prompts[0] == model.prompts[1]


async def test_generator_reports_model_error_at_failed_stage() -> None:
    model = FakeModel(
        [
            model_response(evidence_plan()),
            ModelAPIError("provider unavailable", status_code=503),
        ]
    )

    result = await StudyKitGenerator(model).generate(
        generation_request(), source_chunks()
    )

    assert result.status is GenerationStatus.MODEL_ERROR
    assert result.failed_stage is GenerationStage.CONTENT
    assert result.issues[0].code == "ModelAPIError"


async def test_generator_saves_partial_answer_without_reasoning_content(
    tmp_path: Path,
) -> None:
    partial_content = '{"learning_objectives": ['
    error = ModelResponseError(
        "model generation did not complete normally: length",
        model="deepseek-v4-flash",
        finish_reason="length",
        usage={
            "completion_tokens": 32768,
            "reasoning_tokens": 30000,
        },
        request_id="request-length",
        partial_content=partial_content,
    )
    model = FakeModel([model_response(evidence_plan()), error])

    result = await StudyKitGenerator(model).generate(
        generation_request(), source_chunks(), output_dir=tmp_path
    )

    assert result.status is GenerationStatus.MODEL_ERROR
    assert (tmp_path / "02-learning-content.candidate.txt").read_text(
        encoding="utf-8"
    ) == partial_content
    validation = json.loads(
        (tmp_path / "02-learning-content.validation.json").read_text(
            encoding="utf-8"
        )
    )
    assert validation["partial_candidate"] == {
        "file": "02-learning-content.candidate.txt",
        "characters": len(partial_content),
    }
    assert result.model_info["usage"]["reasoning_tokens"] == 30000
    assert "reasoning_content" not in (
        tmp_path / "02-learning-content.candidate.txt"
    ).read_text(encoding="utf-8")


async def test_generator_classifies_empty_input_without_calling_model() -> None:
    model = FakeModel([])
    result = await StudyKitGenerator(model).generate(generation_request(), [])

    assert result.status is GenerationStatus.INSUFFICIENT_EVIDENCE
    assert result.attempts == 0
    assert model.prompts == []


async def test_generator_rejects_context_mismatch_without_calling_model() -> None:
    model = FakeModel([])
    chunks = source_chunks(count=1)
    chunks[0]["course_version"] = "spring-2025"

    result = await StudyKitGenerator(model).generate(
        generation_request(), chunks
    )

    assert result.status is GenerationStatus.INVALID_INPUT
    assert "course_version_mismatch" in {issue.code for issue in result.issues}
    assert model.prompts == []


async def test_learner_render_hides_internal_evaluation_fields() -> None:
    result = await StudyKitGenerator(FakeModel(successful_responses())).generate(
        generation_request(), source_chunks()
    )

    assert result.studykit is not None
    rendered = render_studykit_markdown(result.studykit)
    internal = practice_flow()["practice"][0]
    assert internal["expected_evidence"][0] not in rendered
    assert internal["evaluation"]["full_credit"] not in rendered


async def test_assembly_relabels_evidence_plan_title_for_learners() -> None:
    plan = evidence_plan()
    plan["unit_title_candidate"] = "Evidence Plan: Lecture 2"
    responses = successful_responses()
    responses[0] = model_response(plan)

    result = await StudyKitGenerator(FakeModel(responses)).generate(
        generation_request(), source_chunks()
    )

    assert result.studykit is not None
    assert result.studykit["title"] == "StudyKit: Lecture 2"


async def test_assembly_removes_evidence_plan_title_suffix() -> None:
    plan = evidence_plan()
    plan["unit_title_candidate"] = "Lecture 3: Approximation Theory — Evidence Plan"
    responses = successful_responses()
    responses[0] = model_response(plan)

    result = await StudyKitGenerator(FakeModel(responses)).generate(
        generation_request(), source_chunks()
    )

    assert result.studykit is not None
    assert result.studykit["title"] == "StudyKit: Lecture 3: Approximation Theory"


async def test_trusted_unit_title_overrides_model_title_candidate() -> None:
    plan = evidence_plan()
    plan["unit_title_candidate"] = "EvidencePlan：错误候选"
    model = FakeModel(
        [
            model_response(plan),
            model_response(learning_content()),
            model_response(practice_flow()),
            model_response(quality_audit()),
        ]
    )

    result = await StudyKitGenerator(model).generate(
        replace(generation_request(), unit_title="可信课程标题"), source_chunks()
    )

    assert result.succeeded
    assert result.studykit is not None
    assert result.studykit["title"] == "StudyKit: 可信课程标题"


def test_title_fallback_removes_all_evidence_plan_label_variants() -> None:
    for candidate in (
        "Evidence Plan: Lecture 1",
        "Lecture 1 — Evidence Plan",
        "Lecture 1（EvidencePlan）",
        "Lecture EvidencePlan 1",
    ):
        title = _studykit_title(candidate)
        assert "evidenceplan" not in title.lower().replace(" ", "")
        assert title.startswith("StudyKit:")


async def test_practice_rejects_internal_field_reference() -> None:
    practice = practice_flow()
    practice["learning_sequence"][0]["activity"] += (
        "，然后使用 expected_evidence 自评"
    )
    responses = [
        model_response(evidence_plan()),
        model_response(learning_content()),
        model_response(practice),
        model_response(practice_flow()),
        model_response(quality_audit()),
    ]

    result = await StudyKitGenerator(FakeModel(responses)).generate(
        generation_request(), source_chunks()
    )

    assert result.succeeded
    practice_stage = next(
        item for item in result.stages if item.stage is GenerationStage.PRACTICE
    )
    assert practice_stage.attempts == 2


async def test_from_practice_reuses_only_upstream_artifacts(
    tmp_path: Path,
) -> None:
    initial_model = FakeModel(successful_responses())
    generator = StudyKitGenerator(initial_model)
    request = generation_request()
    chunks = source_chunks()
    first = await generator.generate(
        request, chunks, output_dir=tmp_path
    )
    assert first.succeeded
    evidence_before = (tmp_path / "01-evidence-plan.json").read_bytes()
    content_before = (tmp_path / "02-learning-content.json").read_bytes()

    rerun_model = FakeModel(
        [model_response(practice_flow()), model_response(quality_audit())]
    )
    rerun = await StudyKitGenerator(rerun_model).generate(
        request,
        chunks,
        output_dir=tmp_path,
        from_stage=GenerationStage.PRACTICE,
    )

    assert rerun.succeeded
    assert len(rerun_model.prompts) == 2
    assert rerun.stages[0].reused is True
    assert rerun.stages[1].reused is True
    assert (tmp_path / "01-evidence-plan.json").read_bytes() == evidence_before
    assert (tmp_path / "02-learning-content.json").read_bytes() == content_before


async def test_from_audit_reuses_all_generation_artifacts(
    tmp_path: Path,
) -> None:
    await StudyKitGenerator(FakeModel(successful_responses())).generate(
        generation_request(), source_chunks(), output_dir=tmp_path
    )
    model = FakeModel([model_response(quality_audit())])

    result = await StudyKitGenerator(model).generate(
        generation_request(),
        source_chunks(),
        output_dir=tmp_path,
        from_stage=GenerationStage.AUDIT,
    )

    assert result.succeeded
    assert len(model.prompts) == 1
    assert all(stage.reused for stage in result.stages[:3])
    assert result.stages[3].stage is GenerationStage.AUDIT


async def test_resume_continues_after_failed_content_stage(
    tmp_path: Path,
) -> None:
    invalid = learning_content()
    invalid["core_concepts"][0]["citations"][0]["page"] = 999
    failed = await StudyKitGenerator(
        FakeModel([model_response(evidence_plan()), model_response(invalid)]),
        max_repairs=0,
    ).generate(generation_request(), source_chunks(), output_dir=tmp_path)
    assert failed.failed_stage is GenerationStage.CONTENT
    assert (tmp_path / "02-learning-content.candidate.json").is_file()
    assert (tmp_path / "02-learning-content.validation.json").is_file()

    model = FakeModel(
        [
            model_response(learning_content()),
            model_response(practice_flow()),
            model_response(quality_audit()),
        ]
    )
    resumed = await StudyKitGenerator(model, max_repairs=0).generate(
        generation_request(),
        source_chunks(),
        output_dir=tmp_path,
        resume=True,
    )

    assert resumed.succeeded
    assert len(model.prompts) == 3
    assert resumed.stages[0].reused is True
    run = json.loads((tmp_path / "run.json").read_text(encoding="utf-8"))
    assert all(item["status"] == "succeeded" for item in run["stages"].values())


async def test_resume_rejects_changed_inputs_without_model_call(
    tmp_path: Path,
) -> None:
    await StudyKitGenerator(FakeModel(successful_responses())).generate(
        generation_request(), source_chunks(), output_dir=tmp_path
    )
    changed = source_chunks()
    changed[0]["content"] = "changed evidence"
    model = FakeModel([])

    result = await StudyKitGenerator(model).generate(
        generation_request(), changed, output_dir=tmp_path, resume=True
    )

    assert result.status is GenerationStatus.INVALID_INPUT
    assert result.issues[0].code == "input_fingerprint_mismatch"
    assert model.prompts == []


async def test_resume_rejects_pre_single_audit_run_version(
    tmp_path: Path,
) -> None:
    await StudyKitGenerator(FakeModel(successful_responses())).generate(
        generation_request(), source_chunks(), output_dir=tmp_path
    )
    run_path = tmp_path / "run.json"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    run["run_version"] = 2
    run_path.write_text(
        json.dumps(run, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    model = FakeModel([])

    result = await StudyKitGenerator(model).generate(
        generation_request(), source_chunks(), output_dir=tmp_path, resume=True
    )

    assert result.status is GenerationStatus.INVALID_INPUT
    assert result.issues[0].code == "run_version_mismatch"
    assert model.prompts == []


async def test_quality_audit_repairs_practice_without_reaudit(
    tmp_path: Path,
) -> None:
    issue = audit_issue(target_stage="practice")
    assembly_issue = audit_issue(
        target_stage="assembly",
        category="formatting",
        description="预组装 JSON 存在重复键。",
    )
    assembly_issue["id"] = "audit-issue-assembly-formatting"
    repaired_practice = practice_flow()
    repaired_practice["learning_sequence"][0]["activity"] += "（已修复）"
    model = FakeModel(
        [
            model_response(evidence_plan()),
            model_response(learning_content()),
            model_response(repaired_practice),
            model_response(quality_audit(issues=[issue, assembly_issue])),
            model_response(practice_flow()),
        ]
    )

    result = await StudyKitGenerator(model).generate(
        generation_request(), source_chunks(), output_dir=tmp_path
    )

    assert result.succeeded
    audit_stage = next(
        item for item in result.stages if item.stage is GenerationStage.AUDIT
    )
    practice_stage = next(
        item for item in result.stages if item.stage is GenerationStage.PRACTICE
    )
    assert audit_stage.attempts == 1
    assert practice_stage.attempts == 2
    assert practice_stage.status == "repaired"
    assert "重新核算符号" in model.prompts[4][1]
    assert '"observed":"候选符号为正。"' in model.prompts[4][1]
    assert '"expected":"根据链式法则应为负。"' in model.prompts[4][1]
    assert '"evidence_chunk_ids"' in model.prompts[4][1]
    assert len(model.prompts) == 5
    assert model.options[3]["thinking_enabled"] is True
    assert model.options[4]["thinking_enabled"] is True
    assert result.studykit is not None
    assert (
        result.studykit["review"]["generator_review_status"]
        == "audit_repairs_applied_unverified"
    )
    assert (
        "post-repair semantic review"
        in result.studykit["review"]["checks_remaining"]
    )
    run = json.loads((tmp_path / "run.json").read_text(encoding="utf-8"))
    assert len(run["stages"]["practice"]["model_calls"]) == 2
    assert len(run["stages"]["audit"]["model_calls"]) == 1
    assert (
        run["stages"]["audit"]["outcome"]
        == "repairs_applied_unverified"
    )
    audit = json.loads(
        (tmp_path / "04-quality-audit.json").read_text(encoding="utf-8")
    )
    assert audit["verdict"] == "fail"
    resolution = json.loads(
        (tmp_path / "04-quality-audit.resolution.json").read_text(
            encoding="utf-8"
        )
    )
    assert resolution["semantic_reaudit_performed"] is False
    assert resolution["repaired_stages"] == ["practice"]
    assert resolution["deterministically_resolved_issue_ids"] == [
        "audit-issue-assembly-formatting"
    ]
    assert not (tmp_path / "04-quality-audit.recheck.json").exists()


async def test_quality_audit_repairs_content_and_practice_once_each(
    tmp_path: Path,
) -> None:
    content_issue = audit_issue(target_stage="content")
    practice_issue = audit_issue(target_stage="practice")
    practice_issue["id"] = "audit-issue-02"
    repaired_content = learning_content()
    repaired_content["core_concepts"][0]["explanation"] += " 已限定。"
    repaired_practice = practice_flow()
    repaired_practice["learning_sequence"][0]["activity"] += "（已修复）"
    model = FakeModel(
        [
            model_response(evidence_plan()),
            model_response(repaired_content),
            model_response(repaired_practice),
            model_response(
                quality_audit(issues=[content_issue, practice_issue])
            ),
            model_response(learning_content()),
            model_response(practice_flow()),
        ]
    )

    result = await StudyKitGenerator(model).generate(
        generation_request(), source_chunks(), output_dir=tmp_path
    )

    assert result.succeeded
    assert len(model.prompts) == 6
    assert "重新核算符号" in model.prompts[4][1]
    assert "重新核算符号" in model.prompts[5][1]
    stages = {item.stage: item for item in result.stages}
    assert stages[GenerationStage.CONTENT].status == "repaired"
    assert stages[GenerationStage.CONTENT].attempts == 2
    assert stages[GenerationStage.PRACTICE].status == "repaired"
    assert stages[GenerationStage.PRACTICE].attempts == 2
    assert stages[GenerationStage.AUDIT].attempts == 1
    run = json.loads((tmp_path / "run.json").read_text(encoding="utf-8"))
    assert len(run["stages"]["content"]["model_calls"]) == 2
    assert len(run["stages"]["practice"]["model_calls"]) == 2
    assert len(run["stages"]["audit"]["model_calls"]) == 1
    resolution = json.loads(
        (tmp_path / "04-quality-audit.resolution.json").read_text(
            encoding="utf-8"
        )
    )
    assert resolution["repaired_stages"] == ["content", "practice"]


async def test_audit_resolves_validated_internal_assembly_fields_and_repairs_content(
    tmp_path: Path,
) -> None:
    content_issue = audit_issue(
        target_stage="content",
        category="terminology_conflict",
        description="学习者内容中的两个术语互相冲突。",
    )
    assembly_issue = audit_issue(
        target_stage="assembly",
        category="internal_field_leak",
        description="标题泄露内部阶段名。",
    )
    assembly_issue.update(
        {
            "id": "audit-issue-assembly-title",
            "location": "preassembled StudyKit.title",
            "evidence_chunk_ids": [],
        }
    )
    repaired_content = learning_content()
    repaired_content["core_concepts"][0]["explanation"] += " 术语已统一。"
    model = FakeModel(
        [
            model_response(evidence_plan()),
            model_response(learning_content()),
            model_response(practice_flow()),
            model_response(
                quality_audit(issues=[assembly_issue, content_issue])
            ),
            model_response(repaired_content),
            model_response(practice_flow()),
        ]
    )

    result = await StudyKitGenerator(model).generate(
        generation_request(), source_chunks(), output_dir=tmp_path
    )

    assert result.succeeded
    assert len(model.prompts) == 6
    stages = {item.stage: item for item in result.stages}
    assert stages[GenerationStage.CONTENT].status == "repaired"
    resolution = json.loads(
        (tmp_path / "04-quality-audit.resolution.json").read_text(
            encoding="utf-8"
        )
    )
    assert resolution["repaired_stages"] == ["content", "practice"]
    assert resolution["deterministically_resolved_issue_ids"] == [
        "audit-issue-assembly-title"
    ]


async def test_quality_audit_repairs_evidence_without_reaudit() -> None:
    issue = audit_issue(
        target_stage="evidence",
        category="source_control_violation",
        description="必要的来源控制未进入证据计划。",
    )
    repaired_plan = evidence_plan()
    repaired_plan["evidence_controls"][0]["statement"] += " 已修复。"
    model = FakeModel(
        [
            model_response(evidence_plan()),
            model_response(learning_content()),
            model_response(practice_flow()),
            model_response(quality_audit(issues=[issue])),
            model_response(repaired_plan),
            model_response(learning_content()),
            model_response(practice_flow()),
        ]
    )

    result = await StudyKitGenerator(model).generate(
        generation_request(), source_chunks()
    )

    assert result.succeeded
    assert len(model.prompts) == 7
    stages = {item.stage: item for item in result.stages}
    assert stages[GenerationStage.EVIDENCE].status == "repaired"
    assert stages[GenerationStage.AUDIT].attempts == 1
    assert "完整 Audit issues JSON" in model.prompts[4][1]


async def test_quality_audit_repairs_all_stages_in_dependency_order() -> None:
    evidence_issue = audit_issue(
        target_stage="evidence",
        category="source_control_violation",
        description="证据控制需要修订。",
    )
    content_issue = audit_issue(target_stage="content")
    content_issue["id"] = "audit-content"
    practice_issue = audit_issue(target_stage="practice")
    practice_issue["id"] = "audit-practice"

    repaired_plan = evidence_plan()
    repaired_plan["evidence_controls"][0]["statement"] += " 已修复。"
    repaired_content = learning_content()
    repaired_content["core_concepts"][0]["explanation"] += " 已修复。"
    repaired_practice = practice_flow()
    repaired_practice["learning_sequence"][0]["activity"] += "（已修复）"
    model = FakeModel(
        [
            model_response(evidence_plan()),
            model_response(learning_content()),
            model_response(practice_flow()),
            model_response(
                quality_audit(
                    issues=[evidence_issue, content_issue, practice_issue]
                )
            ),
            model_response(repaired_plan),
            model_response(repaired_content),
            model_response(repaired_practice),
        ]
    )

    result = await StudyKitGenerator(model).generate(
        generation_request(), source_chunks()
    )

    assert result.succeeded
    stages = {item.stage: item for item in result.stages}
    assert stages[GenerationStage.EVIDENCE].status == "repaired"
    assert stages[GenerationStage.CONTENT].status == "repaired"
    assert stages[GenerationStage.PRACTICE].status == "repaired"
    assert "evidence JSON Schema" in model.prompts[4][1]
    assert "content JSON Schema" in model.prompts[5][1]
    assert "practice JSON Schema" in model.prompts[6][1]


async def test_audit_repair_model_error_is_reported_without_crashing() -> None:
    issue = audit_issue(target_stage="content")
    model = FakeModel(
        [
            model_response(evidence_plan()),
            model_response(learning_content()),
            model_response(practice_flow()),
            model_response(quality_audit(issues=[issue])),
            ModelAPIError("insufficient balance", status_code=402),
        ]
    )

    result = await StudyKitGenerator(
        model, assemble_on_audit_failure=False
    ).generate(
        generation_request(), source_chunks()
    )

    assert result.status is GenerationStatus.MODEL_ERROR
    assert result.failed_stage is GenerationStage.AUDIT
    assert result.issues[0].code == "ModelAPIError"


async def test_content_first_assembles_when_audit_repair_model_errors() -> None:
    issue = audit_issue(target_stage="content")
    model = FakeModel(
        [
            model_response(evidence_plan()),
            model_response(learning_content()),
            model_response(practice_flow()),
            model_response(quality_audit(issues=[issue])),
            ModelAPIError("insufficient balance", status_code=402),
        ]
    )

    result = await StudyKitGenerator(model).generate(
        generation_request(), source_chunks()
    )

    assert result.succeeded
    assert result.studykit is not None
    assert result.issues[0].code == "ModelAPIError"
    assert (
        result.studykit["review"]["generator_review_status"]
        == "audit_unavailable"
    )
    audit_stage = next(
        stage for stage in result.stages
        if stage.stage is GenerationStage.AUDIT
    )
    assert audit_stage.status == GenerationStatus.MODEL_ERROR.value


async def test_global_limitation_audit_finding_is_assembly_resolved(
    tmp_path: Path,
) -> None:
    issue = audit_issue(
        target_stage="content",
        category="source_risk_ignored",
        description="EvidencePlan scope=global limitation 未传播。",
    )
    issue["location"] = "LearningContent.limitations[0]"
    model = FakeModel(
        [
            model_response(evidence_plan()),
            model_response(learning_content()),
            model_response(practice_flow()),
            model_response(quality_audit(issues=[issue])),
        ]
    )

    result = await StudyKitGenerator(model).generate(
        generation_request(), source_chunks(), output_dir=tmp_path
    )

    assert result.succeeded
    assert len(model.prompts) == 4
    resolution = json.loads(
        (tmp_path / "04-quality-audit.resolution.json").read_text(
            encoding="utf-8"
        )
    )
    assert resolution["resolutions"][0]["target_stage"] == "assembly"
    assert resolution["resolutions"][0]["resolution"] == "code_resolved"


async def test_audit_repair_cannot_create_planning_ids(tmp_path: Path) -> None:
    issue = audit_issue(
        target_stage="evidence",
        category="coverage_gap",
        description="证据摘要需要补充限定。",
    )
    repaired = evidence_plan()
    added = deepcopy(repaired["assessment_requirements"][0])
    added["id"] = "req-unplanned"
    repaired["assessment_requirements"].append(added)
    model = FakeModel(
        [
            model_response(evidence_plan()),
            model_response(learning_content()),
            model_response(practice_flow()),
            model_response(quality_audit(issues=[issue])),
            model_response(repaired),
        ]
    )

    result = await StudyKitGenerator(model).generate(
        generation_request(), source_chunks(), output_dir=tmp_path
    )

    assert result.succeeded
    assert result.studykit is not None
    assert (
        result.studykit["review"]["generator_review_status"]
        == "audit_blockers_unresolved"
    )
    validation = json.loads(
        (tmp_path / "01-evidence-plan.audit-repair.validation.json").read_text(
            encoding="utf-8"
        )
    )
    assert validation["identity_adjustments"] == ["assessment_requirements"]
    assert [item["code"] for item in validation["issues"]] == [
        "audit_repair_unchanged"
    ]


async def test_audit_repair_lands_valid_edit_and_discards_identity_drift(
    tmp_path: Path,
) -> None:
    issue = audit_issue(
        target_stage="content",
        category="logical_error",
        description="误区中的反例计算错误。",
    )
    issue["location"] = "LearningContent.common_misconceptions[0].correction"
    original = learning_content()
    repaired = deepcopy(original)
    repaired["common_misconceptions"][0]["correction"] = "反例已正确重算。"
    removed = repaired["core_concepts"].pop()
    added = deepcopy(repaired["core_concepts"][0])
    added["id"] = "unplanned-concept"
    added["evidence_concept_id"] = "unplanned-concept"
    repaired["core_concepts"].append(added)
    model = FakeModel(
        [
            model_response(evidence_plan()),
            model_response(original),
            model_response(practice_flow()),
            model_response(quality_audit(issues=[issue])),
            model_response(repaired),
            model_response(practice_flow()),
        ]
    )

    result = await StudyKitGenerator(model).generate(
        generation_request(), source_chunks(), output_dir=tmp_path
    )

    assert result.succeeded
    landed = json.loads(
        (tmp_path / "02-learning-content.json").read_text(encoding="utf-8")
    )
    assert landed["common_misconceptions"][0]["correction"] == (
        "反例已正确重算。"
    )
    assert [item["id"] for item in landed["core_concepts"]] == [
        item["id"] for item in original["core_concepts"]
    ]
    assert removed["id"] in {item["id"] for item in landed["core_concepts"]}
    run = json.loads((tmp_path / "run.json").read_text(encoding="utf-8"))
    assert run["stages"]["content"]["audit_repair"][
        "identity_adjustments"
    ] == ["core_concepts"]
    resolution = json.loads(
        (tmp_path / "04-quality-audit.resolution.json").read_text(
            encoding="utf-8"
        )
    )
    assert resolution["resolutions"][0]["resolution"] == "model_repaired"


async def test_assembly_sanitizes_internal_stage_labels() -> None:
    plan = evidence_plan()
    plan["limitations"][0]["description"] += " EvidencePlan 已选择证据。"
    issue = audit_issue(
        target_stage="assembly",
        category="internal_field_leak",
        description="最终正文泄露内部阶段标签。",
    )
    issue["location"] = "StudyKit.limitations[0]"
    model = FakeModel(
        [
            model_response(plan),
            model_response(learning_content()),
            model_response(practice_flow()),
            model_response(quality_audit(issues=[issue])),
        ]
    )

    result = await StudyKitGenerator(model).generate(
        generation_request(), source_chunks()
    )

    assert result.succeeded
    assert result.studykit is not None
    limitations = " ".join(result.studykit["limitations"])
    assert "EvidencePlan" not in limitations
    assert "证据规划" in limitations


async def test_quality_audit_keeps_semantic_assembly_blocker() -> None:
    issue = audit_issue(
        target_stage="assembly",
        category="stage_contradiction",
        description="组装产物的阶段内容互相矛盾。",
    )
    model = FakeModel(
        [
            model_response(evidence_plan()),
            model_response(learning_content()),
            model_response(practice_flow()),
            model_response(quality_audit(issues=[issue])),
        ]
    )

    result = await StudyKitGenerator(
        model, assemble_on_audit_failure=False
    ).generate(
        generation_request(), source_chunks()
    )

    assert result.status is GenerationStatus.FAILED_VALIDATION
    assert result.failed_stage is GenerationStage.AUDIT
    assert result.issues[0].code == "stage_contradiction"
    assert len(model.prompts) == 4


async def test_mixed_assembly_blocker_does_not_prevent_deduplicated_repairs(
    tmp_path: Path,
) -> None:
    content_issue = audit_issue(target_stage="content")
    content_issue["id"] = "content-one"
    duplicate_one = audit_issue(target_stage="practice")
    duplicate_one["id"] = "practice-flow-copy"
    duplicate_two = deepcopy(duplicate_one)
    duplicate_two["id"] = "studykit-copy"
    duplicate_two["location"] = "StudyKit.practice[0].expected_evidence"
    assembly_issue = audit_issue(
        target_stage="assembly", category="stage_contradiction"
    )
    assembly_issue["id"] = "assembly-unresolved"
    repaired_content = learning_content()
    repaired_content["core_concepts"][0]["explanation"] += " 已修复。"
    repaired_practice = practice_flow()
    repaired_practice["practice"][0]["expected_evidence"][0] += " 已修复。"
    model = FakeModel(
        [
            model_response(evidence_plan()),
            model_response(learning_content()),
            model_response(practice_flow()),
            model_response(
                quality_audit(
                    issues=[
                        assembly_issue,
                        duplicate_one,
                        duplicate_two,
                        content_issue,
                    ]
                )
            ),
            model_response(repaired_content),
            model_response(repaired_practice),
        ]
    )

    result = await StudyKitGenerator(
        model, assemble_on_audit_failure=False
    ).generate(
        generation_request(), source_chunks(), output_dir=tmp_path
    )

    assert result.status is GenerationStatus.FAILED_VALIDATION
    assert len(model.prompts) == 6
    assert "practice-flow-copy" in model.prompts[5][1]
    assert "studykit-copy" in model.prompts[5][1]
    stages = {item.stage: item for item in result.stages}
    assert stages[GenerationStage.CONTENT].status == "repaired"
    assert stages[GenerationStage.PRACTICE].status == "repaired"
    resolution = json.loads(
        (tmp_path / "04-quality-audit.resolution.json").read_text(encoding="utf-8")
    )
    by_id = {item["issue_id"]: item["resolution"] for item in resolution["resolutions"]}
    assert by_id == {
        "assembly-unresolved": "unresolved_failure",
        "practice-flow-copy": "model_repaired",
        "studykit-copy": "model_repaired",
        "content-one": "model_repaired",
    }


async def test_preassembled_space_prefix_and_mixed_paths_route_to_field_owners(
    tmp_path: Path,
) -> None:
    issue = audit_issue(
        target_stage="assembly", category="dimension_error"
    )
    issue.update(
        {
            "id": "lecture-02-assembly-duplicate",
            "location": (
                "preassembled StudyKit learning_objectives[lo5]; "
                "core_concepts[cc6]; practice[prac-06]"
            ),
        }
    )
    repaired_content = learning_content()
    repaired_content["core_concepts"][0]["explanation"] += " 公式已修复。"
    repaired_practice = practice_flow()
    repaired_practice["practice"][0]["expected_evidence"][0] += " 已同步。"
    model = FakeModel(
        [
            model_response(evidence_plan()),
            model_response(learning_content()),
            model_response(practice_flow()),
            model_response(quality_audit(issues=[issue])),
            model_response(repaired_content),
            model_response(repaired_practice),
        ]
    )

    result = await StudyKitGenerator(model).generate(
        generation_request(), source_chunks(), output_dir=tmp_path
    )

    assert result.succeeded
    assert len(model.prompts) == 6
    assert "learning_objectives[lo5]; core_concepts[cc6]" in model.prompts[4][1]
    assert "practice[prac-06]" in model.prompts[5][1]
    resolution = json.loads(
        (tmp_path / "04-quality-audit.resolution.json").read_text(encoding="utf-8")
    )
    assert resolution["unresolved_issue_ids"] == []
    assert resolution["resolutions"] == [
            {
                "issue_id": "lecture-02-assembly-duplicate",
                "severity": "blocker",
                "target_stage": "content+practice",
            "target_stages": ["content", "practice"],
            "location": (
                "learning_objectives[lo5]; core_concepts[cc6]; "
                "practice[prac-06]"
            ),
            "locations": [
                "learning_objectives[lo5]; core_concepts[cc6]",
                "practice[prac-06]",
            ],
            "resolution": "model_repaired",
        }
    ]


async def test_arbitrary_audit_prose_before_path_is_normalized_and_deduplicated(
    tmp_path: Path,
) -> None:
    content_finding = audit_issue(
        target_stage="content", category="missing_qualification"
    )
    content_finding.update(
        {
            "id": "content-lo5",
            "location": "LearningContent.learning_objectives[lo5]",
        }
    )
    assembled_copy = dict(content_finding)
    assembled_copy.update(
        {
            "id": "assembled-lo5-copy",
            "target_stage": "assembly",
            "location": (
                "模型在 Practice review 的当前候选中发现："
                "StudyKit.learning_objectives[lo5]"
            ),
        }
    )
    repaired = learning_content()
    repaired["learning_objectives"][0]["objective"] += "（带适用范围）"
    model = FakeModel(
        [
            model_response(evidence_plan()),
            model_response(learning_content()),
            model_response(practice_flow()),
            model_response(
                quality_audit(issues=[content_finding, assembled_copy])
            ),
            model_response(repaired),
            model_response(practice_flow()),
        ]
    )

    result = await StudyKitGenerator(model).generate(
        generation_request(), source_chunks(), output_dir=tmp_path
    )

    assert result.succeeded
    assert len(model.prompts) == 6
    resolution = json.loads(
        (tmp_path / "04-quality-audit.resolution.json").read_text(
            encoding="utf-8"
        )
    )
    assert resolution["unresolved_issue_ids"] == []
    assert {
        item["issue_id"]: (item["target_stages"], item["resolution"])
        for item in resolution["resolutions"]
    } == {
        "content-lo5": (["content"], "model_repaired"),
        "assembled-lo5-copy": (["content"], "model_repaired"),
    }


async def test_original_audit_issue_fails_when_any_owner_shard_fails(
    tmp_path: Path,
) -> None:
    issue = audit_issue(target_stage="assembly", category="dimension_error")
    issue.update(
        {
            "id": "mixed-shard-failure",
            "location": (
                "preassembled StudyKit learning_objectives[lo5]; "
                "practice[prac-06]"
            ),
        }
    )
    repaired_content = learning_content()
    repaired_content["core_concepts"][0]["explanation"] += " 已修复。"
    invalid_practice = practice_flow()
    invalid_practice["learning_sequence"][0].pop("practice_ids")
    model = FakeModel(
        [
            model_response(evidence_plan()),
            model_response(learning_content()),
            model_response(practice_flow()),
            model_response(quality_audit(issues=[issue])),
            model_response(repaired_content),
            model_response(invalid_practice),
        ]
    )

    result = await StudyKitGenerator(
        model, assemble_on_audit_failure=False
    ).generate(
        generation_request(), source_chunks(), output_dir=tmp_path
    )

    assert result.status is GenerationStatus.FAILED_VALIDATION
    resolution = json.loads(
        (tmp_path / "04-quality-audit.resolution.json").read_text(encoding="utf-8")
    )
    assert resolution["unresolved_issue_ids"] == ["mixed-shard-failure"]
    assert resolution["resolutions"][0]["resolution"] == "unresolved_failure"


async def test_max_repairs_zero_disables_audit_artifact_repairs() -> None:
    issue = audit_issue(target_stage="practice")
    model = FakeModel(
        [
            model_response(evidence_plan()),
            model_response(learning_content()),
            model_response(practice_flow()),
            model_response(quality_audit(issues=[issue])),
        ]
    )

    result = await StudyKitGenerator(
        model, max_repairs=0, assemble_on_audit_failure=False
    ).generate(
        generation_request(), source_chunks()
    )

    assert result.failed_stage is GenerationStage.AUDIT
    assert result.issues[0].code == "answer_inconsistency"
    assert len(model.prompts) == 4


async def test_audit_repairs_out_of_boundary_issue_in_dependency_order(
    tmp_path: Path,
) -> None:
    issue = audit_issue(target_stage="practice")
    issue["evidence_chunk_ids"] = [
        "mit-6.7960-f24-lecture-02-slides-p081"
    ]
    repaired_plan = evidence_plan()
    repaired_plan["practice_opportunities"][0]["chunk_ids"].append(
        "mit-6.7960-f24-lecture-02-slides-p081"
    )
    repaired_plan["practice_chunk_ids"].append(
        "mit-6.7960-f24-lecture-02-slides-p081"
    )
    repaired_plan["practice_chunk_ids"].sort()
    repaired_practice = practice_flow()
    repaired_practice["practice"][0]["expected_evidence"] += " 已重新核算。"
    model = FakeModel(
        [
            model_response(evidence_plan()),
            model_response(learning_content()),
            model_response(practice_flow()),
            model_response(quality_audit(issues=[issue])),
            model_response(repaired_plan),
            model_response(learning_content()),
            model_response(repaired_practice),
        ]
    )

    result = await StudyKitGenerator(model).generate(
        generation_request(), source_chunks(), output_dir=tmp_path
    )

    assert result.succeeded
    assert len(model.prompts) == 7
    assert result.stages[0].status == "repaired"
    assert result.stages[2].status == "repaired"
    assert "audit-issue-01-evidence-boundary" in model.prompts[4][1]
    assert "practice_chunk_ids" in model.prompts[4][1]
    assert (tmp_path / "04-quality-audit.json").is_file()


async def test_audit_saves_invalid_target_repair_candidate(
    tmp_path: Path,
) -> None:
    issue = audit_issue(target_stage="practice")
    invalid = practice_flow()
    invalid["practice"][0]["source_pages"] = [81]
    model = FakeModel(
        [
            model_response(evidence_plan()),
            model_response(learning_content()),
            model_response(practice_flow()),
            model_response(quality_audit(issues=[issue])),
            model_response(invalid),
        ]
    )

    result = await StudyKitGenerator(
        model, assemble_on_audit_failure=False
    ).generate(
        generation_request(), source_chunks(), output_dir=tmp_path
    )

    assert result.failed_stage is GenerationStage.AUDIT
    assert (
        tmp_path / "03-practice-flow.audit-repair.candidate.json"
    ).is_file()
    assert (
        tmp_path / "03-practice-flow.audit-repair.validation.json"
    ).is_file()


async def test_quality_audit_warning_returns_to_owning_stage() -> None:
    issue = audit_issue(target_stage="practice")
    issue["severity"] = "warning"
    repaired = practice_flow()
    repaired["practice"][0]["expected_evidence"][0] += " 已按建议澄清。"
    model = FakeModel(
        [
            model_response(evidence_plan()),
            model_response(learning_content()),
            model_response(practice_flow()),
            model_response(quality_audit(issues=[issue])),
            model_response(repaired),
        ]
    )

    result = await StudyKitGenerator(model).generate(
        generation_request(), source_chunks()
    )

    assert result.succeeded
    assert result.studykit is not None
    assert (
        result.studykit["review"]["generator_review_status"]
        == "audit_repairs_applied_unverified"
    )
    assert len(model.prompts) == 5
    assert '"mandatory_blockers":[]' in model.prompts[4][1]
    assert '"requested_warning_improvements"' in model.prompts[4][1]


async def test_warning_repair_failure_rolls_back_without_blocking(
    tmp_path: Path,
) -> None:
    issue = audit_issue(target_stage="practice")
    issue["severity"] = "warning"
    invalid = practice_flow()
    invalid["practice"][0]["source_pages"] = [999]
    model = FakeModel(
        [
            model_response(evidence_plan()),
            model_response(learning_content()),
            model_response(practice_flow()),
            model_response(quality_audit(issues=[issue])),
            model_response(invalid),
        ]
    )

    result = await StudyKitGenerator(model).generate(
        generation_request(), source_chunks(), output_dir=tmp_path
    )

    assert result.succeeded
    assert result.studykit is not None
    assert result.studykit["practice"] == practice_flow()["practice"]
    assert (
        result.studykit["review"]["generator_review_status"]
        == "audit_warnings_unresolved"
    )
    resolution = json.loads(
        (tmp_path / "04-quality-audit.resolution.json").read_text(
            encoding="utf-8"
        )
    )
    assert resolution["outcome"] == "warnings_unresolved"
    assert resolution["unresolved_warning_ids"] == ["audit-issue-01"]
    assert resolution["resolutions"][0]["resolution"] == "warning_repair_failed"
    assert (tmp_path / "05-studykit.json").is_file()


async def test_blocker_and_warning_share_one_stage_repair_call(
    tmp_path: Path,
) -> None:
    blocker = audit_issue(target_stage="practice")
    warning = audit_issue(
        target_stage="practice",
        category="pedagogy",
        description="反馈措辞可以更明确。",
    )
    warning.update(
        {
            "id": "audit-warning-02",
            "severity": "warning",
            "location": "PracticeFlow.practice[1].feedback",
        }
    )
    repaired = practice_flow()
    repaired["practice"][0]["expected_evidence"][0] += " 已核算。"
    model = FakeModel(
        [
            model_response(evidence_plan()),
            model_response(learning_content()),
            model_response(practice_flow()),
            model_response(quality_audit(issues=[blocker, warning])),
            model_response(repaired),
        ]
    )

    result = await StudyKitGenerator(model).generate(
        generation_request(), source_chunks(), output_dir=tmp_path
    )

    assert result.succeeded
    assert len(model.prompts) == 5
    assert '"mandatory_blockers"' in model.prompts[4][1]
    assert '"requested_warning_improvements"' in model.prompts[4][1]
    resolution = json.loads(
        (tmp_path / "04-quality-audit.resolution.json").read_text(
            encoding="utf-8"
        )
    )
    assert [item["resolution"] for item in resolution["resolutions"]] == [
        "model_repaired",
        "warning_model_repaired",
    ]


async def test_practice_accepts_multiple_simple_numeric_exercises() -> None:
    flow = practice_flow()
    flow["practice"][0]["numeric_complexity"] = "simple"
    flow["practice"][1]["numeric_complexity"] = "simple"
    model = FakeModel(
        [
            model_response(evidence_plan()),
            model_response(learning_content()),
            model_response(flow),
            model_response(quality_audit()),
        ]
    )

    result = await StudyKitGenerator(model, max_repairs=0).generate(
        generation_request(), source_chunks()
    )

    assert result.succeeded


async def test_pipeline_accepts_nine_practice_opportunities() -> None:
    plan = evidence_plan()
    originals = deepcopy(plan["practice_opportunities"])
    for index in range(5, 9):
        opportunity = deepcopy(originals[index % len(originals)])
        opportunity["id"] = f"opportunity-{index + 1:02d}"
        plan["practice_opportunities"].append(opportunity)

    controls = {item["id"]: item for item in plan["evidence_controls"]}
    plan["practice_chunk_ids"] = sorted(
        {
            chunk_id
            for opportunity in plan["practice_opportunities"]
            for chunk_id in (
                opportunity["chunk_ids"]
                + [
                    control_chunk
                    for control_id in opportunity["control_ids"]
                    for control_chunk in controls[control_id]["chunk_ids"]
                ]
            )
        }
    )

    content = learning_content()
    content_concepts = {
        item["evidence_concept_id"]: item["id"]
        for item in content["core_concepts"]
    }
    objective_for_requirement = {
        requirement_id: objective["id"]
        for objective in content["learning_objectives"]
        for requirement_id in objective["requirement_ids"]
    }
    base_practices = practice_flow()["practice"]
    practices = []
    for index, opportunity in enumerate(plan["practice_opportunities"]):
        practice = deepcopy(base_practices[index % len(base_practices)])
        practice["id"] = f"practice-{index + 1:02d}"
        practice["opportunity_id"] = opportunity["id"]
        practice["practice_type"] = opportunity["practice_type"]
        practice["concept_ids"] = [
            content_concepts[concept_id]
            for concept_id in opportunity["concept_ids"]
        ]
        practice["requirement_ids"] = deepcopy(
            opportunity["requirement_ids"]
        )
        practice["objective_ids"] = [
            objective_for_requirement[opportunity["requirement_ids"][0]]
        ]
        practice["control_ids"] = deepcopy(opportunity["control_ids"])
        practice["source_pages"] = sorted(
            {
                int(chunk_id.rsplit("-p", 1)[1])
                for chunk_id in opportunity["chunk_ids"]
            }
        )
        practices.append(practice)
    flow = practice_flow()
    flow["practice"] = practices
    for step in flow["learning_sequence"]:
        if step["activity_type"] == "practice":
            step["practice_ids"] = [item["id"] for item in practices]
    model = FakeModel(
        [
            model_response(plan),
            model_response(content),
            model_response(flow),
            model_response(quality_audit()),
        ]
    )

    result = await StudyKitGenerator(model, max_repairs=0).generate(
        generation_request(), source_chunks()
    )

    assert result.succeeded
    assert result.studykit is not None
    assert len(result.studykit["practice"]) == 9
    assert len(model.prompts) == 4


async def test_practice_sequence_rejects_unknown_and_omitted_practice_ids() -> None:
    flow = practice_flow()
    practice_step = next(
        item for item in flow["learning_sequence"]
        if item["activity_type"] == "practice"
    )
    practice_step["practice_ids"] = ["unknown-practice", flow["practice"][0]["id"]]
    model = FakeModel(
        [
            model_response(evidence_plan()),
            model_response(learning_content()),
            model_response(flow),
        ]
    )

    result = await StudyKitGenerator(model, max_repairs=0).generate(
        generation_request(), source_chunks()
    )

    assert result.failed_stage is GenerationStage.PRACTICE
    codes = {item.code for item in result.issues}
    assert "unknown_sequence_practice_id" in codes
    assert "sequence_practice_coverage" in codes


async def test_practice_sequence_requires_practice_ids_on_every_step() -> None:
    flow = practice_flow()
    flow["learning_sequence"][0].pop("practice_ids")
    model = FakeModel(
        [
            model_response(evidence_plan()),
            model_response(learning_content()),
            model_response(flow),
        ]
    )

    result = await StudyKitGenerator(model, max_repairs=0).generate(
        generation_request(), source_chunks()
    )

    assert result.failed_stage is GenerationStage.PRACTICE
    assert any("practice_ids" in item.message for item in result.issues)


async def test_practice_sequence_allows_review_to_repeat_practice_ids() -> None:
    flow = practice_flow()
    review_step = next(
        item for item in flow["learning_sequence"]
        if item["activity_type"] == "review"
    )
    review_step["practice_ids"] = [flow["practice"][0]["id"]]
    model = FakeModel(
        [
            model_response(evidence_plan()),
            model_response(learning_content()),
            model_response(flow),
            model_response(quality_audit()),
        ]
    )

    result = await StudyKitGenerator(model, max_repairs=0).generate(
        generation_request(), source_chunks()
    )

    assert result.succeeded


async def test_evidence_rejects_more_than_twelve_practice_opportunities() -> None:
    invalid = evidence_plan()
    original = deepcopy(invalid["practice_opportunities"][0])
    for index in range(5, 13):
        opportunity = deepcopy(original)
        opportunity["id"] = f"opportunity-{index + 1:02d}"
        invalid["practice_opportunities"].append(opportunity)

    result = await StudyKitGenerator(
        FakeModel([model_response(invalid)]),
        max_repairs=0,
    ).generate(generation_request(), source_chunks())

    assert result.failed_stage is GenerationStage.EVIDENCE
    assert result.issues[0].code == "schema_validation"
    assert result.issues[0].location == "practice_opportunities"


async def test_content_rejects_unknown_assessment_requirement() -> None:
    invalid = learning_content()
    invalid["learning_objectives"][0]["requirement_ids"] = ["unknown"]
    result = await StudyKitGenerator(
        FakeModel([model_response(evidence_plan()), model_response(invalid)]),
        max_repairs=0,
    ).generate(generation_request(), source_chunks())

    assert result.failed_stage is GenerationStage.CONTENT
    assert result.issues[0].code == "objective_requirement_coverage"


async def test_practice_rejects_requirement_outside_opportunity() -> None:
    invalid = practice_flow()
    invalid["practice"][0]["requirement_ids"] = ["requirement-02"]
    result = await StudyKitGenerator(
        FakeModel(
            [
                model_response(evidence_plan()),
                model_response(learning_content()),
                model_response(invalid),
            ]
        ),
        max_repairs=0,
    ).generate(generation_request(), source_chunks())

    assert result.failed_stage is GenerationStage.PRACTICE
    assert "practice_requirement_mapping" in {
        issue.code for issue in result.issues
    }


async def test_evidence_rejects_unknown_control_reference() -> None:
    invalid = evidence_plan()
    invalid["assessment_requirements"][0]["control_ids"] = ["missing-control"]
    result = await StudyKitGenerator(
        FakeModel([model_response(invalid)]),
        max_repairs=0,
    ).generate(generation_request(), source_chunks())

    assert result.failed_stage is GenerationStage.EVIDENCE
    assert "unknown_control_id" in {issue.code for issue in result.issues}


async def test_stage_chunk_union_gaps_are_delivered_as_unverified_quality() -> None:
    invalid = evidence_plan()
    unused_content_page = next(
        item for item in invalid["content_chunk_ids"] if item.endswith("p001")
    )
    invalid["content_chunk_ids"].remove(unused_content_page)
    extra_practice_chunk = next(
        item for item in invalid["content_chunk_ids"]
        if item not in invalid["practice_chunk_ids"]
    )
    invalid["practice_chunk_ids"].append(extra_practice_chunk)
    result = await StudyKitGenerator(
        FakeModel(
            [
                model_response(invalid),
                model_response(learning_content()),
                model_response(practice_flow()),
                model_response(quality_audit()),
            ]
        ),
        max_repairs=0,
    ).generate(generation_request(), source_chunks())

    assert result.succeeded
    evidence_stage = result.stages[0]
    assert evidence_stage.status == "succeeded_unverified"
    codes = {issue.code for issue in result.issues}
    assert "content_chunk_selection" in codes
    assert "practice_chunk_selection" in codes
    assert result.studykit is not None
    assert result.studykit["review"]["generator_review_status"] == (
        "stage_quality_unverified"
    )


async def test_missing_practice_opportunity_does_not_block_assembly() -> None:
    plan = evidence_plan()
    extra = deepcopy(plan["practice_opportunities"][0])
    extra["id"] = "additional-combinable-opportunity"
    plan["practice_opportunities"].append(extra)
    model = FakeModel(
        [
            model_response(plan),
            model_response(learning_content()),
            model_response(practice_flow()),
            model_response(quality_audit()),
        ]
    )

    result = await StudyKitGenerator(model, max_repairs=0).generate(
        generation_request(), source_chunks()
    )

    assert result.succeeded
    practice_stage = next(
        item for item in result.stages
        if item.stage is GenerationStage.PRACTICE
    )
    assert practice_stage.status == "succeeded_unverified"
    assert [item.code for item in practice_stage.issues] == [
        "opportunity_coverage"
    ]
    assert result.studykit is not None
    assert result.studykit["review"]["generator_review_status"] == (
        "stage_quality_unverified"
    )


async def test_content_terminology_conflict_does_not_block_assembly() -> None:
    content = learning_content()
    content["glossary"][0]["term_en"] = "gradient descent"
    content["glossary"][0]["term_zh"] = "另一种译名"
    model = FakeModel(
        [
            model_response(evidence_plan()),
            model_response(content),
            model_response(practice_flow()),
            model_response(quality_audit()),
        ]
    )

    result = await StudyKitGenerator(model, max_repairs=0).generate(
        generation_request(), source_chunks()
    )

    assert result.succeeded
    content_stage = next(
        item for item in result.stages
        if item.stage is GenerationStage.CONTENT
    )
    assert content_stage.status == "succeeded_unverified"
    assert [item.code for item in content_stage.issues] == [
        "terminology_conflict"
    ]


async def test_practice_must_copy_opportunity_controls_and_type() -> None:
    invalid = practice_flow()
    controlled = next(
        item for item in invalid["practice"] if item["control_ids"]
    )
    controlled["control_ids"] = ["invented-control"]
    controlled["practice_type"] = "comparison"
    result = await StudyKitGenerator(
        FakeModel(
            [
                model_response(evidence_plan()),
                model_response(learning_content()),
                model_response(invalid),
            ]
        ),
        max_repairs=0,
    ).generate(generation_request(), source_chunks())

    assert result.failed_stage is GenerationStage.PRACTICE
    codes = {issue.code for issue in result.issues}
    assert "practice_control_mapping" in codes
    assert "practice_type_mapping" in codes


async def test_practice_accepts_evidence_concept_ids_mapped_by_content() -> None:
    plan = evidence_plan()
    flow = practice_flow()
    opportunities = {
        item["id"]: item for item in plan["practice_opportunities"]
    }
    for item in flow["practice"]:
        item["concept_ids"] = deepcopy(
            opportunities[item["opportunity_id"]]["concept_ids"]
        )
    result = await StudyKitGenerator(
        FakeModel(
            [
                model_response(plan),
                model_response(learning_content()),
                model_response(flow),
                model_response(quality_audit()),
            ]
        )
    ).generate(generation_request(), source_chunks())

    assert result.succeeded


async def test_practice_global_limitations_are_normalized_from_evidence(
    tmp_path: Path,
) -> None:
    plan = evidence_plan()
    flow = practice_flow()
    invented = deepcopy(plan["limitations"][0])
    invented["code"] = "renamed-by-model"
    invented["description"] = "Practice rewrote this global limitation."
    local = deepcopy(plan["limitations"][0])
    local.update(
        {
            "code": "local-practice-note",
            "description": "本练习的局部限制。",
            "scope": "stage_internal",
        }
    )
    flow["limitations"] = [invented, local]
    model = FakeModel(
        [
            model_response(plan),
            model_response(learning_content()),
            model_response(flow),
            model_response(quality_audit()),
        ]
    )
    result = await StudyKitGenerator(model, max_repairs=0).generate(
        generation_request(), source_chunks(), output_dir=tmp_path
    )

    assert result.succeeded
    assert len(model.prompts) == 4
    artifact = json.loads(
        (tmp_path / "03-practice-flow.json").read_text(encoding="utf-8")
    )
    inherited = [
        item for item in plan["limitations"] if item["scope"] == "global"
    ]
    assert artifact["limitations"] == [*inherited, local]


async def test_practice_rejects_malformed_limitations_without_normalizing() -> None:
    flow = practice_flow()
    flow["limitations"] = ["not an object"]
    invalid = await StudyKitGenerator(
        FakeModel(
            [
                model_response(evidence_plan()),
                model_response(learning_content()),
                model_response(flow),
            ]
        ),
        max_repairs=0,
    ).generate(generation_request(), source_chunks())
    assert invalid.failed_stage is GenerationStage.PRACTICE
    assert "schema_validation" in {
        issue.code for issue in invalid.issues
    }


async def test_non_cs_unit_runs_without_math_or_code_practice_types() -> None:
    plan = evidence_plan()
    plan["unit_title_candidate"] = "近代城市史"
    plan["lecture_summary"] = "本单元比较城市化阶段、术语和计量单位。"
    plan["evidence_controls"] = [
        {
            "id": "control-term",
            "control_type": "terminology",
            "statement": "来源中的“都市区”采用其历史定义。",
            "required_action": "state_explicitly",
            "chunk_ids": ["mit-6.7960-f24-lecture-02-slides-p008"],
        },
        {
            "id": "control-order",
            "control_type": "ordering",
            "statement": "先比较工业化前后，再讨论政策变化。",
            "required_action": "follow",
            "chunk_ids": ["mit-6.7960-f24-lecture-02-slides-p026"],
        },
        {
            "id": "control-unit",
            "control_type": "unit",
            "statement": "人口密度按来源中的每平方公里表示。",
            "required_action": "qualify",
            "chunk_ids": ["mit-6.7960-f24-lecture-02-slides-p044"],
        },
    ]
    control_ids = [item["id"] for item in plan["evidence_controls"]]
    practice_types = ("interpretation", "comparison", "application")
    for index, concept in enumerate(plan["core_concept_candidates"]):
        concept["term_en"] = f"historical term {index + 1}"
        concept["term_zh"] = concept["term_en"]
        concept["summary"] = "来源中的历史概念。"
        concept["control_ids"] = [control_ids[index % len(control_ids)]]
    for index, requirement in enumerate(plan["assessment_requirements"]):
        requirement["description"] = "解释一项可观察的历史证据。"
        requirement["control_ids"] = [control_ids[index % len(control_ids)]]
    for index, opportunity in enumerate(plan["practice_opportunities"]):
        opportunity["practice_type"] = practice_types[
            index % len(practice_types)
        ]
        opportunity["description"] = "解释、比较或应用来源中的历史证据。"
        opportunity["control_ids"] = [control_ids[index % len(control_ids)]]
    controls = {item["id"]: item for item in plan["evidence_controls"]}
    plan["practice_chunk_ids"] = sorted(
        {
            chunk_id
            for opportunity in plan["practice_opportunities"]
            for chunk_id in (
                opportunity["chunk_ids"]
                + [
                    control_chunk
                    for control_id in opportunity["control_ids"]
                    for control_chunk in controls[control_id]["chunk_ids"]
                ]
            )
        }
    )

    content = learning_content()
    for index, concept in enumerate(content["core_concepts"]):
        concept["term_en"] = f"historical term {index + 1}"
        concept["term_zh"] = f"历史术语 {index + 1}"
        concept["explanation"] = "根据来源解释这一历史概念。"
    content["glossary"] = []
    content["common_misconceptions"] = []
    content["prerequisites"]["items"] = [
        {"topic": "阅读史料", "required_level": "能够辨认时间和来源"}
    ]
    for objective in content["learning_objectives"]:
        objective["objective"] = "能够解释并比较来源中的历史证据。"
        objective["evidence_required"] = "给出有页码依据的简短解释。"

    flow = practice_flow()
    opportunities = {
        item["id"]: item for item in plan["practice_opportunities"]
    }
    for item in flow["practice"]:
        opportunity = opportunities[item["opportunity_id"]]
        item["practice_type"] = opportunity["practice_type"]
        item["control_ids"] = deepcopy(opportunity["control_ids"])
        item["question"] = "依据指定页，解释或比较一项历史证据。"
        item["hint"] = "先辨认来源中的时间、术语或单位。"
        item["deliverable"] = "提交一段带页码依据的简短回答。"
        item["expected_evidence"] = ["回答准确使用来源中的术语和顺序。"]
        item["evaluation"] = {
            "full_credit": "解释与来源一致并遵守相关控制。",
            "partial_credit": "引用了来源，但解释或控制执行不完整。",
        }
    for item in flow["learning_sequence"]:
        item["activity"] = "阅读、解释或比较本单元史料。"
        if "concept_explanation" in item:
            item["concept_explanation"] = "关注时间顺序、术语和单位。"

    chunks = source_chunks()
    for index, chunk in enumerate(chunks, start=1):
        chunk["content"] = f"城市史来源材料，第 {index} 页。"
    model = FakeModel(
        [
            model_response(plan),
            model_response(content),
            model_response(flow),
            model_response(quality_audit()),
        ]
    )
    result = await StudyKitGenerator(model).generate(
        generation_request(), chunks
    )

    assert result.succeeded
    assert result.studykit is not None
    assert {
        item["practice_type"] for item in result.studykit["practice"]
    } <= {"interpretation", "comparison", "application"}


async def test_final_limitations_are_grouped_and_bounded() -> None:
    chunks = source_chunks()
    for chunk in chunks:
        chunk["parse_warnings"] = [
            "removed_duplicate_lines:3",
            "removed_hidden_formula_noise_lines:2",
            "replaced_invalid_unicode_surrogates:1",
        ]
    result = await StudyKitGenerator(FakeModel(successful_responses())).generate(
        generation_request(), chunks
    )

    assert result.succeeded
    assert result.studykit is not None
    limitations = result.studykit["limitations"]
    assert len(limitations) <= 10
    assert any("文本提取质量风险" in item for item in limitations)
    assert not any("81 页" in item for item in limitations)
    assert not any("p001:" in item for item in limitations)
    assert not any(
        "replaced_invalid_unicode_surrogates" in item
        for item in limitations
    )


async def test_final_title_and_limitations_hide_internal_pipeline_names() -> None:
    plan = evidence_plan()
    plan["unit_title_candidate"] = "Lecture 4: Architectures for Grids — EvidencePlan"
    plan["limitations"][0]["description"] = (
        "parse warnings include low_extracted_text, "
        "removed duplicate lines, removed hidden formula noise, and "
        "replaced_invalid_unicode_surrogates."
    )
    model = FakeModel(
        [
            model_response(plan),
            model_response(learning_content()),
            model_response(practice_flow()),
            model_response(quality_audit()),
        ]
    )

    result = await StudyKitGenerator(model).generate(
        generation_request(), source_chunks()
    )

    assert result.succeeded
    assert result.studykit is not None
    assert result.studykit["title"] == (
        "StudyKit: Lecture 4: Architectures for Grids"
    )
    learner_text = json.dumps(result.studykit, ensure_ascii=False)
    assert "EvidencePlan" not in learner_text
    assert "parse warnings" not in learner_text
    assert "low_extracted_text" not in learner_text
    assert "removed_duplicate_lines" not in learner_text
    assert "removed duplicate lines" not in learner_text
    assert "removed_hidden_formula_noise_lines" not in learner_text
    assert "removed hidden formula noise" not in learner_text
    assert "replaced_invalid_unicode_surrogates" not in learner_text
