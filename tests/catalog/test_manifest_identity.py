from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import pytest
import yaml


MANIFEST_ROOT = Path(__file__).parents[2] / "data" / "manifests"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TERM_VERSION = re.compile(r"^(spring|summer|fall|winter|lent)-\d{4}$|^\d{4}-\d{2}$")


def _canonical_identity(manifest: dict[str, Any]) -> str:
    """Return the offering identity used to reject duplicate manifest records."""

    return str(manifest.get("course_id") or "").strip().casefold()


def _inventory_path(manifest: dict[str, Any], root: Path) -> Path:
    snapshot = Path(str(manifest.get("local_snapshot") or ""))
    return root / snapshot / "source-inventory.json"


def _manifest_errors(
    manifest: dict[str, Any], *, root: Path, check_unit_sources: bool = True
) -> list[str]:
    errors: list[str] = []
    required = (
        "course_id",
        "primary_course_number",
        "institution",
        "term",
        "year",
        "course_version",
    )
    for field in required:
        if not str(manifest.get(field) or "").strip():
            errors.append(f"missing {field}")

    course_id = str(manifest.get("course_id") or "")
    course_version = str(manifest.get("course_version") or "")
    if not _TERM_VERSION.fullmatch(course_version):
        errors.append("course_version must be a term-version")
    if course_id and course_version and not course_id.endswith(f"-{course_version}"):
        errors.append("course_id must end with course_version")
    if re.fullmatch(r"\d{4}-\d{2}", course_version):
        # Some institutions identify a completed offering by academic year
        # rather than a four-season term (for example Cambridge Lent 2025-26).
        # Preserve that identity instead of coercing it into a false season.
        start_year, end_year = course_version.split("-")
        if str(manifest.get("year") or "") not in {start_year, str(int(start_year) + 1)}:
            errors.append("year must agree with academic-year course_version")
    else:
        if str(manifest.get("term") or "").casefold() != course_version.split("-", 1)[0]:
            errors.append("term must agree with course_version")
        if str(manifest.get("year") or "") != course_version.rsplit("-", 1)[-1]:
            errors.append("year must agree with course_version")

    declared_hash = manifest.get("inventory_sha256")
    inventory = _inventory_path(manifest, root)
    if declared_hash is not None:
        if not isinstance(declared_hash, str) or not _SHA256.fullmatch(declared_hash):
            errors.append("inventory_sha256 must be a lowercase SHA-256")
        elif inventory.is_file() and hashlib.sha256(inventory.read_bytes()).hexdigest() != declared_hash:
            errors.append("inventory_sha256 does not match source-inventory.json")

    if not check_unit_sources:
        return errors

    unit_ids: set[str] = set()
    for unit in manifest.get("units") or []:
        unit_id = str(unit.get("unit_id") or "").strip()
        if not unit_id or unit_id in unit_ids:
            errors.append(f"duplicate or missing unit_id: {unit_id!r}")
        unit_ids.add(unit_id)
        sources = unit.get("sources") or []
        if len(sources) != 1:
            errors.append(f"{unit_id}: expected exactly one prepared source")
            continue
        source = sources[0]
        source_id = str(source.get("source_id") or "")
        material_set_id = str(source.get("material_set_id") or "")
        if not source_id or unit_id not in source_id:
            errors.append(f"{unit_id}: source_id must name the unit")
        if not material_set_id or not material_set_id.endswith(unit_id):
            errors.append(f"{unit_id}: material_set_id must end with unit_id")

    return errors


def _assert_no_duplicate_canonical_identities(manifests: list[dict[str, Any]]) -> None:
    seen: dict[str, int] = {}
    for manifest in manifests:
        identity = _canonical_identity(manifest)
        if identity:
            seen[identity] = seen.get(identity, 0) + 1
    duplicates = sorted(identity for identity, count in seen.items() if count > 1)
    if duplicates:
        raise AssertionError(f"duplicate canonical manifest identities: {duplicates}")


@pytest.fixture
def manifest_fixture(tmp_path: Path) -> tuple[dict[str, Any], Path]:
    inventory = tmp_path / "data" / "raw" / "demo" / "spring-2026" / "source-inventory.json"
    inventory.parent.mkdir(parents=True)
    inventory.write_bytes(b'{"artifacts": []}\n')
    manifest = {
        "course_id": "demo-cs1-spring-2026",
        "primary_course_number": "CS 1",
        "institution": "Demo University",
        "term": "Spring",
        "year": 2026,
        "course_version": "spring-2026",
        "local_snapshot": "data/raw/demo/spring-2026/",
        "inventory_sha256": hashlib.sha256(inventory.read_bytes()).hexdigest(),
        "units": [
            {
                "unit_id": "lecture-01",
                "sources": [
                    {
                        "source_id": "demo-cs1-spring-2026-lecture-01-material",
                        "material_set_id": "demo-cs1-spring-2026-lecture-01",
                    }
                ],
            }
        ],
    }
    return manifest, tmp_path


def test_repository_manifests_have_structural_course_version_identity() -> None:
    manifests = [yaml.safe_load(path.read_text(encoding="utf-8")) or {} for path in sorted(MANIFEST_ROOT.glob("*.yaml"))]
    assert manifests
    for manifest in manifests:
        assert _manifest_errors(manifest, root=MANIFEST_ROOT.parents[1], check_unit_sources=False) == [], manifest.get("course_id")


def test_fixture_covers_identity_fields_inventory_hash_and_unit_naming(manifest_fixture) -> None:
    manifest, root = manifest_fixture
    assert _manifest_errors(manifest, root=root) == []


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (lambda m: m.update({"course_id": "demo-cs1-fall-2026"}), "course_id must end"),
        (lambda m: m["units"][0]["sources"].append({"source_id": "extra-lecture-01", "material_set_id": "extra-lecture-01"}), "exactly one"),
        (lambda m: m["units"][0]["sources"][0].update({"source_id": "demo-source"}), "source_id"),
        (lambda m: m.update({"inventory_sha256": "not-a-hash"}), "inventory_sha256"),
    ],
)
def test_manifest_identity_worker_rejects_structural_mutations(manifest_fixture, mutation, expected: str) -> None:
    manifest, root = manifest_fixture
    mutation(manifest)
    assert any(expected in error for error in _manifest_errors(manifest, root=root))


def test_duplicate_canonical_identity_is_rejected(manifest_fixture) -> None:
    manifest, root = manifest_fixture
    duplicate = dict(manifest)
    assert _manifest_errors(duplicate, root=root) == []
    with pytest.raises(AssertionError, match="duplicate canonical"):
        _assert_no_duplicate_canonical_identities([manifest, duplicate])
