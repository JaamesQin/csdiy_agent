#!/usr/bin/env python3
"""Build page-anchored SourceChunks from one PDF."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.retrieval.parser import parse_pdf_pages, write_jsonl
from app.retrieval.schema_validation import validate_instance


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--material-set-id", required=True)
    parser.add_argument("--course-id")
    parser.add_argument("--course-version")
    parser.add_argument("--unit-id", required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--scope", choices=("public", "private"), default="public")
    parser.add_argument("--owner-id")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    chunks = parse_pdf_pages(
        args.pdf,
        material_set_id=args.material_set_id,
        scope=args.scope,
        owner_id=args.owner_id,
        course_id=args.course_id,
        course_version=args.course_version,
        unit_id=args.unit_id,
        source_id=args.source_id,
    )
    schema_path = ROOT / "schemas/source_chunk.schema.json"
    for chunk in chunks:
        validate_instance(chunk, schema_path)
    write_jsonl(chunks, args.output)
    warning_pages = sum(bool(chunk["parse_warnings"]) for chunk in chunks)
    print(
        f"wrote {len(chunks)} page chunks to {args.output} "
        f"({warning_pages} pages with warnings)"
    )


if __name__ == "__main__":
    main()
