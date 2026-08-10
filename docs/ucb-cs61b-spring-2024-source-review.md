# UC Berkeley CS 61B Spring 2024 source review

Review date: 2026-08-09

Status: source preparation is ready for StudyKit generation; generation has not started

## Course identity and scope

The official site identifies this offering as **CS 61B Data Structures, Spring 2024** at the University of California, Berkeley. The staff page lists Justin Yokota and Peyrin Kao as instructors.

- <https://sp24.datastructur.es/>
- <https://sp24.datastructur.es/staff/>
- <https://sp24.datastructur.es/policies/>

The strict scope is all 40 numbered lecture rows on the official schedule, in chronological order. This includes the seven rows marked optional (lectures 27, 31, 34, 37, 38, 39, and 40). Ten exam, holiday, spring-break, RRR, and final-exam rows are not lecture units.

Thirty-nine scheduled Google Slides decks were publicly exportable as PDF without authentication. Lecture 34, “Software Engineering III,” is the sole gap: its scheduled deck redirects anonymous users to Google sign-in. That unit uses a clearly labeled, deterministic PDF transcript derived from the uncorrected English automatic captions of the official Spring 2024 recording. It is not represented as the missing slide deck.

Local layout:

```text
data/manifests/ucb-cs61b-spring-2024.yaml
data/raw/ucb-cs61b/spring-2024/site/
data/raw/ucb-cs61b/spring-2024/derived/
data/sources/ucb-cs61b-spring-2024/lecture-NN/chunks.jsonl
```

Raw originals, the Lecture 34 caption/transcript derivation, chunks, page renders, and QA sidecars are reproducible local artifacts excluded by `.gitignore`. The tracked manifest records canonical URLs, exact local paths, byte sizes, page counts, SHA-256 checksums, processing state, and the Lecture 34 derivation chain. Its SHA-256 at preflight was `415d1d0fc14f59ce8425ed185c4e1874f81672fcf77ecd3e04714a88f26f71c6`.

## Acquisition and provenance

The home, policies, staff, resources, labs, homeworks, projects, and calendar pages were captured as metadata-only HTML snapshots. The 39 accessible slide decks were downloaded from their Google Slides `/export/pdf` endpoints while preserving a chronological `lecture-NN` mapping from the official schedule.

For Lecture 34, the official recording is <https://www.youtube.com/watch?v=8XY1TNODHw4>. Anonymous `yt-dlp` access using the `android_vr` player client retrieved the advertised English ASR caption tracks without downloading the video or using cookies/sign-in. A local deterministic transform grouped 915 timestamped caption segments into 62 paragraphs and rendered a nine-page PDF. The manifest records hashes for the raw VTT, raw JSON3, derived Markdown, and derived PDF.

Acquisition totals:

- 39 original slide PDFs: 41,615,665 bytes and 2,851 pages;
- one Lecture 34 transcript-fallback PDF: 30,195 bytes and 9 pages;
- 40 generation sources: 41,645,860 bytes and 2,860 pages;
- eight metadata-only HTML snapshots;
- canonical inventory SHA-256: `b995182866969255d3a39c93c1d8b3723fdefa5148f6d5589e38328e31501878`.

Every generation PDF is genuine, readable, and unencrypted. Every current file matches the byte size, page count, and SHA-256 stored in the manifest.

## Included and excluded material

Included for lecture generation:

- all 40 numbered Spring 2024 lecture units;
- exactly one PDF source and one material set per unit;
- 39 original lecture slide decks and one official-recording ASR transcript fallback;
- 2,860 page-anchored SourceChunks produced by `pdf-page-v0.2`.

Retained as metadata-only shared sources:

- course home/schedule, policies, staff, resources, and calendar;
- labs, homeworks, and projects indexes.

Deliberately excluded from lecture chunks:

- 13 discussion topics, including worksheets, solutions, and discussion slide decks;
- 10 lab topics and their slide decks/specifications;
- six homework rows and eight project-milestone rows;
- assessed work, Gradescope-gated materials, and exams;
- ten nonlecture schedule rows;
- old/pre-recorded Spring 2023 video links;
- Spring 2024 recordings and readings as additional sources for units that already have slides.

These exclusions preserve the current generator’s exactly-one-source-per-unit constraint and keep solutions and assessed work outside lecture evidence. Official recordings and readings remain discoverable as unit metadata.

## Access and license decision

No explicit license for the course site, lecture decks, or recording captions was found. All sources therefore use `license_status: unknown`, `redistribution_allowed: false`, and local-processing-only handling. The raw sources and derived chunks remain ignored; the tracked files contain only metadata, hashes, and audit documentation.

No login, Google account, Gradescope account, or other authenticated course system was used. Lecture 34’s inaccessible deck remains explicitly recorded as authentication-required rather than bypassed.

## Chunking and visual review

Each PDF was processed independently with the repository’s production builder:

```bash
.venv/bin/python scripts/build_course_chunks.py \
  --pdf <raw-or-derived-pdf> \
  --output data/sources/ucb-cs61b-spring-2024/lecture-NN/chunks.jsonl \
  --material-set-id ucb-cs61b-sp24-lecture-NN \
  --course-id ucb-cs61b-spring-2024 \
  --course-version spring-2024 \
  --unit-id lecture-NN \
  --source-id <manifest-source-id> \
  --scope public
```

The builder validated every line against `schemas/source_chunk.schema.json` before writing. All 2,860 pages were also rendered to low-resolution PNGs. No render failed.

The repository-local StudyKit skill’s `standard` quality mode and `review-pages-v1` selector produced 418 visual-review pages: first/middle/last identity pages, all parser-risk pages, one duplicate-removal spot check per deck, deterministic 20% formula-candidate samples (bounded per source), and all nine fallback transcript pages. Thirty-two labeled contact sheets were inspected. Every selected page was legible and correctly oriented; no clipping, black-page, missing-glyph, or source-identity blocker was found.

All 15 low-text pages were inspected and match intentionally sparse title, diagram, screenshot, animation-step, or closing content:

- `lecture-01` p10;
- `lecture-06` p118;
- `lecture-21` p19;
- `lecture-22` p79;
- `lecture-25` p8;
- `lecture-26` p64;
- `lecture-31` p34;
- `lecture-33` p66 and p70;
- `lecture-37` p51;
- `lecture-38` p8, p10, and p22;
- `lecture-40` p3 and p35.

Lecture 38 p11 visibly contains the deck’s intentionally enormous repeated `A` sequence; removing 41 hidden formula-noise text-layer lines there is expected. Lecture 35’s source PDF caused benign malformed-number warnings in both pypdf and Poppler, but all 79 pages parsed, chunked, rendered, and passed the selected visual review.

Native text extraction is retrieval evidence, not a guarantee of exact formula rendering. The skill’s final-formula visual hard gate remains an authoring-time requirement after content generation; it has not been falsely marked complete during source preparation.

## No-model production preflight

For every unit, deterministic preflight verified:

- exact schedule order, dates, titles, and scheduled slide URLs;
- raw source existence, size, hash, PDF readability, encryption state, and page count;
- SourceChunk schema validity and exact course/version/unit/source/material-set identity;
- exactly one source and one material set;
- unique global chunk IDs, unique page anchors, and contiguous pages `1..N`;
- all 2,860 chunks contain usable text;
- rendered-image counts and completed visual-review sidecars;
- production `scripts.generate_studykit.build_request(...)` acceptance;
- production `app.generation.evidence.build_evidence_bundle(...)` acceptance;
- absence of `outputs/ucb-cs61b-spring-2024` and authoring-stage artifacts.

All 40 request builds and all 40 evidence bundles passed. Detailed counts are in `evaluations/ucb-cs61b-spring-2024-parser-results.md`.

## Pipeline boundary

Preparation is complete through deterministic inventory, acquisition, provenance, PDF normalization, chunk construction, schema validation, identity checks, page rendering, formula-candidate selection, and pre-generation visual QA.

The next command would begin model-backed StudyKit authoring and was intentionally **not** run:

```bash
.venv/bin/python scripts/generate_studykit.py \
  --chunks data/sources/ucb-cs61b-spring-2024/lecture-01/chunks.jsonl \
  --manifest data/manifests/ucb-cs61b-spring-2024.yaml \
  --unit-id lecture-01 \
  --output-dir outputs/ucb-cs61b-spring-2024/lecture-01
```

No `01-evidence-plan.json`, StudyKit output, DeepSeek request, staged authoring command, or lecture-regression command was created or run.
