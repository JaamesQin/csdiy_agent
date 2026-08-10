# MIT 6.S081 Fall 2021 source and StudyKit review

Review date: 2026-08-09

Status: 24 source-supported lecture StudyKits generated and validated; one official lecture remains a documented source gap

## Course identity and requested scope

The linked archive is the Fall 2021 offering of **MIT 6.S081: Operating System Engineering**:

- <https://pdos.csail.mit.edu/6.828/2021/>
- <https://pdos.csail.mit.edu/6.828/2021/schedule.html>
- <https://pdos.csail.mit.edu/6.828/2021/general.html>

The archive lives under the historical `6.828/2021` URL namespace, but the course homepage identifies this undergraduate offering as 6.S081 and distinguishes it from the graduate 6.828 seminar. The canonical repository identity is therefore `mit-6.s081-fall-2021`; `6.828` is retained as a legacy URL alias.

The official schedule contains 25 numbered lectures. Twenty-four have a public, substantive course-produced source that can support a StudyKit. Lecture 25, “Q&A” on 2021-12-08, has no published lecture artifact and is recorded as a source gap rather than fabricated.

## Acquisition and local layout

The public snapshot contains 70 course-hosted files, including 25 original PDFs plus HTML, text, C, and supporting files. Every acquired file has a canonical URL, byte count, and SHA-256 record. The normalized source-inventory fingerprint is:

```text
a07a800dca6eb3d623b50692395430be11b8027678a3ef93f241d45773c5ffa1
```

Local layout:

```text
data/manifests/mit-6.s081-fall-2021.yaml
data/raw/mit-6.s081/fall-2021/site/...
data/raw/mit-6.s081/fall-2021/prepared/lecture-NN-*.pdf
data/sources/mit-6.s081-fall-2021/lecture-NN/chunks.jsonl
outputs/mit-6.s081-fall-2021/<build-id>/...
```

The catalog manifest and this review are tracked. Raw files, derived page chunks, rendered review pages, and StudyKit outputs remain reproducible local artifacts excluded by `.gitignore`.

Two broken links in the archived site were preserved and corrected transparently:

- `lec-los.txt` returned 404; the course-hosted target is `lec/l-os.txt`.
- the root `xv6-book-riscv-rev2.pdf` path returned 404; the course-hosted target is `xv6/book-riscv-rev2.pdf`.

No authenticated page, paywall, login flow, or external assignment system was accessed.

## Prepared lecture evidence

Each supported lecture has exactly one stable material set and one page-anchored prepared PDF:

- 14 sources are byte-for-byte PDF copies;
- Lecture 2 is a deterministic merge of its two official PDFs, with a provenance cover and recorded page ranges;
- nine official plain-text lecture notes are deterministically paginated to PDF for stable page anchors.

The schedule links Fall 2020 resources for Lectures 14 through 23. Their `resource_vintage` remains explicitly `2020_resource_linked_by_fall_2021_schedule`; they are not relabeled as 2021 originals. Lecture 20 uses the linked 2020 Biscuit slides, and the other nine units in that range use linked notes.

One source per unit is intentional. Course pages, readings, external papers, videos, and xv6 reference material are metadata-only or excluded; they are not silently combined with lecture evidence.

## Academic-integrity and source boundaries

The ten lab pages and two homework pages are retained only as provenance metadata. They are excluded from lecture chunks, learning claims, and generated practice. Q&A decks that contain code or solution walkthroughs were constrained to conceptual mechanisms:

- Lecture 2 pages 69–77 and Lecture 5 pages 2–10 are older homework-solution sections and are not cited.
- Lecture 8 code-walkthrough pages are not used to reproduce lab implementations.
- Lecture 13 page 8 is a COW solution walkthrough and is excluded from evidence.

The generated exercises are new, formative tasks; they do not provide submission-ready lab or homework answers.

## Access and licensing

The course-site footer declares CC BY 3.0 US for the HTML site. The scope of that notice over individual lecture PDFs, notes, and derived artifacts is not explicit. Lecture artifacts therefore use `license_status: unknown_artifact_scope` and `redistribution_allowed: false`.

Raw lecture material, chunks, page images, and StudyKits remain local and untracked. The repository records only metadata, checksums, review notes, and the catalog manifest.

## Parsing and visual review

All 24 prepared PDFs were accepted by Poppler and pypdf. `scripts/build_course_chunks.py` generated one `pdf-page-v0.2` SourceChunk per one-based PDF page and validated every JSONL object against `schemas/source_chunk.schema.json`.

Preparation totals:

| Check | Result |
| --- | ---: |
| Supported units | 24 |
| Prepared PDF pages / SourceChunks | 587 / 587 |
| Pages with parser warnings | 61 |
| Low-text pages | 30 |
| Hidden-text warning pages | 0 |
| Empty native-text chunks | 1 |
| Formula/risk candidates detected for review | 165 |
| Visually reviewed pages | 427 |

The one empty extraction is Lecture 1 page 18. It renders legibly as a system-call table but is not cited as textual evidence. Visual review covered every deterministic selector page, every low-text page, and every page used by the EvidencePlan or final StudyKit. The two missed citation pages in the first review-plan pass were repaired for Lecture 7 (page 4) and Lecture 10 (pages 5 and 11), independently re-audited, and recorded in resolution files.

No structured formula was retained in the final StudyKits. Formula-like and diagram-heavy pages were handled as visual review risks, not inferred from hidden text.

## StudyKit generation

The repository-local `skills/studykit-generator` workflow was used with:

- pipeline `0.2.0`;
- `quality_mode: standard`;
- `delivery_policy: draft`;
- learner language `zh-CN`;
- target duration 180 minutes per unit;
- three parallel author workers plus independent cross-audits.

Every unit contains the required authored stages, independent audit, preserved candidate, deterministic final JSON/YAML/Markdown, validation reports, review plan, and metrics. All 24 finalizations passed candidate validation, review validation, and semantic-equivalence verification.

Build ID:

```text
8905ecd85275372bb2684127ba30a27046650d6b94e3c4d8320c51387ca561db
```

No provider client, API key, DeepSeek command, regression generator, or model API call was used. The current Agent authored the StudyKits from the prepared evidence, as required by the skill contract.

The build index is under:

```text
outputs/mit-6.s081-fall-2021/8905ecd85275372bb2684127ba30a27046650d6b94e3c4d8320c51387ca561db/STUDYKIT_INDEX.md
```

