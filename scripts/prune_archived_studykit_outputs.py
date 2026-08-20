#!/usr/bin/env python3
"""Delete ignored output checkpoints after a verified SQLite archive exists."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.catalog.archive import StudyKitArchive


def _tree_size(path: Path) -> int:
    if path.is_symlink() or path.is_file():
        return path.lstat().st_size
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def prune(
    *,
    outputs_root: Path,
    database: Path,
    execute: bool,
) -> dict[str, object]:
    expected = (ROOT / "outputs").resolve()
    resolved = outputs_root.resolve()
    if resolved != expected or outputs_root.is_symlink():
        raise ValueError(f"refusing non-canonical outputs root: {outputs_root}")
    archive = StudyKitArchive(database)
    integrity_issues = archive.verify_integrity()
    builds = archive.list_builds()
    if integrity_issues or not builds:
        raise RuntimeError("a non-empty, integrity-clean StudyKit archive is required")

    targets = sorted(outputs_root.iterdir(), key=lambda item: item.name)
    for target in targets:
        if target.is_symlink():
            raise ValueError(f"refusing symlink under outputs: {target}")
    deleted = [
        {"path": target.relative_to(ROOT).as_posix(), "bytes": _tree_size(target)}
        for target in targets
    ]
    if execute:
        for target in targets:
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()

    database_bytes = database.read_bytes()
    return {
        "executed": execute,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "outputs_root": outputs_root.relative_to(ROOT).as_posix(),
        "archive": {
            "path": str(database),
            "sha256": hashlib.sha256(database_bytes).hexdigest(),
            "bytes": len(database_bytes),
            "build_count": len(builds),
            "document_count": sum(item.unit_count for item in builds),
            "build_ids": [item.build_id for item in builds],
        },
        "deleted_entry_count": len(deleted) if execute else 0,
        "deleted_bytes": sum(item["bytes"] for item in deleted) if execute else 0,
        "targets": deleted,
        "remaining_entries": sorted(item.name for item in outputs_root.iterdir()),
        "recoverability": "archived text artifacts are recoverable from SQLite; excluded images and caches are not",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outputs-root", type=Path, default=ROOT / "outputs")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = prune(outputs_root=args.outputs_root, database=args.database, execute=args.execute)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.report.with_suffix(args.report.suffix + ".tmp")
        temporary.write_text(rendered, encoding="utf-8")
        temporary.replace(args.report)
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
