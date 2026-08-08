#!/usr/bin/env python3
"""Run multiple StudyKit lectures concurrently with one async scheduler."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.generation.model import DeepSeekModel
from scripts.generate_studykit import generate_outputs


def _case(value: str) -> tuple[str, Path]:
    unit_id, separator, raw_path = value.partition("=")
    if not separator or not unit_id.strip() or not raw_path.strip():
        raise argparse.ArgumentTypeError("case must be UNIT_ID=CHUNKS_PATH")
    return unit_id.strip(), Path(raw_path.strip())


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a fixed StudyKit regression batch concurrently."
    )
    parser.add_argument(
        "--case",
        action="append",
        type=_case,
        required=True,
        help="Repeat as UNIT_ID=CHUNKS_PATH.",
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--target-minutes", type=int, default=180)
    parser.add_argument("--request-timeout", type=float, default=600.0)
    parser.add_argument("--stage-max-tokens", type=int, default=65_536)
    parser.add_argument("--network-retries", type=int, default=0)
    parser.add_argument("--invalid-json-retries", type=int, default=2)
    parser.add_argument("--length-retries", type=int, default=1)
    return parser


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _retry_counts(run: dict[str, Any] | None) -> dict[str, int]:
    counts = {
        "empty_message_content": 0,
        "invalid_message_json": 0,
        "length_limited_content": 0,
    }
    if run is None:
        return counts
    for stage in run.get("stages", {}).values():
        if not isinstance(stage, dict):
            continue
        for call in stage.get("model_calls", []):
            if not isinstance(call, dict):
                continue
            for diagnostic in call.get("retry_diagnostics", []):
                code = diagnostic.get("code") if isinstance(diagnostic, dict) else None
                if code in counts:
                    counts[code] += 1
    return counts


def _summarize(unit_id: str, output_dir: Path, result: Any) -> dict[str, Any]:
    run = _read_json(output_dir / "run.json")
    audit = _read_json(output_dir / "04-quality-audit.json")
    resolution = _read_json(output_dir / "04-quality-audit.resolution.json")
    studykit = result.studykit if isinstance(result.studykit, dict) else None
    usage = result.model_info.get("usage", {}) if result.model_info else {}
    audit_issues = audit.get("issues", []) if audit else []
    blockers = [
        item for item in audit_issues
        if isinstance(item, dict) and item.get("severity") == "blocker"
    ]
    warnings = [
        item for item in audit_issues
        if isinstance(item, dict) and item.get("severity") == "warning"
    ]
    unresolved_ids = (
        resolution.get("unresolved_issue_ids", []) if resolution else []
    )
    unresolved_warning_ids = (
        resolution.get("unresolved_warning_ids", []) if resolution else []
    )
    warning_resolution_counts = (
        resolution.get("warning_resolution_counts", {}) if resolution else {}
    )
    retries = _retry_counts(run)
    return {
        "unit_id": unit_id,
        "status": result.status.value,
        "failed_stage": (
            result.failed_stage.value if result.failed_stage is not None else None
        ),
        "issues": [item.to_dict() for item in result.issues],
        "audit_verdict": audit.get("verdict") if audit else None,
        "audit_resolution": resolution.get("outcome") if resolution else None,
        "generation_succeeded": result.status.value == "succeeded",
        "audit_direct_pass": bool(
            audit and audit.get("verdict") == "pass" and not audit_issues
        ),
        "repairs_applied_unverified": bool(
            resolution
            and resolution.get("outcome") == "repairs_applied_unverified"
        ),
        "warning_count": len(warnings),
        "warning_model_repaired_count": warning_resolution_counts.get(
            "warning_model_repaired", 0
        ),
        "warning_code_resolved_count": warning_resolution_counts.get(
            "warning_code_resolved", 0
        ),
        "warning_unresolved_count": warning_resolution_counts.get(
            "warning_unresolved", 0
        ),
        "warning_repair_failed_count": warning_resolution_counts.get(
            "warning_repair_failed", 0
        ),
        "unresolved_warning_ids": unresolved_warning_ids,
        "unresolved_blocker_count": len(unresolved_ids),
        "unresolved_blocker_ids": unresolved_ids,
        "practice_count": len(studykit.get("practice", [])) if studykit else None,
        "markdown_generated": (output_dir / "studykit.md").is_file(),
        "retry_counts": retries,
        "usage": usage,
    }


async def _run(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.concurrency <= 0:
        raise ValueError("concurrency must be positive")
    unit_ids = [unit_id for unit_id, _ in args.case]
    if len(unit_ids) != len(set(unit_ids)):
        raise ValueError("unit IDs must be unique")
    missing = [str(path) for _, path in args.case if not path.is_file()]
    if missing:
        raise ValueError(f"missing chunk files: {missing}")
    if not args.manifest.is_file():
        raise ValueError(f"missing manifest: {args.manifest}")

    args.output_root.mkdir(parents=True, exist_ok=False)
    semaphore = asyncio.Semaphore(args.concurrency)

    async def run_case(unit_id: str, chunks_path: Path) -> dict[str, Any]:
        async with semaphore:
            output_dir = args.output_root / unit_id
            try:
                model = DeepSeekModel.from_env()
                model.timeout_seconds = args.request_timeout
                model.max_retries = args.network_retries
                model.max_invalid_json_retries = args.invalid_json_retries
                model.max_length_retries = args.length_retries
                result = await generate_outputs(
                    model=model,
                    chunks_path=chunks_path,
                    manifest_path=args.manifest,
                    unit_id=unit_id,
                    output_dir=output_dir,
                    target_minutes=args.target_minutes,
                    request_timeout=args.request_timeout,
                    stage_max_tokens=args.stage_max_tokens,
                )
            except Exception as exc:
                return {
                    "unit_id": unit_id,
                    "status": "runner_error",
                    "failed_stage": None,
                    "issues": [
                        {
                            "stage": "runner",
                            "code": type(exc).__name__,
                            "message": str(exc)[:500],
                        }
                    ],
                    "audit_verdict": None,
                    "audit_resolution": None,
                    "practice_count": None,
                    "markdown_generated": False,
                    "retry_counts": _retry_counts(
                        _read_json(output_dir / "run.json")
                    ),
                    "usage": {},
                }
            return _summarize(unit_id, output_dir, result)

    started = time.perf_counter()
    summaries = await asyncio.gather(
        *(run_case(unit_id, path) for unit_id, path in args.case)
    )
    summaries.sort(key=lambda item: item["unit_id"])
    report = {
        "elapsed_seconds": time.perf_counter() - started,
        "concurrency": args.concurrency,
        "successes": sum(item["status"] == "succeeded" for item in summaries),
        "audit_direct_passes": sum(
            item.get("audit_direct_pass", False) for item in summaries
        ),
        "repairs_applied_unverified": sum(
            item.get("repairs_applied_unverified", False) for item in summaries
        ),
        "warning_count": sum(item.get("warning_count", 0) for item in summaries),
        "warning_model_repaired_count": sum(
            item.get("warning_model_repaired_count", 0) for item in summaries
        ),
        "warning_code_resolved_count": sum(
            item.get("warning_code_resolved_count", 0) for item in summaries
        ),
        "warning_unresolved_count": sum(
            item.get("warning_unresolved_count", 0) for item in summaries
        ),
        "warning_repair_failed_count": sum(
            item.get("warning_repair_failed_count", 0) for item in summaries
        ),
        "unresolved_blocker_count": sum(
            item.get("unresolved_blocker_count", 0) for item in summaries
        ),
        "retry_counts": {
            code: sum(
                item.get("retry_counts", {}).get(code, 0) for item in summaries
            )
            for code in (
                "empty_message_content",
                "invalid_message_json",
                "length_limited_content",
            )
        },
        "total": len(summaries),
        "results": summaries,
    }
    (args.output_root / "regression-summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summaries


def main() -> None:
    args = _parser().parse_args()
    try:
        summaries = asyncio.run(_run(args))
    except (OSError, ValueError) as exc:
        print(f"regression setup failed: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    succeeded = sum(item["status"] == "succeeded" for item in summaries)
    print(f"StudyKit regression: {succeeded}/{len(summaries)} succeeded")
    if succeeded != len(summaries):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
