# CMU 15-213/15-503 Summer 2026 source review

Review date: 2026-08-08

Status: canonical portable-v0.2 fast StudyKit build succeeded; all 24 source-supported units validated and passed the fast audit/review gate

## Course identity and scope

The official course homepage identifies this offering as **15-213/15-503 Introduction to Computer Systems, Summer 2026**, taught by Brian Railing, with 15-122 as the prerequisite:

- <https://www.cs.cmu.edu/~213/>
- <https://www.cs.cmu.edu/~213/schedule.html>
- <https://www.cs.cmu.edu/~213/syllabus/syllabus.pdf>

The strict lecture scope is every link under `lectures/` in the official schedule. There are 24 unique lecture-deck links. All 24 returned HTTP 200, were downloaded as genuine PDFs, and are represented by chronological `lecture-01` through `lecture-24` units. Chronological IDs are necessary because source filename prefixes collide and are not ordered consistently.

Local layout:

```text
data/manifests/cmu-15.213-summer-2026.yaml
data/raw/cmu-15.213/summer-2026/site/lectures/<original-filename>.pdf
data/sources/cmu-15.213-summer-2026/lecture-NN/chunks.jsonl
```

The raw PDFs and generated chunks are reproducible local artifacts excluded by `.gitignore`. The manifest is the tracked record of canonical URLs, local paths, byte sizes, page counts, and SHA-256 checksums.

## Included and excluded material

Included for lecture generation:

- 24 public lecture PDFs;
- exactly one PDF source per lecture unit;
- 1,441 page-anchored SourceChunks using `pdf-page-v0.1`.

Retained as metadata-only shared sources:

- course homepage;
- schedule;
- labs schedule and policies;
- written assignments schedule and policies;
- syllabus.

Deliberately excluded from lecture chunks:

- 12 activity/solution PDFs;
- 7 recitation/review PDFs;
- 2 activity TAR archives;
- lab handouts delivered through authenticated Autolab;
- written assignment materials delivered through authenticated Canvas.

The exclusions keep each generation input within the current one-source-per-unit constraint and avoid mixing solutions or restricted course work into learner evidence.

## Public-material gaps

Two instructional schedule rows do not have a public lecture deck:

- May 15, “More machine prog basics and OH”: no linked material;
- May 21, “Machine Prog: Data”: only an activity and solution are linked.

They are recorded in the manifest coverage section but are not invented as lecture-deck units. Recitations and review sessions remain outside the strict “all lecture decks” scope.

The labs page exposes schedule and policy metadata but leaves every Materials cell blank. The assignments page exposes written-assignment topics and dates but no public handouts. Its prose says there are 10 written assignments while the table lists W1-W11; the snapshot preserves this discrepancy without resolving it. The labs page lists L6 as released July 8, while the main schedule associates “L6 out” with July 9.

## Access and license decision

All mirrored lecture files are publicly accessible without authentication. No official course-material license statement was found on the course pages, so every source is recorded with `license_status: unknown` and `redistribution_allowed: false`.

The PDFs and their derived chunks remain local and untracked. The repository adds only URLs, metadata, checksums, and review documentation. No login, paywall, CMU SAML flow, Autolab course, or Canvas course was accessed.

## Parser and visual review

Every PDF was opened successfully by both Poppler and pypdf. Chunk construction validated every page object against `schemas/source_chunk.schema.json` before writing JSONL.

Automated preflight results:

- 24 manifest units exactly match the 24 schedule lecture links in schedule order;
- 24 PDFs match manifest byte sizes, page counts, and SHA-256 checksums;
- 24 chunk files pass SourceChunk schema and production evidence-bundle validation;
- 1,441 of 1,441 chunks contain usable text;
- 508 pages contain parser warnings;
- 505 pages had repeated PDF text-layer lines removed (2,303 lines total);
- 5 pages were flagged for low extracted text;
- 0 pages are empty.

Visual sampling rendered the first, middle, and last page of every deck, plus all five low-text pages, for 77 reviewed pages total. All sampled pages rendered legibly. The low-text warnings are expected sparse photo, title, divider, or closing slides:

- `lecture-01` pages 42 and 67;
- `lecture-02` page 1;
- `lecture-03` page 58;
- `lecture-24` page 1.

Detailed per-unit counts are recorded in `evaluations/cmu-15.213-summer-2026-parser-results.md`.

## Authoring and finalization

The canonical portable-v0.2 fast build succeeded for all 24 source-supported units. It contains 1,441 page chunks, 24/24 validated units, 24/24 passed fast audit/review, and 1,020 selected/actual final visual-review pages according to the per-unit metrics. No provider-backed generator or network call was used.

- Build index: `outputs/cmu-15.213-summer-2026/40bd4156f8432f731a6dce34d04cd3cdf7e198a7c754d1533131b7e7754938f6/STUDYKIT_INDEX.md`
- Course result: `outputs/cmu-15.213-summer-2026/40bd4156f8432f731a6dce34d04cd3cdf7e198a7c754d1533131b7e7754938f6/result.json`
- StudyKit evaluation: `evaluations/cmu-15.213-summer-2026-studykit-results.md`

The build reused already-authorized, hash-matched checkpoints where available and preserved the independent audit history; it did not regenerate those units in place.
