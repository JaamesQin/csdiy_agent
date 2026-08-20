#!/usr/bin/env python3
"""Render deterministic parser-risk PDF pages for catalog course review.

This is an offline coordinator utility. It does not fetch sources, invoke a
model, or decide that a page has passed visual review. It records the risk
selection and the rendered image paths so a human/host visual pass can be
audited separately.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
SKILL_SCRIPTS = ROOT / "skills" / "studykit-generator" / "scripts"
if str(SKILL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SKILL_SCRIPTS))
from workflow_policy import _has_risk  # noqa: E402


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_chunks(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def consecutive_runs(pages: list[int]) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    for page in sorted(set(pages)):
        if not runs or page != runs[-1][1] + 1:
            runs.append((page, page))
        else:
            runs[-1] = (runs[-1][0], page)
    return runs


def render_pages(pdf: Path, pages: list[int], destination_dir: Path, dpi: int) -> None:
    """Render contiguous page runs, reusing already-rendered pages."""
    destination_dir.mkdir(parents=True, exist_ok=True)
    for start, end in consecutive_runs(pages):
        expected = [destination_dir / f"page-{page:04d}.png" for page in range(start, end + 1)]
        if all(path.is_file() for path in expected):
            continue
        temporary_prefix = destination_dir / f".render-{start:04d}-{end:04d}"
        subprocess.run(
            [
                "pdftoppm", "-png", "-r", str(dpi),
                "-f", str(start), "-l", str(end), str(pdf),
                str(temporary_prefix),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for rendered in destination_dir.glob(f"{temporary_prefix.name}-*.png"):
            page = int(rendered.stem.rsplit("-", 1)[1])
            rendered.replace(destination_dir / f"page-{page:04d}.png")
        missing = [str(path) for path in expected if not path.is_file()]
        if missing:
            raise FileNotFoundError(f"pdftoppm did not create: {missing}")


def course_plan(manifest_path: Path, output_root: Path, repository_root: Path, dpi: int) -> dict[str, Any]:
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    course_id = str(manifest["course_id"])
    course_output = output_root / course_id
    units: list[dict[str, Any]] = []
    for unit in manifest.get("units", []):
        sources = unit.get("sources") or []
        if len(sources) != 1:
            raise ValueError(f"{course_id}/{unit['unit_id']} must have exactly one source")
        source = sources[0]
        chunks_path = repository_root / source["chunks_path"]
        chunks = load_chunks(chunks_path)
        risky: dict[int, list[dict[str, Any]]] = {}
        for chunk in chunks:
            anchor = chunk.get("anchor") or {}
            if anchor.get("type") != "page" or not (
                _has_risk(chunk) or not str(chunk.get("content") or "").strip()
            ):
                continue
            page = int(anchor["value"])
            risky.setdefault(page, []).append({
                "chunk_id": chunk.get("chunk_id"),
                "warnings": chunk.get("parse_warnings", []),
                "content_empty": not bool(str(chunk.get("content") or "").strip()),
            })
        local_path = repository_root / source["local_path"]
        rendered: list[dict[str, Any]] = []
        pages = sorted(risky)
        if pages and local_path.suffix.lower() == ".pdf":
            render_pages(local_path, pages, course_output / unit["unit_id"], dpi)
        for page, reasons in sorted(risky.items()):
            record: dict[str, Any] = {
                "page": page,
                "reasons": reasons,
                "source_path": source["local_path"],
                "source_sha256": source.get("sha256"),
                "rendered": False,
            }
            if local_path.suffix.lower() == ".pdf":
                image = course_output / unit["unit_id"] / f"page-{page:04d}.png"
                record.update({
                    "rendered": True,
                    "image_path": str(image.relative_to(repository_root)),
                    "image_sha256": sha256_file(image),
                })
            else:
                record["render_skip_reason"] = "source_is_not_pdf"
            rendered.append(record)
        units.append({
            "unit_id": unit["unit_id"],
            "source_id": source.get("source_id"),
            "chunks_path": source["chunks_path"],
            "source_path": source["local_path"],
            "source_kind": "pdf" if local_path.suffix.lower() == ".pdf" else "non_pdf",
            "source_sha256": source.get("sha256"),
            "risk_page_count": len(rendered),
            "risk_pages": rendered,
        })
    result = {
        "review_version": "risk-pages-v1",
        "course_id": course_id,
        "course_version": manifest.get("course_version"),
        "catalog_manifest": str(manifest_path.relative_to(repository_root)),
        "quality_mode": "fast",
        "page_selector_version": "review-pages-v1",
        "render_dpi": dpi,
        "visual_review_status": "rendered_pending_inspection",
        "units": units,
        "risk_page_count": sum(unit["risk_page_count"] for unit in units),
        "rendered_page_count": sum(
            sum(int(page["rendered"]) for page in unit["risk_pages"])
            for unit in units
        ),
        "non_pdf_risk_page_count": sum(
            sum(not page["rendered"] for page in unit["risk_pages"])
            for unit in units
        ),
    }
    course_output.mkdir(parents=True, exist_ok=True)
    (course_output / "risk-page-plan.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog-manifest", action="append", required=True, type=Path)
    parser.add_argument("--repository-root", type=Path, default=ROOT)
    parser.add_argument("--output-root", type=Path, default=ROOT / "data" / "raw" / "catalog-visual-review-v1")
    parser.add_argument("--dpi", type=int, default=100)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if shutil.which("pdftoppm") is None:
        raise SystemExit("pdftoppm is required for PDF risk-page rendering")
    repository_root = args.repository_root.resolve()
    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    courses = [
        course_plan(path.resolve(), output_root, repository_root, args.dpi)
        for path in args.catalog_manifest
    ]
    summary = {
        "review_version": "risk-pages-v1",
        "quality_mode": "fast",
        "page_selector_version": "review-pages-v1",
        "render_dpi": args.dpi,
        "courses": courses,
        "course_count": len(courses),
        "risk_page_count": sum(course["risk_page_count"] for course in courses),
        "rendered_page_count": sum(course["rendered_page_count"] for course in courses),
        "non_pdf_risk_page_count": sum(course["non_pdf_risk_page_count"] for course in courses),
        "visual_review_status": "rendered_pending_inspection",
    }
    (output_root / "risk-page-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "output_root": str(output_root),
        "course_count": summary["course_count"],
        "risk_page_count": summary["risk_page_count"],
        "rendered_page_count": summary["rendered_page_count"],
        "non_pdf_risk_page_count": summary["non_pdf_risk_page_count"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
