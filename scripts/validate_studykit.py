#!/usr/bin/env python3
"""Validate a StudyKit schema and all page citations."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.retrieval.citations import validate_citations
from app.retrieval.parser import read_jsonl
from app.retrieval.schema_validation import validate_yaml


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("studykit", type=Path)
    parser.add_argument("--chunks", type=Path, required=True)
    args = parser.parse_args()

    studykit = validate_yaml(args.studykit, ROOT / "schemas/studykit.schema.json")
    issues = validate_citations(studykit, read_jsonl(args.chunks))
    if issues:
        for issue in issues:
            print(
                f"{issue.location}: {issue.source_id} page {issue.page}: {issue.reason}"
            )
        raise SystemExit(1)
    print(f"valid StudyKit; all citations resolve: {args.studykit}")


if __name__ == "__main__":
    main()
