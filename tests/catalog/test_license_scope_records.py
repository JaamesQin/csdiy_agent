"""Offline license and redistribution records for catalog manifests.

These tests deliberately use manifest-shaped dictionaries instead of URLs or
provider clients.  The worker is a small test-only projection of the source
inventory contract: uncertain artifact scope is never upgraded by a course
page license, and assessed material remains metadata-only.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pytest


def _source_record(source: dict[str, Any], *, origin: str, unit_id: str | None = None) -> dict[str, Any]:
    """Project one local manifest source into an offline catalog record."""

    license_status = source.get("license_status") or "unknown"
    artifact_scope_unknown = license_status == "unknown_artifact_scope"
    redistribution_allowed = source.get("redistribution_allowed") is True
    if license_status in {"unknown", "unknown_artifact_scope"}:
        redistribution_allowed = False

    return {
        "source_id": source["source_id"],
        "origin": origin,
        "unit_id": unit_id,
        "license_status": license_status,
        "redistribution_allowed": redistribution_allowed,
        "artifact_scope": "unknown" if artifact_scope_unknown else "declared",
        "license": source.get("license"),
        "license_evidence": source.get("license_evidence"),
        "processing_status": source.get("processing_status"),
        "index_allowed": source.get("index_allowed", False),
        "assessed": source.get("assessed", False),
        "metadata_only": source.get("processing_status") == "metadata_only",
    }


def offline_license_scope_records(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Build local license records without resolving or downloading any URL."""

    records: list[dict[str, Any]] = []
    for source in manifest.get("shared_sources", []):
        records.append(_source_record(source, origin="shared"))
    for unit in manifest.get("units", []):
        for source in unit.get("sources", []):
            records.append(_source_record(source, origin="unit", unit_id=unit["unit_id"]))

    for item in manifest.get("excluded_assessed_materials", []):
        records.append(
            _source_record(
                {
                    "source_id": item["source_id"],
                    "license_status": item.get("license_status", "unknown"),
                    "redistribution_allowed": False,
                    "processing_status": "metadata_only",
                    "index_allowed": False,
                    "assessed": True,
                    "license_evidence": item.get("license_evidence"),
                },
                origin="excluded_assessed_material",
                unit_id=item.get("unit_id"),
            )
        )
    return records


@pytest.fixture
def catalog_manifest_fixture() -> dict[str, Any]:
    """A complete local inventory fixture covering each license boundary."""

    return {
        "course_id": "fixture-course-spring-2026",
        "source_gap_units": [{"unit_id": "lecture-03", "reason": "no published source"}],
        "shared_sources": [
            {
                "source_id": "course-home",
                "type": "html",
                "license_status": "unknown",
                "redistribution_allowed": False,
                "processing_status": "metadata_only",
                "index_allowed": False,
            },
            {
                "source_id": "course-policy",
                "type": "html",
                "license_status": "confirmed",
                "license": "https://creativecommons.org/licenses/by/4.0/",
                "license_evidence": "official course policy, section 2",
                "redistribution_allowed": True,
                "processing_status": "metadata_only",
                "index_allowed": False,
            },
        ],
        "units": [
            {
                "unit_id": "lecture-01",
                "sources": [
                    {
                        "source_id": "lecture-01-slides",
                        "type": "pdf",
                        "license_status": "unknown_artifact_scope",
                        "redistribution_allowed": False,
                        "processing_status": "chunks_ready",
                        "index_allowed": True,
                    }
                ],
            },
            {
                "unit_id": "lecture-02",
                "sources": [
                    {
                        "source_id": "lecture-02-slides",
                        "type": "pdf",
                        "license_status": "confirmed",
                        "license": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
                        "license_evidence": "official source page footer",
                        "redistribution_allowed": True,
                        "processing_status": "chunks_ready",
                        "index_allowed": True,
                    }
                ],
            },
        ],
        "excluded_assessed_materials": [
            {
                "source_id": "homework-01",
                "unit_id": "lecture-02",
                "license_status": "unknown",
                "license_evidence": "assessment boundary in source inventory",
            }
        ],
    }


def _by_id(records: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {record["source_id"]: record for record in records}


def test_unknown_license_is_non_redistributable(catalog_manifest_fixture: dict[str, Any]) -> None:
    record = _by_id(offline_license_scope_records(catalog_manifest_fixture))["course-home"]

    assert record["license_status"] == "unknown"
    assert record["redistribution_allowed"] is False
    assert record["license"] is None


def test_unknown_artifact_scope_is_not_cured_by_a_course_license(catalog_manifest_fixture: dict[str, Any]) -> None:
    record = _by_id(offline_license_scope_records(catalog_manifest_fixture))["lecture-01-slides"]

    assert record["license_status"] == "unknown_artifact_scope"
    assert record["artifact_scope"] == "unknown"
    assert record["redistribution_allowed"] is False


def test_explicit_license_evidence_preserves_declared_redistribution(catalog_manifest_fixture: dict[str, Any]) -> None:
    records = _by_id(offline_license_scope_records(catalog_manifest_fixture))

    assert records["lecture-02-slides"]["redistribution_allowed"] is True
    assert records["lecture-02-slides"]["license"] == "https://creativecommons.org/licenses/by-nc-sa/4.0/"
    assert records["lecture-02-slides"]["license_evidence"] == "official source page footer"


def test_metadata_only_assessed_material_is_excluded_from_content_and_redistribution(
    catalog_manifest_fixture: dict[str, Any],
) -> None:
    record = _by_id(offline_license_scope_records(catalog_manifest_fixture))["homework-01"]

    assert record["origin"] == "excluded_assessed_material"
    assert record["assessed"] is True
    assert record["metadata_only"] is True
    assert record["index_allowed"] is False
    assert record["redistribution_allowed"] is False


def test_source_gaps_remain_explicit_and_do_not_become_license_records(catalog_manifest_fixture: dict[str, Any]) -> None:
    records = offline_license_scope_records(catalog_manifest_fixture)

    assert catalog_manifest_fixture["source_gap_units"] == [{"unit_id": "lecture-03", "reason": "no published source"}]
    assert "lecture-03" not in {record["unit_id"] for record in records}
    assert len(records) == 5
