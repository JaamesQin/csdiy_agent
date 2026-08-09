#!/usr/bin/env python3
"""Create a deterministic unit execution plan; never invokes a model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from workflow_policy import resolve_options, worker_count


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
    parser.add_argument("--no-subtasks", action="store_true")
    parser.add_argument("--write", type=Path)
    args = parser.parse_args()
    if len(set(args.units)) != len(args.units):
        parser.error("duplicate unit IDs are not allowed")
    options = resolve_options(args.quality_mode, args.delivery_policy, args.generation_policy, args.default_decision)
    workers = worker_count(len(args.units), args.parallel_units, args.available_slots, not args.no_subtasks)
    groups = [[] for _ in range(workers)]
    for index, unit in enumerate(args.units):
        groups[index % workers].append(unit)
    plan = {
        **options,
        "parallel_units": args.parallel_units,
        "worker_count": workers,
        "stage_timeout_seconds": 600,
        "transient_retry_limit": 1,
        "stage_order": ["01-evidence-plan", "02-learning-content", "03-practice-flow", "04-quality-audit", "05-studykit"],
        "workers": [
            {"worker": index + 1, "units": group, "output_dirs": [str((args.output_dir / unit).resolve()) for unit in group]}
            for index, group in enumerate(groups)
        ],
        "isolation": "worker may write only its assigned unit directory; coordinator owns root summaries",
    }
    rendered = json.dumps(plan, ensure_ascii=False, indent=2) + "\n"
    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
