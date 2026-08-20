# Cambridge Semantics of Programming Languages 2025–26 source review

Review date: 2026-08-12
Course namespace: `cambridge-semantics-of-programming-languages-2025-26`
Build: `ff5d60747dbcc5327685c3d81764165550c388874a7472ed478882443ead9c01`

## Source scope

The build uses the catalog manifest `data/manifests/cambridge-semantics-of-programming-languages-2025-26.yaml` and the 12 supplied current chunk files under `data/sources/cambridge-semantics-of-programming-languages/lecture-01..12/chunks.jsonl`. The inventory contains 96 chunks over 96 prepared lecture pages. The per-unit source IDs, page ranges and SHA-256 values are preserved in the build `manifest.yaml`; no catalog registry, source chunks, manifest, golden artifact, or other course namespace was modified by this build.

The source is the public 2025–26 Cambridge Semantics of Programming Languages notes, partitioned into the official 12 lecture units. The build does not use recordings, Moodle/Panopto, past examinations, solutions, implementations, supervision material, assessed work, or external textbook facts. The source license remains unknown at artifact level, so the artifacts retain local processing/draft scope and source attribution.

## Content coverage

The host author mapped each learning objective, prerequisite, concept, misconception and practice item to the current unit's page chunk anchors. The units cover:

1. semantics, L1 syntax, transition systems and small-step execution;
2. rule instances, derivations, search and language-design choices;
3. L1 typing, Progress, Preservation, Safety and inference;
4. the collected L1 definition, derivations, variants and dynamic testing;
5. mathematical/structural induction, ASTs, determinacy and inversion;
6. rule induction and type-safety proof structure;
7. functions, binding, alpha conversion, substitution and evaluation strategy;
8. substitution preservation, let, recursive functions and implementation;
9. products, sums, records, references, well-typed stores and evaluation contexts;
10. subtyping, variance and record-based objects;
11. semantic/contextual equivalence and observable stores;
12. concurrency, interleavings, races, mutexes, ordered 2PL and thread-local semantics.

Each unit has five complete, answerable practices. The independent audit sidecar for every unit records five per-practice reviews, checks the mapped requirement/concept and current chunk anchors, and confirms a concrete setting, observable expected evidence, aligned hint/evaluation, and no generic shell or assessed solution. The 12 auditors are distinct from the common host author identity; no practice audit is deferred.

## Representation and review boundaries

The supplied chunks report 53 warning chunks, all from duplicate-line removal; no hidden/overlay text and no formula-candidate chunks are reported. All 96 pages were rendered locally under the isolated build's `ingestion/page-images/` directory. The notation/formula-risk page for each unit was visually checked. The final kits do not assert a resolved formula that depends on an ambiguous glyph; each unit records a page-specific `formula_unresolved` limitation and carries the visible-source boundary. Hidden text, if present in any other extraction layer, is excluded from learner-facing evidence.

The build is `quality_mode=standard`, `delivery_policy=draft`, `language=zh-CN`, target 180 minutes per unit, and `parallel_units=auto`. The plan uses two non-overlapping worker groups, below the four-worker ceiling. Stage checkpoints are present in order `01 → 02 → 03 → 04 → 05`; no targeted repair was needed. Candidate, final JSON and YAML are semantically equal for all 12 units.

## Validation and delivery

Portable validation passed for all 12 units: candidate and final `validate_artifacts.py`, `finalize_studykit.py`, `validate_review.py`, and `verify_unit_outputs.py` all passed. Root `course-summary.json`, `result.json`, `batch-summary.json`, `coordinator-handoff.json` and `finalization-report.json` reconcile to requested/completed/validated/audited `12/12`, failed `0`, pending `0`.

The legacy root validator was run separately and failed all 12 because its older schema requires a different `prerequisites` shape and page-citation representation. That legacy result is recorded separately in `evaluations/cambridge-semantics-of-programming-languages-2025-26-build-results.json`; it is not treated as a portable StudyKit failure and is not merged with the portable validator counts.

## Output paths

The isolated build root is:

`outputs/cambridge-semantics-of-programming-languages-2025-26/ff5d60747dbcc5327685c3d81764165550c388874a7472ed478882443ead9c01/`

Each unit is under `courses/cambridge-semantics-of-programming-languages-2025-26/units/lecture-01..12/` and contains the five ordered checkpoints, independent audit sidecar, review plan, metrics, candidate/final JSON, YAML, Markdown, validation reports and review validation. Root execution/reconcile files and the combined ingestion evidence are in the build root and its `ingestion/` directory. Environment and validator records are in `evaluations/`.
