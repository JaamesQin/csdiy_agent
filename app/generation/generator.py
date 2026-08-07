"""Staged StudyKit generation, recovery, validation and assembly."""

from __future__ import annotations

import hashlib
import inspect
import json
import re
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable

import jsonschema

from app.generation.evidence import (
    DEFAULT_SOURCE_CHUNK_SCHEMA,
    EvidenceBundle,
    EvidenceValidationError,
    build_evidence_bundle,
)
from app.generation.model import (
    ModelError,
    ModelResponse,
    ModelResponseError,
    StructuredModel,
)
from app.generation.prompts import (
    PROMPT_VERSION,
    PROMPT_VERSIONS,
    SYSTEM_PROMPT,
    build_audit_repair_prompt,
    build_stage_prompt,
    build_stage_repair_prompt,
)
from app.generation.result import (
    GenerationIssue,
    GenerationRequest,
    GenerationResult,
    GenerationStage,
    GenerationStatus,
    StageResult,
)
from app.retrieval.citations import _expand_pages, validate_citations
from app.retrieval.render import render_studykit_markdown
from app.retrieval.schema_validation import load_json

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STUDYKIT_SCHEMA = ROOT / "schemas/studykit.schema.json"
DEFAULT_STAGE_SCHEMAS = {
    GenerationStage.EVIDENCE: ROOT / "schemas/evidence-plan.schema.json",
    GenerationStage.CONTENT: ROOT / "schemas/learning-content.schema.json",
    GenerationStage.PRACTICE: ROOT / "schemas/practice-flow.schema.json",
    GenerationStage.AUDIT: ROOT / "schemas/quality-audit.schema.json",
}
STAGE_FILENAMES = {
    GenerationStage.EVIDENCE: "01-evidence-plan.json",
    GenerationStage.CONTENT: "02-learning-content.json",
    GenerationStage.PRACTICE: "03-practice-flow.json",
    GenerationStage.AUDIT: "04-quality-audit.json",
    GenerationStage.ASSEMBLE: "05-studykit.json",
}
SEMANTIC_STAGES = (
    GenerationStage.EVIDENCE,
    GenerationStage.CONTENT,
    GenerationStage.PRACTICE,
    GenerationStage.AUDIT,
)
ALL_STAGES = (*SEMANTIC_STAGES, GenerationStage.ASSEMBLE)
PIPELINE_VERSION = "studykit-pipeline-v0.6-012"
RUN_VERSION = 14


@dataclass
class _StageCall:
    output: dict[str, Any] | None
    issues: tuple[GenerationIssue, ...]
    responses: list[ModelResponse]
    model_error: ModelError | None = None
    duration_seconds: float = 0.0


class StudyKitGenerator:
    """Generate three reviewable semantic artifacts, then assemble deterministically."""

    def __init__(
        self,
        model: StructuredModel,
        *,
        audit_model: StructuredModel | None = None,
        studykit_schema_path: Path = DEFAULT_STUDYKIT_SCHEMA,
        source_chunk_schema_path: Path = DEFAULT_SOURCE_CHUNK_SCHEMA,
        stage_schema_paths: dict[GenerationStage, Path] | None = None,
        max_repairs: int = 1,
        stage_timeout_seconds: float = 600.0,
        stage_max_tokens: int = 65_536,
    ) -> None:
        if not 0 <= max_repairs <= 1:
            raise ValueError("max_repairs must be zero or one")
        if stage_timeout_seconds <= 0 or stage_max_tokens <= 0:
            raise ValueError("stage timeout and max_tokens must be positive")
        self._model = model
        self._audit_model = audit_model or model
        self._studykit_schema_path = studykit_schema_path
        self._source_chunk_schema_path = source_chunk_schema_path
        self._stage_schema_paths = dict(
            stage_schema_paths or DEFAULT_STAGE_SCHEMAS
        )
        self._max_repairs = max_repairs
        self._stage_timeout_seconds = stage_timeout_seconds
        self._stage_max_tokens = stage_max_tokens

    async def generate(
        self,
        request: GenerationRequest,
        chunks: Iterable[dict[str, Any]],
        *,
        output_dir: Path | None = None,
        resume: bool = False,
        from_stage: GenerationStage | str | None = None,
        manifest_hash: str | None = None,
    ) -> GenerationResult:
        """Run or recover the pipeline while preserving the original public entry."""

        try:
            evidence = build_evidence_bundle(
                request, chunks, schema_path=self._source_chunk_schema_path
            )
        except EvidenceValidationError as exc:
            insufficient = {"no_chunks", "no_usable_chunks"}
            status = (
                GenerationStatus.INSUFFICIENT_EVIDENCE
                if all(issue.code in insufficient for issue in exc.issues)
                else GenerationStatus.INVALID_INPUT
            )
            return self._result(
                status, request, (), exc.issues, (), failed_stage=None
            )

        requested_stage = _coerce_stage(from_stage)
        fingerprint = self._fingerprint(request, evidence, manifest_hash)
        run = self._new_run(fingerprint, manifest_hash)
        reused: dict[GenerationStage, dict[str, Any]] = {}
        stages: list[StageResult] = []

        if output_dir is not None:
            output_dir.mkdir(parents=True, exist_ok=True)
            if resume or requested_stage is not None:
                recovery = self._load_recovery(
                    output_dir,
                    fingerprint,
                    requested_stage=requested_stage,
                    resume=resume,
                    evidence=evidence,
                    request=request,
                )
                if isinstance(recovery, tuple):
                    reused, start_stage = recovery
                    existing = _read_json(output_dir / "run.json")
                    if isinstance(existing, dict):
                        run = existing
                else:
                    issue = recovery
                    return self._result(
                        GenerationStatus.INVALID_INPUT,
                        request,
                        evidence.used_chunk_ids,
                        (issue,),
                        (),
                        failed_stage=requested_stage,
                    )
            else:
                start_stage = GenerationStage.EVIDENCE
            self._write_run(output_dir, run)
        else:
            if resume or requested_stage is not None:
                issue = GenerationIssue(
                    stage="recovery",
                    code="output_dir_required",
                    message="resume/from-stage requires output_dir",
                )
                return self._result(
                    GenerationStatus.INVALID_INPUT,
                    request,
                    evidence.used_chunk_ids,
                    (issue,),
                    (),
                    failed_stage=requested_stage,
                )
            start_stage = GenerationStage.EVIDENCE

        artifacts: dict[GenerationStage, dict[str, Any]] = dict(reused)
        audit_repairs_applied = (
            run.get("stages", {})
            .get(GenerationStage.AUDIT.value, {})
            .get("outcome")
            == "repairs_applied_unverified"
        )
        for stage in ALL_STAGES:
            if _stage_index(stage) < _stage_index(start_stage):
                stages.append(
                    StageResult(stage=stage, status="succeeded", reused=True)
                )

        for stage in ALL_STAGES[_stage_index(start_stage) :]:
            if stage is GenerationStage.AUDIT:
                preassembled = self._assemble(
                    request,
                    evidence,
                    artifacts[GenerationStage.EVIDENCE],
                    artifacts[GenerationStage.CONTENT],
                    artifacts[GenerationStage.PRACTICE],
                )
                audit_candidate = _audit_projection(preassembled)
                audit_call = await self._generate_stage(
                    stage,
                    request,
                    evidence,
                    load_json(self._stage_schema_paths[stage]),
                    evidence_plan=artifacts[GenerationStage.EVIDENCE],
                    learning_content=artifacts[GenerationStage.CONTENT],
                    practice_flow=artifacts[GenerationStage.PRACTICE],
                    assembled_candidate=audit_candidate,
                )
                audit_responses = list(audit_call.responses)
                audit_error = audit_call.model_error
                audit_issues = audit_call.issues
                audit_output = audit_call.output
                repaired_stages: list[GenerationStage] = []
                deterministically_resolved: list[dict[str, Any]] = []
                audit_outcome: str | None = None

                if (
                    audit_error is None
                    and audit_output is not None
                    and not audit_issues
                    and _audit_blockers(audit_output)
                ):
                    if output_dir is not None:
                        _write_json(
                            output_dir / STAGE_FILENAMES[stage],
                            audit_output,
                        )
                    blockers = _audit_blockers(audit_output)
                    assembly_validation_issues = self._validate_final(
                        evidence, preassembled
                    )
                    deterministically_resolved = [
                        item
                        for item in blockers
                        if _assembly_blocker_is_resolved(
                            item, assembly_validation_issues
                        )
                    ]
                    resolved_ids = {
                        item["id"] for item in deterministically_resolved
                    }
                    actionable_blockers = [
                        item for item in blockers if item["id"] not in resolved_ids
                    ]
                    promoted_boundary_blockers = (
                        _promote_audit_boundary_blockers(
                            actionable_blockers,
                            artifacts[GenerationStage.EVIDENCE],
                        )
                    )
                    actionable_blockers = [
                        *promoted_boundary_blockers,
                        *actionable_blockers,
                    ]
                    blocker_targets = {
                        issue["target_stage"]
                        for issue in actionable_blockers
                    }
                    if self._max_repairs == 0 and actionable_blockers:
                        audit_issues = _audit_generation_issues(
                            actionable_blockers
                        )
                    elif "assembly" in blocker_targets:
                        audit_issues = _audit_generation_issues(
                            actionable_blockers
                        )
                    else:
                        for target in (
                            GenerationStage.EVIDENCE,
                            GenerationStage.CONTENT,
                            GenerationStage.PRACTICE,
                        ):
                            target_issues = [
                                item
                                for item in actionable_blockers
                                if item["target_stage"] == target.value
                            ]
                            if not target_issues:
                                continue
                            repair = await self._repair_artifact_from_audit(
                                target,
                                request,
                                evidence,
                                (
                                    None
                                    if target is GenerationStage.EVIDENCE
                                    else artifacts[GenerationStage.EVIDENCE]
                                ),
                                artifacts.get(GenerationStage.CONTENT),
                                artifacts[target],
                                target_issues,
                            )
                            if (
                                output_dir is not None
                                and (repair.output is None or repair.issues)
                            ):
                                self._record_audit_repair_failure(
                                    output_dir,
                                    target,
                                    repair.output,
                                    repair.issues,
                                )
                            if repair.model_error is not None:
                                audit_error = repair.model_error
                                break
                            if repair.output is None or repair.issues:
                                audit_issues = repair.issues
                                break
                            artifacts[target] = repair.output
                            repaired_stages.append(target)
                            repair_infos = tuple(
                                _model_info(item) for item in repair.responses
                            )
                            self._record_audit_repair_success(
                                output_dir,
                                run,
                                target,
                                repair.output,
                                repair_infos,
                                duration_seconds=repair.duration_seconds,
                            )
                            for index, prior in enumerate(stages):
                                if prior.stage is target:
                                    stages[index] = replace(
                                        prior,
                                        status="repaired",
                                        attempts=prior.attempts
                                        + len(repair.responses),
                                        model_info=(
                                            *prior.model_info,
                                            *repair_infos,
                                        ),
                                        duration_seconds=(
                                            prior.duration_seconds
                                            + repair.duration_seconds
                                        ),
                                    )
                                    break

                        if audit_error is None and not audit_issues and (
                            repaired_stages or deterministically_resolved
                        ):
                            audit_repairs_applied = bool(repaired_stages)
                            audit_outcome = (
                                "repairs_applied_unverified"
                                if repaired_stages
                                else "audit_findings_deterministically_resolved"
                            )
                            self._record_audit_resolution(
                                output_dir,
                                audit_output,
                                repaired_stages,
                                deterministically_resolved,
                            )

                model_infos = tuple(
                    _model_info(item) for item in audit_responses
                )
                audit_duration = audit_call.duration_seconds
                if audit_error is not None:
                    audit_issues = (
                        GenerationIssue(
                            stage="audit",
                            code=type(audit_error).__name__,
                            message=str(audit_error),
                        ),
                    )
                    audit_status = GenerationStatus.MODEL_ERROR
                else:
                    audit_status = GenerationStatus.FAILED_VALIDATION
                if audit_output is None or audit_issues:
                    stages.append(
                        StageResult(
                            stage=stage,
                            status=audit_status.value,
                            attempts=len(audit_responses),
                            issues=audit_issues,
                            model_info=model_infos,
                            duration_seconds=audit_duration,
                        )
                    )
                    self._record_failure(
                        output_dir,
                        run,
                        stage,
                        audit_output,
                        audit_issues,
                        model_infos,
                        duration_seconds=audit_duration,
                    )
                    return self._result(
                        audit_status,
                        request,
                        evidence.used_chunk_ids,
                        audit_issues,
                        tuple(stages),
                        failed_stage=stage,
                    )

                artifacts[stage] = audit_output
                stages.append(
                    StageResult(
                        stage=stage,
                        status="succeeded",
                        attempts=len(audit_responses),
                        model_info=model_infos,
                        duration_seconds=audit_duration,
                    )
                )
                self._record_success(
                    output_dir,
                    run,
                    stage,
                    audit_output,
                    model_infos,
                    duration_seconds=audit_duration,
                )
                if audit_outcome is not None and output_dir is not None:
                    run["stages"][stage.value]["outcome"] = audit_outcome
                    self._write_run(output_dir, run)
                continue

            if stage is GenerationStage.ASSEMBLE:
                assembly_started = time.perf_counter()
                candidate = self._assemble(
                    request,
                    evidence,
                    artifacts[GenerationStage.EVIDENCE],
                    artifacts[GenerationStage.CONTENT],
                    artifacts[GenerationStage.PRACTICE],
                    audit_repairs_applied=audit_repairs_applied,
                )
                issues = self._validate_final(evidence, candidate)
                assembly_duration = time.perf_counter() - assembly_started
                if issues:
                    stage_result = StageResult(
                        stage=stage,
                        status="failed_validation",
                        attempts=0,
                        issues=issues,
                        duration_seconds=assembly_duration,
                    )
                    stages.append(stage_result)
                    self._record_failure(
                        output_dir,
                        run,
                        stage,
                        candidate,
                        issues,
                        duration_seconds=assembly_duration,
                    )
                    return self._result(
                        GenerationStatus.FAILED_VALIDATION,
                        request,
                        evidence.used_chunk_ids,
                        issues,
                        tuple(stages),
                        failed_stage=stage,
                    )
                artifacts[stage] = candidate
                stages.append(
                    StageResult(
                        stage=stage,
                        status="succeeded",
                        duration_seconds=assembly_duration,
                    )
                )
                self._record_success(
                    output_dir,
                    run,
                    stage,
                    candidate,
                    None,
                    duration_seconds=assembly_duration,
                )
                continue

            schema = load_json(self._stage_schema_paths[stage])
            plan = artifacts.get(GenerationStage.EVIDENCE)
            content = artifacts.get(GenerationStage.CONTENT)
            call = await self._generate_stage(
                stage,
                request,
                evidence,
                schema,
                evidence_plan=plan,
                learning_content=content,
                practice_flow=None,
                assembled_candidate=None,
            )
            model_infos = tuple(_model_info(item) for item in call.responses)
            if call.model_error is not None:
                issue = GenerationIssue(
                    stage=stage.value,
                    code=type(call.model_error).__name__,
                    message=str(call.model_error),
                )
                stages.append(
                    StageResult(
                        stage=stage,
                        status="model_error",
                        attempts=len(call.responses) + 1,
                        issues=(issue,),
                        model_info=model_infos,
                        duration_seconds=call.duration_seconds,
                    )
                )
                self._record_failure(
                    output_dir,
                    run,
                    stage,
                    call.output,
                    (issue,),
                    model_infos,
                    duration_seconds=call.duration_seconds,
                    raw_candidate=next(
                        (
                            response.raw_content
                            for response in reversed(call.responses)
                            if response.raw_content
                        ),
                        None,
                    ),
                )
                return self._result(
                    GenerationStatus.MODEL_ERROR,
                    request,
                    evidence.used_chunk_ids,
                    (issue,),
                    tuple(stages),
                    failed_stage=stage,
                )
            if call.output is None or call.issues:
                stages.append(
                    StageResult(
                        stage=stage,
                        status="failed_validation",
                        attempts=len(call.responses),
                        issues=call.issues,
                        model_info=model_infos,
                        duration_seconds=call.duration_seconds,
                    )
                )
                self._record_failure(
                    output_dir,
                    run,
                    stage,
                    call.output,
                    call.issues,
                    model_infos,
                    duration_seconds=call.duration_seconds,
                )
                return self._result(
                    GenerationStatus.FAILED_VALIDATION,
                    request,
                    evidence.used_chunk_ids,
                    call.issues,
                    tuple(stages),
                    failed_stage=stage,
                )
            artifacts[stage] = call.output
            stages.append(
                StageResult(
                    stage=stage,
                    status="succeeded",
                    attempts=len(call.responses),
                    model_info=model_infos,
                    duration_seconds=call.duration_seconds,
                )
            )
            self._record_success(
                output_dir,
                run,
                stage,
                call.output,
                model_infos,
                duration_seconds=call.duration_seconds,
            )

        final = artifacts[GenerationStage.ASSEMBLE]
        all_model_info = [
            info for stage in stages for info in stage.model_info
        ]
        return GenerationResult(
            status=GenerationStatus.SUCCEEDED,
            studykit=final,
            issues=(),
            used_chunk_ids=evidence.used_chunk_ids,
            attempts=sum(stage.attempts for stage in stages),
            prompt_version=PROMPT_VERSION,
            model_info={
                "calls": all_model_info,
                "usage": _sum_usage(all_model_info),
            },
            stages=tuple(stages),
        )

    async def _generate_stage(
        self,
        stage: GenerationStage,
        request: GenerationRequest,
        evidence: EvidenceBundle,
        schema: dict[str, Any],
        *,
        evidence_plan: dict[str, Any] | None,
        learning_content: dict[str, Any] | None,
        practice_flow: dict[str, Any] | None,
        assembled_candidate: dict[str, Any] | None,
    ) -> _StageCall:
        started = time.perf_counter()
        prompt = build_stage_prompt(
            stage,
            request,
            evidence,
            schema,
            evidence_plan=evidence_plan,
            learning_content=learning_content,
            practice_flow=practice_flow,
            assembled_candidate=assembled_candidate,
        )
        candidate: dict[str, Any] | None = None
        responses: list[ModelResponse] = []
        issues: tuple[GenerationIssue, ...] = ()
        for attempt in range(self._max_repairs + 1):
            try:
                response = await self._call_model(
                    prompt,
                    thinking_enabled=(
                        True
                        if stage is GenerationStage.AUDIT
                        else (
                            True
                            if attempt == 0
                            else _needs_semantic_repair(issues)
                        )
                    ),
                    model=(
                        self._audit_model
                        if stage is GenerationStage.AUDIT
                        else self._model
                    ),
                )
            except ModelError as exc:
                error_response = _model_error_response(exc)
                if error_response is not None:
                    responses.append(error_response)
                return _StageCall(
                    candidate,
                    issues,
                    responses,
                    exc,
                    time.perf_counter() - started,
                )
            responses.append(response)
            candidate = _normalize_stage_candidate(
                stage,
                dict(response.output),
                evidence_plan,
            )
            issues = self._validate_stage(
                stage,
                schema,
                evidence,
                candidate,
                evidence_plan,
                request,
                learning_content,
            )
            if not issues:
                return _StageCall(
                    candidate,
                    (),
                    responses,
                    duration_seconds=time.perf_counter() - started,
                )
            if attempt < self._max_repairs:
                prompt = build_stage_repair_prompt(
                    stage,
                    request,
                    evidence,
                    schema,
                    candidate,
                    issues,
                    evidence_plan=evidence_plan,
                    learning_content=learning_content,
                    practice_flow=practice_flow,
                    assembled_candidate=assembled_candidate,
                )
        return _StageCall(
            candidate,
            issues,
            responses,
            duration_seconds=time.perf_counter() - started,
        )

    async def _repair_artifact_from_audit(
        self,
        stage: GenerationStage,
        request: GenerationRequest,
        evidence: EvidenceBundle,
        evidence_plan: dict[str, Any] | None,
        learning_content: dict[str, Any] | None,
        candidate: dict[str, Any],
        audit_issues: list[dict[str, Any]],
    ) -> _StageCall:
        """Apply one semantic repair requested by the independent audit."""

        started = time.perf_counter()
        schema = load_json(self._stage_schema_paths[stage])
        prompt = build_audit_repair_prompt(
            stage,
            request,
            evidence,
            schema,
            candidate,
            audit_issues,
            evidence_plan=evidence_plan,
            learning_content=(
                learning_content
                if stage is GenerationStage.PRACTICE
                else None
            ),
        )
        try:
            response = await self._call_model(
                prompt, thinking_enabled=True, model=self._model
            )
        except ModelError as exc:
            responses = []
            error_response = _model_error_response(exc)
            if error_response is not None:
                responses.append(error_response)
            repair_issues = tuple(
                GenerationIssue(
                    stage="audit",
                    code=item["category"],
                    message=item["repair_instruction"],
                    location=item["location"],
                )
                for item in audit_issues
            )
            return _StageCall(
                candidate,
                repair_issues,
                responses,
                exc,
                time.perf_counter() - started,
            )
        repaired = _normalize_stage_candidate(
            stage,
            dict(response.output),
            evidence_plan,
        )
        validation = self._validate_stage(
            stage,
            schema,
            evidence,
            repaired,
            evidence_plan,
            request,
            learning_content,
        )
        if repaired == candidate:
            validation = (
                *validation,
                GenerationIssue(
                    stage=stage.value,
                    code="audit_repair_unchanged",
                    message="audit repair returned an unchanged artifact",
                    location=stage.value,
                ),
            )
        return _StageCall(
            repaired,
            validation,
            [response],
            duration_seconds=time.perf_counter() - started,
        )

    async def _call_model(
        self,
        prompt: str,
        *,
        thinking_enabled: bool,
        model: StructuredModel | None = None,
    ) -> ModelResponse:
        selected_model = model or self._model
        kwargs = {
            "system_prompt": SYSTEM_PROMPT,
            "user_prompt": prompt,
            "thinking_enabled": thinking_enabled,
            "max_tokens": self._stage_max_tokens,
            "timeout_seconds": self._stage_timeout_seconds,
        }
        # Keep small local FakeModels written for the v0.1 protocol usable.
        parameters = inspect.signature(selected_model.generate_json).parameters
        accepts_kwargs = any(
            parameter.kind is inspect.Parameter.VAR_KEYWORD
            for parameter in parameters.values()
        )
        supported = (
            kwargs
            if accepts_kwargs
            else {key: value for key, value in kwargs.items() if key in parameters}
        )
        return await selected_model.generate_json(**supported)

    def _validate_stage(
        self,
        stage: GenerationStage,
        schema: dict[str, Any],
        evidence: EvidenceBundle,
        candidate: dict[str, Any],
        plan: dict[str, Any] | None,
        request: GenerationRequest | None = None,
        learning_content: dict[str, Any] | None = None,
    ) -> tuple[GenerationIssue, ...]:
        issues = list(_schema_issues(stage.value, schema, candidate))
        if issues:
            return tuple(issues)
        chunk_index = {chunk["chunk_id"]: chunk for chunk in evidence.usable_chunks}
        if stage is GenerationStage.EVIDENCE:
            for location, chunk_id in _iter_plan_chunk_ids(candidate):
                if chunk_id not in chunk_index:
                    issues.append(
                        GenerationIssue(
                            stage=stage.value,
                            code="unknown_chunk_id",
                            message=f"chunk_id {chunk_id!r} is not in the input",
                            location=location,
                        )
                    )
            issues.extend(_unique_field_issues(stage.value, candidate, "page_segments", "id"))
            issues.extend(
                _unique_field_issues(
                    stage.value, candidate, "core_concept_candidates", "id"
                )
            )
            available_pages = {
                chunk["anchor"]["value"] for chunk in evidence.usable_chunks
            }
            for index, segment in enumerate(candidate["page_segments"]):
                for page in _expand_pages(segment["pages"]):
                    if page not in available_pages:
                        issues.append(
                            GenerationIssue(
                                stage=stage.value,
                                code="page_not_parsed",
                                message=f"segment page {page} is not in the input",
                                location=f"page_segments[{index}].pages",
                            )
                        )
            issues.extend(
                _unique_field_issues(
                    stage.value, candidate, "practice_opportunities", "id"
                )
            )
            issues.extend(
                _unique_field_issues(
                    stage.value, candidate, "assessment_requirements", "id"
                )
            )
            issues.extend(
                _unique_field_issues(
                    stage.value, candidate, "evidence_controls", "id"
                )
            )
            concept_ids = {
                item["id"] for item in candidate["core_concept_candidates"]
            }
            control_ids = {
                item["id"] for item in candidate["evidence_controls"]
            }
            for collection in (
                "core_concept_candidates",
                "assessment_requirements",
                "practice_opportunities",
            ):
                for index, item in enumerate(candidate[collection]):
                    unknown_controls = set(item["control_ids"]) - control_ids
                    if unknown_controls:
                        issues.append(
                            GenerationIssue(
                                stage=stage.value,
                                code="unknown_control_id",
                                message=(
                                    "unknown control ids: "
                                    f"{sorted(unknown_controls)}"
                                ),
                                location=f"{collection}[{index}].control_ids",
                            )
                        )
            core_ids = {
                item["id"]
                for item in candidate["core_concept_candidates"]
                if item["priority"] == "core"
            }
            covered_concepts: set[str] = set()
            requirement_ids = {
                item["id"] for item in candidate["assessment_requirements"]
            }
            requirement_concepts: set[str] = set()
            for index, requirement in enumerate(
                candidate["assessment_requirements"]
            ):
                unknown = set(requirement["concept_ids"]) - concept_ids
                if unknown:
                    issues.append(
                        GenerationIssue(
                            stage=stage.value,
                            code="unknown_concept_id",
                            message=f"unknown concept ids: {sorted(unknown)}",
                            location=(
                                f"assessment_requirements[{index}].concept_ids"
                            ),
                        )
                    )
                requirement_concepts.update(requirement["concept_ids"])
            covered_requirements: set[str] = set()
            for index, opportunity in enumerate(
                candidate["practice_opportunities"]
            ):
                unknown = set(opportunity["concept_ids"]) - concept_ids
                if unknown:
                    issues.append(
                        GenerationIssue(
                            stage=stage.value,
                            code="unknown_concept_id",
                            message=f"unknown concept ids: {sorted(unknown)}",
                            location=(
                                f"practice_opportunities[{index}].concept_ids"
                            ),
                        )
                    )
                covered_concepts.update(opportunity["concept_ids"])
                unknown_requirements = (
                    set(opportunity["requirement_ids"]) - requirement_ids
                )
                if unknown_requirements:
                    issues.append(
                        GenerationIssue(
                            stage=stage.value,
                            code="unknown_requirement_id",
                            message=(
                                "unknown requirement ids: "
                                f"{sorted(unknown_requirements)}"
                            ),
                            location=(
                                f"practice_opportunities[{index}].requirement_ids"
                            ),
                        )
                    )
                covered_requirements.update(opportunity["requirement_ids"])
            missing_core = core_ids - covered_concepts
            if missing_core:
                issues.append(
                    GenerationIssue(
                        stage=stage.value,
                        code="core_practice_coverage",
                        message=(
                            "core concepts without a practice opportunity: "
                            f"{sorted(missing_core)}"
                        ),
                        location="practice_opportunities",
                    )
                )
            missing_requirement_concepts = core_ids - requirement_concepts
            if missing_requirement_concepts:
                issues.append(
                    GenerationIssue(
                        stage=stage.value,
                        code="core_requirement_coverage",
                        message=(
                            "core concepts without an assessment requirement: "
                            f"{sorted(missing_requirement_concepts)}"
                        ),
                        location="assessment_requirements",
                    )
                )
            missing_requirements = requirement_ids - covered_requirements
            if missing_requirements:
                issues.append(
                    GenerationIssue(
                        stage=stage.value,
                        code="requirement_opportunity_coverage",
                        message=(
                            "requirements without a practice opportunity: "
                            f"{sorted(missing_requirements)}"
                        ),
                        location="practice_opportunities",
                    )
                )
            expected_content_chunks = {
                chunk_id
                for collection in (
                    candidate["core_concept_candidates"],
                    candidate["assessment_requirements"],
                    candidate["evidence_controls"],
                )
                for item in collection
                for chunk_id in item["chunk_ids"]
            }
            actual_content_chunks = set(candidate["content_chunk_ids"])
            if actual_content_chunks != expected_content_chunks:
                issues.append(
                    GenerationIssue(
                        stage=stage.value,
                        code="content_chunk_selection",
                        message=(
                            f"missing={sorted(expected_content_chunks - actual_content_chunks)}, "
                            f"extra={sorted(actual_content_chunks - expected_content_chunks)}"
                        ),
                        location="content_chunk_ids",
                    )
                )
            opportunity_control_ids = {
                control_id
                for item in candidate["practice_opportunities"]
                for control_id in item["control_ids"]
            }
            controls_by_id = {
                item["id"]: item for item in candidate["evidence_controls"]
            }
            expected_practice_chunks = {
                chunk_id
                for item in candidate["practice_opportunities"]
                for chunk_id in item["chunk_ids"]
            }
            expected_practice_chunks.update(
                chunk_id
                for control_id in opportunity_control_ids
                if control_id in controls_by_id
                for chunk_id in controls_by_id[control_id]["chunk_ids"]
            )
            actual_practice_chunks = set(candidate["practice_chunk_ids"])
            if actual_practice_chunks != expected_practice_chunks:
                issues.append(
                    GenerationIssue(
                        stage=stage.value,
                        code="practice_chunk_selection",
                        message=(
                            f"missing={sorted(expected_practice_chunks - actual_practice_chunks)}, "
                            f"extra={sorted(actual_practice_chunks - expected_practice_chunks)}"
                        ),
                        location="practice_chunk_ids",
                    )
                )
            opportunity_types = {
                item["practice_type"]
                for item in candidate["practice_opportunities"]
            }
            issues.extend(
                _practice_type_diversity_issues(
                    stage.value, opportunity_types, "practice_opportunities"
                )
            )
        elif stage is GenerationStage.CONTENT:
            assert plan is not None
            allowed = set(plan["content_chunk_ids"])
            allowed_pages = {
                (chunk_index[item]["source_id"], chunk_index[item]["anchor"]["value"])
                for item in allowed
            }
            outline_pages = {
                chunk["anchor"]["value"] for chunk in evidence.all_chunks
            }
            issues.extend(
                _content_reference_issues(
                    candidate,
                    allowed_pages,
                    outline_pages=outline_pages,
                )
            )
            issues.extend(
                _unique_field_issues(stage.value, candidate, "learning_objectives", "id")
            )
            issues.extend(
                _unique_field_issues(stage.value, candidate, "core_concepts", "id")
            )
            issues.extend(_sequence_issues(stage.value, candidate, "outline", "order"))
            evidence_ids = {
                item["id"] for item in plan["core_concept_candidates"]
            }
            required_ids = {
                item["id"]
                for item in plan["core_concept_candidates"]
                if item["priority"] == "core"
            }
            actual_ids = {
                item["evidence_concept_id"]
                for item in candidate["core_concepts"]
            }
            unknown_ids = actual_ids - evidence_ids
            missing_ids = required_ids - actual_ids
            if unknown_ids:
                issues.append(
                    GenerationIssue(
                        stage=stage.value,
                        code="unknown_evidence_concept",
                        message=f"unknown evidence concept ids: {sorted(unknown_ids)}",
                        location="core_concepts",
                    )
                )
            if missing_ids:
                issues.append(
                    GenerationIssue(
                        stage=stage.value,
                        code="missing_core_concept",
                        message=f"missing core concepts: {sorted(missing_ids)}",
                        location="core_concepts",
                    )
                )
            requirement_ids = {
                item["id"] for item in plan["assessment_requirements"]
            }
            used_requirements = {
                requirement_id
                for objective in candidate["learning_objectives"]
                for requirement_id in objective["requirement_ids"]
            }
            unknown_requirements = used_requirements - requirement_ids
            missing_requirements = requirement_ids - used_requirements
            if unknown_requirements or missing_requirements:
                issues.append(
                    GenerationIssue(
                        stage=stage.value,
                        code="objective_requirement_coverage",
                        message=(
                            f"missing={sorted(missing_requirements)}, "
                            f"unknown={sorted(unknown_requirements)}"
                        ),
                        location="learning_objectives",
                    )
                )
            issues.extend(_terminology_issues(candidate))
        elif stage is GenerationStage.PRACTICE:
            assert plan is not None
            allowed_pages = {
                chunk_index[item]["anchor"]["value"]
                for item in plan["practice_chunk_ids"]
            }
            sequence_pages = {
                chunk["anchor"]["value"] for chunk in evidence.all_chunks
            }
            for index, item in enumerate(candidate["practice"]):
                for page in item["source_pages"]:
                    if page not in allowed_pages:
                        issues.append(
                            GenerationIssue(
                                stage=stage.value,
                                code="page_not_selected",
                                message=f"practice page {page} is outside practice chunks",
                                location=f"practice[{index}].source_pages",
                            )
                        )
                if item["question"].strip() == item["deliverable"].strip():
                    issues.append(
                        GenerationIssue(
                            stage=stage.value,
                            code="practice_not_actionable",
                            message="question and deliverable must not be identical",
                            location=f"practice[{index}]",
                        )
                    )
            for index, item in enumerate(candidate["learning_sequence"]):
                source_pages = item.get("source_pages")
                if source_pages is None:
                    continue
                for page in _expand_pages(source_pages):
                    if page not in sequence_pages:
                        issues.append(
                            GenerationIssue(
                                stage=stage.value,
                                code="page_not_selected",
                                message=(
                                    f"learning sequence page {page} is outside "
                                    "selected chunks"
                                ),
                                location=f"learning_sequence[{index}].source_pages",
                            )
                        )
            issues.extend(_unique_field_issues(stage.value, candidate, "practice", "id"))
            issues.extend(
                _sequence_issues(
                    stage.value, candidate, "learning_sequence", "step"
                )
            )
            total_minutes = sum(
                item["duration_minutes"]
                for item in candidate["learning_sequence"]
            )
            if request is not None and total_minutes != request.target_minutes:
                issues.append(
                    GenerationIssue(
                        stage=stage.value,
                        code="study_time_mismatch",
                        message=(
                            f"learning_sequence totals {total_minutes} minutes; "
                            f"expected {request.target_minutes}"
                        ),
                        location="learning_sequence",
                    )
                )
            assert learning_content is not None
            objective_ids = {
                item["id"] for item in learning_content["learning_objectives"]
            }
            objective_requirements = {
                item["id"]: set(item["requirement_ids"])
                for item in learning_content["learning_objectives"]
            }
            concept_ids = {
                item["id"] for item in learning_content["core_concepts"]
            }
            concept_ids.update(
                item["evidence_concept_id"]
                for item in learning_content["core_concepts"]
            )
            covered_objectives = {
                objective_id
                for item in candidate["practice"]
                for objective_id in item["objective_ids"]
            }
            covered_concepts = {
                concept_id
                for item in candidate["practice"]
                for concept_id in item["concept_ids"]
            }
            covered_requirements = {
                requirement_id
                for item in candidate["practice"]
                for requirement_id in item["requirement_ids"]
            }
            unknown_objectives = covered_objectives - objective_ids
            unknown_concepts = covered_concepts - concept_ids
            missing_objectives = objective_ids - covered_objectives
            if unknown_objectives or missing_objectives:
                issues.append(
                    GenerationIssue(
                        stage=stage.value,
                        code="objective_coverage",
                        message=(
                            f"missing={sorted(missing_objectives)}, "
                            f"unknown={sorted(unknown_objectives)}"
                        ),
                        location="practice",
                    )
                )
            if unknown_concepts:
                issues.append(
                    GenerationIssue(
                        stage=stage.value,
                        code="unknown_content_concept",
                        message=f"unknown concept ids: {sorted(unknown_concepts)}",
                        location="practice",
                    )
                )
            plan_requirements = {
                item["id"] for item in plan["assessment_requirements"]
            }
            required_requirements = {
                requirement_id
                for values in objective_requirements.values()
                for requirement_id in values
            }
            unknown_requirements = covered_requirements - plan_requirements
            missing_requirements = required_requirements - covered_requirements
            if unknown_requirements or missing_requirements:
                issues.append(
                    GenerationIssue(
                        stage=stage.value,
                        code="requirement_coverage",
                        message=(
                            f"missing={sorted(missing_requirements)}, "
                            f"unknown={sorted(unknown_requirements)}"
                        ),
                        location="practice",
                    )
                )
            if plan is not None:
                opportunity_ids = {
                    item["id"] for item in plan["practice_opportunities"]
                }
                actual_opportunities = {
                    item["opportunity_id"] for item in candidate["practice"]
                }
                missing_opportunities = opportunity_ids - actual_opportunities
                unknown_opportunities = actual_opportunities - opportunity_ids
                if missing_opportunities or unknown_opportunities:
                    issues.append(
                        GenerationIssue(
                            stage=stage.value,
                            code="opportunity_coverage",
                            message=(
                                f"missing={sorted(missing_opportunities)}, "
                                f"unknown={sorted(unknown_opportunities)}"
                            ),
                            location="practice",
                        )
                    )
                opportunity_requirements = {
                    item["id"]: set(item["requirement_ids"])
                    for item in plan["practice_opportunities"]
                }
                opportunities = {
                    item["id"]: item for item in plan["practice_opportunities"]
                }
                for index, item in enumerate(candidate["practice"]):
                    allowed_requirements = opportunity_requirements.get(
                        item["opportunity_id"], set()
                    )
                    invalid_requirements = (
                        set(item["requirement_ids"]) - allowed_requirements
                    )
                    objective_allowed = {
                        requirement_id
                        for objective_id in item["objective_ids"]
                        for requirement_id in objective_requirements.get(
                            objective_id, set()
                        )
                    }
                    invalid_objective_requirements = (
                        set(item["requirement_ids"]) - objective_allowed
                    )
                    if invalid_requirements or invalid_objective_requirements:
                        issues.append(
                            GenerationIssue(
                                stage=stage.value,
                                code="practice_requirement_mapping",
                                message=(
                                    f"outside_opportunity={sorted(invalid_requirements)}, "
                                    "outside_objectives="
                                    f"{sorted(invalid_objective_requirements)}"
                                ),
                                location=f"practice[{index}].requirement_ids",
                            )
                        )
                    opportunity = opportunities.get(item["opportunity_id"])
                    if opportunity is not None:
                        expected_controls = set(opportunity["control_ids"])
                        actual_controls = set(item["control_ids"])
                        if actual_controls != expected_controls:
                            issues.append(
                                GenerationIssue(
                                    stage=stage.value,
                                    code="practice_control_mapping",
                                    message=(
                                        "missing="
                                        f"{sorted(expected_controls - actual_controls)}, "
                                        "unknown="
                                        f"{sorted(actual_controls - expected_controls)}"
                                    ),
                                    location=f"practice[{index}].control_ids",
                                )
                            )
                        if item["practice_type"] != opportunity["practice_type"]:
                            issues.append(
                                GenerationIssue(
                                    stage=stage.value,
                                    code="practice_type_mapping",
                                    message=(
                                        f"expected {opportunity['practice_type']!r}, "
                                        f"got {item['practice_type']!r}"
                                    ),
                                    location=f"practice[{index}].practice_type",
                                )
                            )
            actual_types = {
                item["practice_type"] for item in candidate["practice"]
            }
            issues.extend(
                _practice_type_diversity_issues(
                    stage.value, actual_types, "practice"
                )
            )
            activity_types = {
                item["activity_type"]
                for item in candidate["learning_sequence"]
            }
            missing_activities = {
                "prerequisite", "content", "practice", "review"
            } - activity_types
            if missing_activities:
                issues.append(
                    GenerationIssue(
                        stage=stage.value,
                        code="learning_flow_coverage",
                        message=(
                            "learning sequence lacks activity types: "
                            f"{sorted(missing_activities)}"
                        ),
                        location="learning_sequence",
                    )
                )
            issues.extend(_learner_internal_field_issues(candidate))
        elif stage is GenerationStage.AUDIT:
            blockers = _audit_blockers(candidate)
            expected_verdict = "fail" if blockers else "pass"
            if candidate["verdict"] != expected_verdict:
                issues.append(
                    GenerationIssue(
                        stage=stage.value,
                        code="audit_verdict_mismatch",
                        message=(
                            f"verdict must be {expected_verdict!r} for the "
                            "reported issue severities"
                        ),
                        location="verdict",
                    )
                )
        if stage is GenerationStage.CONTENT:
            for index, limitation in enumerate(candidate["limitations"]):
                if limitation["scope"] == "global":
                    issues.append(
                        GenerationIssue(
                            stage=stage.value,
                            code="downstream_global_limitation",
                            message=(
                                "only EvidencePlan may establish global "
                                "source limitations"
                            ),
                            location=f"limitations[{index}].scope",
                        )
                    )
        elif stage is GenerationStage.PRACTICE:
            assert plan is not None
            inherited_global_limitations = [
                limitation
                for limitation in plan["limitations"]
                if limitation["scope"] == "global"
            ]
            for index, limitation in enumerate(candidate["limitations"]):
                if (
                    limitation["scope"] == "global"
                    and limitation not in inherited_global_limitations
                ):
                    issues.append(
                        GenerationIssue(
                            stage=stage.value,
                            code="downstream_global_limitation",
                            message=(
                                "Practice may only copy global limitations "
                                "verbatim from EvidencePlan"
                            ),
                            location=f"limitations[{index}]",
                        )
                    )
        return tuple(issues)

    def _assemble(
        self,
        request: GenerationRequest,
        evidence: EvidenceBundle,
        plan: dict[str, Any],
        content: dict[str, Any],
        practice: dict[str, Any],
        *,
        audit_repairs_applied: bool = False,
    ) -> dict[str, Any]:
        model_limitations = [
            _learner_limitation_text(item["description"])
            for item in plan["limitations"]
            if item["scope"] == "global"
        ]
        limitations = _deduplicate(
            [
                *model_limitations,
                *_group_parse_warnings(evidence),
                "这是模型生成的初稿，尚待人工审核，不替代原始资料。",
            ]
        )
        limitations = limitations[:10]
        return {
            "studykit_version": "0.1",
            "status": "draft",
            "course_id": request.course_id,
            "course_version": request.course_version,
            "unit_id": request.unit_id,
            "title": _studykit_title(plan["title"]),
            "language": request.language,
            "estimated_study_time_minutes": sum(
                item["duration_minutes"] for item in practice["learning_sequence"]
            ),
            "estimated_study_time_status": "model_estimated",
            "scope": {
                "summary": plan["lecture_summary"],
                "included_sources": [dict(item) for item in request.included_sources],
                "excluded_sources": [
                    "unverified sources",
                    "video transcripts unless present in included_sources",
                    "homework and solutions",
                ],
                "citation_anchor_types": ["page"],
            },
            "learning_objectives": content["learning_objectives"],
            "prerequisites": content["prerequisites"],
            "prerequisite_check": content["prerequisite_check"],
            "outline": content["outline"],
            "core_concepts": content["core_concepts"],
            "glossary": content["glossary"],
            "common_misconceptions": content["common_misconceptions"],
            "learning_sequence": practice["learning_sequence"],
            "practice": practice["practice"],
            "practice_feedback_policy": _feedback_policy(),
            "citations": _assemble_citations(plan, evidence),
            "review": {
                "human_review_status": "pending",
                "human_reviewed_at": None,
                "generator_review_status": (
                    "audit_repairs_applied_unverified"
                    if audit_repairs_applied
                    else "validation_complete"
                ),
                "checks_remaining": [
                    "human content review",
                    "visual source review",
                    *(
                        ["post-repair semantic review"]
                        if audit_repairs_applied
                        else []
                    ),
                ],
            },
            "limitations": limitations,
        }

    def _validate_final(
        self, evidence: EvidenceBundle, candidate: dict[str, Any]
    ) -> tuple[GenerationIssue, ...]:
        schema = load_json(self._studykit_schema_path)
        issues = list(_schema_issues("assemble", schema, candidate))
        if issues:
            return tuple(issues)
        issues.extend(_runtime_contract_issues(candidate))
        issues.extend(_sequence_issues("assemble", candidate, "outline", "order"))
        issues.extend(
            _sequence_issues(
                "assemble", candidate, "learning_sequence", "step"
            )
        )
        issues.extend(_final_internal_field_issues(candidate))
        for collection, field in (
            ("learning_objectives", "id"),
            ("core_concepts", "id"),
            ("practice", "id"),
            ("citations", "citation_id"),
        ):
            issues.extend(
                _unique_field_issues("assemble", candidate, collection, field)
            )
        for issue in validate_citations(candidate, evidence.all_chunks):
            issues.append(
                GenerationIssue(
                    stage="assemble",
                    code=issue.reason,
                    message=f"{issue.source_id} page {issue.page}: {issue.reason}",
                    location=issue.location,
                )
            )
        try:
            render_studykit_markdown(candidate)
        except (KeyError, TypeError, ValueError) as exc:
            issues.append(
                GenerationIssue(
                    stage="assemble",
                    code="not_renderable",
                    message=f"learner Markdown rendering failed: {exc}",
                )
            )
        return tuple(issues)

    def _fingerprint(
        self,
        request: GenerationRequest,
        evidence: EvidenceBundle,
        manifest_hash: str | None,
    ) -> str:
        value = {
            "pipeline_version": PIPELINE_VERSION,
            "request": request.to_prompt_dict(),
            "chunks": list(evidence.all_chunks),
            "manifest_hash": manifest_hash,
            "prompt_versions": PROMPT_VERSIONS,
            "schema_hashes": self._schema_hashes(),
            "model": getattr(self._model, "model", type(self._model).__name__),
            "audit_model": getattr(
                self._audit_model, "model", type(self._audit_model).__name__
            ),
            "generation_options": {
                "stage_timeout_seconds": self._stage_timeout_seconds,
                "stage_max_tokens": self._stage_max_tokens,
                "max_repairs": self._max_repairs,
                "max_empty_content_retries": getattr(
                    self._model, "max_empty_content_retries", None
                ),
                "audit_max_empty_content_retries": getattr(
                    self._audit_model, "max_empty_content_retries", None
                ),
                "max_invalid_json_retries": getattr(
                    self._model, "max_invalid_json_retries", None
                ),
                "audit_max_invalid_json_retries": getattr(
                    self._audit_model, "max_invalid_json_retries", None
                ),
                "max_length_retries": getattr(
                    self._model, "max_length_retries", None
                ),
                "audit_max_length_retries": getattr(
                    self._audit_model, "max_length_retries", None
                ),
            },
        }
        return _hash_json(value)

    def _schema_hashes(self) -> dict[str, str]:
        paths = {
            **{stage.value: path for stage, path in self._stage_schema_paths.items()},
            "assemble": self._studykit_schema_path,
            "source_chunk": self._source_chunk_schema_path,
        }
        return {
            name: hashlib.sha256(path.read_bytes()).hexdigest()
            for name, path in paths.items()
        }

    def _new_run(
        self, fingerprint: str, manifest_hash: str | None
    ) -> dict[str, Any]:
        return {
            "run_version": RUN_VERSION,
            "pipeline_version": PIPELINE_VERSION,
            "input_fingerprint": fingerprint,
            "manifest_hash": manifest_hash,
            "prompt_versions": PROMPT_VERSIONS,
            "schema_hashes": self._schema_hashes(),
            "model": getattr(self._model, "model", type(self._model).__name__),
            "audit_model": getattr(
                self._audit_model, "model", type(self._audit_model).__name__
            ),
            "generation_options": {
                "stage_timeout_seconds": self._stage_timeout_seconds,
                "stage_max_tokens": self._stage_max_tokens,
                "max_repairs": self._max_repairs,
                "max_empty_content_retries": getattr(
                    self._model, "max_empty_content_retries", None
                ),
                "audit_max_empty_content_retries": getattr(
                    self._audit_model, "max_empty_content_retries", None
                ),
                "max_invalid_json_retries": getattr(
                    self._model, "max_invalid_json_retries", None
                ),
                "audit_max_invalid_json_retries": getattr(
                    self._audit_model, "max_invalid_json_retries", None
                ),
                "max_length_retries": getattr(
                    self._model, "max_length_retries", None
                ),
                "audit_max_length_retries": getattr(
                    self._audit_model, "max_length_retries", None
                ),
            },
            "stages": {
                stage.value: {"status": "pending"} for stage in ALL_STAGES
            },
        }

    def _load_recovery(
        self,
        output_dir: Path,
        fingerprint: str,
        *,
        requested_stage: GenerationStage | None,
        resume: bool,
        evidence: EvidenceBundle,
        request: GenerationRequest,
    ) -> tuple[dict[GenerationStage, dict[str, Any]], GenerationStage] | GenerationIssue:
        run = _read_json(output_dir / "run.json")
        if not isinstance(run, dict):
            return GenerationIssue(
                stage="recovery",
                code="run_not_found",
                message="run.json is required for resume/from-stage",
            )
        if run.get("run_version") != RUN_VERSION:
            return GenerationIssue(
                stage="recovery",
                code="run_version_mismatch",
                message="run.json version is incompatible; start a fresh run",
            )
        if run.get("input_fingerprint") != fingerprint:
            return GenerationIssue(
                stage="recovery",
                code="input_fingerprint_mismatch",
                message="inputs, schemas, prompts, or manifest changed; artifacts cannot be reused",
            )
        start = requested_stage
        if start is None and resume:
            start = GenerationStage.ASSEMBLE
            for stage in ALL_STAGES:
                entry = run.get("stages", {}).get(stage.value, {})
                if entry.get("status") != "succeeded":
                    start = stage
                    break
        assert start is not None
        reused: dict[GenerationStage, dict[str, Any]] = {}
        for stage in ALL_STAGES[: _stage_index(start)]:
            path = output_dir / STAGE_FILENAMES[stage]
            artifact = _read_json(path)
            if not isinstance(artifact, dict):
                return GenerationIssue(
                    stage="recovery",
                    code="missing_upstream_artifact",
                    message=f"{path.name} is required to start from {start.value}",
                )
            issues = (
                self._validate_final(evidence, artifact)
                if stage is GenerationStage.ASSEMBLE
                else self._validate_stage(
                    stage,
                    load_json(self._stage_schema_paths[stage]),
                    evidence,
                    artifact,
                    reused.get(GenerationStage.EVIDENCE),
                    request,
                    reused.get(GenerationStage.CONTENT),
                )
            )
            if issues:
                return GenerationIssue(
                    stage="recovery",
                    code="invalid_upstream_artifact",
                    message=f"{path.name} no longer passes validation: {issues[0].message}",
                )
            reused[stage] = artifact
        return reused, start

    def _record_success(
        self,
        output_dir: Path | None,
        run: dict[str, Any],
        stage: GenerationStage,
        artifact: dict[str, Any],
        model_infos: tuple[dict[str, Any], ...] | None,
        *,
        duration_seconds: float,
    ) -> None:
        if output_dir is None:
            return
        _write_json(output_dir / STAGE_FILENAMES[stage], artifact)
        entry: dict[str, Any] = {
            "status": "succeeded",
            "reused": False,
            "duration_seconds": duration_seconds,
        }
        if model_infos is not None:
            previous = run["stages"].get(stage.value, {})
            previous_calls = previous.get("model_calls", [])
            calls = [*previous_calls, *model_infos]
            entry["attempts"] = len(calls)
            entry["model_calls"] = calls
            entry["duration_seconds"] += previous.get("duration_seconds", 0.0)
        run["stages"][stage.value] = entry
        self._write_run(output_dir, run)

    def _record_failure(
        self,
        output_dir: Path | None,
        run: dict[str, Any],
        stage: GenerationStage,
        candidate: dict[str, Any] | None,
        issues: tuple[GenerationIssue, ...],
        model_infos: tuple[dict[str, Any], ...] = (),
        *,
        duration_seconds: float = 0.0,
        raw_candidate: str | None = None,
    ) -> None:
        if output_dir is None:
            return
        stem = STAGE_FILENAMES[stage].removesuffix(".json")
        if candidate is not None:
            _write_json(output_dir / f"{stem}.candidate.json", candidate)
        validation: dict[str, Any] = {
            "issues": [issue.to_dict() for issue in issues]
        }
        if raw_candidate:
            candidate_path = output_dir / f"{stem}.candidate.txt"
            candidate_path.write_text(raw_candidate, encoding="utf-8")
            validation["partial_candidate"] = {
                "file": candidate_path.name,
                "characters": len(raw_candidate),
            }
        _write_json(
            output_dir / f"{stem}.validation.json",
            validation,
        )
        run["stages"][stage.value] = {
            "status": "failed",
            "attempts": len(model_infos),
            "issues": [issue.to_dict() for issue in issues],
            "model_calls": list(model_infos),
            "duration_seconds": duration_seconds,
        }
        self._write_run(output_dir, run)

    @staticmethod
    def _record_audit_repair_failure(
        output_dir: Path,
        stage: GenerationStage,
        candidate: dict[str, Any] | None,
        issues: tuple[GenerationIssue, ...],
    ) -> None:
        stem = STAGE_FILENAMES[stage].removesuffix(".json")
        if candidate is not None:
            _write_json(
                output_dir / f"{stem}.audit-repair.candidate.json",
                candidate,
            )
        _write_json(
            output_dir / f"{stem}.audit-repair.validation.json",
            {"issues": [issue.to_dict() for issue in issues]},
        )

    def _record_audit_repair_success(
        self,
        output_dir: Path | None,
        run: dict[str, Any],
        stage: GenerationStage,
        artifact: dict[str, Any],
        model_infos: tuple[dict[str, Any], ...],
        *,
        duration_seconds: float,
    ) -> None:
        if output_dir is None:
            return
        _write_json(output_dir / STAGE_FILENAMES[stage], artifact)
        previous = run["stages"].get(stage.value, {})
        calls = [*previous.get("model_calls", []), *model_infos]
        run["stages"][stage.value] = {
            **previous,
            "status": "succeeded",
            "reused": False,
            "attempts": len(calls),
            "model_calls": calls,
            "duration_seconds": (
                previous.get("duration_seconds", 0.0) + duration_seconds
            ),
            "audit_repair": {
                "applied": True,
                "semantic_reaudit_performed": False,
            },
        }
        self._write_run(output_dir, run)

    @staticmethod
    def _record_audit_resolution(
        output_dir: Path | None,
        audit_output: dict[str, Any],
        repaired_stages: list[GenerationStage],
        deterministically_resolved: list[dict[str, Any]],
    ) -> None:
        if output_dir is None:
            return
        blockers = _audit_blockers(audit_output)
        _write_json(
            output_dir / "04-quality-audit.resolution.json",
            {
                "resolution_version": 1,
                "audit_verdict": audit_output["verdict"],
                "outcome": (
                    "repairs_applied_unverified"
                    if repaired_stages
                    else "audit_findings_deterministically_resolved"
                ),
                "semantic_reaudit_performed": False,
                "audit_issue_ids": [item["id"] for item in blockers],
                "repaired_stages": [stage.value for stage in repaired_stages],
                "deterministically_resolved_issue_ids": [
                    item["id"] for item in deterministically_resolved
                ],
                "deterministic_validation": {
                    stage.value: "passed" for stage in repaired_stages
                },
            },
        )

    @staticmethod
    def _write_run(output_dir: Path, run: dict[str, Any]) -> None:
        _write_json(output_dir / "run.json", run)

    @staticmethod
    def _result(
        status: GenerationStatus,
        request: GenerationRequest,
        used_chunk_ids: tuple[str, ...],
        issues: tuple[GenerationIssue, ...],
        stages: tuple[StageResult, ...],
        *,
        failed_stage: GenerationStage | None,
    ) -> GenerationResult:
        del request
        infos = [info for stage in stages for info in stage.model_info]
        return GenerationResult(
            status=status,
            studykit=None,
            issues=issues,
            used_chunk_ids=used_chunk_ids,
            attempts=sum(stage.attempts for stage in stages),
            prompt_version=PROMPT_VERSION,
            model_info={"calls": infos, "usage": _sum_usage(infos)} if infos else {},
            stages=stages,
            failed_stage=failed_stage,
        )


def _schema_issues(
    stage: str, schema: dict[str, Any], candidate: dict[str, Any]
) -> tuple[GenerationIssue, ...]:
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)
    validator = validator_cls(schema)
    result = []
    for error in sorted(
        validator.iter_errors(candidate), key=lambda item: list(item.absolute_path)
    ):
        location = ".".join(str(item) for item in error.absolute_path) or "$"
        result.append(
            GenerationIssue(
                stage=stage,
                code="schema_validation",
                message=error.message,
                location=location,
            )
        )
    return tuple(result)


def _iter_plan_chunk_ids(plan: dict[str, Any]) -> Iterable[tuple[str, str]]:
    for field in ("content_chunk_ids", "practice_chunk_ids"):
        for index, chunk_id in enumerate(plan[field]):
            yield f"{field}[{index}]", chunk_id
    for field in (
        "page_segments",
        "core_concept_candidates",
        "evidence_controls",
        "assessment_requirements",
        "practice_opportunities",
    ):
        for index, item in enumerate(plan[field]):
            for chunk_index, chunk_id in enumerate(item["chunk_ids"]):
                yield f"{field}[{index}].chunk_ids[{chunk_index}]", chunk_id
    for index, item in enumerate(plan["limitations"]):
        for chunk_index, chunk_id in enumerate(item["chunk_ids"]):
            yield f"limitations[{index}].chunk_ids[{chunk_index}]", chunk_id


def _content_reference_issues(
    content: dict[str, Any],
    allowed_pages: set[tuple[str, int]],
    *,
    outline_pages: set[int] | None = None,
) -> list[GenerationIssue]:
    issues: list[GenerationIssue] = []
    for index, concept in enumerate(content["core_concepts"]):
        for citation_index, citation in enumerate(concept["citations"]):
            key = (citation["source_id"], citation["page"])
            if key not in allowed_pages:
                issues.append(
                    GenerationIssue(
                        stage="content",
                        code="page_not_selected",
                        message=f"citation {key!r} is outside content chunks",
                        location=(
                            f"core_concepts[{index}].citations[{citation_index}]"
                        ),
                    )
                )
    valid_page_numbers = {page for _, page in allowed_pages}
    for index, misconception in enumerate(content["common_misconceptions"]):
        for support_index, support in enumerate(misconception.get("support", [])):
            if support["page"] not in valid_page_numbers:
                issues.append(
                    GenerationIssue(
                        stage="content",
                        code="page_not_selected",
                        message=(
                            f"misconception support page {support['page']} is "
                            "outside content chunks"
                        ),
                        location=(
                            f"common_misconceptions[{index}]."
                            f"support[{support_index}].page"
                        ),
                    )
                )
    valid_outline_pages = (
        valid_page_numbers if outline_pages is None else outline_pages
    )
    for index, item in enumerate(content["outline"]):
        try:
            pages = _expand_pages(item["pages"])
        except ValueError:
            continue
        for page in pages:
            if page not in valid_outline_pages:
                issues.append(
                    GenerationIssue(
                        stage="content",
                        code="page_not_selected",
                        message=(
                            f"outline page {page} is outside input SourceChunks"
                        ),
                        location=f"outline[{index}].pages",
                    )
                )
    return issues


def _sequence_issues(
    stage: str, candidate: dict[str, Any], collection: str, field: str
) -> list[GenerationIssue]:
    values = [item.get(field) for item in candidate.get(collection, [])]
    if values == list(range(1, len(values) + 1)):
        return []
    return [
        GenerationIssue(
            stage=stage,
            code="non_contiguous_sequence",
            message=f"{collection}.{field} must be contiguous starting at 1",
            location=collection,
        )
    ]


def _unique_field_issues(
    stage: str, candidate: dict[str, Any], collection: str, field: str
) -> list[GenerationIssue]:
    values = [
        item.get(field)
        for item in candidate.get(collection, [])
        if isinstance(item, dict)
    ]
    if len(values) == len(set(values)):
        return []
    return [
        GenerationIssue(
            stage=stage,
            code="duplicate_id",
            message=f"{collection} contains duplicate {field} values",
            location=collection,
        )
    ]


def _runtime_contract_issues(candidate: dict[str, Any]) -> list[GenerationIssue]:
    issues: list[GenerationIssue] = []
    if not candidate.get("prerequisites", {}).get("items"):
        issues.append(
            GenerationIssue(
                stage="assemble",
                code="missing_prerequisites",
                message="prerequisites.items must be non-empty",
                location="prerequisites.items",
            )
        )
    return issues


def _learner_internal_field_issues(
    practice: dict[str, Any],
) -> list[GenerationIssue]:
    """Reject references to fields that are intentionally hidden from learners."""

    internal_names = (
        "expected_evidence",
        "evaluation",
        "rubric",
        "control_ids",
        "requirement_ids",
    )
    issues: list[GenerationIssue] = []
    for index, item in enumerate(practice.get("learning_sequence", [])):
        for field in ("activity", "concept_explanation"):
            value = item.get(field)
            if not isinstance(value, str):
                continue
            matched = next(
                (name for name in internal_names if name in value.lower()),
                None,
            )
            if matched is not None:
                issues.append(
                    GenerationIssue(
                        stage="practice",
                        code="internal_field_leak",
                        message=(
                            f"learner-facing text references internal field "
                            f"{matched!r}"
                        ),
                        location=f"learning_sequence[{index}].{field}",
                    )
                )
    return issues


def _practice_type_diversity_issues(
    stage: str, actual: set[str], location: str
) -> list[GenerationIssue]:
    if len(actual) >= 2:
        return []
    return [
        GenerationIssue(
            stage=stage,
            code="practice_type_coverage",
            message=(
                "at least two evidence-supported practice types are required; "
                f"got {sorted(actual)}"
            ),
            location=location,
        )
    ]


def _terminology_issues(content: dict[str, Any]) -> list[GenerationIssue]:
    seen: dict[str, str] = {}
    issues: list[GenerationIssue] = []
    terms = [
        *content.get("core_concepts", []),
        *content.get("glossary", []),
    ]
    for index, item in enumerate(terms):
        english = item.get("term_en", "").strip().lower()
        chinese = item.get("term_zh", "").strip()
        previous = seen.get(english)
        if previous is not None and previous != chinese:
            issues.append(
                GenerationIssue(
                    stage="content",
                    code="terminology_conflict",
                    message=(
                        f"{english!r} maps to both {previous!r} and {chinese!r}"
                    ),
                    location=f"terms[{index}].term_zh",
                )
            )
        elif english:
            seen[english] = chinese
    return issues


def _audit_blockers(audit: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for item in audit.get("issues", [])
        if item.get("severity") == "blocker"
    ]


def _audit_projection(candidate: dict[str, Any]) -> dict[str, Any]:
    """Expose only model-authored learner content to the semantic audit."""

    learner_fields = (
        "title",
        "estimated_study_time_minutes",
        "estimated_study_time_status",
        "learning_objectives",
        "prerequisites",
        "prerequisite_check",
        "outline",
        "core_concepts",
        "glossary",
        "common_misconceptions",
        "learning_sequence",
        "practice",
        "limitations",
    )
    projection = {
        field: candidate[field]
        for field in learner_fields
        if field in candidate
    }
    scope = candidate.get("scope")
    if isinstance(scope, dict) and "summary" in scope:
        projection["scope"] = {"summary": scope["summary"]}
    return projection


def _promote_audit_boundary_blockers(
    blockers: list[dict[str, Any]], plan: dict[str, Any]
) -> list[dict[str, Any]]:
    """Turn an out-of-boundary downstream fix into an Evidence repair first.

    The original downstream blocker remains actionable.  Adding a synthetic
    Evidence blocker lets the existing dependency-ordered repair loop update
    the plan before repairing Content or Practice, without a second Audit.
    """

    allowed = {
        "content": set(plan["content_chunk_ids"]),
        "practice": set(plan["practice_chunk_ids"]),
    }
    promoted: list[dict[str, Any]] = []
    for item in blockers:
        target = item["target_stage"]
        if target not in allowed:
            continue
        outside = sorted(
            set(item["evidence_chunk_ids"]) - allowed[target]
        )
        if outside:
            selection_field = f"{target}_chunk_ids"
            promoted.append(
                {
                    "id": f"{item['id']}-evidence-boundary",
                    "severity": "blocker",
                    "category": "source_control_violation",
                    "target_stage": "evidence",
                    "location": selection_field,
                    "description": (
                        f"The audited {target} repair requires SourceChunks "
                        f"that its EvidencePlan boundary does not select: "
                        f"{outside}."
                    ),
                    "evidence_chunk_ids": outside,
                    "observed": (
                        f"{selection_field} excludes {outside}, so the "
                        f"downstream repair cannot cite them."
                    ),
                    "expected": (
                        f"Existing EvidencePlan objects relevant to audit "
                        f"issue {item['id']!r} select these chunks and the "
                        f"deterministic {selection_field} union includes them."
                    ),
                    "repair_instruction": (
                        "Without inventing new concept, requirement, control, "
                        "or opportunity IDs, attach the listed SourceChunks to "
                        "the existing planning object(s) that support the "
                        f"audited {target} correction; then recompute "
                        f"{selection_field} as the required deterministic "
                        "union. Preserve unrelated planning content."
                    ),
                }
            )
    return promoted


def _audit_generation_issues(
    blockers: list[dict[str, Any]],
) -> tuple[GenerationIssue, ...]:
    return tuple(
        GenerationIssue(
            stage="audit",
            code=item["category"],
            message=item["description"],
            location=item["location"],
        )
        for item in blockers
    )


def _assembly_blocker_is_resolved(
    item: dict[str, Any],
    assembly_validation_issues: tuple[GenerationIssue, ...],
) -> bool:
    """Accept only assembly findings covered by deterministic validation."""

    if item["target_stage"] != "assembly" or assembly_validation_issues:
        return False
    if item["category"] == "formatting":
        return True
    if item["category"] != "internal_field_leak":
        return False
    location = item["location"].lower()
    return "title" in location or "limitations" in location


def _normalize_stage_candidate(
    stage: GenerationStage,
    candidate: dict[str, Any],
    plan: dict[str, Any] | None,
) -> dict[str, Any]:
    """Normalize fields that are deterministic copies of upstream artifacts."""

    if stage is not GenerationStage.PRACTICE or plan is None:
        return candidate
    limitations = candidate.get("limitations")
    if not isinstance(limitations, list) or not all(
        isinstance(item, dict) for item in limitations
    ):
        return candidate
    local = [
        item for item in limitations if item.get("scope") != "global"
    ]
    inherited = [
        dict(item)
        for item in plan.get("limitations", [])
        if item.get("scope") == "global"
    ]
    return {**candidate, "limitations": [*inherited, *local]}


def _group_parse_warnings(evidence: EvidenceBundle) -> list[str]:
    grouped: dict[str, list[int]] = {}
    for warning in evidence.parse_warnings:
        chunk_id, _, detail = warning.partition(":")
        kind = detail.split(":", 1)[0] or "unknown"
        match = re.search(r"-p(\d+)$", chunk_id)
        if match is not None:
            grouped.setdefault(kind, []).append(int(match.group(1)))
    labels = {
        "low_extracted_text": "文本提取量较低",
        "removed_hidden_formula_noise_lines": "移除了隐藏公式噪声行",
        "removed_duplicate_lines": "移除了重复文本行",
        "replaced_invalid_unicode_surrogates": "修复了无效 Unicode 字符",
    }
    if not grouped:
        return []
    warning_labels = "、".join(
        labels.get(kind, kind) for kind in sorted(grouped)
    )
    return [
        "部分页面存在文本提取质量风险"
        f"（{warning_labels}）；依赖公式、图形或版式的内容应回看原始资料。"
    ]


def _assemble_citations(
    plan: dict[str, Any], evidence: EvidenceBundle
) -> list[dict[str, Any]]:
    index = {chunk["chunk_id"]: chunk for chunk in evidence.usable_chunks}
    citations: list[dict[str, Any]] = []
    for segment_index, segment in enumerate(plan["page_segments"], start=1):
        by_source: dict[str, list[int]] = {}
        for chunk_id in segment["chunk_ids"]:
            chunk = index[chunk_id]
            by_source.setdefault(chunk["source_id"], []).append(
                chunk["anchor"]["value"]
            )
        for source_index, (source_id, pages) in enumerate(
            sorted(by_source.items()), start=1
        ):
            for range_index, page_range in enumerate(
                _compress_pages(pages), start=1
            ):
                citations.append(
                    {
                        "citation_id": (
                            f"cite-segment-{segment_index:02d}-"
                            f"{source_index:02d}-{range_index:02d}"
                        ),
                        "source_id": source_id,
                        "pages": page_range,
                        "supports": segment["topic"],
                    }
                )
    return citations


def _compress_pages(pages: Iterable[int]) -> list[str]:
    ordered = sorted(set(pages))
    result: list[str] = []
    if not ordered:
        return result
    start = previous = ordered[0]
    for page in ordered[1:]:
        if page == previous + 1:
            previous = page
            continue
        result.append(str(start) if start == previous else f"{start}–{previous}")
        start = previous = page
    result.append(str(start) if start == previous else f"{start}–{previous}")
    return result


def _feedback_policy() -> dict[str, Any]:
    return {
        "scope": "current_answer_only",
        "persistence": "none",
        "aggregate_accuracy": "disabled",
        "aggregate_mastery": "disabled",
        "feedback_should": [
            "指出本次回答中正确的知识点。",
            "指出最重要的错误或遗漏并给出修正提示。",
            "引用与本题相关的来源页码。",
        ],
        "feedback_should_not": [
            "保存或展示累计答题记录。",
            "统计总正确率或推断整体掌握度。",
        ],
    }


def _studykit_title(plan_title: str) -> str:
    """Remove stage-specific labeling from the learner-facing title."""

    title = re.sub(
        r"(?i)(?:\s*[—–-]\s*|\s+)evidence\s*plan\s*$",
        "",
        plan_title.strip(),
    ).strip()
    if re.match(r"(?i)^evidence\s*plan\s*:", title):
        return re.sub(
            r"(?i)^evidence\s*plan\s*:",
            "StudyKit:",
            title,
            count=1,
        )
    if re.match(r"(?i)^studykit\s*:", title):
        return title
    return f"StudyKit: {title}"


_INTERNAL_DIAGNOSTIC_REPLACEMENTS = {
    "parse warnings": "解析质量提示",
    "low_extracted_text": "文本提取量较低",
    "low extracted text": "文本提取量较低",
    "removed_duplicate_lines": "已移除重复文本",
    "removed duplicate lines": "已移除重复文本",
    "removed_hidden_formula_noise_lines": "已移除隐藏公式噪声",
    "removed hidden formula noise": "已移除隐藏公式噪声",
    "replaced_invalid_unicode_surrogates": "已修复无效 Unicode 字符",
    "replaced invalid unicode surrogates": "已修复无效 Unicode 字符",
}


def _learner_limitation_text(value: str) -> str:
    result = value
    for internal, learner_facing in _INTERNAL_DIAGNOSTIC_REPLACEMENTS.items():
        result = re.sub(
            re.escape(internal),
            learner_facing,
            result,
            flags=re.IGNORECASE,
        )
    return result


def _final_internal_field_issues(
    candidate: dict[str, Any],
) -> list[GenerationIssue]:
    issues: list[GenerationIssue] = []
    title = candidate.get("title", "")
    if isinstance(title, str) and re.search(
        r"(?i)\bevidence\s*plan\b", title
    ):
        issues.append(
            GenerationIssue(
                stage="assemble",
                code="internal_field_leak",
                message="learner-facing title contains EvidencePlan",
                location="title",
            )
        )
    for index, limitation in enumerate(candidate.get("limitations", [])):
        if not isinstance(limitation, str):
            continue
        leaked = [
            token
            for token in _INTERNAL_DIAGNOSTIC_REPLACEMENTS
            if re.search(re.escape(token), limitation, flags=re.IGNORECASE)
        ]
        if leaked:
            issues.append(
                GenerationIssue(
                    stage="assemble",
                    code="internal_field_leak",
                    message=(
                        "learner-facing limitation contains internal "
                        f"diagnostic names: {sorted(leaked)}"
                    ),
                    location=f"limitations[{index}]",
                )
            )
    return issues


def _needs_semantic_repair(issues: tuple[GenerationIssue, ...]) -> bool:
    return any(issue.code != "schema_validation" for issue in issues)


def _model_info(response: ModelResponse) -> dict[str, Any]:
    usage = dict(response.usage)
    for diagnostic in response.retry_diagnostics:
        for key, value in diagnostic.get("usage", {}).items():
            if isinstance(value, int) and not isinstance(value, bool):
                usage[key] = usage.get(key, 0) + value
    result = {
        "model": response.model,
        "finish_reason": response.finish_reason,
        "usage": usage,
        "request_id": response.request_id,
    }
    if response.transport_attempts > 1:
        result["transport_attempts"] = response.transport_attempts
        result["final_response_usage"] = response.usage
    if response.retry_diagnostics:
        result["retry_diagnostics"] = list(response.retry_diagnostics)
    return result


def _model_error_response(error: ModelError) -> ModelResponse | None:
    if not isinstance(error, ModelResponseError) or error.model is None:
        return None
    return ModelResponse(
        output={},
        raw_content=error.partial_content or "",
        model=error.model,
        finish_reason=error.finish_reason or "error",
        usage=error.usage,
        request_id=error.request_id,
        transport_attempts=error.transport_attempts,
        retry_diagnostics=error.retry_diagnostics,
    )


def _sum_usage(infos: Iterable[dict[str, Any]]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for info in infos:
        for key, value in info.get("usage", {}).items():
            if isinstance(value, int) and not isinstance(value, bool):
                totals[key] = totals.get(key, 0) + value
    return totals


def _deduplicate(items: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def _coerce_stage(value: GenerationStage | str | None) -> GenerationStage | None:
    if value is None or isinstance(value, GenerationStage):
        return value
    try:
        return GenerationStage(value)
    except ValueError as exc:
        raise ValueError(
            "from_stage must be evidence, content, practice, audit, or assemble"
        ) from exc


def _stage_index(stage: GenerationStage) -> int:
    return ALL_STAGES.index(stage)


def _hash_json(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
