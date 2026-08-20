# Successor prompt: build StudyKits for the CS self-learning catalog

Copy everything below into the successor task.

---

/goal Build a resumable, audited course-ingestion program for every actual course listed by PKUFlyingPig/cs-self-learning. For each course, locate at least one completed semester with public instructional evidence, download and organize the evidence, generate manifests and anchored chunks, and use the repository's StudyKit Generator skill to produce validated Chinese StudyKits. Do not stop after a sample or a single batch. Global success requires at least one validated semester-level build for every course target in the pinned catalog snapshot.

Choose execution order deliberately. Prioritize broadly useful and popular introductory courses, prerequisite courses that unlock many later courses, breadth across major computer-science directions, stable public evidence, and reuse of already-prepared work. Prefer complete, staff-authored lecture notes or online textbooks when the other factors are comparable; distinguish these from slides, readings, transcripts, and video-only evidence. AI relevance and non-CS accessibility are demand signals, not a replacement for breadth: use them to break ties or raise a course within a breadth cohort, never to reduce the final denominator or silently exclude difficult targets.

You are the long-running coordinator for this repository. Resolve the current repository root from the working environment; do not assume a machine-specific absolute path.

## 1. Read and obey the repository contracts first

Before changing files:

1. Read `AGENTS.md` completely.
2. Read `skills/studykit-generator/SKILL.md` completely. The repository-local skill is authoritative for this run.
3. Read the skill's required references completely:
   - `skills/studykit-generator/references/contract.md`
   - `skills/studykit-generator/references/formats.md`
   - `skills/studykit-generator/references/examples.md`
   - `skills/studykit-generator/references/quality-modes.md`
   - `skills/studykit-generator/references/parallelism.md`
4. Announce that you are using the StudyKit Generator skill and explain why.
5. Run `.venv/bin/python skills/studykit-generator/scripts/check_environment.py`.
6. Inspect `git status --short --ignored` and preserve all existing work. Never clean, reset, stash, overwrite, or mass-stage the dirty worktree.

This is an offline authoring workflow. Never call `StudyKitGenerator` from the online chat route. Never invoke `scripts/generate_studykit.py` or `scripts/run_lecture_regression.py`: they use a provider-backed pipeline and are not the portable skill workflow. Never request a model endpoint, API key, or provider configuration. The current host Agent is the author.

Use `.venv/bin/python` and `.venv/bin/pytest -q`. Tests must not require network access or model credentials. If you add a production capability, follow `AGENTS.md` and update all required status documents together; otherwise add only course/catalog-specific documentation.

## 2. Preserve and resume the work already present

Disk state is authoritative; re-audit it rather than assuming this summary is current.

Known state at the handoff:

- `mit-6.s081-fall-2021` is fully generated. It has 24 validated source-supported StudyKits, 587 chunks, 427 visually reviewed pages, and one documented official source gap for Lecture 25. Its successful build ID is `8905ecd85275372bb2684127ba30a27046650d6b94e3c4d8320c51387ca561db`. A tracked reviewed portable-v0.2.0 package exists under `data/reviewed/`.
- `cmu-15.213-summer-2026` has a validated fast-mode StudyKit build: 24/24 units and 1,441 page chunks. Reconcile its build ID and hashes before resuming; do not author a duplicate standard build over it.
- `ucb-cs61b-spring-2024` has a validated fast-mode StudyKit build: 40/40 units and 2,860 chunks. Lecture 34 uses a clearly labeled deterministic PDF derived from the official public recording's uncorrected English ASR captions because the scheduled Google Slides deck requires authentication. Reconcile its build ID and hashes before resuming; do not author a duplicate standard build over it.
- `mit-6.7960-fall-2024` has 23 StudyKits for the officially available Lectures 01–21, 23, and 24.
- Raw data under `data/raw/`, chunks under `data/sources/`, builds under `outputs/`, environments, and private data are intentionally ignored. Manifests and course review/evaluation documents are the tracked reproducibility records.
- Additional archives, docs, evaluations, or generated artifacts may still be untracked user work. Preserve them. Do not stage or commit unless explicitly asked.

The four seed course lines are now complete or reconciled. Reconcile the existing global discovery registry before starting the next batch so all four course lines count toward the same success metric.

## 3. Reuse every applicable repository resource

Do not recreate capabilities that are already present. Audit and reuse these tracked resources first:

- `scripts/discover_csdiy_courses.py`: deterministic offline catalog discovery and classification;
- `scripts/audit_csdiy_registry.py`: reconciliation of registry, manifests, chunks, and builds;
- `scripts/prepare_studykit_build.py`: creation or safe resumption of fingerprinted portable-v0.2 builds;
- `scripts/build_course_chunks.py`: production `pdf-page-v0.2` page chunking;
- `data/catalog/csdiy-course-registry.yaml`: current machine-readable catalog state;
- `docs/csdiy-catalog-progress.md`: generated catalog progress view;
- `evaluations/csdiy-catalog-registry-audit.json`: latest deterministic audit snapshot;
- `data/manifests/`: the four current catalog CourseManifests and conventions;
- tracked `data/reviewed/` packages for MIT 6.7960 and MIT 6.S081;
- immutable, human-approved calibration examples under `data/golden/`;
- ignored local `data/raw/`, `data/sources/`, and `outputs/` checkpoints;
- root runtime schemas under `schemas/` and portable schemas under `skills/studykit-generator/assets/schemas/`;
- `docs/studykit_standard.md`, `docs/studykit_generation.md`, `docs/material_source_strategy.md`, and existing per-course source reviews;
- `evaluations/studykit_benchmark/` and current per-course parser/StudyKit evaluations.

Before the next batch, reconcile the known CS168 classification drift: the
pinned guide is under `计算机网络` and the course teaches Internet protocols,
so `ucb-cs168` must count as `networks`, not `architecture`. The current
misclassification is caused by first-match title keyword inference
(`Architecture` appears before `network` in the discovery rules); fix the
classification logic or apply an evidence-backed override, regenerate the
projection, and add an offline regression test before trusting direction
counts.

The repository-local StudyKit Generator is currently v0.2.1 and takes precedence over an older host-installed skill. Do not use a host v0.1 script for a new v0.2 build merely because it is also installed.

The root runtime schemas and portable skill schemas are separate compatibility gates. Do not assume they are interchangeable. Validate new portable artifacts with the skill contract, then run applicable repository compatibility checks. Preserve older valid v0.1 artifacts under their original version instead of mutating them into v0.2 outputs.

Treat `data/golden/` as immutable human-approved calibration data. Never bulk-generate into it or overwrite it. Treat tracked `data/reviewed/` as reviewed deliverables and ignored `outputs/` as full local checkpoints; reconcile by build ID, fingerprint, hashes, schema version, and validation reports before regenerating anything.

The local repository ZIP may be used only as a last-resort recovery source for missing local files. It is not newer authority than the checked-out repository, tracked manifests, or verified hashes.

Generating a validated StudyKit does not by itself authorize insertion into the online `StudyKitStore` or a future database. Keep outputs in draft/reviewed artifact storage until the user separately authorizes database or online-catalog publication.

## 4. Maintain selected-course status and breadth-first priority

Create and maintain this tracked human-readable status document:

```text
docs/csdiy-selected-course-status.md
```

If an equivalent canonical document already exists, extend it rather than creating a duplicate. `data/catalog/csdiy-course-registry.yaml` remains the machine-readable source of truth; the status document is a deterministic human-readable projection and must never become a conflicting second state system.

The status document must record:

- pinned upstream commit and retrieval time;
- classified nav-leaf and actual course-target counts;
- counts by state and major CS direction;
- every currently selected course and high-priority candidate;
- current batch, recent state transitions, blockers, and next actions;
- selected term, manifest, inventory, chunk count, build ID, validated-unit count, source gaps, audit state, and visual-review state;
- links to manifests, source reviews, evaluations, reviewed packages, and local StudyKit indexes;
- last registry reconciliation timestamp and command;
- the boundary between tracked reproducibility records and ignored local data.

Seed it with the four current course lines:

- MIT 6.7960 — artificial intelligence / deep learning;
- MIT 6.S081 — operating systems;
- CMU 15.213 — computer systems;
- UCB CS61B — data structures and program design.

UCB CS61A Spring 2024 is already the selected offering and should resume at source inventory, not offering research. CS61A is valuable because it supplies a broad Python/programming entry point, introduces abstraction and interpreters, unlocks later courses, and complements rather than duplicates CS61B.

For every real course target, persist evidence-backed priority fields such as:

```text
introductory_value
learner_demand
downstream_prerequisite_value
direction_coverage_gain
public_source_readiness
existing_work_reuse
redundancy_penalty
estimated_ingestion_cost
notes_completeness
notes_kind
notes_public_readiness
ai_relevance
non_cs_accessibility
priority_cohort
priority_reason
```

Do not infer popularity from personal preference or star counts alone. Acceptable evidence includes prominence in the pinned guide, explicit starting-course recommendations, prerequisite relationships, broad foundational scope, stable official archives, and documented adoption.

Use this execution order:

1. audit MIT 6.7960 and MIT 6.S081, then finish CMU 15.213 and UCB CS61B;
2. finish the next mixed breadth batch: UCB CS61A, UCB CS188, MIT 6.042J (preferred over MIT 18.06 for notes completeness), UCB CS168, UCB CS186, and UCB CS61C;
3. within that batch, raise CS188 and accessible mathematical foundations when notes/public evidence are comparable, because AI is a major learner-demand signal, but do not turn the batch into an AI-only path;
4. maximize breadth by selecting one representative course from each remaining uncovered major direction before adding near-duplicates;
5. only then deepen already-covered directions.

For the next mixed batch, use these research candidates and re-probe every URL before selection: `ucb-cs61a` / Spring 2024, `ucb-cs188` / Spring 2024, `mit-6-042j` / Spring 2015, `ucb-cs168` / Spring 2025, `ucb-cs186` / Spring 2025, and `ucb-cs61c` / Fall 2024. CS61A is already offering-selected; the other five remain candidates until public access, completed-term identity, source coverage, and license scope are recorded.

Track at least programming foundations, data structures/algorithms, systems, operating systems, architecture, networks, databases, programming languages, compilers, software engineering, distributed systems, security, AI, machine learning, graphics/vision, theory, discrete mathematics/probability, and numerical/scientific computing. After the current four courses and CS61A, generally prioritize networks, databases, architecture, programming languages/compilers, security, and foundational mathematics. Record any exception.

## 5. Pin and enumerate the upstream catalog deterministically

The source catalog is:

- repository: `https://github.com/PKUFlyingPig/cs-self-learning`
- site: `https://csdiy.wiki/`
- navigation source: `mkdocs.yml`

Do not scrape the rendered table of contents as the sole inventory. Clone or fetch the public repository into an ignored snapshot such as:

```text
data/raw/catalog-sources/cs-self-learning/<upstream-commit-sha>/
```

Record the exact upstream commit SHA, retrieval timestamp, repository URL, `mkdocs.yml` SHA-256, and docs-tree fingerprint. Pin this SHA for the entire run. A newer upstream commit is a future incremental run; do not chase a moving target while trying to reach completion.

Audit and reuse the existing deterministic discovery script:

```text
scripts/discover_csdiy_courses.py
```

It must recursively parse `mkdocs.yml` navigation, resolve every Markdown leaf, and generate a tracked registry such as:

```text
data/catalog/csdiy-course-registry.yaml
docs/csdiy-catalog-progress.md
docs/csdiy-selected-course-status.md
```

The script already supports `--upstream-root`, `--output`, `--progress-output`, `--dry-run`, and `--resume`. Verify those behaviors before extending it. It must remain idempotent and must never call a model or provider. Add or update focused offline tests only for demonstrated gaps.

### Course classification

Do not silently treat every Markdown leaf as a course and do not silently exclude ambiguous pages.

For every nav leaf, record:

- nav category and title;
- source Markdown path and public csdiy.wiki page URL;
- upstream commit SHA and page hash;
- extracted outbound links with visible labels and surrounding section headings;
- `target_type`: `course`, `course_sequence`, `book`, `roadmap`, `tool`, or `other`;
- `is_course_target` and an evidence-backed reason;
- institution, course number, title, aliases, and language when supported by the page;
- classification confidence and review status.

Determine `major_direction` from substantive course evidence, with the pinned nav category and guide path taking precedence over a generic word in the title. Record `direction_evidence` and optional `secondary_directions`. Do not classify a networking course as computer architecture merely because its title says “Internet Architecture”: for example, `ucb-cs168` is under `计算机网络`, teaches routing/transport/application protocols, and must have `major_direction: networks`; `architecture` is only a secondary concept there. Add a focused regression test for every discovered title/category conflict and require an independent audit of those cases before using direction counts for priority decisions.

Exclude obvious tools, forewords, book-only pages, and roadmaps from the course success denominator, but keep them in the registry with reasons. Have a different agent audit the classification. The denominator is every leaf that actually describes a course or course sequence.

Split pages that name multiple distinct official courses when necessary. Examples include paired university offerings or `A/B` course sequences. Preserve a `course_family_id` and page provenance, but give each distinct official course identity its own coverage record unless the official institution treats the sequence as one inseparable offering. Deduplicate Chinese/English translations and aliases without losing their source paths. Do not hard-code the expected count; compute and report it from the pinned snapshot.

## 6. Maintain a resumable global state machine

The registry is the source of truth for progress. Each course target needs states such as:

```text
discovered
classified
researching_offering
offering_selected
sources_inventoried
downloaded
prepared
chunked
authoring
audited
validated
complete
blocked_no_public_evidence
blocked_access
failed_recoverable
```

At minimum, persist these fields:

- canonical course ID and aliases;
- guide-page provenance;
- candidate offering URLs and probe results;
- selected term, official identity evidence, and selection rationale;
- rejected terms and exact rejection reasons;
- raw inventory path/hash;
- manifest path;
- unit counts, public source gaps, and exclusion counts;
- chunk/page/warning/empty counts;
- build ID and output index;
- validation, audit, and visual-review status;
- last successful checkpoint, retry count, issue code, and next action.

Write registry updates atomically after every course stage, then reconcile `docs/csdiy-selected-course-status.md`. A restart must resume at the first missing or invalid checkpoint, using the skill's fingerprint rules. Never edit a completed build in place when inputs or versions differ; create a new build ID.

Audit and extend `scripts/audit_csdiy_registry.py` as needed. It must reconcile the registry and selected-course status with manifests, raw inventories, chunks, reviewed packages, output builds, and validation reports, and identify false-complete records, missing files, duplicate canonical identities, orphan builds, and status-document drift.

## 7. Research and select a usable semester

For each course, inspect the guide Markdown/page and follow its labeled course-site, textbook, video, assignment, and resource-repository links. The CS168 guide page is a representative example: it links a specific semester site, an official textbook, videos, and a resource repository.

The guide link is a lead, not necessarily the selected source. It may point to:

- a future or not-yet-started term;
- an empty shell;
- a term whose slides require authentication;
- a stale redirect or dead domain;
- a semester with only assignments and no lecture evidence.

When that happens, search the public web for another offering of the same official course. Prefer primary sources and use queries combining institution, course number, term/year, `schedule`, `lectures`, `slides`, `notes`, and `syllabus`. Check institution archive indexes, instructor pages, prior-term selectors, stable URL patterns, official GitHub organizations, and course-site navigation. Do not substitute a different course merely because it covers similar content.

### Offering selection policy

Choose the best completed public offering, not mechanically the newest:

1. It must be the same official course identity or a documented renumbering/alias.
2. It must have an explicit semester/version supported by official evidence.
3. It must be publicly accessible without login, paywall, DRM, robots bypass, or private-network access.
4. It should have a schedule or ordered module list and substantive lecture evidence for most units.
5. Prefer institution/course-staff-hosted slides, notes, or handouts.
6. Prefer a past completed term over a future or partially published term.
7. Preserve resource vintage when a schedule links older notes or slides; never relabel them as current originals.
8. Record every attempted candidate, HTTP/final URL, content type, authentication redirect, coverage estimate, and rejection rationale.

Source preference for an otherwise valid offering:

```text
official lecture slides/PDFs
official lecture notes or staff-authored HTML/TXT
official textbook chapters explicitly scheduled for the course
official recording transcripts/captions
official recordings only when an authorized transcript can be obtained
```

During offering research, explicitly classify the instructional evidence rather than treating every linked resource as “lecture notes”. Persist at least `notes_kind` (`full_lecture_notes`, `online_textbook`, `per_lecture_notes`, `slides`, `transcript`, `readings_only`, or `none`), `notes_completeness` (`complete`, `substantial`, `supplementary`, or `unknown`), `notes_public_status`, and `notes_license_status`. Prefer a complete staff-authored notes corpus when it does not reduce direction breadth; use slides as primary evidence when the official notes are incomplete, as with CS186. A public textbook or notes page may still have unknown redistribution rights.

Do not download large video binaries when slides, notes, or transcripts suffice. An ASR transcript may be used only when public and clearly labeled as uncorrected. Do not bypass an authentication-gated slide deck. If a Google Slides deck is public, prefer the official `/export/pdf` endpoint over PPTX because PDF preserves canonical slide order and page anchors.

If no usable public evidence exists for one term, keep searching other official terms. If none can be found after a documented, reasonable archive search, mark the course blocked and keep the global result `partial`; never fabricate evidence or falsely claim success. Global `succeeded` is not allowed while any real course target is blocked. State what authorized source or user action would unblock it.

## 8. Download and inventory sources safely

Only fetch public HTTP(S). Reject embedded credentials and non-global addresses, revalidate redirects, use timeouts and byte caps, and preserve final URLs. Do not bypass login, paywalls, DRM, robots controls, or technical restrictions.

For each selected offering, preserve source-relative paths under:

```text
data/raw/<canonical-course-number>/<term>/site/...
```

Create a deterministic `source-inventory.json` containing:

- course identity and selected semester;
- official homepage/schedule/syllabus URLs;
- every requested source URL and final URL;
- local path, media type, byte size, SHA-256, access status, and license evidence;
- PDF magic/readability/page count or HTML/text encoding details;
- schedule row/module, date, official title, and resource vintage;
- failed links and corrected official alternatives;
- source gaps and excluded materials.

Verify content, not just HTTP 200: an auth/login HTML response is not a PDF. Public accessibility does not imply redistribution permission. Use `license_status: unknown` or `unknown_artifact_scope` and `redistribution_allowed: false` when the artifact license is not explicit.

Do not recursively mirror an entire site without bounds. Download the schedule, identity/licensing pages, and the selected instructional artifacts. Keep labs, homework, projects, exams, and solutions metadata-only unless the user separately authorizes a non-assessed use. Never ingest solutions into learner evidence or generate submit-ready coursework answers.

## 9. Normalize units and prepare stable evidence

Derive unit order from the official schedule/module sequence, never lexical filenames. Use stable lowercase IDs:

```text
course_id: <institution>-<course-number>-<term>
unit_id: lecture-01, lecture-02, ...
source_id: <course-short>-<term>-lecture-01-material
material_set_id: <course-short>-<term>-lecture-01
```

For a lecture course, include every numbered/source-supported lecture in the selected offering. For a module/chapter-based MOOC, use the official module order. Record sessions with no public evidence instead of inventing units. A course may be considered complete with documented per-unit gaps only if it still has at least one substantive validated StudyKit and every source-supported official unit was processed.

Current repository compatibility favors exactly one prepared source and one material set per unit. When a lecture needs multiple official PDFs, create one deterministic prepared PDF with a provenance cover and recorded page ranges. For official HTML/TXT notes, either use the portable skill's anchored ingestion or create a deterministic, clearly labeled paginated PDF when page review is important. Preserve the raw hash and transformation method. Never silently merge materials from different semesters.

Write prepared files under:

```text
data/raw/<canonical-course-number>/<term>/prepared/
```

Create `prepared-materials.json` with raw-to-prepared provenance, page mappings, hashes, and transformation versions.

## 10. Write the catalog CourseManifest

Create one tracked catalog manifest:

```text
data/manifests/<course-id>.yaml
```

Follow the rich conventions in the existing CMU, CS61B, and MIT 6.S081 manifests. Do not confuse this catalog CourseManifest with the portable skill build's `manifest.yaml` under `outputs/`.

Record at least:

- course ID, official number, aliases, title, institution/department;
- term, year, version, language;
- official homepage, schedule, and download provenance;
- instructors/prerequisites only when officially evidenced;
- inventory hash, access/license/redistribution status;
- coverage counts, source gaps, exclusions, and known link issues;
- metadata-only shared sources;
- ordered units with stable IDs;
- exactly one prepared source per unit, including URL(s), local path, bytes, pages, SHA-256, vintage, derivation, processing status, anchor type, and parser version.

There is no authoritative root CourseManifest schema yet. Add deterministic structural and identity validation as part of the catalog automation, but do not claim a schema exists unless you actually implement and document it.

## 11. Build and validate chunks

For prepared PDFs, use the repository production page parser:

```bash
.venv/bin/python scripts/build_course_chunks.py \
  --pdf data/raw/<course>/<term>/prepared/lecture-01.pdf \
  --output data/sources/<course-id>/lecture-01/chunks.jsonl \
  --material-set-id <material-set-id> \
  --course-id <course-id> \
  --course-version <term-version> \
  --unit-id lecture-01 \
  --source-id <source-id> \
  --scope public
```

The current parser is `pdf-page-v0.2`. It emits one one-based page chunk and schema-validates each line. For non-PDF inputs, use `skills/studykit-generator/scripts/ingest_materials.py` according to the skill format contract, or normalize them transparently to page-anchored prepared PDFs.

Automate a batch preflight that checks every unit:

- raw/prepared file existence, byte size, SHA-256, and readability;
- PDF page count equals manifest page count equals chunk count;
- every chunk validates against the root and portable SourceChunk schemas;
- exact course/version/unit/source/material-set identities;
- exactly one source and one material set per prepared unit;
- unique chunk IDs and unique `(source_id, anchor)` pairs;
- contiguous one-based page anchors for PDFs;
- at least one usable nonempty chunk;
- warning, low-text, empty, hidden-text, and formula-candidate counts.

Render page images. Visually inspect all pages required by `review-pages-v1`, all low/empty/garbled or hidden-layer risks, every EvidencePlan page used later, every final citation page, and every retained formula page. Keep visible transcription separate from native extraction. Hidden/overlay text is diagnostic only and must never support a learner-facing claim.

Write tracked per-course review documentation:

```text
docs/<course-id>-source-review.md
evaluations/<course-id>-parser-results.md
```

## 12. Generate StudyKits with the portable skill

Use the repository-local `$studykit-generator` workflow, not the root provider-backed generator.

Defaults unless a course requires an explicit override:

```text
language: zh-CN
target_minutes: 180 per unit
quality_mode: fast
delivery_policy: draft
scope: public
parallel_units: auto
```

This successor task has an explicit fast-mode acceleration choice. `fast` and
`standard` are alternatives, not additive passes: do not author the same unit
in both modes or run a duplicate standard build merely to increase audit
counts. If the mode or any fingerprinted input/version changes, create a new
build ID. Fast mode still requires real anchors, formula visual checks,
hidden-text exclusion, semantic equality of final formats, and an independent
audit of the resulting units.

Create a new fingerprinted build:

```text
outputs/<course-id>/<build-id>/
```

Initialize a new fingerprinted portable-v0.2 build with:

```bash
.venv/bin/python scripts/prepare_studykit_build.py \
  --catalog-manifest data/manifests/<course-id>.yaml \
  --repository-root . \
  --output-base outputs \
  --quality-mode fast \
  --delivery-policy draft \
  --parallel-units auto
```

Then run `skills/studykit-generator/scripts/plan_execution.py` before authoring. The course coordinator owns ingestion, grouping, fingerprints, root manifest/run/result/batch summaries, and the final course index.

For each unit, checkpoint these artifacts in order:

```text
01-evidence-plan.json
02-learning-content.json
03-practice-flow.json
04-quality-audit.json
04-quality-audit.resolution.json       # only if repaired
05-studykit.candidate.json
review-plan.json
metrics.json
```

Then deterministically validate and finalize:

```bash
.venv/bin/python skills/studykit-generator/scripts/validate_artifacts.py \
  --chunks data/sources/<course-id>/<unit-id>/chunks.jsonl \
  --studykit outputs/<course-id>/<build-id>/courses/<course-id>/units/<unit-id>/05-studykit.candidate.json \
  --report outputs/<course-id>/<build-id>/courses/<course-id>/units/<unit-id>/validation.candidate.json

.venv/bin/python skills/studykit-generator/scripts/finalize_studykit.py \
  --chunks data/sources/<course-id>/<unit-id>/chunks.jsonl \
  --studykit outputs/<course-id>/<build-id>/courses/<course-id>/units/<unit-id>/05-studykit.candidate.json \
  --output-dir outputs/<course-id>/<build-id>/courses/<course-id>/units/<unit-id>

.venv/bin/python skills/studykit-generator/scripts/validate_review.py \
  --studykit outputs/<course-id>/<build-id>/courses/<course-id>/units/<unit-id>/05-studykit.json \
  --review-plan outputs/<course-id>/<build-id>/courses/<course-id>/units/<unit-id>/review-plan.json \
  --delivery-policy draft \
  --report outputs/<course-id>/<build-id>/courses/<course-id>/units/<unit-id>/review-validation.json

.venv/bin/python skills/studykit-generator/scripts/verify_unit_outputs.py \
  --unit-dir outputs/<course-id>/<build-id>/courses/<course-id>/units/<unit-id>
```

Every material claim, prerequisite, concept, misconception, and practice task must cite real source anchors. Practice must be new and formative, with hints and deliverables, not copied graded answers. Preserve formula provenance; decoded LaTeX must have one backslash layer. Ambiguous formulas need page-specific `formula_unresolved` records. Candidate JSON, final JSON, and YAML must be semantically equal.

Standard mode requires a substantive independent audit by an agent other than the author. Apply at most one targeted repair per affected stage, preserve the original audit, write a resolution, and re-audit repaired blockers. Do not mark visual review complete until `actual_reviewed_pages` exactly records what the coordinator inspected.

Write per-course final records:

```text
outputs/<course-id>/<build-id>/STUDYKIT_INDEX.md
outputs/<course-id>/<build-id>/course-summary.json
outputs/<course-id>/<build-id>/batch-summary.json
outputs/<course-id>/<build-id>/run.json
outputs/<course-id>/<build-id>/result.json
outputs/<course-id>/<build-id>/finalization-report.json
evaluations/<course-id>-studykit-results.md
```

Return `succeeded` for a course only when all requested source-supported units validate. Otherwise use `partial` or `failed` with structured issues and a recoverable next action.

## 13. Use subagents deliberately and safely

Launch subagents because this is a catalog-scale task. The root coordinator must first freeze the catalog inventory and allocate unique course namespaces.

- Parallelize across independent course IDs in bounded batches.
- A course worker may coordinate only its assigned raw, manifest, source, doc, evaluation, and output namespaces.
- Never allow two workers to write the same course or registry file.
- The root coordinator alone merges registry state and global summaries.
- A build coordinator owns one isolated build root and may use at most four unit workers; this is a per-build safety limit, not the global session limit.
- Saturate a larger session with multiple isolated build coordinators. With 16 session slots, use three coordinators with four unit workers each plus one global coordinator: `3 * (1 coordinator + 4 workers) + 1 global = 16`.
- For the six-course mixed batch, use two waves of three coordinators when all six cannot fit without starving the global coordinator: Wave A `CS61A + CS188 + MIT 6.042J`; Wave B `CS168 + CS186 + CS61C`. Do source probing/inventory independently per course and start the next disjoint coordinator as soon as a prior handoff is mergeable.
- Within a large course, parallelize authoring by unit according to the skill planner; reserve the coordinator slot and never leave it waiting for all other courses before scheduling available units.
- Cross-audit each worker's units with a different agent.
- Checkpoint after every source, unit stage, course, and batch.
- A failed course does not cancel other courses, but global success remains blocked.

Do not treat a configured session limit such as 8 or 16 as permission to put
that many workers into one build. Do not emulate workers with nested `codex
exec`, a shared mutable registry queue, or overlapping output directories.
The global coordinator owns allocation, handoff hash checks, registry merges,
and status projection; isolated coordinators own their own manifests, builds,
unit directories, and course-level handoff records.

Do not ask subagents to interpret the skill without reading it themselves. The root agent must also understand and enforce the skill contract.

## 14. Tests and final integrity gates

Add offline tests for catalog parsing, deduplication, state transitions, resume behavior, URL/probe record parsing, manifest/chunk reconciliation, and global completion logic.

Run at least:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q \
  tests/retrieval tests/generation tests/catalog skills/studykit-generator/tests

git diff --check
git status --short --ignored
```

Run the full suite before the final global handoff. Loopback integration tests may require sandbox approval as described by `AGENTS.md`. Tests must never require external network or credentials; use fixtures/fakes for discovery and downloader tests.

For every ignored raw/chunk/output path, confirm `.gitignore` behavior with `git check-ignore -v`. Stage only explicit tracked metadata/scripts/docs if the user later requests staging. Never use `git add .`.

## 15. Global completion definition

Do not stop after CS168, after the prepared courses, or after a representative batch. Continue resuming the registry until the pinned catalog snapshot meets all gates.

Global status may be `succeeded` only when:

1. Every nav leaf in the pinned upstream snapshot is classified and independently audited.
2. Every actual course target has a canonical identity and at least one selected official semester/version.
3. Every actual course target has authorized public source data downloaded locally with a reproducible inventory.
4. Every source-supported official unit in the selected offering has a manifest entry and schema-valid chunks.
5. Every course target has at least one validated StudyKit, and all requested source-supported units for that offering succeeded.
6. Every source gap, inaccessible artifact, vintage mismatch, license limitation, and academic-integrity exclusion is explicit.
7. Every course build has independent audit, required visual review, final JSON/YAML/Markdown, and successful validators.
8. The global registry audit reports zero unclassified, queued, false-complete, failed, or blocked course targets.
9. `docs/csdiy-selected-course-status.md` agrees with the registry and reports direction coverage and priority state accurately.
10. A tracked global index links every course manifest, review, evaluation, and local StudyKit index, and aggregate counts reconcile.
11. No authentication bypass, provider/model API call, fabricated course identity, fabricated citation, hidden-text evidence, or submit-ready assessed solution was used.

If any real course target lacks public evidence after exhaustive documented official-archive research, return `partial`, not `succeeded`. List the exact target, every offering checked, access failure evidence, and the smallest authorized user action needed to continue. Never weaken the denominator or silently substitute an unrelated course to make the numbers look complete.

## 16. Communication and handoff

Lead progress updates with measurable outcomes: pinned catalog SHA, classified/target counts, selected/high-priority counts, direction coverage, complete/prepared/researching/blocked counts, current batch, pages/chunks, visual-review totals, and validator results. Do not leave the user without an update during long work.

At each batch boundary, provide:

- newly completed course IDs and build-index paths;
- courses that moved to a new state;
- structured blockers and next actions;
- validation/test summary;
- updated global denominator and completion percentage;
- updated `docs/csdiy-selected-course-status.md`.

The final handoff must be self-contained and link the global registry/index, selected-course status document, all new tracked automation, and the aggregate evaluation. Explicitly distinguish ignored local data from tracked reproducibility metadata, report the pinned upstream commit and direction coverage, and state whether anything was staged or committed.

---
