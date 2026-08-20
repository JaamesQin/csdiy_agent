# CMU 15-213 Summer 2026 parser results

Evaluation date: 2026-08-08

Parser: `pdf-page-v0.1`

Result: all 24 lecture units are source-prepared and have completed canonical StudyKit authoring, validation, and the fast audit/review gate

## Summary

| Check | Result |
| --- | ---: |
| Official schedule lecture links | 24 |
| Downloaded and verified lecture PDFs | 24 |
| Generated and schema-valid chunk files | 24 |
| PDF pages / SourceChunks | 1,441 |
| Usable non-empty chunks | 1,441 |
| Empty chunks | 0 |
| Pages with any parser warning | 508 |
| Pages with duplicate-line removal | 505 |
| Duplicate text-layer lines removed | 2,303 |
| Low-text pages | 5 |
| Visually reviewed pages | 77 |

`removed_duplicate_lines` indicates repeated text-layer objects were deduplicated within a page while preserving the page anchor. It is not a missing-content warning. All five `low_extracted_text` pages were visually inspected and are intentionally sparse.

## Per-unit results

| Unit | Title | Pages | Warning pages | Low-text pages | Status |
| --- | --- | ---: | ---: | --- | --- |
| `lecture-01` | Overview | 67 | 4 | p42, p67 | ready |
| `lecture-02` | Bits, Bytes, & Integers | 66 | 15 | p1 | ready |
| `lecture-03` | Machine Prog: Basics | 82 | 22 | p58 | ready |
| `lecture-04` | Machine Prog: Control | 72 | 33 | - | ready |
| `lecture-05` | Machine Prog: Procedures | 81 | 34 | - | ready |
| `lecture-06` | Design and Debugging | 68 | 7 | - | ready |
| `lecture-07` | Linking | 43 | 18 | - | ready |
| `lecture-08` | Machine Prog: Advanced | 62 | 27 | - | ready |
| `lecture-09` | The Memory Hierarchy | 72 | 23 | - | ready |
| `lecture-10` | Cache Memories | 71 | 30 | - | ready |
| `lecture-11` | Virtual Memory: Concepts | 42 | 21 | - | ready |
| `lecture-12` | Virtual Memory: Details | 40 | 13 | - | ready |
| `lecture-13` | Code Optimization | 48 | 19 | - | ready |
| `lecture-14` | Dynamic Memory Allocation: Basic | 59 | 22 | - | ready |
| `lecture-15` | Dynamic Memory Allocation: Advanced | 37 | 9 | - | ready |
| `lecture-16` | Processes and Multitasking | 66 | 34 | - | ready |
| `lecture-17` | Exceptional Control Flow | 65 | 21 | - | ready |
| `lecture-18` | System Level I/O and File Systems | 51 | 16 | - | ready |
| `lecture-19` | File Systems / Network Programming (Part I) | 59 | 15 | - | ready |
| `lecture-20` | Network Programming (Part II) | 58 | 23 | - | ready |
| `lecture-21` | Concurrent Programming | 72 | 36 | - | ready |
| `lecture-22` | Synchronization: Basic | 53 | 22 | - | ready |
| `lecture-23` | Synchronization: Advanced | 45 | 26 | - | ready |
| `lecture-24` | Thread-Level Parallelism | 62 | 18 | p1 | ready |

## Validation performed

For every unit, the no-model preflight checked:

- exact equality between the schedule's ordered `/lectures/*.pdf` links and manifest source URLs;
- unique chronological unit and source IDs;
- raw file existence, byte size, SHA-256, PDF readability, and page count;
- SourceChunk JSON Schema validity for every page;
- matching course ID, course version, unit ID, source ID, and material-set ID;
- exactly one source and one material set per generation input;
- unique chunk IDs and `(source_id, page)` anchors;
- contiguous one-based page anchors;
- production `build_request` and `build_evidence_bundle` acceptance;
- absence of a CMU StudyKit output directory.

The canonical fast build completed all 24 units. Final course-level records are in `outputs/cmu-15.213-summer-2026/40bd4156f8432f731a6dce34d04cd3cdf7e198a7c754d1533131b7e7754938f6/`; the tracked authoring evaluation is `evaluations/cmu-15.213-summer-2026-studykit-results.md`.
