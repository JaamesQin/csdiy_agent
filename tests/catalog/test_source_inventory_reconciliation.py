from __future__ import annotations

import hashlib
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from jsonschema import ValidationError, validate
from pypdf import PdfReader, PdfWriter


INVENTORY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "schema_version",
        "course_id",
        "selected_term",
        "official_homepage",
        "artifacts",
        "failures",
        "source_gaps",
        "excluded",
        "downloaded_count",
        "failed_count",
    ],
    "properties": {
        "schema_version": {"const": "source-inventory-v0.1"},
        "course_id": {"type": "string", "minLength": 1},
        "selected_term": {"type": "string", "minLength": 1},
        "official_homepage": {"type": "string", "format": "uri"},
        "artifacts": {"type": "array", "items": {"$ref": "#/$defs/artifact"}},
        "schedule": {"type": "array", "items": {"$ref": "#/$defs/schedule"}},
        "failures": {"type": "array", "items": {"type": "object"}},
        "source_gaps": {"type": "array", "items": {"type": "object"}},
        "excluded": {"type": "array", "items": {"type": "string"}},
        "downloaded_count": {"type": "integer", "minimum": 0},
        "failed_count": {"type": "integer", "minimum": 0},
    },
    "$defs": {
        "artifact": {
            "type": "object",
            "required": [
                "kind",
                "unit",
                "title",
                "requested_url",
                "final_url",
                "local_path",
                "media_type",
                "bytes",
                "sha256",
                "access_status",
                "license_status",
                "redistribution_allowed",
                "resource_vintage",
            ],
            "properties": {
                "requested_url": {"type": "string", "format": "uri"},
                "final_url": {"type": "string", "format": "uri"},
                "media_type": {"type": "string", "pattern": r"^[^/]+/[^/]+$"},
                "bytes": {"type": "integer", "minimum": 1},
                "sha256": {"type": "string", "pattern": r"^[0-9a-f]{64}$"},
                "redistribution_allowed": {"type": "boolean"},
            },
        },
        "schedule": {
            "type": "object",
            "required": ["unit_id", "order", "date", "official_title", "resource_vintage"],
            "properties": {
                "unit_id": {"type": "string", "pattern": r"^lecture-[0-9]{2}$"},
                "order": {"type": "integer", "minimum": 1},
                "date": {"type": "string"},
                "official_title": {"type": "string", "minLength": 1},
                "resource_vintage": {"type": "string", "minLength": 1},
            },
        },
    },
}


@dataclass(frozen=True)
class ResponseFixture:
    final_url: str
    media_type: str
    body: bytes
    encoding: str | None = None
    pdf_readable: bool | None = None
    page_count: int | None = None


class OfflineSourceInventoryWorker:
    """A local-only source worker: an unknown URL is an accidental network call."""

    def __init__(self, responses: dict[str, ResponseFixture], root: Path) -> None:
        self.responses = responses
        self.root = root
        self.requested_urls: list[str] = []

    def fetch(self, requested_url: str, *, local_path: str, kind: str, unit: str | None, title: str) -> dict[str, Any]:
        self.requested_urls.append(requested_url)
        if requested_url not in self.responses:
            raise AssertionError(f"unexpected network/provider access: {requested_url}")
        response = self.responses[requested_url]
        path = self.root / local_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(response.body)
        record: dict[str, Any] = {
            "kind": kind,
            "unit": unit,
            "title": title,
            "requested_url": requested_url,
            "final_url": response.final_url,
            "local_path": local_path,
            "media_type": response.media_type,
            "bytes": len(response.body),
            "sha256": hashlib.sha256(response.body).hexdigest(),
            "access_status": "downloaded",
            "license_status": "unknown",
            "redistribution_allowed": False,
            "resource_vintage": "spring-2026",
        }
        if response.media_type == "application/pdf":
            record.update(
                {
                    "pdf_magic": response.body.startswith(b"%PDF-"),
                    "pdf_readable": response.pdf_readable,
                    "page_count": response.page_count,
                }
            )
        elif response.media_type.startswith("text/"):
            record["encoding"] = response.encoding
        return record


def _pdf_bytes(page_count: int = 2) -> bytes:
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=72, height=72)
    output = __import__("io").BytesIO()
    writer.write(output)
    return output.getvalue()


@pytest.fixture
def inventory_fixture(tmp_path: Path) -> tuple[dict[str, Any], OfflineSourceInventoryWorker]:
    homepage = "https://fixture.test/course"
    pdf_url = "https://fixture.test/course/lecture-01"
    final_pdf_url = "https://cdn.fixture.test/lecture-01.pdf"
    pdf = _pdf_bytes()
    html = "<html><meta charset='gb18030'><title>课程日程</title></html>".encode("gb18030")
    worker = OfflineSourceInventoryWorker(
        {
            homepage: ResponseFixture(homepage, "text/html", html, encoding="gb18030"),
            pdf_url: ResponseFixture(
                final_pdf_url,
                "application/pdf",
                pdf,
                pdf_readable=True,
                page_count=len(PdfReader(__import__("io").BytesIO(pdf)).pages),
            ),
        },
        tmp_path,
    )
    artifacts = [
        worker.fetch(homepage, local_path="site/index.html", kind="identity", unit=None, title="Schedule"),
        worker.fetch(pdf_url, local_path="prepared/lecture-01.pdf", kind="lecture", unit="lecture-01", title="Intro"),
    ]
    artifacts[0].update({"license_status": "unknown", "redistribution_allowed": False})
    artifacts[1].update({"license_status": "CC BY-NC-SA 4.0", "redistribution_allowed": True})
    inventory = {
        "schema_version": "source-inventory-v0.1",
        "course_id": "fixture-course-spring-2026",
        "selected_term": "spring-2026",
        "official_homepage": homepage,
        "artifacts": artifacts,
        "schedule": [
            {"unit_id": "lecture-01", "order": 1, "date": "2026-01-20", "official_title": "Intro", "resource_vintage": "spring-2026"},
            {"unit_id": "lecture-02", "order": 2, "date": "2026-01-22", "official_title": "Missing notes", "resource_vintage": "spring-2026"},
        ],
        "failures": [{"requested_url": "https://fixture.test/course/lecture-02", "code": "404", "final_url": None}],
        "source_gaps": [{"unit_id": "lecture-02", "code": "notes_absent", "action": "recorded source gap"}],
        "excluded": ["video binaries", "homework", "solutions"],
        "downloaded_count": 2,
        "failed_count": 1,
    }
    return inventory, worker


def test_inventory_schema_reconciles_urls_metadata_and_denominators(inventory_fixture) -> None:
    inventory, worker = inventory_fixture
    validate(inventory, INVENTORY_SCHEMA)

    pdf = next(item for item in inventory["artifacts"] if item["media_type"] == "application/pdf")
    assert (pdf["requested_url"], pdf["final_url"]) == (
        "https://fixture.test/course/lecture-01",
        "https://cdn.fixture.test/lecture-01.pdf",
    )
    assert inventory["downloaded_count"] == len(inventory["artifacts"])
    assert inventory["failed_count"] == len(inventory["failures"])
    assert worker.requested_urls == ["https://fixture.test/course", "https://fixture.test/course/lecture-01"]


def test_pdf_fixture_records_magic_readability_pages_bytes_and_sha(inventory_fixture) -> None:
    inventory, _ = inventory_fixture
    pdf = next(item for item in inventory["artifacts"] if item["media_type"] == "application/pdf")
    assert pdf["pdf_magic"] is True
    assert pdf["pdf_readable"] is True
    assert pdf["page_count"] == 2
    assert pdf["bytes"] > 0
    assert len(pdf["sha256"]) == 64


def test_html_fixture_preserves_declared_encoding_and_schedule_unit_mapping(inventory_fixture) -> None:
    inventory, _ = inventory_fixture
    html = next(item for item in inventory["artifacts"] if item["media_type"] == "text/html")
    assert html["encoding"] == "gb18030"
    assert {row["unit_id"] for row in inventory["schedule"]} == {"lecture-01", "lecture-02"}
    assert [row["unit_id"] for row in sorted(inventory["schedule"], key=lambda row: row["order"])] == ["lecture-01", "lecture-02"]


def test_failures_exclusions_and_gaps_remain_explicit(inventory_fixture) -> None:
    inventory, _ = inventory_fixture
    assert inventory["failures"][0]["code"] == "404"
    assert inventory["failures"][0]["requested_url"].startswith("https://")
    assert "solutions" in inventory["excluded"]
    assert inventory["source_gaps"] == [{"unit_id": "lecture-02", "code": "notes_absent", "action": "recorded source gap"}]


def test_pdf_login_html_cannot_satisfy_pdf_integrity_contract(tmp_path: Path) -> None:
    worker = OfflineSourceInventoryWorker(
        {"https://fixture.test/bad.pdf": ResponseFixture("https://fixture.test/login", "application/pdf", b"<html>login</html>", pdf_readable=False, page_count=None)},
        tmp_path,
    )
    record = worker.fetch("https://fixture.test/bad.pdf", local_path="bad.pdf", kind="lecture", unit="lecture-01", title="Bad")
    assert record["pdf_magic"] is False
    assert record["pdf_readable"] is False
    assert record["page_count"] is None

    invalid = {"schema_version": "source-inventory-v0.1", "course_id": "x", "selected_term": "y", "official_homepage": "https://fixture.test", "artifacts": [record], "failures": [], "source_gaps": [], "excluded": [], "downloaded_count": 1, "failed_count": 0}
    strict_schema = deepcopy(INVENTORY_SCHEMA)
    strict_schema["$defs"]["artifact"]["required"].append("pdf_magic")
    strict_schema["$defs"]["artifact"]["properties"]["pdf_magic"] = {"const": True}
    with pytest.raises(ValidationError):
        validate(invalid, strict_schema)


def test_worker_rejects_unstubbed_network_or_provider_access(tmp_path: Path) -> None:
    worker = OfflineSourceInventoryWorker({}, tmp_path)
    with pytest.raises(AssertionError, match="unexpected network/provider access"):
        worker.fetch("https://not-in-fixture.test/source", local_path="x", kind="lecture", unit="lecture-01", title="x")
