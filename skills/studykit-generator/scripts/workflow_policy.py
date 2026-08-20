#!/usr/bin/env python3
"""Deterministic quality-mode, review-page, fingerprint, and batch helpers."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable


QUALITY_MODES = ("fast", "standard", "strict")
DELIVERY_POLICIES = ("draft", "publish")
PAGE_SELECTOR_VERSION = "review-pages-v1"
PIPELINE_VERSION = "0.2.1"
MAX_UNIT_WORKERS_PER_COORDINATOR = 4
BUILTIN_DECISION = Path(__file__).resolve().parents[1] / "references/default-mode-decision.json"
STAGE_ORDER = (
    "01-evidence-plan",
    "02-learning-content",
    "03-practice-flow",
    "04-quality-audit",
    "05-studykit",
)


def resolve_options(
    quality_mode: str | None = None,
    delivery_policy: str | None = None,
    generation_policy: str | None = None,
    decision_file: Path | None = None,
) -> dict[str, Any]:
    """Resolve v0.2 inputs while preserving the old delivery-policy alias."""
    warnings: list[str] = []
    if generation_policy is not None:
        if delivery_policy is not None:
            raise ValueError("generation_policy and delivery_policy are mutually exclusive")
        if generation_policy not in {"draft", "strict", "publish"}:
            raise ValueError("generation_policy must be draft or strict")
        delivery_policy = "draft" if generation_policy == "draft" else "publish"
        warnings.append("generation_policy is deprecated; use delivery_policy")
    delivery_policy = delivery_policy or "draft"
    if delivery_policy not in DELIVERY_POLICIES:
        raise ValueError(f"delivery_policy must be one of {DELIVERY_POLICIES}")
    source = "explicit"
    if quality_mode is None:
        decision_file = decision_file or BUILTIN_DECISION
        if not decision_file.is_file():
            raise ValueError("quality_mode is required until an offline default-mode decision exists")
        decision = json.loads(decision_file.read_text(encoding="utf-8"))
        quality_mode = decision.get("default_quality_mode")
        source = "offline-noninferiority-decision"
    if quality_mode not in QUALITY_MODES:
        raise ValueError(f"quality_mode must be one of {QUALITY_MODES}")
    return {
        "quality_mode": quality_mode,
        "quality_mode_source": source,
        "delivery_policy": delivery_policy,
        "warnings": warnings,
    }


def _page(item: dict[str, Any]) -> int | None:
    value = item.get("page")
    if value is None and isinstance(item.get("anchor"), dict):
        if item["anchor"].get("type") == "page":
            value = item["anchor"].get("value")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _has_risk(item: dict[str, Any]) -> bool:
    warning_values: list[Any] = []
    for key in ("parse_warnings", "warnings", "risk", "status", "formula"):
        value = item.get(key)
        if value:
            warning_values.append(value)
    text = json.dumps(warning_values, ensure_ascii=False).lower()
    return any(token in text for token in (
        "hidden_text", "hidden text", "garbled", "replacement", "replaced_invalid_unicode", "�",
        # The production PDF parser emits ``low_extracted_text``.  Keep the
        # older ``low_extraction`` spelling for compatibility with hand-built
        # candidates and older ingestion reports.
        "low_extracted_text", "low extracted text",
        "low_extraction", "low extraction", "formula_unresolved",
        "empty_or_unstructured_text", "empty_page",
    )) or bool(item.get("risk"))


def _deterministic_sample(pages: Iterable[int], source_hash: str) -> list[int]:
    pages = sorted(set(pages))
    if not pages:
        return []
    count = min(10, max(3, math.ceil(len(pages) * 0.2)))
    count = min(count, len(pages))
    ranked = sorted(
        pages,
        key=lambda page: hashlib.sha256(f"{source_hash}:{page}".encode()).hexdigest(),
    )
    return sorted(ranked[:count])


def select_review_pages(
    mode: str,
    candidates: list[dict[str, Any]],
    *,
    source_hash: str,
    evidence_pages: Iterable[int] = (),
    final_formula_pages: Iterable[int] = (),
    identity_pages: Iterable[int] = (),
    theorem_pages: Iterable[int] = (),
) -> dict[str, Any]:
    """Return the deterministic visual-review plan for one unit."""
    if mode not in QUALITY_MODES:
        raise ValueError(f"unknown quality mode: {mode}")
    candidate_pages = {_page(item) for item in candidates}
    candidate_pages.discard(None)
    needs_vision = {_page(item) for item in candidates if item.get("needs_host_vision") or item.get("status") == "needs_host_vision"}
    needs_vision.discard(None)
    risky = {_page(item) for item in candidates if _has_risk(item)}
    risky.discard(None)
    finals = set(map(int, final_formula_pages))
    base = set(map(int, identity_pages)) | set(map(int, theorem_pages)) | risky | finals
    reasons: dict[int, set[str]] = {}
    for label, pages in (
        ("identity", identity_pages), ("theorem_or_strong_claim", theorem_pages),
        ("risk", risky), ("final_formula", finals),
    ):
        for page in pages:
            reasons.setdefault(int(page), set()).add(label)
    sampled: list[int] = []
    if mode == "standard":
        for page in evidence_pages:
            base.add(int(page)); reasons.setdefault(int(page), set()).add("evidence_plan")
        remaining = candidate_pages - base
        sampled = _deterministic_sample(remaining, source_hash)
        for page in sampled:
            base.add(page); reasons.setdefault(page, set()).add("deterministic_20_percent_sample")
    elif mode == "strict":
        for page in needs_vision | finals:
            base.add(page); reasons.setdefault(page, set()).add("all_needs_host_vision")
    return {
        "quality_mode": mode,
        "page_selector_version": PAGE_SELECTOR_VERSION,
        "source_hash": source_hash,
        "selected_pages": sorted(base),
        "selection_reasons": {str(p): sorted(reasons[p]) for p in sorted(reasons)},
        "sampled_pages": sampled,
        "required_final_formula_pages": sorted(finals),
        "actual_reviewed_pages": [],
    }


def build_fingerprint(inventory: Any, quality_mode: str, **versions: str) -> str:
    """Concurrency is intentionally absent: it must not invalidate checkpoints."""
    payload = {
        "inventory": inventory,
        "quality_mode": quality_mode,
        "page_selector_version": PAGE_SELECTOR_VERSION,
        "pipeline_version": PIPELINE_VERSION,
        "versions": versions,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def validate_stage_checkpoints(stage_dir: Path, quality_mode: str) -> list[dict[str, str]]:
    """Check the offline, ordered stage handoff without reading registry state.

    A checkpoint is deliberately just an existing JSON artifact. Content
    validation belongs to the artifact validator; this function prevents a
    standard run from silently skipping or reordering 01..05.
    """
    if quality_mode not in QUALITY_MODES:
        raise ValueError(f"unknown quality mode: {quality_mode}")
    issues: list[dict[str, str]] = []
    seen_missing = False
    for stage in STAGE_ORDER:
        path = stage_dir / f"{stage}.json"
        if not path.is_file():
            seen_missing = True
            issues.append({"code": "checkpoint_missing", "stage": stage, "location": str(path)})
        elif seen_missing:
            issues.append({"code": "checkpoint_order_violation", "stage": stage, "location": str(path)})
        else:
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                issues.append({"code": "checkpoint_invalid_json", "stage": stage, "location": str(path), "message": str(exc)})
                continue
            if not isinstance(value, dict):
                issues.append({"code": "checkpoint_not_object", "stage": stage, "location": str(path)})
    return issues


def coordinator_slot_budget(session_slots: int, coordinator_count: int, global_coordinator_reserve: int = 1) -> int:
    """Return an equal slot budget for each isolated build coordinator.

    ``session_slots`` is the whole-session limit.  One global coordinator slot
    is reserved by default; each build coordinator's own slot is included in
    its budget, so ``worker_count`` subtracts one again when choosing unit
    workers.  The function does not raise the per-coordinator four-worker
    safety ceiling.
    """

    if session_slots < 1:
        raise ValueError("session_slots must be positive")
    if coordinator_count < 1:
        raise ValueError("coordinator_count must be positive")
    if global_coordinator_reserve < 0:
        raise ValueError("global_coordinator_reserve cannot be negative")
    usable = session_slots - global_coordinator_reserve
    if usable < coordinator_count:
        raise ValueError("session_slots cannot reserve one slot for every build coordinator")
    return usable // coordinator_count


def worker_count(unit_count: int, parallel_units: str | int, available_slots: int | None = None, supports_subtasks: bool = True) -> int:
    if unit_count < 0:
        raise ValueError("unit_count cannot be negative")
    if unit_count == 0:
        return 0
    if not supports_subtasks or parallel_units in {"off", 1, "1"}:
        return 1
    if parallel_units == "auto":
        capacity = 2 if available_slots is None else max(1, available_slots - 1)
        return min(unit_count, capacity, MAX_UNIT_WORKERS_PER_COORDINATOR)
    try:
        requested = int(parallel_units)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"parallel_units must be auto, off, or 1..{MAX_UNIT_WORKERS_PER_COORDINATOR} per coordinator") from exc
    if not 1 <= requested <= MAX_UNIT_WORKERS_PER_COORDINATOR:
        raise ValueError(f"parallel_units must be auto, off, or 1..{MAX_UNIT_WORKERS_PER_COORDINATOR} per coordinator")
    capacity = requested if available_slots is None else max(1, available_slots - 1)
    return min(unit_count, requested, capacity, MAX_UNIT_WORKERS_PER_COORDINATOR)


def summarize_batch(units: list[dict[str, Any]], parallel_units: str | int, workers: int) -> dict[str, Any]:
    succeeded = [u for u in units if u.get("status") == "succeeded"]
    status = "succeeded" if len(succeeded) == len(units) else ("partial" if succeeded else "failed")
    return {
        "status": status,
        "parallel_units": parallel_units,
        "worker_count": workers,
        "units": units,
        "succeeded_units": [u["unit_id"] for u in succeeded],
        "failed_units": [
            {"unit_id": u["unit_id"], "failed_stage": u.get("failed_stage"), "recovery_action": u.get("recovery_action")}
            for u in units if u.get("status") != "succeeded"
        ],
    }
