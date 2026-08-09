---
name: studykit-generator
description: Build cited, reviewable StudyKits from raw course materials, including PDFs, scanned pages and images, Office files, web pages, Markdown, text, tables, structured data, and source code. Use when a user asks to ingest one or many course resources, identify courses and units, turn lectures or chapters into Chinese self-study packages, recover an interrupted authoring run, or validate and render existing StudyKit artifacts. Do not use for ordinary course Q&A, instant chat answers, unsupported access bypass, or submitting students' assessed work.
metadata:
  version: "0.2.0"
  triggers:
    - "把这些课程资料整理成带引用的学习包"
    - "从讲义、网页或扫描 PDF 生成整课 StudyKit"
    - "恢复或验证 StudyKit generator 的阶段产物"
---

# StudyKit Generator

Create offline, auditable learning artifacts from authorized source material. Act as the authoring model; never create a provider client, request an API key, or silently omit an input.

## Start safely

1. Confirm that the user may process every input. Do not bypass login, paywalls, DRM, robots controls, encryption, or network restrictions.
2. Require at least one material or public URL and an output directory. Default to `zh-CN`, 180 target minutes per unit, `draft` delivery policy, and private scope. The bundled completed offline non-inferiority decision selects `standard`; an explicit `quality_mode` overrides it. This decision is release-ready: benchmark deductions are improvement targets, not reasons to withhold v0.2.0.
3. Run `python scripts/check_environment.py`. Treat MinerU, Tesseract, LibreOffice, and PyMuPDF as optional enhancements, never prerequisites.
4. Read [references/contract.md](references/contract.md). Read [references/formats.md](references/formats.md) when inputs include PDF, images, URLs, Office, legacy, or media formats. Read [references/examples.md](references/examples.md) for invocation examples.

## Ingest every source

Run the deterministic inventory first:

```bash
python scripts/ingest_materials.py \
  --material /path/to/lecture.pdf \
  --material /path/to/notes.md \
  --output-dir /path/to/build/ingestion \
  --scope private --owner-id local-user \
  --render-pdf auto
```

Repeat `--material` and `--url` without a fixed count. Use `--render-pdf all` for math-heavy or scanned PDFs. Inspect `ingestion-report.json`; every requested source must be present as parsed, partial, or failed.

Use the quality-mode page selector in [references/quality-modes.md](references/quality-modes.md). Inspect every selected `page_image` using the host's image-viewing capability. Transcribe text and formulas into Markdown/LaTeX, preserving the page and visible region. Merge the transcription into the matching chunk without replacing trustworthy native text. Record `parser_version`, `model_assisted`, and warnings. Every formula included in the final StudyKit must be visually checked in every mode. If no page image could be rendered, use the native text, record `formula_unresolved`, and never invent a formula.

For image inputs, inspect the original image path and create anchored chunks. Optional MinerU output may be preferred for complex layouts, but absence of MinerU must not pause or route the work to a human.

## Group courses and units

Use all extracted chunks, filenames, headings, syllabus cues, and source metadata to propose course groups and ordered units. Never group by filename alone.

- Preserve unknown `course_id` or version as null.
- Use stable lowercase hyphenated IDs.
- If multiple courses are present, create separate course manifests.
- If a source spans units, retain the source in each relevant unit but assign only relevant anchors.
- Save `manifest.yaml`, source hashes, grouping evidence, warnings, and a deterministic build fingerprint containing `quality_mode` and the page-selector version. Concurrency is metrics only and never changes the fingerprint.
- The coordinator alone performs ingestion, grouping, fingerprinting, and the final cross-unit summary. Use [references/parallelism.md](references/parallelism.md) for capability-aware unit parallelism. Checkpoint after every stage.

Copy and fill `assets/templates/manifest.yaml` and `assets/templates/result.json`. Do not overwrite an output directory whose fingerprint belongs to different inputs or versions.

## Author each unit

Create these JSON artifacts in order for each unit. In `fast`, one authoring pass may jointly produce stages 01–03, but it must still checkpoint each file before the audit pass:

1. `01-evidence-plan.json`: map topics and learning requirements to exact chunk IDs and source anchors. Exclude unsupported claims.
2. `02-learning-content.json`: write objectives, prerequisites, outline, concepts, glossary, misconceptions, and learning sequence. Cite every material claim.
3. `03-practice-flow.json`: create progressively difficult practice with hints, deliverables, expected evidence, evaluation criteria, and source anchors. Do not reproduce graded answers.
4. `04-quality-audit.json`: audit identity, coverage, citations, formula fidelity, factual support, ordering, timing, copyright, and academic integrity.
5. Apply at most one targeted repair to each affected artifact. Preserve the original audit and record the repair resolution.
6. Assemble `05-studykit.json` from the repaired artifacts. Do not add facts during assembly.

Before assembly, run a compact representation check in every mode:

- emit JSON-decoded LaTeX with one command backslash; reject accidental double escaping such as a decoded `\\\\varepsilon`;
- inventory every source formula or notation convention selected by EvidencePlan, including tensor/channel indices, and either retain it with provenance or record a page-specific omission/unresolved limitation;
- create `formula_unresolved` for every deliberately untranscribed ambiguous formula instead of merely mentioning ambiguity in prose;
- state explicitly that hidden/overlay text was excluded whenever ingestion detected it, and distinguish visible-slide evidence from hidden layers;
- ensure practice covers any notation convention that is itself a learning requirement.

Also write `review-plan.json` and `metrics.json` from their templates. The plan records selected pages and reasons before review, then the pages actually reviewed. Metrics record stage duration, retries, repairs, token counts when available, and concurrency. The coordinator writes root `batch-summary.json` and checks candidate/final/YAML semantic equality across every successful unit.

Follow `assets/templates/studykit.json` and `assets/schemas/studykit.schema.json`. Use citation objects shaped as:

```json
{"source_id":"lecture-notes-a1b2c3d4e5","anchor":{"type":"page","value":7}}
```

Valid anchor types are `page`, `heading`, `slide`, `paragraph`, `sheet`, and `image`. Preserve formula provenance as `formula` metadata containing LaTeX when resolved and an image reference plus warning when unresolved.

## Validate and deliver

Validate and render deterministically:

```bash
python scripts/validate_artifacts.py \
  --chunks /path/to/build/ingestion/chunks.jsonl \
  --studykit /path/to/build/units/lecture-02/05-studykit.json \
  --report /path/to/build/units/lecture-02/validation.json
```

Fix schema or missing-anchor errors, then run:

```bash
python scripts/finalize_studykit.py \
  --chunks /path/to/build/ingestion/chunks.jsonl \
  --studykit /path/to/build/units/lecture-02/05-studykit.candidate.json \
  --output-dir /path/to/build/units/lecture-02
```

Render learner Markdown from validated fields only; omit internal audit reasoning and ingestion diagnostics. Produce `05-studykit.json`, `studykit.yaml`, `studykit.md`, and `validation.json`.

Run `scripts/validate_review.py` before delivery. Citation anchors must exist; hidden text cannot support claims; candidate JSON, final JSON, and YAML must be semantically identical; and every final formula page must appear in `actual_reviewed_pages`. Also inspect decoded LaTeX, EvidencePlan-to-final notation coverage, page-specific unresolved records, and the visible-versus-hidden evidence statement. `delivery_policy: draft` permits an explicit unresolved warning, while `publish` treats it as a blocker. In strict mode, use an independent auditor and re-audit after blocker repair; any remaining blocker prevents success.

Return `succeeded` only when all requested units validate. Return `partial` when some units validate, and include their paths. Return `failed` or `ingestion_failed` with `failed_stage`, structured issues, retry count, recoverability, and `next_action`; never return only prose.

## Preserve integrity

- Keep public and private materials isolated by scope and owner.
- Use source material, not background knowledge, for course facts and formulas.
- Label explanations and inferences separately from source summaries.
- Keep formula screenshots and anchors when transcription is uncertain; never silently normalize a symbol.
- Do not expose chain-of-thought or hidden evaluator fields.
- Do not turn this offline authoring workflow into synchronous end-user chat behavior.
