#!/usr/bin/env python3
"""Create a deterministic unit execution plan; never invokes a model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from workflow_policy import coordinator_slot_budget, resolve_options, worker_count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unit", action="append", required=True, dest="units")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--quality-mode", choices=("fast", "standard", "strict"))
    parser.add_argument("--default-decision", type=Path)
    parser.add_argument("--delivery-policy", choices=("draft", "publish"))
    parser.add_argument("--generation-policy", choices=("draft", "strict"))
    parser.add_argument("--parallel-units", default="auto")
    parser.add_argument("--available-slots", type=int)
    parser.add_argument("--session-slots", type=int, help="whole-session slot budget shared by isolated build coordinators")
    parser.add_argument("--coordinator-id", default="coordinator-1")
    parser.add_argument("--coordinator-count", type=int, default=1)
    parser.add_argument("--global-coordinator-reserve", type=int, default=1)
    parser.add_argument("--no-subtasks", action="store_true")
    parser.add_argument("--write", type=Path)
    args = parser.parse_args()
    if len(set(args.units)) != len(args.units):
        parser.error("duplicate unit IDs are not allowed")
    if args.available_slots is not None and args.session_slots is not None:
        parser.error("use either --available-slots (per coordinator) or --session-slots (whole session), not both")
    if args.coordinator_count > 1 and args.session_slots is None and args.available_slots is None:
        parser.error("multiple coordinators require --session-slots or a per-coordinator --available-slots budget")
    try:
        coordinator_slots = (
            coordinator_slot_budget(args.session_slots, args.coordinator_count, args.global_coordinator_reserve)
            if args.session_slots is not None
            else args.available_slots
        )
    except ValueError as exc:
        parser.error(str(exc))
    options = resolve_options(args.quality_mode, args.delivery_policy, args.generation_policy, args.default_decision)
    workers = worker_count(len(args.units), args.parallel_units, coordinator_slots, not args.no_subtasks)
    groups = [[] for _ in range(workers)]
    for index, unit in enumerate(args.units):
        groups[index % workers].append(unit)
    plan = {
        **options,
        "parallel_units": args.parallel_units,
        "worker_count": workers,
        "coordinator": {
            "id": args.coordinator_id,
            "scope": "single-build",
            "isolated": True,
            "coordinator_count": args.coordinator_count,
            "slot_budget": coordinator_slots,
            "output_isolation_key": str(args.output_dir.resolve()),
            "global_merge_owner": "global-coordinator",
        },
        "session_slots": args.session_slots,
        "global_coordinator_reserve": args.global_coordinator_reserve,
        "stage_timeout_seconds": 600,
        "transient_retry_limit": 1,
        "stage_order": ["01-evidence-plan", "02-learning-content", "03-practice-flow", "04-quality-audit", "05-studykit"],
        "workers": [
            {"worker": index + 1, "units": group, "output_dirs": [str((args.output_dir / unit).resolve()) for unit in group]}
            for index, group in enumerate(groups)
        ],
        "isolation": "worker may write only its assigned unit directory; this coordinator owns only its isolated build root; global coordinator owns registry and aggregate summaries",
    }
    rendered = json.dumps(plan, ensure_ascii=False, indent=2) + "\n"
    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
