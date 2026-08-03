"""Text-first PDF parser that preserves one-based page anchors."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

from pypdf import PdfReader

PARSER_VERSION = "pdf-page-v0.1"
_NOISE_LINE = re.compile(
    r"(?:sha1_base64=|</?latexit|^[A-Za-z0-9+/=]{160,}$)",
    re.IGNORECASE,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_pdf_text(text: str) -> tuple[str, list[str]]:
    kept: list[str] = []
    removed = 0
    duplicate_lines = 0
    seen_lines: set[str] = set()
    for raw_line in text.replace("\x00", "").splitlines():
        line = " ".join(raw_line.split())
        if not line:
            if kept and kept[-1]:
                kept.append("")
            continue
        if _NOISE_LINE.search(line):
            removed += 1
            continue
        # Some slide PDFs embed the same accessibility/LaTeX description many
        # times on one page. Deduplicate it without changing the page anchor.
        if line in seen_lines:
            duplicate_lines += 1
            continue
        seen_lines.add(line)
        kept.append(line)

    normalized = "\n".join(kept).strip()
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    warnings: list[str] = []
    if removed:
        warnings.append(f"removed_hidden_formula_noise_lines:{removed}")
    if duplicate_lines:
        warnings.append(f"removed_duplicate_lines:{duplicate_lines}")
    if len(normalized) < 40:
        warnings.append("low_extracted_text")
    return normalized, warnings


def infer_heading(text: str) -> str | None:
    for line in text.splitlines():
        candidate = line.strip()
        if 3 <= len(candidate) <= 160 and not candidate.isdigit():
            return candidate
    return None


def parse_pdf_pages(
    pdf_path: Path,
    *,
    material_set_id: str,
    scope: str,
    owner_id: str | None,
    course_id: str | None,
    course_version: str | None,
    unit_id: str,
    source_id: str,
) -> list[dict[str, Any]]:
    if scope not in {"public", "private"}:
        raise ValueError("scope must be public or private")
    if scope == "public" and owner_id is not None:
        raise ValueError("public chunks cannot have an owner_id")
    if scope == "private" and not owner_id:
        raise ValueError("private chunks require owner_id")

    reader = PdfReader(str(pdf_path))
    if reader.is_encrypted:
        raise ValueError(f"encrypted PDFs are unsupported: {pdf_path}")

    chunks: list[dict[str, Any]] = []
    for page_number, page in enumerate(reader.pages, start=1):
        extracted = page.extract_text() or ""
        content, warnings = normalize_pdf_text(extracted)
        chunks.append(
            {
                "chunk_id": f"{source_id}-p{page_number:03d}",
                "material_set_id": material_set_id,
                "scope": scope,
                "owner_id": owner_id,
                "course_id": course_id,
                "course_version": course_version,
                "unit_id": unit_id,
                "source_id": source_id,
                "anchor": {"type": "page", "value": page_number},
                "heading": infer_heading(content),
                "content": content,
                "content_type": "mixed",
                "parser_version": PARSER_VERSION,
                "parse_warnings": warnings,
            }
        )
    return chunks


def write_jsonl(chunks: Iterable[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as stream:
        for chunk in chunks:
            stream.write(json.dumps(chunk, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]
