# MIT 6.5840 / 6.824 Spring 2026 source review

## Selection

- Canonical target: `mit-6-824`; selected offering: `mit-6-824-spring-2026`.
- Official identity: MIT 6.5840 Distributed Systems, formerly 6.824.
- Official homepage: <https://pdos.csail.mit.edu/6.5840/>.
- Schedule: <https://pdos.csail.mit.edu/6.824/schedule.html>.
- The schedule is a completed Spring 2026 offering and lists 21 numbered lectures.
- Research record: `docs/research/mit-6-824-offering-research-20260812.md`.

## Evidence inventory

The selected offering has 21/21 official lecture artifacts. Text notes are primary evidence for most lectures; L5 (Go patterns), L17 (AWS Lambda), and L21 (Byzantine Fault Tolerance) use official staff-linked PDF slides. L10 is explicitly retained as the official lab Q&A instructional note and is not relabeled as a general lecture note.

- Raw inventory: `data/raw/mit-6.5840/spring-2026/source-inventory.json`.
- Prepared provenance: `data/raw/mit-6.5840/spring-2026/prepared-materials.json`.
- Prepared sources: `data/raw/mit-6.5840/spring-2026/prepared/lecture-01.pdf` through `lecture-21.pdf`.
- Chunks: `data/sources/mit-6.5840-spring-2026/lecture-*/chunks.jsonl`.
- Manifest: `data/manifests/mit-6-824-spring-2026.yaml`.

Text notes were converted with `plain_text_to_paginated_pdf_v1` using Pandoc/XeLaTeX so the production `pdf-page-v0.2` parser provides stable page anchors. The original public text files and the raw-to-prepared hashes remain in the ignored raw snapshot and prepared-materials record. Official PDFs were retained verbatim.

Automated input preflight currently reports 21 units, 183 page chunks, zero empty chunks, and 29 parser-warning pages. Warning pages remain candidates for rendering and visual review; they are not silently discarded.

## Scope and exclusions

The official schedule's L22 project demos, labs, optional project, paper-question pages, external paper PDFs, exams, and student code/solutions are metadata-only or excluded. No recordings were found on the official home or schedule. The official artifacts do not state an artifact-level redistribution licence, so `license_status=unknown_artifact_scope` and `redistribution_allowed=false` remain in the inventory and manifest.

This review stops before StudyKit authoring. A future fingerprinted build must independently audit every newly generated practice item and every citation; no existing practice-scope deferral is applied to this new course.
