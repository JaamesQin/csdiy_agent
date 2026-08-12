# Usage examples

## 1. Generate a course from mixed local files

User prompt:

> Use $studykit-generator to ingest `syllabus.html`, eight lecture PDFs, and `labs/`. Identify the course and lecture units, then create Chinese StudyKits under `outputs/course-build`.

Expand directories into individual `--material` arguments. Run ingestion with `--render-pdf all` when the lectures contain mathematics. Group the sources, write a course manifest, and author each unit sequentially. Expected result: `succeeded` with one course and one validated artifact directory per detected unit.

## 2. Mix a URL with a scanned handout

User prompt:

> Use $studykit-generator on the public course page URL and `week3-scan.pdf`; keep unknown semester metadata null.

Run:

```bash
python scripts/ingest_materials.py \
  --url https://example.edu/course \
  --material week3-scan.pdf \
  --output-dir build/ingestion \
  --scope public --render-pdf all
```

Inspect rendered scan pages with host vision, add model-assisted chunks, and retain the URL and file as separate sources. Do not infer a semester without evidence.

## 3. Preserve uncertain mathematics

User prompt:

> Generate a strict StudyKit from these optimization notes. Preserve every theorem and formula anchor.

Compare native PDF text with rendered pages. For a matrix whose subscript cannot be resolved, store its crop and a page-specific `formula_unresolved`; state the limitation and avoid exercises that depend on the ambiguous symbol. Verify the decoded JSON LaTeX has only one command-escape layer. Continue with supported concepts. Strict mode blocks unsupported claims, not the whole build merely because MinerU is absent.

## 4. Resume a partial multi-unit build

User prompt:

> Resume the previous $studykit-generator run after unit 4 without regenerating completed units.

Read `run.json`, recompute the input/version fingerprint, validate every completed stage hash, and continue at the first missing stage. If fingerprints differ, create a new build and return an `input_fingerprint_mismatch` issue for the old one.

## 5. Validate an existing candidate

```bash
python scripts/validate_artifacts.py \
  --chunks build/ingestion/chunks.jsonl \
  --studykit build/courses/course/units/unit-01/05-studykit.candidate.json \
  --report build/courses/course/units/unit-01/validation.candidate.json
```

Exit zero means the candidate schemas and citation anchors validate. Finalize it, write `review-validation.json` with `validate_review.py`, and run `verify_unit_outputs.py`; semantic and formula audit still remains required before publication.

## 6. Plan fast parallel authoring

```bash
python scripts/plan_execution.py \
  --unit lecture-02 --unit lecture-03 --unit lecture-04 --unit lecture-08 \
  --output-dir build/courses/mit-6-7960/units \
  --quality-mode fast --delivery-policy draft \
  --parallel-units auto --available-slots 4 \
  --write build/execution-plan.json
```

This produces isolated worker groups for one build coordinator (one of four
slots remains with that coordinator). It does not invoke a model. Populate
each unit's `review-plan.json` before visual review and `metrics.json` as stages
checkpoint.

## 9. Run isolated build coordinators in one session

Use distinct build roots and coordinator IDs when processing independent
courses. The global session budget is divided before launch; no coordinator
may write another coordinator's manifest, output root, source namespace, or
registry state:

```bash
python scripts/plan_execution.py \
  --unit lecture-10 --unit lecture-11 --unit lecture-12 \
  --output-dir outputs/cmu-15-213/build-a/courses/cmu-15-213/units \
  --coordinator-id cmu-15-213-build-a \
  --coordinator-count 3 --session-slots 16 \
  --parallel-units auto --write outputs/cmu-15-213/build-a/execution-plan.json
```

With three coordinators and a 16-slot session, the deterministic allocation is
five slots per coordinator: four unit workers and one coordinator, with one
slot reserved for the global coordinator. Run the same command for the other
two disjoint build roots using unique IDs. Merge only validated handoff
records after all unit-level checks; never use the registry as a mutable work
queue.

## 7. Use the evaluated default

Omitting `--quality-mode` now uses the bundled, completed four-lecture decision and selects `standard`:

```bash
python scripts/plan_execution.py \
  --unit lecture-09 --output-dir build/units
```

Pass `--quality-mode fast|standard|strict` for an explicit override, or `--default-decision PATH` to use a newer compatible offline decision.

## 8. Preserve an indexing convention and hidden-text boundary

When EvidencePlan selects a CNN kernel convention such as `w[c_out,c_in,:,:]`, carry it into a structured formula or concept with its page citation and include a notation exercise when pedagogically relevant. If the PDF also contains a hidden book-text layer, state in `limitations` that only visible slide content supports learner-facing claims. Do not replace the visible convention with hidden text even when the hidden layer is easier to parse.
