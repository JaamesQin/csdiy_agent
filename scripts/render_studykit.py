#!/usr/bin/env python3
"""Render an internal StudyKit YAML file as user-facing Markdown."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.retrieval.render import render_studykit_markdown
from app.retrieval.schema_validation import validate_yaml


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("studykit", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    studykit = validate_yaml(args.studykit, ROOT / "schemas/studykit.schema.json")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_studykit_markdown(studykit), encoding="utf-8")
    print(f"rendered {args.output}")


if __name__ == "__main__":
    main()
