# MIT 6.7960 Fall 2024 portable StudyKits

Status: approved for future database import on 2026-08-10.

This compact package contains 23 reviewed draft StudyKits for Lecture 01–21,
23, and 24. Lecture 22 and 25 are absent because the official OCW snapshot
does not provide those lecture notes.

The approval decision combines deterministic validation of all 23 units with
a semantic spot check of Lecture 09, 18, and 21. The sampled units were judged
adequate for catalog use. Known non-blocking limitations remain recorded in
each unit's StudyKit and quality-audit files.

This is a portable StudyKit v0.1 package, not an online `data/golden` package.
Before database import, the catalog adapter must either support the portable
citation shape (`anchor.type` and `anchor.value`) or normalize it to the online
runtime schema. Do not copy these files directly into `data/golden`.

Per unit, the retained files are:

- `05-studykit.json`: canonical database-import payload.
- `studykit.yaml`: human-readable structured equivalent.
- `studykit.md`: learner-facing rendering.
- `validation.json`: schema and citation-anchor validation result.
- `04-quality-audit.json` and `04-quality-audit.resolution.json`: review trail.

The unified SourceChunks are retained separately under
`data/sources/mit-6.7960-fall-2024/full-course-v0.1.0/`. Page images and formula
inspection artifacts remain in the ignored authoring build under `outputs/`;
they are not database-import payloads.
