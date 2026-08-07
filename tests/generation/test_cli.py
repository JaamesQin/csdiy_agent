from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from app.generation.result import GenerationStatus
from scripts.generate_studykit import generate_outputs
from tests.generation.helpers import (
    ROOT,
    evidence_plan,
    learning_content,
    model_response,
    practice_flow,
    quality_audit,
    source_chunks,
)
from tests.generation.test_generator import FakeModel


async def test_cli_workflow_writes_three_artifacts(tmp_path: Path) -> None:
    chunks_path = tmp_path / "chunks.jsonl"
    chunks_path.write_text(
        "".join(
            json.dumps(chunk, ensure_ascii=False) + "\n"
            for chunk in source_chunks()
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "generated"

    result = await generate_outputs(
        model=FakeModel(
            [
                model_response(evidence_plan()),
                model_response(learning_content()),
                model_response(practice_flow()),
                model_response(quality_audit()),
            ]
        ),
        chunks_path=chunks_path,
        manifest_path=(
            ROOT / "data/manifests/mit-6.7960-fall-2024.yaml"
        ),
        unit_id="lecture-02",
        output_dir=output_dir,
    )

    assert result.status is GenerationStatus.SUCCEEDED
    assert (output_dir / "studykit.yaml").is_file()
    assert (output_dir / "studykit.md").is_file()
    assert (output_dir / "01-evidence-plan.json").is_file()
    assert (output_dir / "02-learning-content.json").is_file()
    assert (output_dir / "03-practice-flow.json").is_file()
    assert (output_dir / "04-quality-audit.json").is_file()
    assert (output_dir / "05-studykit.json").is_file()
    assert (output_dir / "run.json").is_file()
    report = json.loads(
        (output_dir / "validation.json").read_text(encoding="utf-8")
    )
    assert report["status"] == "succeeded"
    assert report["artifacts"]["studykit_yaml"].endswith("studykit.yaml")


def test_cli_reports_missing_llm_key_without_traceback(tmp_path: Path) -> None:
    env = os.environ.copy()
    env.pop("DEEPSEEK_API_KEY", None)
    env.pop("COURSEPILOT_LLM_API_KEY", None)

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/generate_studykit.py"),
            "--chunks",
            str(tmp_path / "missing.jsonl"),
            "--manifest",
            str(tmp_path / "missing.yaml"),
            "--unit-id",
            "lecture-02",
            "--output-dir",
            str(tmp_path / "output"),
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "DEEPSEEK_API_KEY is required" in result.stderr
    assert "Traceback" not in result.stderr
