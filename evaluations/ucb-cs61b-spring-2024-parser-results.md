# UC Berkeley CS 61B Spring 2024 parser results

Evaluation date: 2026-08-09

Parser: `pdf-page-v0.2`

Quality mode: `standard` (`review-pages-v1`)

Result: all 40 numbered lecture units pass deterministic source preparation and have completed canonical StudyKit authoring, validation, and the fast audit/review gate

## Summary

| Check | Result |
| --- | ---: |
| Official numbered lecture rows | 40 |
| Public original slide PDFs | 39 |
| Official-recording ASR transcript fallbacks | 1 |
| Generated and schema-valid chunk files | 40 |
| PDF pages / SourceChunks | 2,860 |
| Usable non-empty chunks | 2,860 |
| Empty chunks | 0 |
| Pages with any parser warning | 1,203 |
| Pages with duplicate-line removal | 1,188 |
| Duplicate text-layer lines removed | 5,116 |
| Low-text pages | 15 |
| Hidden formula-noise pages | 1 |
| Formula-candidate pages | 1,247 |
| Rendered page images | 2,860 |
| Visually reviewed pages | 418 |
| Production request/evidence preflights | 40 / 40 passed |
| Model calls | 0 |

`removed_duplicate_lines:N` means repeated PDF text-layer objects were deduplicated within a page while preserving its page anchor. It is common in exported Google Slides and is not, by itself, a missing-content warning. The 15 low-text pages and Lecture 38’s one hidden-noise page were all visually checked.

## Per-unit results

| Unit | Official schedule title | Pages | Warning pages | Low-text pages | Formula candidates | Reviewed | Status |
| --- | --- | ---: | ---: | --- | ---: | ---: | --- |
| `lecture-01` | Intro | 50 | 20 | p10 | 14 | 8 | ready |
| `lecture-02` | Defining and Using Classes | 49 | 32 | — | 24 | 9 | ready |
| `lecture-03` | Lists I: References, Recursion, and Lists | 64 | 39 | — | 44 | 13 | ready |
| `lecture-04` | Lists II: SLLists | 97 | 73 | — | 58 | 14 | ready |
| `lecture-05` | Lists III: DLLists and Arrays | 48 | 16 | — | 26 | 9 | ready |
| `lecture-06` | Testing | 121 | 82 | p118 | 73 | 15 | ready |
| `lecture-07` | Lists IV: Arrays and Lists | 90 | 52 | — | 43 | 13 | ready |
| `lecture-08` | Inheritance I: Interface and Implementation Inheritance | 68 | 35 | — | 32 | 11 | ready |
| `lecture-09` | Inheritance II: Extends, Casting, Higher Order Functions | 96 | 64 | — | 51 | 14 | ready |
| `lecture-10` | Inheritance III: Subtype Polymorphism, Comparators, Comparable | 82 | 49 | — | 34 | 11 | ready |
| `lecture-11` | Inheritance IV: Iterators, Object Methods | 95 | 66 | — | 68 | 14 | ready |
| `lecture-12` | Asymptotics I | 63 | 28 | — | 43 | 13 | ready |
| `lecture-13` | Ask Anything: Midterm 1 | 11 | 0 | — | 2 | 5 | ready |
| `lecture-14` | Disjoint Sets | 70 | 13 | — | 22 | 8 | ready |
| `lecture-15` | Asymptotics II | 92 | 43 | — | 78 | 14 | ready |
| `lecture-16` | ADTs, Sets, Maps, BSTs | 56 | 7 | — | 12 | 7 | ready |
| `lecture-17` | B-Trees (2-3, 2-3-4 Trees) | 61 | 26 | — | 38 | 12 | ready |
| `lecture-18` | Red Black Trees | 78 | 36 | — | 3 | 7 | ready |
| `lecture-19` | Hashing | 103 | 23 | — | 46 | 13 | ready |
| `lecture-20` | Hashing II | 63 | 12 | — | 30 | 10 | ready |
| `lecture-21` | Heaps and Priority Queues | 64 | 39 | p19 | 7 | 8 | ready |
| `lecture-22` | Tree and Graph Traversals | 107 | 7 | p79 | 62 | 15 | ready |
| `lecture-23` | Graph Traversals and Implementations | 78 | 33 | — | 49 | 14 | ready |
| `lecture-24` | Shortest Paths | 120 | 82 | — | 77 | 14 | ready |
| `lecture-25` | Minimum Spanning Trees | 110 | 87 | p8 | 22 | 10 | ready |
| `lecture-26` | Directed Acyclic Graphs | 64 | 38 | p64 | 28 | 10 | ready |
| `lecture-27` | Software Engineering I | 42 | 3 | — | 0 | 4 | ready |
| `lecture-28` | Prefix Operations and Tries | 59 | 38 | — | 27 | 10 | ready |
| `lecture-29` | Sorting I: Selection Sort, Heapsort | 95 | 19 | — | 14 | 7 | ready |
| `lecture-30` | Sorting II: Mergesort and Insertion Sort | 112 | 16 | — | 59 | 14 | ready |
| `lecture-31` | Software Engineering II | 51 | 13 | p34 | 10 | 8 | ready |
| `lecture-32` | Sorting III: Quicksort | 80 | 17 | — | 31 | 10 | ready |
| `lecture-33` | Sorting IV: Sorting and Algorithmic Bounds | 76 | 6 | p66, p70 | 37 | 14 | ready |
| `lecture-34` | Software Engineering III | 9 | 0 | — | 1 | 9 | ready (ASR fallback) |
| `lecture-35` | Sorting V: More Quicksort, Radix Sorts | 79 | 47 | — | 15 | 7 | ready |
| `lecture-36` | Sorting VI: Radix vs. Comparison Sorting | 44 | 10 | — | 23 | 9 | ready |
| `lecture-37` | Software Engineering IV | 51 | 10 | p51 | 6 | 7 | ready |
| `lecture-38` | Compression | 71 | 12 | p8, p10, p22 | 15 | 11 | ready |
| `lecture-39` | Complexity and P=NP? | 55 | 3 | — | 20 | 8 | ready |
| `lecture-40` | Summary, Fun | 36 | 7 | p3, p35 | 3 | 9 | ready |

## Visual QA result

All 2,860 pages rendered successfully. The standard selector chose 418 pages across 40 sources, and all 418 were inspected through 32 labeled contact sheets. Selection covered source identity, every parser-risk page, deterministic formula-candidate samples, duplicate-removal spot checks, and the full nine-page Lecture 34 fallback.

No reviewed page showed an orientation, clipping, black-page, missing-glyph, or wrong-source blocker. The 15 low-text pages were intentionally sparse. Lecture 38 p11’s repeated `A` string accounts for the sole hidden-formula-noise removal. Lecture 35’s malformed-number parser warnings were non-blocking because all 79 pages parsed and rendered correctly.

The pre-generation review is complete. Formula-bearing pages used in the eventual authored StudyKit still require the separate final-formula visual hard gate.

## Validation performed

For every unit, the no-model preflight checked:

- exact equality with official schedule order, title, date, and slide URL;
- unique chronological unit, source, material-set, and global chunk IDs;
- raw file existence, byte size, SHA-256, PDF readability, encryption state, and page count;
- SourceChunk JSON Schema validity for every page;
- matching course ID, course version, unit ID, source ID, and material-set ID;
- exactly one source and one material set per generation input;
- unique, contiguous one-based page anchors;
- rendered-image and sidecar counts;
- completed selected-page review with no remaining blockers;
- production `build_request` and `build_evidence_bundle` acceptance;
- canonical fast StudyKit output, candidate/final/review artifacts, and unit validation records are present for all 40 units.

No provider-backed generator, `scripts/generate_studykit.py`, `scripts/run_lecture_regression.py`, or online model API was used. Final course-level records are in `outputs/ucb-cs61b-spring-2024/a748c428609e7a5bc9f0697a06ae0d7fbd56e2469aaaba8f5b034121f2479ab1/`; the tracked authoring evaluation is `evaluations/ucb-cs61b-spring-2024-studykit-results.md`.

## Repository verification

- Focused retrieval/generation/skill tests: 32 passed.
- Full repository test suite: 156 passed.

The full suite's three localhost HTTP integration tests required loopback access outside the filesystem sandbox. The repository declares `uvicorn[standard]==0.52.0`, but the configured package index offered releases only through 0.39.0; the ignored local `.venv` used 0.39.0 for this test run. No tracked dependency file was changed.
