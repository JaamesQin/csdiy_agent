from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts.audit_csdiy_registry import reconcile_target
from scripts.discover_csdiy_courses import candidate_offerings, discover, merge_progress


FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "csdiy_catalog"


@dataclass(frozen=True)
class FakeResponse:
    url: str
    status_code: int
    content_type: str
    body: str = ""
    redirect_chain: tuple[str, ...] = ()
    requires_auth: bool = False


class OfflineProbeWorker:
    """A deliberately local-only probe double used by the record tests."""

    def __init__(self, responses: dict[str, FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def probe(self, candidate: dict[str, Any]) -> dict[str, Any]:
        url = str(candidate["url"])
        self.calls.append(url)
        if url not in self.responses:
            raise AssertionError(f"unexpected network/provider access: {url}")
        response = self.responses[url]
        license_markers = ("CC BY-SA 4.0", "CC BY-NC-SA 4.0", "Creative Commons")
        licenses = [marker for marker in license_markers if marker in response.body]
        if response.requires_auth or response.status_code in {401, 403}:
            status = "auth_required"
        elif response.status_code >= 400:
            status = "failed"
        elif response.content_type.startswith("text/html"):
            status = "verified_public"
        else:
            status = "unsupported_content_type"
        return {
            "url": url,
            "probe_status": status,
            "probe_result": {
                "status_code": response.status_code,
                "final_url": response.url,
                "content_type": response.content_type,
                "auth_required": response.requires_auth,
                "redirect_chain": list(response.redirect_chain),
                "license_mentions": licenses,
            },
        }


def _links() -> list[dict[str, str | None]]:
    return [
        {"target": "https://fixture.test/course/spring-2024", "label": "Course schedule", "section_heading": "Official resources"},
        {"target": "https://fixture.test/course/slides.pdf", "label": "Lecture slides", "section_heading": "Official resources"},
        {"target": "https://fixture.test/about", "label": "About", "section_heading": "Other"},
        {"target": "relative/schedule", "label": "Course schedule", "section_heading": "Other"},
    ]


def test_candidate_urls_are_dedicated_records_with_unrun_probe_state() -> None:
    records = candidate_offerings(_links())

    assert [record["url"] for record in records] == [
        "https://fixture.test/course/spring-2024",
        "https://fixture.test/course/slides.pdf",
    ]
    assert all(record["probe_status"] == "not_run" for record in records)
    assert all(record["probe_result"] is None for record in records)
    assert all(record["rejection_reason"] is None for record in records)


def test_fake_probe_records_capture_redirect_content_auth_and_license_fields() -> None:
    candidate = candidate_offerings(_links())[0]
    final_url = "https://fixture.test/archive/cs61b-spring-2024"
    worker = OfflineProbeWorker(
        {
            candidate["url"]: FakeResponse(
                url=final_url,
                status_code=200,
                content_type="text/html; charset=utf-8",
                body="Syllabus; licensed CC BY-SA 4.0",
                redirect_chain=(candidate["url"], final_url),
            )
        }
    )

    record = worker.probe(candidate)

    assert record["url"] == candidate["url"]
    assert record["probe_status"] == "verified_public"
    assert record["probe_result"] == {
        "status_code": 200,
        "final_url": final_url,
        "content_type": "text/html; charset=utf-8",
        "auth_required": False,
        "redirect_chain": [candidate["url"], final_url],
        "license_mentions": ["CC BY-SA 4.0"],
    }
    assert worker.calls == [candidate["url"]]


@pytest.mark.parametrize(
    ("response", "expected_status"),
    [
        (FakeResponse("https://fixture.test/login", 200, "text/html", requires_auth=True), "auth_required"),
        (FakeResponse("https://fixture.test/missing", 404, "text/html"), "failed"),
        (FakeResponse("https://fixture.test/archive.pdf", 200, "application/pdf"), "unsupported_content_type"),
    ],
)
def test_failed_auth_and_non_html_links_remain_explicit_records(
    response: FakeResponse, expected_status: str
) -> None:
    worker = OfflineProbeWorker({"https://fixture.test/candidate": response})

    record = worker.probe({"url": "https://fixture.test/candidate"})

    assert record["probe_status"] == expected_status
    assert record["probe_result"]["final_url"] == response.url
    assert record["probe_result"]["status_code"] == response.status_code


def test_failed_link_record_is_preserved_when_resuming(tmp_path: Path) -> None:
    output = tmp_path / "registry.yaml"
    progress = tmp_path / "progress.md"
    initial = discover(FIXTURE_ROOT, output, progress)
    target = initial["course_targets"][0]
    candidate = {"url": "https://fixture.test/broken", "probe_status": "failed", "probe_result": {"status_code": 404}, "rejection_reason": "not found"}
    target["candidate_offerings"] = [candidate]
    target["state"] = "researching_offering"
    output.write_text(yaml.safe_dump(initial, sort_keys=False), encoding="utf-8")

    resumed = discover(FIXTURE_ROOT, output, progress, resume=True)

    assert resumed["course_targets"][0]["candidate_offerings"] == [candidate]
    assert resumed["course_targets"][0]["state"] == "researching_offering"


def test_resume_is_idempotent_for_probe_records_and_selected_metadata(tmp_path: Path) -> None:
    output = tmp_path / "registry.yaml"
    progress = tmp_path / "progress.md"
    first = discover(FIXTURE_ROOT, output, progress)
    target = first["course_targets"][0]
    target["candidate_offerings"] = [{"url": "https://fixture.test/ok", "probe_status": "verified_public", "probe_result": {"final_url": "https://fixture.test/ok", "content_type": "text/html"}}]
    target["selected_offering"] = {"course_id": "ucb-cs61b-spring-2024", "course_version": "spring-2024"}
    target["state"] = "offering_selected"
    output.write_text(yaml.safe_dump(first, sort_keys=False), encoding="utf-8")

    resumed = discover(FIXTURE_ROOT, output, progress, resume=True)
    output.write_text(yaml.safe_dump(resumed, sort_keys=False), encoding="utf-8")
    resumed_again = discover(FIXTURE_ROOT, output, progress, resume=True)

    assert resumed_again == resumed
    assert resumed_again["course_targets"][0]["candidate_offerings"][0]["probe_status"] == "verified_public"
    assert resumed_again["course_targets"][0]["selected_offering"]["course_version"] == "spring-2024"


def test_coverage_parser_counts_manifest_units_and_valid_chunks_without_network() -> None:
    target = {
        "canonical_course_id": "fixture-course",
        "state": "offering_selected",
        "selected_offering": {"course_id": "fixture-course-spring-2024"},
        "manifest_path": "data/manifests/fixture-course.yaml",
    }
    manifest_records = [
        {"unit_id": "lecture-01", "source_count": 1, "raw_exists": True, "raw_sha256_matches": True, "chunks_exists": True, "chunk_count": 2, "valid_chunk_count": 2, "source_page_count": 2},
        {"unit_id": "lecture-02", "source_count": 1, "raw_exists": True, "raw_sha256_matches": True, "chunks_exists": True, "chunk_count": 1, "valid_chunk_count": 0, "source_page_count": 1},
    ]

    coverage = reconcile_target(
        target,
        manifest_records,
        [
            {
                "build_id": "fixture-build",
                "result_status": "partial",
                "index_exists": False,
                "unit_records": [
                    {
                        "unit_id": "lecture-01",
                        "final_exists": True,
                        "validation_exists": True,
                        "status": "draft",
                        "validation_status": "succeeded",
                    }
                ],
            }
        ],
    )

    assert coverage["unit_count"] == 2
    assert coverage["chunk_count"] == 3
    assert coverage["validated_unit_count"] == 1
    assert coverage["state"] == "authoring"


def test_merge_progress_keeps_complete_probe_result_without_aliasing_input() -> None:
    new = {"candidate_offerings": [{"url": "https://fixture.test/course", "probe_status": "not_run", "probe_result": None}]}
    old = {"candidate_offerings": [{"url": "https://fixture.test/course", "probe_status": "verified_public", "probe_result": {"status_code": 200, "final_url": "https://fixture.test/course"}}]}

    merged = merge_progress(copy.deepcopy(new), old)

    assert merged["candidate_offerings"] == old["candidate_offerings"]
    assert new["candidate_offerings"][0]["probe_status"] == "not_run"
