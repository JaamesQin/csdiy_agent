from __future__ import annotations

from pathlib import Path

import pytest

from scripts.discover_csdiy_courses import build_course_targets, classify_leaf


@pytest.fixture
def identity_catalog_fixture(tmp_path: Path) -> tuple[Path, list[dict[str, object]]]:
    """Build the identity edge cases in a fresh, offline catalog snapshot."""

    cases: list[dict[str, object]] = [
        {
            "title": "Harvard CS50: This is CS50x",
            "source_path": "docs/programming/CS50.md",
            "category_path": ["programming foundations"],
            "body": "# Harvard CS50: This is CS50x\nHarvard University course.",
            "ids": ["harvard-cs50x"],
            "target_type": "course",
        },
        {
            "title": "Harvard CS50P Introduction to Programming with Python",
            "source_path": "docs/programming/CS50P.md",
            "category_path": ["programming foundations"],
            "body": "# Harvard CS50P Introduction to Programming with Python\nCS50 is the related family stem.",
            "ids": ["harvard-cs50p"],
            "target_type": "course",
        },
        {
            "title": "Harvard CS50 AI with Python",
            "source_path": "docs/artificial-intelligence/CS50.md",
            "category_path": ["artificial intelligence"],
            "body": "# Harvard CS50 AI with Python\nHarvard University course.",
            "ids": ["harvard-cs50-ai"],
            "target_type": "course",
        },
        {
            "title": "Stanford CS231n: CNN for Visual Recognition",
            "source_path": "docs/deep-learning/CS231.md",
            "category_path": ["deep learning"],
            "body": "# Stanford CS231n: CNN for Visual Recognition\nOfferings are versions of one course.",
            "ids": ["stanford-cs231n"],
            "target_type": "course",
        },
        {
            "title": "UCB EE16A&B: Designing Information Devices and Systems I&II",
            "source_path": "docs/electronics/EE16.md",
            "category_path": ["electronics"],
            "body": "# UCB EE16A&B: Designing Information Devices and Systems I&II\nEE16 is an umbrella alias.",
            "ids": ["ucb-ee16a", "ucb-ee16b"],
            "target_type": "course_sequence",
        },
        {
            "title": "MIT 18.01 and 18.02 Calculus",
            "source_path": "docs/math/MITmaths.md",
            "category_path": ["mathematics"],
            "body": "# MIT 18.01 and 18.02 Calculus\nThe sequence contains 18.01 and 18.02.",
            "ids": ["mit-18-01", "mit-18-02"],
            "target_type": "course_sequence",
        },
    ]
    for case in cases:
        page = tmp_path / Path(*str(case["source_path"]).split("/"))
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(str(case["body"]), encoding="utf-8")
    return tmp_path, cases


def test_identity_fixture_matches_reported_repair_contract(identity_catalog_fixture) -> None:
    root, cases = identity_catalog_fixture

    classified = [
        classify_leaf(
            {
                "title": case["title"],
                "source_path": case["source_path"],
                "category_path": case["category_path"],
            },
            root,
            "offline-fixture",
        )
        for case in cases
    ]

    for case, leaf in zip(cases, classified):
        assert leaf["course_target_ids"] == case["ids"]
        assert leaf["target_type"] == case["target_type"]

    targets = build_course_targets(classified, {})
    assert [target["canonical_course_id"] for target in targets] == [
        "harvard-cs50-ai",
        "harvard-cs50p",
        "harvard-cs50x",
        "mit-18-01",
        "mit-18-02",
        "stanford-cs231n",
        "ucb-ee16a",
        "ucb-ee16b",
    ]
    assert len(targets) == 8


@pytest.mark.parametrize(
    ("case_index", "forbidden_ids"),
    [
        (0, {"harvard-cs50"}),
        (1, {"harvard-cs50", "cs50"}),
        (2, {"harvard-cs50", "cs50"}),
        (3, {"stanford-cs231"}),
        (4, {"ucb-ee16"}),
        (5, {"mit-18-01-18"}),
    ],
)
def test_identity_repairs_do_not_reintroduce_pseudo_targets(
    identity_catalog_fixture, case_index: int, forbidden_ids: set[str]
) -> None:
    root, cases = identity_catalog_fixture
    case = cases[case_index]
    leaf = classify_leaf(
        {
            "title": case["title"],
            "source_path": case["source_path"],
            "category_path": case["category_path"],
        },
        root,
        "offline-fixture",
    )

    assert forbidden_ids.isdisjoint(leaf["course_target_ids"])
