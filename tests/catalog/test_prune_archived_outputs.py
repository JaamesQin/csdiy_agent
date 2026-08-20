from __future__ import annotations

from pathlib import Path

import pytest

from scripts.prune_archived_studykit_outputs import prune


def test_prune_refuses_any_root_other_than_repository_outputs(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="non-canonical outputs root"):
        prune(
            outputs_root=tmp_path,
            database=tmp_path / "missing.sqlite3",
            execute=False,
        )
