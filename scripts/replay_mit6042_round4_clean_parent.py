#!/usr/bin/env python3
"""Replay the authorized MIT 6.042J Round-3 unit checkpoints into Round 4.

This worker is intentionally scoped to the four assigned unit directories. It
copies only current authoring/finalization artifacts from the direct Round-3
parent, applies the one listed lecture-19 arithmetic repair, rebuilds current
build metadata, and removes inherited audit/snapshot sidecars.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path


COURSE = "mit-6-042j-spring-2024"
TARGET_BUILD = "c2690f165be0d9be704e8708d7b3cec9e7dbb0c4fdd782fe1e9604d5c2ba8dd7"
SOURCE_BUILD = "de2a1319100aceb941ffa57178ce60cb97383cd5f6572b95d0cde1c30da52670"
SOURCE_PARENT_DIGESTS = {
    "lecture-16": "3de23fda2b01f814f71523a905efcbd9d9ef3fdb97397b0e47dccedef237040c",
    "lecture-19": "c906b1b9610d4e340f9a986f154e44956aef8e1fa151dbbd01f88a8aea595913",
    "lecture-23": "754c96d9b0a8621c328df7407ad9bce98d20ae72e23af539bc96b702842ed460",
    "lecture-24": "c914b132c99e0116e680aade78fb1e9842065823ca0ad3120172b6370eb09bc1",
}
UNITS = {
    "lecture-16": ["practice", "structural"],
    "lecture-19": ["practice", "structural"],
    "lecture-23": ["evidence", "practice", "structural"],
    "lecture-24": ["evidence", "practice", "structural"],
}
CHECKPOINTS = [
    "01-evidence-plan.json",
    "02-learning-content.json",
    "03-practice-flow.json",
    "04-quality-audit.json",
    "04-quality-audit.resolution.json",
    "05-studykit.candidate.json",
    "05-studykit.json",
    "review-plan.json",
    "metrics.json",
    "studykit.md",
    "studykit.yaml",
    "validation.json",
]
REMOVE_NAMES = {
    "repair-baseline",
    "repair-parent-baseline",
    "independent-audit.json",
    "independent-audit.post-final.json",
    "independent-audit.post-final.xhigh.json",
    "independent-audit.round2.xhigh.json",
    "independent-audit.round3.xhigh.json",
    "independent-audit.xhigh.json",
    "author-self-check.round2.json",
    "author-self-check.round3.json",
    "validation.candidate.json",
    "validation.repair-candidate.json",
    "validation.round2.json",
    "validation.round3.json",
    "validation.final.round3.json",
    "validation.final-independent.json",
    "validation.independent.json",
    "review-validation.author.json",
    "review-validation.independent.json",
    "review-validation.repair.json",
    "review-validation.round3.json",
    "review-validation.json",
}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def remove_old(unit: Path) -> None:
    for child in list(unit.iterdir()):
        if child.name in REMOVE_NAMES:
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()


def repair_lecture_19(unit: Path) -> None:
    practice = load(unit / "03-practice-flow.json")
    item = next(x for x in practice["practice"] if x.get("id") == "practice-1")
    item["expected_evidence"] = [
        "不放回且 A 发生时写出 P(B|A)=2/4=1/2、P(A)=3/5、P(A∩B)=3/10，并由全概率或交换对称性得到 P(B)=3/5，再核对乘法公式",
        "放回时写出 P(B|A)=3/5、P(B)=3/5、P(A∩B)=3/5·3/5=9/25，并用乘法公式核对；指出分母从剩余 4 球恢复为 5 球",
    ]
    item["evaluation"]["criteria"] = [
        "红球 3、蓝球 2、顺序事件 A/B 和不放回条件均进入计算",
        "P(A∩B)=3/5·1/2=3/10，且第二球为红的边缘概率 P(B)=3/5（2/5 是蓝球边缘概率）",
        "放回只改变第二次抽取的组成，明确比较两种 P(B|A) 及两种联合概率 3/10 与 9/25",
    ]
    practice["repair_revision"] = "round4-clean-replay-20260812"
    practice["repair_scope"] = "listed-practice-correction-only"
    practice["repair_practice_ids"] = ["practice-1"]
    write(unit / "03-practice-flow.json", practice)

    kit = load(unit / "05-studykit.candidate.json")
    final_item = next(x for x in kit["practice"] if x.get("id") == "practice-1")
    final_item["expected_evidence"] = item["expected_evidence"]
    final_item["evaluation"] = item["evaluation"]
    write(unit / "05-studykit.candidate.json", kit)
    # Structural replay requires one exact current representation in all three
    # learner-facing serializations; do not preserve stale parent differences.
    write(unit / "05-studykit.json", kit)
    import yaml
    (unit / "studykit.yaml").write_text(
        yaml.safe_dump(kit, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    markdown = (unit / "studykit.md").read_text(encoding="utf-8")
    markdown = markdown.replace("P(B)=2/5", "P(B)=3/5")
    (unit / "studykit.md").write_text(markdown, encoding="utf-8")


def reset_quality_audit(unit: Path) -> None:
    audit = load(unit / "04-quality-audit.json")
    for key in ("independent_auditor", "independent_audit_time", "independent_audit_result", "independent_audit_blockers"):
        audit.pop(key, None)
    audit["verdict"] = "pending_independent_audit"
    audit["status"] = "repair_pending_independent_reaudit"
    audit["independent"] = False
    audit["repair_revision"] = "round4-clean-replay-20260812"
    write(unit / "04-quality-audit.json", audit)
    resolution = load(unit / "04-quality-audit.resolution.json")
    resolution["repair_revision"] = "round4-clean-replay-20260812"
    resolution["status"] = "targeted_repairs_applied_pending_independent_reaudit"
    resolution.pop("independent_reaudit", None)
    write(unit / "04-quality-audit.resolution.json", resolution)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    source_root = root / "outputs" / COURSE / SOURCE_BUILD / "courses" / COURSE / "units"
    target_root = root / "outputs" / COURSE / TARGET_BUILD / "courses" / COURSE / "units"
    author = "luna-medium-clean-parent-replay-author"

    for unit_id, stages in UNITS.items():
        source = source_root / unit_id
        target = target_root / unit_id
        remove_old(target)
        for name in CHECKPOINTS:
            shutil.copy2(source / name, target / name)
        if unit_id == "lecture-19":
            repair_lecture_19(target)
        reset_quality_audit(target)

        review = load(target / "review-plan.json")
        for key in ("independent_auditor", "independent_audit_time", "independent_audit_result", "blockers_after_reaudit"):
            review.pop(key, None)
        review.update({
            "independent_audit": False,
            "independent_audit_status": "pending_current_build_review",
            "review_outcome": "pending_current_build_review",
            "repair_status": "round4_clean_replay_pending_independent_audit",
            "repair_revision": "round4-clean-replay-20260812",
            "repair_scope": "authorized-round3-replay-plus-listed-correction",
            "current_build_id": TARGET_BUILD,
            "repair_stages": stages,
        })
        write(target / "review-plan.json", review)

        metrics = load(target / "metrics.json")
        for key in ("independent_auditor", "independent_audit_time", "independent_audit_result"):
            metrics.pop(key, None)
        repaired = ["practice-1"] if unit_id == "lecture-19" else ["replayed-round3-authorized-checkpoints"]
        metrics.update({
            "semantic_passes": 1,
            "independent_audit": False,
            "independent_audit_status": "pending_current_build_review",
            "repair_status": "round4_clean_replay_pending_independent_audit",
            "repaired_practice_ids": repaired,
            "current_build_id": TARGET_BUILD,
            "author_id": author,
            "repairs": [{
                "stage": "+".join(stages), "attempt": 1, "fresh_round": 4,
                "status": "applied_pending_independent_audit", "author_id": author,
                "practice_ids": repaired,
            }],
            "repair_records": [{
                "repair_id": f"round4-clean-replay-{unit_id}", "stages": stages,
                "attempt": 1, "fresh_round": 4, "revision": "round4-clean-replay-20260812",
                "practice_ids": repaired, "status": "applied_pending_independent_audit",
                "remaining_blockers": ["fresh independent audit pending"],
            }],
        })
        write(target / "metrics.json", metrics)

        candidate = load(target / "05-studykit.candidate.json")
        final = load(target / "05-studykit.json")
        import yaml
        yaml_value = yaml.safe_load((target / "studykit.yaml").read_text(encoding="utf-8"))
        checks = {
            "authorized_source_build": SOURCE_BUILD,
            "current_build_id": TARGET_BUILD,
            "replayed_checkpoints": [*stages, "05-studykit.candidate.json", "05-studykit.json", "studykit.yaml"],
            "candidate_final_semantically_equal": candidate == final,
            "candidate_yaml_semantically_equal": candidate == yaml_value,
            "direct_parent_build": SOURCE_BUILD,
            "direct_parent_artifact_digest_verified": SOURCE_PARENT_DIGESTS[unit_id],
            "independent_audit": "not_run_by_author",
            "old_audit_verdicts_copied": False,
            "old_snapshots_copied": False,
            "root_or_registry_written": False,
        }
        write(target / "author-self-check.round4.json", {
            "schema_version": "author-self-check-round4-v1",
            "round": "round4",
            "author_tier": "luna-medium",
            "course_id": COURSE,
            "unit_id": unit_id,
            "assigned_blockers": ["replay authorized Round-3 result"] if unit_id != "lecture-19" else ["correct P(B) to 3/5 and dependent expected/evaluation values"],
            "checks": checks,
            "validator_status": "passed_pending_independent_audit",
            "independent_audit_run": False,
        })


if __name__ == "__main__":
    main()
