from __future__ import annotations

import json
from copy import deepcopy

from scripts.evaluate_studykit_quality import evaluate_quality
from tests.generation.helpers import ROOT, draft_candidate, practice_flow


def _profile() -> dict:
    path = (
        ROOT
        / "data/golden/mit-6.7960-fall-2024-lecture-02-quality.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def _candidate() -> dict:
    candidate = draft_candidate()
    flow = practice_flow()
    candidate["practice"] = flow["practice"]
    candidate["learning_sequence"] = flow["learning_sequence"]
    return candidate


def test_golden_derived_profile_accepts_covered_candidate() -> None:
    assert evaluate_quality(_candidate(), _profile()) == []


def test_profile_rejects_complex_numeric_regression_and_missing_practice() -> None:
    candidate = deepcopy(_candidate())
    candidate["practice"] = candidate["practice"][:1]
    candidate["core_concepts"][0]["explanation"] = (
        "错误地写成 x_in^T g_out，并要求完整数值反向传播。"
    )

    failures = evaluate_quality(candidate, _profile())

    assert "too few practices: 1" in failures
    assert "forbidden text pattern: x_in^T g_out" in failures
    assert "forbidden text pattern: 完整数值反向传播" in failures


def test_profile_does_not_limit_number_of_simple_practices_by_default() -> None:
    candidate = deepcopy(_candidate())
    for practice in candidate["practice"]:
        practice["numeric_complexity"] = "simple"
    profile = _profile()
    profile.pop("maximum_simple_numeric_practices", None)

    failures = evaluate_quality(candidate, profile)

    assert not any(
        failure.startswith("too many simple numeric practices")
        for failure in failures
    )
