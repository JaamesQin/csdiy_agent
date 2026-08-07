#!/usr/bin/env python3
"""Generate a validated draft StudyKit from local page-level SourceChunks."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.generation.generator import StudyKitGenerator
from app.generation.model import DeepSeekModel, ModelError, StructuredModel
from app.generation.result import GenerationRequest, GenerationResult, GenerationStage
from app.retrieval.parser import read_jsonl
from app.retrieval.render import render_studykit_markdown
from app.retrieval.schema_validation import load_yaml


def _find_unit(manifest: dict[str, Any], unit_id: str) -> dict[str, Any]:
    for unit in manifest.get("units", []):
        if unit.get("unit_id") == unit_id:
            return unit
    raise ValueError(f"unit_id {unit_id!r} was not found in the manifest")


def _source_metadata(
    unit: dict[str, Any],
    chunk_source_ids: set[str],
) -> tuple[dict[str, Any], ...]:
    sources: list[dict[str, Any]] = []
    for source in unit.get("sources", []):
        source_id = source.get("source_id")
        if source_id not in chunk_source_ids:
            continue
        title = (
            source.get("title")
            or unit.get("official_resource_title")
            or unit.get("title")
        )
        metadata = {
            key: value
            for key, value in source.items()
            if key
            in {
                "source_id",
                "type",
                "sha256",
                "official_url",
                "local_path",
            }
        }
        metadata["title"] = title
        missing = [
            field
            for field in ("source_id", "title", "type", "sha256")
            if not metadata.get(field)
        ]
        if missing:
            raise ValueError(
                f"source {source_id!r} is missing metadata: {', '.join(missing)}"
            )
        sources.append(metadata)

    found_ids = {source["source_id"] for source in sources}
    if found_ids != chunk_source_ids:
        missing_ids = sorted(chunk_source_ids - found_ids)
        raise ValueError(
            f"manifest unit does not declare chunk sources: {missing_ids}"
        )
    return tuple(sources)


def build_request(
    manifest: dict[str, Any],
    chunks: list[dict[str, Any]],
    *,
    unit_id: str,
    language: str,
    target_minutes: int,
) -> GenerationRequest:
    """Resolve trusted generation context from the local course manifest."""

    unit = _find_unit(manifest, unit_id)
    chunk_source_ids = {str(chunk.get("source_id")) for chunk in chunks}
    material_set_ids = {
        chunk.get("material_set_id")
        for chunk in chunks
        if isinstance(chunk.get("material_set_id"), str)
    }
    material_set_id = (
        next(iter(material_set_ids)) if len(material_set_ids) == 1 else None
    )
    return GenerationRequest(
        course_id=manifest.get("course_id"),
        course_version=manifest.get("course_version"),
        unit_id=unit_id,
        included_sources=_source_metadata(unit, chunk_source_ids),
        material_set_id=material_set_id,
        language=language,
        target_minutes=target_minutes,
    )


async def generate_outputs(
    *,
    model: StructuredModel,
    chunks_path: Path,
    manifest_path: Path,
    unit_id: str,
    output_dir: Path,
    language: str = "zh-CN",
    target_minutes: int = 180,
    max_repairs: int = 1,
    resume: bool = False,
    from_stage: GenerationStage | str | None = None,
    request_timeout: float = 600.0,
    stage_max_tokens: int = 65_536,
) -> GenerationResult:
    """Run generation and write artifacts without exposing provider secrets."""

    chunks = read_jsonl(chunks_path)
    manifest = load_yaml(manifest_path)
    request = build_request(
        manifest,
        chunks,
        unit_id=unit_id,
        language=language,
        target_minutes=target_minutes,
    )
    generator = StudyKitGenerator(
        model,
        max_repairs=max_repairs,
        stage_timeout_seconds=request_timeout,
        stage_max_tokens=stage_max_tokens,
    )
    manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    result = await generator.generate(
        request,
        chunks,
        output_dir=output_dir,
        resume=resume,
        from_stage=from_stage,
        manifest_hash=manifest_hash,
    )

    report = result.validation_report()
    report["inputs"] = {
        "chunks": str(chunks_path),
        "manifest": str(manifest_path),
        "unit_id": unit_id,
    }
    report["artifacts"] = {}

    if result.succeeded and result.studykit is not None:
        yaml_path = output_dir / "studykit.yaml"
        markdown_path = output_dir / "studykit.md"
        yaml_path.write_text(
            yaml.safe_dump(
                result.studykit,
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        markdown_path.write_text(
            render_studykit_markdown(result.studykit),
            encoding="utf-8",
        )
        report["artifacts"] = {
            "studykit_yaml": str(yaml_path),
            "learner_markdown": str(markdown_path),
        }

    report_path = output_dir / "validation.json"
    report["artifacts"]["validation_report"] = str(report_path)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a draft StudyKit from local SourceChunk JSONL."
    )
    parser.add_argument("--chunks", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--unit-id", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--language", default="zh-CN")
    parser.add_argument("--target-minutes", type=int, default=180)
    parser.add_argument(
        "--max-repairs",
        type=int,
        choices=(0, 1),
        default=1,
        help="Targeted repairs per semantic stage (at most one).",
    )
    recovery = parser.add_mutually_exclusive_group()
    recovery.add_argument(
        "--resume",
        action="store_true",
        help="Reuse validated completed stages and continue at the first failure.",
    )
    recovery.add_argument(
        "--from-stage",
        choices=[stage.value for stage in GenerationStage],
        help="Rerun this stage and all downstream stages.",
    )
    parser.add_argument(
        "--request-timeout",
        type=float,
        default=600.0,
        help="Seconds allowed for each long non-streaming model response.",
    )
    parser.add_argument(
        "--stage-max-tokens",
        type=int,
        default=65_536,
        help="Maximum output tokens for each semantic stage.",
    )
    parser.add_argument(
        "--network-retries",
        type=int,
        default=0,
        help="Transport retries; keep at zero to avoid duplicate long requests.",
    )
    parser.add_argument(
        "--invalid-json-retries",
        type=int,
        default=2,
        help=(
            "Retries for completed responses whose message.content is not "
            "strict JSON; retries keep the same thinking mode."
        ),
    )
    parser.add_argument(
        "--length-retries",
        type=int,
        default=1,
        help=(
            "Retries for finish_reason=length; retries keep thinking and the "
            "configured token ceiling."
        ),
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    try:
        model = DeepSeekModel.from_env()
        model.timeout_seconds = args.request_timeout
        model.max_retries = args.network_retries
        model.max_invalid_json_retries = args.invalid_json_retries
        model.max_length_retries = args.length_retries
        result = asyncio.run(
            generate_outputs(
                model=model,
                chunks_path=args.chunks,
                manifest_path=args.manifest,
                unit_id=args.unit_id,
                output_dir=args.output_dir,
                language=args.language,
                target_minutes=args.target_minutes,
                max_repairs=args.max_repairs,
                resume=args.resume,
                from_stage=args.from_stage,
                request_timeout=args.request_timeout,
                stage_max_tokens=args.stage_max_tokens,
            )
        )
    except (ModelError, OSError, ValueError, yaml.YAMLError) as exc:
        print(f"generation setup failed: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    report = args.output_dir / "validation.json"
    if not result.succeeded:
        print(
            f"generation failed with status={result.status.value}; see {report}",
            file=sys.stderr,
        )
        raise SystemExit(1)
    print(f"generated StudyKit artifacts in {args.output_dir}")


if __name__ == "__main__":
    main()
