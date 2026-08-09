#!/usr/bin/env python3
"""Reject incomplete, synthetic-looking, or overlapping aligned-run timing records."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
from typing import Any


MODES = ("fast", "standard", "strict")


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def validate_timing(summary: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    setup = summary.get("setup", {})
    try:
        setup_start = _timestamp(setup["started_at"])
        setup_end = _timestamp(setup["completed_at"])
        setup_duration = float(setup["total_duration_seconds"])
        if setup_end <= setup_start or setup_duration <= 0:
            issues.append("setup timing must be positive")
    except (KeyError, TypeError, ValueError):
        setup_end = None
        issues.append("setup timing is incomplete")
    previous_end = setup_end
    for mode in MODES:
        record = summary.get("modes", {}).get(mode, {})
        try:
            start = _timestamp(record["started_at"])
            end = _timestamp(record["completed_at"])
            duration = float(record["total_duration_seconds"])
        except (KeyError, TypeError, ValueError):
            issues.append(f"{mode} timing is incomplete")
            continue
        if end <= start or duration <= 0:
            issues.append(f"{mode} timing must be positive")
        elapsed = (end - start).total_seconds()
        if abs(elapsed - duration) > max(1.0, duration * 0.02):
            issues.append(f"{mode} duration does not match timestamps")
        if previous_end and start < previous_end:
            issues.append(f"{mode} overlaps setup or previous mode")
        previous_end = end
        stages = record.get("stage_durations_seconds") or record.get("stage_duration_seconds")
        if not isinstance(stages, dict) or not stages:
            issues.append(f"{mode} stage timings are missing")
        else:
            stage_total = sum(float(value) for value in stages.values())
            if abs(stage_total - duration) > max(1.0, duration * 0.05):
                issues.append(f"{mode} stage timings do not close to total")
        if not isinstance(record.get("reviewed_page_count"), int) or record["reviewed_page_count"] <= 0:
            issues.append(f"{mode} reviewed_page_count must be positive")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()
    issues = validate_timing(json.loads(args.summary.read_text(encoding="utf-8")))
    result = {"status": "succeeded" if not issues else "failed", "issues": issues}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
