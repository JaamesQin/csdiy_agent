from __future__ import annotations

import json
import importlib.util
from pathlib import Path
import subprocess
import sys
import zipfile


SKILL = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([PYTHON, *args], text=True, capture_output=True, check=False)


def test_text_ingestion_preserves_every_source(tmp_path: Path) -> None:
    first = tmp_path / "lecture.md"
    second = tmp_path / "notes.txt"
    first.write_text("# Gradient descent\nUpdate: x = x - alpha * g", encoding="utf-8")
    second.write_text("Independent notes with enough useful source text for learning.", encoding="utf-8")
    output = tmp_path / "out"
    result = _run(
        str(SKILL / "scripts/ingest_materials.py"),
        "--material", str(first), "--material", str(second),
        "--output-dir", str(output), "--scope", "public",
    )
    assert result.returncode == 0, result.stderr
    report = json.loads((output / "ingestion-report.json").read_text())
    assert report["status"] == "succeeded"
    assert report["source_count"] == report["parsed_source_count"] == 2
    assert len((output / "chunks.jsonl").read_text().splitlines()) == 2


def test_ooxml_slide_ingestion(tmp_path: Path) -> None:
    pptx = tmp_path / "slides.pptx"
    with zipfile.ZipFile(pptx, "w") as archive:
        archive.writestr(
            "ppt/slides/slide1.xml",
            '<p:sld xmlns:p="p" xmlns:a="a"><a:t>First slide formula x equals y</a:t></p:sld>',
        )
    output = tmp_path / "out"
    result = _run(str(SKILL / "scripts/ingest_materials.py"), "--material", str(pptx), "--output-dir", str(output))
    assert result.returncode == 0, result.stderr
    chunk = json.loads((output / "chunks.jsonl").read_text().strip())
    assert chunk["anchor"] == {"type": "slide", "value": 1}
    assert "First slide" in chunk["content"]


def test_image_uses_host_vision_fallback(tmp_path: Path) -> None:
    image = tmp_path / "formula.png"
    image.write_bytes(b"not decoded by deterministic ingestion")
    output = tmp_path / "out"
    result = _run(str(SKILL / "scripts/ingest_materials.py"), "--material", str(image), "--output-dir", str(output))
    assert result.returncode == 0, result.stderr
    formulas = json.loads((output / "formula-candidates.json").read_text())
    assert formulas[0]["status"] == "needs_host_vision"
    assert formulas[0]["page_image"] == str(image.resolve())


def test_text_ingestion_replaces_unpaired_surrogates(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location("skill_ingest", SKILL / "scripts/ingest_materials.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    normalized = module._normalize_text("Lecture text: \ud83d and valid context.")
    assert normalized == "Lecture text: � and valid context."


def test_validator_accepts_generic_anchor(tmp_path: Path) -> None:
    digest = "a" * 64
    chunk = {
        "chunk_id": "notes-heading-intro", "material_set_id": "set-1", "scope": "public",
        "owner_id": None, "course_id": None, "course_version": None, "unit_id": "unit-1",
        "source_id": "notes-a", "anchor": {"type": "heading", "value": "Intro"},
        "heading": "Intro", "content": "A supported concept.", "content_type": "text",
        "parser_version": "test", "parse_warnings": [],
    }
    chunks = tmp_path / "chunks.jsonl"
    chunks.write_text(json.dumps(chunk) + "\n")
    citation = {"source_id": "notes-a", "anchor": {"type": "heading", "value": "Intro"}}
    kit = {
        "studykit_version": "0.1", "status": "draft", "course_id": None, "course_version": None,
        "unit_id": "unit-1", "title": "Intro", "language": "zh-CN",
        "scope": {"included_sources": [{"source_id": "notes-a", "title": "Notes", "type": "text", "sha256": digest}], "citation_anchor_types": ["heading"]},
        "learning_objectives": [{"id": "obj-1", "objective": "Understand it"}], "prerequisites": [],
        "outline": [{"order": 1, "topic": "Intro", "anchors": [citation], "purpose": "Learn"}],
        "core_concepts": [{"id": "c-1", "term": "Concept", "claim_type": "source", "explanation": "Supported", "citations": [citation]}],
        "glossary": [], "learning_sequence": [{"step": 1, "activity": "Read", "duration_minutes": 10, "citations": [citation]}],
        "practice": [{"id": "p-1", "level": "recall", "question": "Explain", "hint": "Read", "deliverable": "Text", "expected_evidence": ["Meaning"], "evaluation": {"full_credit": "Correct"}, "citations": [citation]}],
        "citations": [{**citation, "citation_id": "cite-1", "supports": "Concept"}],
        "review": {"generator_review_status": "passed", "audit_findings": []}, "limitations": [],
    }
    kit_path = tmp_path / "kit.json"
    kit_path.write_text(json.dumps(kit))
    result = _run(str(SKILL / "scripts/validate_artifacts.py"), "--chunks", str(chunks), "--studykit", str(kit_path))
    assert result.returncode == 0, result.stdout + result.stderr


def test_validator_rejects_missing_anchor(tmp_path: Path) -> None:
    chunks = tmp_path / "chunks.jsonl"
    chunks.write_text("")
    kit = tmp_path / "kit.json"
    kit.write_text("{}")
    result = _run(str(SKILL / "scripts/validate_artifacts.py"), "--chunks", str(chunks), "--studykit", str(kit))
    assert result.returncode == 1
    assert '"status": "failed"' in result.stdout


def test_submission_zip_has_skill_at_root(tmp_path: Path) -> None:
    archive = tmp_path / "studykit-generator.zip"
    result = _run(str(SKILL / "scripts/package_skill.py"), "--output", str(archive))
    assert result.returncode == 0, result.stderr
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
    assert "SKILL.md" in names
    assert all(not name.startswith("studykit-generator/") for name in names)
    assert not any("__pycache__" in name for name in names)
    assert "references/default-mode-decision.json" in names


def test_release_prompt_documents_standard_representation_checks() -> None:
    skill_text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    modes_text = (SKILL / "references/quality-modes.md").read_text(encoding="utf-8")
    agent_text = (SKILL / "agents/openai.yaml").read_text(encoding="utf-8")
    decision = json.loads((SKILL / "references/default-mode-decision.json").read_text())
    assert decision["default_quality_mode"] == "standard"
    assert decision["release_status"] == "approved"
    for marker in ("formula_unresolved", "hidden", "LaTeX", "indices"):
        assert marker.lower() in (skill_text + modes_text + agent_text).lower()


def test_finalize_renders_valid_candidate(tmp_path: Path) -> None:
    digest = "b" * 64
    citation = {"source_id": "notes-b", "anchor": {"type": "page", "value": 1}}
    chunk = {
        "chunk_id": "notes-b-page-1", "material_set_id": "set-1", "scope": "public",
        "owner_id": None, "course_id": "course", "course_version": "v1", "unit_id": "unit-1",
        "source_id": "notes-b", "anchor": {"type": "page", "value": 1}, "heading": "One",
        "content": "Supported", "content_type": "text", "parser_version": "test", "parse_warnings": [],
    }
    chunks = tmp_path / "chunks.jsonl"
    chunks.write_text(json.dumps(chunk) + "\n")
    kit = {
        "studykit_version": "0.1", "status": "draft", "course_id": "course", "course_version": "v1",
        "unit_id": "unit-1", "title": "Unit", "language": "zh-CN",
        "scope": {"included_sources": [{"source_id": "notes-b", "title": "Notes", "type": "pdf", "sha256": digest}], "citation_anchor_types": ["page"]},
        "learning_objectives": [{"id": "o1", "objective": "Learn"}], "prerequisites": [],
        "outline": [{"order": 1, "topic": "One", "anchors": [citation], "purpose": "Learn"}],
        "core_concepts": [{"id": "c1", "term": "Term", "claim_type": "source", "explanation": "Supported", "citations": [citation]}],
        "glossary": [], "learning_sequence": [{"step": 1, "activity": "Read", "duration_minutes": 5, "citations": [citation]}],
        "practice": [{"id": "p1", "level": "recall", "question": "What?", "hint": "Read", "deliverable": "Text", "expected_evidence": ["Term"], "evaluation": {}, "citations": [citation]}],
        "citations": [{**citation, "citation_id": "ref1", "supports": "Term"}],
        "review": {"generator_review_status": "passed", "audit_findings": []}, "limitations": [],
    }
    candidate = tmp_path / "candidate.json"
    candidate.write_text(json.dumps(kit))
    output = tmp_path / "final"
    result = _run(str(SKILL / "scripts/finalize_studykit.py"), "--chunks", str(chunks), "--studykit", str(candidate), "--output-dir", str(output))
    assert result.returncode == 0, result.stdout + result.stderr
    assert (output / "05-studykit.json").is_file()
    assert (output / "studykit.yaml").is_file()
    assert "# Unit" in (output / "studykit.md").read_text()
