# MIT 6.S081 Fall 2021 portable StudyKits

Status: approved for repository storage and future database import on
2026-08-10. The user confirmed that the derived StudyKit package may be
uploaded.

This compact package contains 24 reviewed draft StudyKits for Lecture 01–24.
Lecture 25 is absent because the official Fall 2021 schedule provides a Q&A
entry but no substantive lecture source; no StudyKit was fabricated.

The approval combines a fresh deterministic v0.2 validation of every unit with
a semantic and visual spot check of Lecture 07, 15, and 17. The sampled units
cover page faults and copy-on-write, crash recovery and write-ahead logging, and
user-level virtual memory with concurrent garbage collection. Their learning
claims, exercises, limitations, chunks, and selected page images were mutually
consistent and adequate for catalog use.

All 24 units passed each of these gates with zero reported issues:

- StudyKit schema and citation-anchor validation;
- review-plan and final-formula coverage validation under `delivery_policy: draft`;
- candidate/final/YAML semantic and metrics consistency checks;
- learner Markdown scan for internal review and evaluator fields.

Known non-blocking limitations remain explicit. The source inventory contains
61 parser-warning pages, 30 low-text pages, and one empty chunk. The build has no
structured final formulas, and its delivery policy remains `draft`; database
import must preserve each unit's limitations and must not relabel it as a
publish-policy or golden artifact.

Per unit, the retained files are:

- `05-studykit.json`: canonical database-import payload;
- `studykit.yaml`: human-readable structured equivalent;
- `studykit.md`: learner-facing rendering;
- `validation.json`: fresh schema and citation-anchor validation result;
- `04-quality-audit.json`: independent semantic audit trail;
- `review-plan.json` and `review-validation.json`: visual-review evidence and gate result;
- `metrics.json`: quality mode, reviewed-page count, timing, and repair metrics.

The public source snapshot is retained outside Git under
`data/raw/mit-6.s081/fall-2021/`. Per-unit SourceChunks, ingestion reports, and
page images are retained outside Git under
`data/sources/mit-6.s081-fall-2021/`. Keep the chunks until database ingestion
has stored both the evidence text and citation anchors; page images may then be
archived separately according to the storage policy.

This is a portable StudyKit v0.2 package, not an online `data/golden` package.
It may be stored under `data/reviewed`, but must not be copied into
`data/golden`. Do not import the old application code or the duplicate
`.agents/skills` tree from the source ZIP.
