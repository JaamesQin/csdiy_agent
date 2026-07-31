from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("api_key", [None, "too-short"])
def test_service_refuses_to_start_without_strong_key(api_key: str | None) -> None:
    env = os.environ.copy()
    if api_key is None:
        env.pop("COURSEPILOT_API_KEY", None)
    else:
        env["COURSEPILOT_API_KEY"] = api_key

    result = subprocess.run(
        [sys.executable, "-c", "import app.main"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert result.returncode != 0
    assert "COURSEPILOT_API_KEY" in result.stderr
    if api_key is not None:
        assert api_key not in result.stderr
