from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys


SKILL = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("workflow_policy", SKILL / "scripts/workflow_policy.py")
assert spec and spec.loader
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


def test_mode_parsing_and_legacy_alias(tmp_path: Path) -> None:
    options = policy.resolve_options("fast", generation_policy="strict")
    assert options["delivery_policy"] == "publish"
    assert options["warnings"]
    decision = tmp_path / "decision.json"
    decision.write_text(json.dumps({"default_quality_mode": "standard"}))
    assert policy.resolve_options(decision_file=decision)["quality_mode"] == "standard"


def test_builtin_offline_decision_selects_standard() -> None:
    options = policy.resolve_options()
    assert options["quality_mode"] == "standard"
    assert options["quality_mode_source"] == "offline-noninferiority-decision"


def test_review_page_sets_and_deterministic_sampling() -> None:
    candidates = [{"page": page, "needs_host_vision": True} for page in range(1, 31)]
    candidates[10]["warnings"] = ["hidden_text"]
    fast = policy.select_review_pages("fast", candidates, source_hash="a" * 64, identity_pages=[1], theorem_pages=[2], final_formula_pages=[3])
    assert fast["selected_pages"] == [1, 2, 3, 11]
    standard_a = policy.select_review_pages("standard", candidates, source_hash="a" * 64, evidence_pages=[4], identity_pages=[1], final_formula_pages=[3])
    standard_b = policy.select_review_pages("standard", candidates, source_hash="a" * 64, evidence_pages=[4], identity_pages=[1], final_formula_pages=[3])
    assert standard_a == standard_b
    assert 3 <= len(standard_a["sampled_pages"]) <= 10
    strict = policy.select_review_pages("strict", candidates, source_hash="a" * 64, final_formula_pages=[40])
    assert strict["selected_pages"] == list(range(1, 31)) + [40]


def test_fingerprint_includes_mode_not_concurrency() -> None:
    fast = policy.build_fingerprint(["x"], "fast", schema="1")
    strict = policy.build_fingerprint(["x"], "strict", schema="1")
    assert fast != strict
    assert "parallel" not in policy.build_fingerprint.__code__.co_varnames


def test_worker_capacity_and_batch_failure_isolation() -> None:
    assert policy.worker_count(8, "auto", available_slots=4) == 3
    assert policy.worker_count(8, "auto") == 2
    assert policy.worker_count(8, 4, available_slots=20) == 4
    assert policy.worker_count(2, "auto", supports_subtasks=False) == 1
    summary = policy.summarize_batch([
        {"unit_id": "u1", "status": "succeeded"},
        {"unit_id": "u2", "status": "failed", "failed_stage": "03", "recovery_action": "resume 03"},
    ], "auto", 2)
    assert summary["status"] == "partial"
    assert summary["succeeded_units"] == ["u1"]


def test_execution_plan_rejects_duplicate_units(tmp_path: Path) -> None:
    result = subprocess.run([
        sys.executable, str(SKILL / "scripts/plan_execution.py"),
        "--unit", "u1", "--unit", "u1", "--output-dir", str(tmp_path), "--quality-mode", "fast",
    ], text=True, capture_output=True, check=False)
    assert result.returncode == 2
    assert "duplicate" in result.stderr


def test_review_hard_gates() -> None:
    review_spec = importlib.util.spec_from_file_location("validate_review", SKILL / "scripts/validate_review.py")
    assert review_spec and review_spec.loader
    module = importlib.util.module_from_spec(review_spec)
    review_spec.loader.exec_module(module)
    kit = {"core_concepts": [{"formula": {"status": "formula_unresolved", "image": "p.png"}}]}
    review = {"quality_mode": "strict", "selected_pages": [2], "actual_reviewed_pages": [], "required_final_formula_pages": [2], "independent_audit": False}
    codes = {issue["code"] for issue in module.validate(kit, review, "publish")}
    assert {"review_pages_missing", "final_formula_not_visually_verified", "unresolved_formula_blocker", "independent_audit_missing"} <= codes
