# MIT 6.S081 Fall 2021 StudyKit results

Evaluation date: 2026-08-09

Result: **24 of 24 requested source-supported lecture units succeeded; 0 failed**

Build ID: `8905ecd85275372bb2684127ba30a27046650d6b94e3c4d8320c51387ca561db`

## Aggregate result

| Check | Result |
| --- | ---: |
| Official numbered lectures | 25 |
| Source-supported/requested StudyKits | 24 |
| Completed StudyKits | 24 |
| Documented source-gap lectures | 1 (`lecture-25`) |
| Prepared PDFs | 24 |
| PDF pages / SourceChunks | 587 / 587 |
| Pages with parser warnings | 61 |
| Low-text pages | 30 |
| Empty chunks | 1 |
| Visually reviewed pages | 427 |
| Independent audits passed | 24 |
| Learning objectives | 112 |
| New formative practice items | 121 |
| Final citation records | 289 |
| Validator-observed citation occurrences | 2,119 |
| Structured formulas retained | 0 |
| Failed units | 0 |
| Provider/model API calls | 0 |

The course catalog language is English; the generated learner artifacts use `zh-CN`. Each unit has a 180-minute learning sequence. Delivery is `draft`, so the artifacts are complete and validated but deliberately do not claim assessed or instructor-approved status.

## Per-unit result

| Unit | Official title | Source vintage | Pages | Warning | Low text | Reviewed | Objectives | Practice | Status |
| --- | --- | --- | ---: | ---: | --- | ---: | ---: | ---: | --- |
| `lecture-01` | Introduction and examples | Fall 2021 | 18 | 2 | p10, p18 | 13 | 4 | 5 | pass |
| `lecture-02` | C and gdb | Fall 2021 | 111 | 12 | p67 | 38 | 5 | 5 | pass |
| `lecture-03` | OS organization and system calls | Fall 2021 | 25 | 0 | - | 25 | 5 | 5 | pass |
| `lecture-04` | Page tables | Fall 2021 | 26 | 2 | p22, p24 | 20 | 4 | 5 | pass |
| `lecture-05` | GDB, calling conventions and stack frames RISC-V | Fall 2021 | 44 | 0 | - | 16 | 5 | 5 | pass |
| `lecture-06` | Isolation and system call entry/exit | Fall 2021 | 27 | 2 | p10 | 26 | 5 | 5 | pass |
| `lecture-07` | Page faults | Fall 2021 | 23 | 2 | p9, p11 | 19 | 4 | 5 | pass |
| `lecture-08` | Q&A labs I | Fall 2021 | 25 | 6 | p5, p8, p12, p14, p16, p25 | 23 | 5 | 5 | pass |
| `lecture-09` | Interrupts | Fall 2021 | 22 | 1 | p16 | 22 | 5 | 5 | pass |
| `lecture-10` | Multiprocessors and locking | Fall 2021 | 33 | 3 | p3, p10, p30 | 30 | 4 | 5 | pass |
| `lecture-11` | Scheduling I | Fall 2021 | 30 | 1 | p20 | 26 | 5 | 5 | pass |
| `lecture-12` | Scheduling II | Fall 2021 | 26 | 3 | p13, p14, p25 | 26 | 5 | 5 | pass |
| `lecture-13` | Q&A labs II | Fall 2021 | 12 | 2 | p8, p11 | 12 | 4 | 5 | pass |
| `lecture-14` | File systems | 2020, linked by 2021 schedule | 4 | 1 | - | 4 | 5 | 5 | pass |
| `lecture-15` | Crash recovery | 2020, linked by 2021 schedule | 4 | 2 | - | 4 | 5 | 5 | pass |
| `lecture-16` | File-system performance and fast crash recovery | 2020, linked by 2021 schedule | 5 | 1 | - | 5 | 4 | 5 | pass |
| `lecture-17` | Virtual memory for applications | 2020, linked by 2021 schedule | 3 | 0 | - | 3 | 5 | 5 | pass |
| `lecture-18` | OS organization | 2020, linked by 2021 schedule | 5 | 2 | - | 5 | 5 | 5 | pass |
| `lecture-19` | Virtual machines | 2020, linked by 2021 schedule | 4 | 1 | - | 4 | 4 | 5 | pass |
| `lecture-20` | Kernels and high-level languages | 2020, linked by 2021 schedule | 67 | 5 | p21, p22, p23, p24 | 49 | 5 | 6 | pass |
| `lecture-21` | Networking | 2020, linked by 2021 schedule | 4 | 0 | - | 4 | 5 | 5 | pass |
| `lecture-22` | Meltdown | 2020, linked by 2021 schedule | 3 | 1 | - | 3 | 4 | 5 | pass |
| `lecture-23` | Multi-core scalability and RCU | 2020, linked by 2021 schedule | 4 | 1 | - | 4 | 5 | 5 | pass |
| `lecture-24` | Current research: Radiation tolerance | Fall 2021 | 62 | 11 | p9, p25 | 46 | 5 | 5 | pass |

## Validation performed

For all 24 units, the source preflight checked:

- prepared-file existence, byte size, SHA-256, PDF readability, and page count;
- exact course, version, unit, source, and material-set identities;
- one source and one material set per unit;
- root and portable SourceChunk schema validity;
- unique chunk IDs and unique `(source_id, page)` anchors;
- contiguous one-based page anchors matching PDF page counts;
- exact concatenation of per-unit chunks into the build ingestion artifact.

For every authored unit, the workflow checked:

- schema-valid EvidencePlan, LearningContent, PracticeFlow, and QualityAudit stages;
- candidate compliance with the portable StudyKit schema;
- every citation against a real non-hidden SourceChunk page;
- a substantive independent audit by an agent other than the author;
- complete visual review of all selector, risk, evidence-plan, and final-citation pages;
- candidate JSON validation before finalization;
- final JSON/YAML/Markdown generation;
- review validation under the draft delivery policy;
- semantic equality of candidate JSON, final JSON, and YAML.

The final read-only sweep reran 96 unit-level CLI checks: candidate validation, finalization validation, review validation, and output verification for each unit. All 96 exited successfully. Stored validation reports have `status: succeeded` and empty issue lists for 24 of 24 units.

## Test evidence

The repository-local skill environment check passed for native PDF ingestion and visual fallback. Optional MinerU and PyMuPDF were absent; pypdf, jsonschema, PyYAML, Poppler, Tesseract, and LibreOffice were available.

Tests were run with Python 3.12 in the ignored local environment `.venv/py312`:

```text
tests/retrieval tests/generation skills/studykit-generator/tests: 128 passed
full repository suite: 196 passed
```

`PYTHON_DOTENV_DISABLED=1` was used so the user's ignored local `.env` did not affect the startup test. The `.env` file was not modified.

## Known limitations

- Lecture 25, “Q&A,” has no public substantive lecture source; no StudyKit was invented for it.
- Lectures 14–23 use 2020 resources explicitly linked by the Fall 2021 schedule. All claims preserve that historical provenance.
- Lecture artifacts have an unclear license scope and remain local-only.
- Lecture 1 page 18 has empty native extraction but was visually legible and is not used as textual evidence.
- No structured formula survived the evidence and visual-review gates; the build does not pretend native text extraction is a formula transcription.
- The generated practice is formative and excludes submission-ready lab or homework solutions.

## Build records

The local build contains:

- `STUDYKIT_INDEX.md` with links to every final Markdown, JSON, and YAML StudyKit;
- `course-summary.json`, `batch-summary.json`, `run.json`, and `result.json`;
- `visual-review/review-log.json`;
- `finalization-report.json`;
- per-unit stage, audit, review, validation, metrics, and final artifact files.

No root DeepSeek generator or lecture-regression command was run. The repository-local portable skill workflow was used end to end.

