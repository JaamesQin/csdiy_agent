from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts.audit_csdiy_registry import build_audit


class OfflineCompletionGateWorker:
    """Build a complete catalog graph locally; no network or model is used."""

    course_id = "fixture-cs101-spring-2026"
    target_id = "fixture-cs101"
    unit_id = "lecture-01"

    def __init__(self, root: Path) -> None:
        self.root = root
        self.registry_path = root / "data" / "catalog" / "registry.yaml"
        self.manifest_path = root / "data" / "manifests" / f"{self.course_id}.yaml"
        self.source_path = root / "data" / "raw" / f"{self.course_id}.pdf"
        self.chunks_path = root / "data" / "sources" / self.course_id / self.unit_id / "chunks.jsonl"
        self.build_path = root / "outputs" / self.course_id / "build-v1"
        self.unit_path = self.build_path / "courses" / self.course_id / "units" / self.unit_id

    def create(self) -> tuple[Path, dict[str, Any]]:
        self.source_path.parent.mkdir(parents=True)
        self.source_path.write_bytes(b"offline source bytes")
        self.chunks_path.parent.mkdir(parents=True)
        self.chunks_path.write_text(json.dumps({"chunk_id": "p1", "text": "fixture"}) + "\n", encoding="utf-8")

        self.manifest_path.parent.mkdir(parents=True)
        manifest = {
            "course_id": self.course_id,
            "course_version": "spring-2026",
            "primary_course_number": "CS101",
            "official_url": "https://fixture.invalid/cs101/spring-2026",
            "units": [
                {
                    "unit_id": self.unit_id,
                    "sources": [
                        {
                            "local_path": str(self.source_path.relative_to(self.root)),
                            "chunks_path": str(self.chunks_path.relative_to(self.root)),
                            "sha256": hashlib.sha256(self.source_path.read_bytes()).hexdigest(),
                            "page_count": 1,
                        }
                    ],
                }
            ],
        }
        self.manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

        self.unit_path.mkdir(parents=True)
        (self.build_path / "courses" / self.course_id).mkdir(exist_ok=True)
        (self.build_path / "STUDYKIT_INDEX.md").write_text("# Fixture StudyKit\n", encoding="utf-8")
        (self.build_path / "result.json").write_text(json.dumps({"status": "succeeded"}), encoding="utf-8")
        (self.build_path / "run.json").write_text(json.dumps({"author_id": "author-1"}), encoding="utf-8")
        (self.unit_path / "05-studykit.json").write_text(json.dumps({"status": "draft"}), encoding="utf-8")
        (self.unit_path / "validation.json").write_text(json.dumps({"status": "succeeded"}), encoding="utf-8")
        (self.unit_path / "review-plan.json").write_text(json.dumps({"actual_reviewed_pages": [1]}), encoding="utf-8")
        (self.unit_path / "independent-audit.json").write_text(
            json.dumps({"auditor_id": "reviewer-1", "author_id": "author-1", "result": "pass", "actual_reviewed_pages": [1]}),
            encoding="utf-8",
        )

        registry: dict[str, Any] = {
            "source_catalog": {"pinned_commit": "fixture"},
            "classification": {"independent_audit_status": "succeeded"},
            "nav_leaves": [
                {
                    "leaf_key": "courses::CS101",
                    "is_course_target": True,
                    "classification_review_status": "independently_audited",
                }
            ],
            "course_targets": [
                {
                    "canonical_course_id": self.target_id,
                    "course_numbers": ["CS101"],
                    "state": "complete",
                    "classification_review_status": "independently_audited",
                    "selected_offering": {
                        "course_id": self.course_id,
                        "course_version": "spring-2026",
                        "official_url": "https://fixture.invalid/cs101/spring-2026",
                    },
                    "source_inventory": {
                        "status": "complete",
                        "manifest_path": str(self.manifest_path.relative_to(self.root)),
                        "unit_ids": [self.unit_id],
                    },
                    "manifest_path": str(self.manifest_path.relative_to(self.root)),
                    "audit": {
                        "classification": "independently_audited",
                        "independent_audit_status": "succeeded",
                    },
                }
            ],
            "summary": {
                "nav_leaf_count": 1,
                "course_nav_leaf_count": 1,
                "course_target_count": 1,
                "excluded_leaf_count": 0,
            },
        }
        self.registry_path.parent.mkdir(parents=True)
        self.registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")
        return self.registry_path, registry


@pytest.fixture
def complete_catalog(tmp_path: Path) -> tuple[OfflineCompletionGateWorker, Path, dict[str, Any]]:
    worker = OfflineCompletionGateWorker(tmp_path)
    registry_path, registry = worker.create()
    return worker, registry_path, registry


def _audit(worker: OfflineCompletionGateWorker, registry_path: Path) -> dict[str, Any]:
    _, audit = build_audit(registry_path, worker.root)
    return audit


def test_global_gate_requires_the_entire_offline_completion_chain(
    complete_catalog: tuple[OfflineCompletionGateWorker, Path, dict[str, Any]],
) -> None:
    worker, registry_path, registry = complete_catalog
    target = registry["course_targets"][0]
    report = _audit(worker, registry_path)
    target_report = report["target_reports"][0]

    assert target["state"] == "complete"
    assert target["classification_review_status"] == "independently_audited"
    assert target["selected_offering"]["course_id"] == worker.course_id
    assert target["source_inventory"]["status"] == "complete"
    assert target_report["unit_count"] == 1
    assert target_report["chunk_count"] == 1
    assert target_report["validated_unit_count"] == 1
    assert target_report["audit_passed_unit_count"] == 1
    assert target_report["state"] == "complete"
    assert report["unclassified_or_unreviewed_leaf_count"] == 0
    assert report["orphan_manifests"] == []
    assert report["orphan_builds"] == []
    assert report["global_gate"] == "succeeded"


@pytest.mark.parametrize("mutation", ["false_complete", "blocked", "unclassified"])
def test_global_gate_never_succeeds_with_a_false_complete_blocked_or_unclassified_target(
    complete_catalog: tuple[OfflineCompletionGateWorker, Path, dict[str, Any]], mutation: str
) -> None:
    worker, registry_path, registry = complete_catalog
    if mutation == "false_complete":
        worker.chunks_path.unlink()
        registry["course_targets"][0]["state"] = "complete"
    elif mutation == "blocked":
        registry["course_targets"][0]["state"] = "blocked"
        registry["course_targets"][0]["next_action"] = "resolve_blocker"
        (worker.unit_path / "independent-audit.json").write_text(
            json.dumps(
                {
                    "auditor_id": "reviewer-1",
                    "author_id": "author-1",
                    "result": "block",
                    "actual_reviewed_pages": [1],
                    "blockers": ["fixture blocker"],
                }
            ),
            encoding="utf-8",
        )
    else:
        registry["nav_leaves"][0]["classification_review_status"] = "needs_review"
        registry["course_targets"][0]["state"] = "classified"
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")

    report = _audit(worker, registry_path)

    assert report["global_gate"] != "succeeded"
    if mutation == "false_complete":
        assert report["false_complete_targets"] == [worker.target_id]
    elif mutation == "blocked":
        assert report["target_reports"][0]["state"] != "complete"
    else:
        assert report["unclassified_or_unreviewed_leaf_count"] == 1
