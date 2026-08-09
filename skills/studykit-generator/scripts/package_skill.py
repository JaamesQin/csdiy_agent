#!/usr/bin/env python3
"""Build a deterministic, text-only submission ZIP with SKILL.md at its root."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import zipfile


ALLOWED = {".md", ".py", ".json", ".yaml", ".yml", ".txt"}
IGNORED_PARTS = {"__pycache__", ".pytest_cache"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-dir", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    skill = args.skill_dir.resolve()
    if not (skill / "SKILL.md").is_file():
        raise SystemExit("SKILL.md not found")
    files = sorted(
        path for path in skill.rglob("*")
        if path.is_file() and path.suffix.lower() in ALLOWED
        and not any(part in IGNORED_PARTS for part in path.parts)
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            info = zipfile.ZipInfo(str(path.relative_to(skill)))
            info.date_time = (2026, 1, 1, 0, 0, 0)
            info.external_attr = (0o755 if path.suffix == ".py" else 0o644) << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    print(f"{args.output} {args.output.stat().st_size} bytes sha256={digest} files={len(files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
