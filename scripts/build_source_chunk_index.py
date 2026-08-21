#!/usr/bin/env python3
"""Build the public exact/FTS SourceChunk index from approved archive builds."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.retrieval.source_chunks import SourceChunk, initialize_source_chunk_index


DEFAULT_ARCHIVE = ROOT / "data" / "archive" / "studykits.sqlite3"
DEFAULT_OUTPUT = ROOT / "data" / "indexes" / "source_chunks.sqlite3"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def collect_approved_chunks(archive: Path, repository_root: Path) -> list[SourceChunk]:
    """Load only hash-bound sources for approved documents and builds."""

    uri = f"{archive.resolve().as_uri()}?mode=ro&immutable=1"
    chunks: list[SourceChunk] = []
    seen_ids: set[str] = set()
    with sqlite3.connect(uri, uri=True) as connection:
        connection.row_factory = sqlite3.Row
        builds = connection.execute(
            """
            SELECT build_id, course_id, course_version, metadata_json
            FROM studykit_builds
            WHERE build_status = 'succeeded' AND review_status = 'approved'
            ORDER BY course_id, course_version
            """
        ).fetchall()
        for build in builds:
            metadata = json.loads(build["metadata_json"])
            source_records = _source_records(metadata)
            approved_units = {
                str(row[0])
                for row in connection.execute(
                    """
                    SELECT unit_id FROM studykit_documents
                    WHERE build_id = ? AND review_status = 'approved'
                    ORDER BY unit_id
                    """,
                    (build["build_id"],),
                )
            }
            for unit_id in sorted(approved_units):
                record = source_records.get(unit_id)
                if record is None:
                    raise ValueError(f"{build['build_id']}/{unit_id}: source metadata missing")
                path = _source_path(repository_root, record, unit_id)
                for raw in _load_jsonl(path):
                    chunk = _approved_chunk(raw, build, unit_id, record)
                    if chunk is None:
                        continue
                    if chunk.chunk_id in seen_ids:
                        raise ValueError(f"duplicate approved chunk_id: {chunk.chunk_id}")
                    seen_ids.add(chunk.chunk_id)
                    chunks.append(chunk)
    return chunks


def build_index(
    archive: Path,
    output: Path,
    repository_root: Path,
    *,
    replace: bool = False,
) -> int:
    chunks = collect_approved_chunks(archive, repository_root)
    if not chunks:
        raise ValueError("archive contains no approved public source chunks")
    if output.exists() and not replace:
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp-{os.getpid()}")
    if temporary.exists():
        temporary.unlink()
    try:
        initialize_source_chunk_index(temporary, chunks)
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()
    return len(chunks)


def _source_records(metadata: Any) -> dict[str, dict[str, Any]]:
    run = metadata.get("run") if isinstance(metadata, dict) else None
    fingerprint = run.get("fingerprint_payload") if isinstance(run, dict) else None
    units = fingerprint.get("units") if isinstance(fingerprint, dict) else None
    if not isinstance(units, list):
        raise ValueError("approved build has no fingerprinted source units")
    result: dict[str, dict[str, Any]] = {}
    for record in units:
        if not isinstance(record, dict) or not isinstance(record.get("unit_id"), str):
            raise ValueError("approved build has an invalid source unit record")
        unit_id = record["unit_id"]
        if unit_id in result:
            raise ValueError(f"duplicate source unit record: {unit_id}")
        result[unit_id] = record
    return result


def _source_path(repository_root: Path, record: dict[str, Any], unit_id: str) -> Path:
    relative = record.get("chunks_path")
    expected = record.get("chunks_sha256")
    if not isinstance(relative, str) or not isinstance(expected, str):
        raise ValueError(f"{unit_id}: incomplete chunks path/hash metadata")
    root = repository_root.resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError(f"{unit_id}: chunks path is unavailable or outside the repository")
    if _sha256_file(path) != expected:
        raise ValueError(f"{unit_id}: chunks_sha256 mismatch")
    return path


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    values = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if any(not isinstance(value, dict) for value in values):
        raise ValueError(f"{path}: every JSONL row must be an object")
    return values


def _approved_chunk(
    raw: dict[str, Any],
    build: sqlite3.Row,
    unit_id: str,
    source_record: dict[str, Any],
) -> SourceChunk | None:
    if raw.get("scope") != "public" or raw.get("content_type") == "hidden_text":
        return None
    if any("hidden" in str(item).casefold() for item in raw.get("parse_warnings", [])):
        return None
    expected_identity = {
        "course_id": str(build["course_id"]),
        "course_version": str(build["course_version"]),
        "unit_id": unit_id,
    }
    if any(raw.get(key) != value for key, value in expected_identity.items()):
        raise ValueError(f"{build['build_id']}/{unit_id}: chunk identity mismatch")
    if source_record.get("source_id") and raw.get("source_id") != source_record["source_id"]:
        raise ValueError(f"{build['build_id']}/{unit_id}: chunk source_id mismatch")
    anchor = raw.get("anchor")
    if not isinstance(anchor, dict):
        raise ValueError(f"{build['build_id']}/{unit_id}: chunk anchor missing")
    anchor_type = anchor.get("type")
    anchor_value = anchor.get("value")
    if not isinstance(anchor_type, str) or not isinstance(anchor_value, (str, int)):
        raise ValueError(f"{build['build_id']}/{unit_id}: invalid chunk anchor")
    text = raw.get("content")
    if not isinstance(text, str) or not text.strip():
        return None
    return SourceChunk(
        chunk_id=str(raw.get("chunk_id") or ""),
        course_id=expected_identity["course_id"],
        course_version=expected_identity["course_version"],
        unit_id=unit_id,
        source_id=str(raw.get("source_id") or ""),
        page=anchor_value if anchor_type == "page" and isinstance(anchor_value, int) else None,
        anchor_type=anchor_type,
        anchor_value=str(anchor_value),
        heading=str(raw["heading"]) if isinstance(raw.get("heading"), str) else None,
        text=text,
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        build_id=str(build["build_id"]),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--repository-root", type=Path, default=ROOT)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    count = build_index(
        args.archive,
        args.output,
        args.repository_root,
        replace=args.replace,
    )
    print(json.dumps({"status": "succeeded", "chunk_count": count, "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
