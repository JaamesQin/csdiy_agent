# Input and output contract

## Inputs

| Field | Required | Default | Meaning |
| --- | --- | --- | --- |
| `materials[]` or URLs | yes | — | Any number of authorized source files or public HTTP(S) resources |
| `output_dir` | yes | — | A new build directory or a matching resumable build |
| `language` | no | `zh-CN` | Learner-facing language |
| `target_minutes` | no | `180` per unit | Target learning time |
| `quality_mode` | no | `standard` | `fast`, `standard`, or `strict`; the bundled four-lecture non-inferiority decision supplies the default |
| `delivery_policy` | no | `draft` | `draft` permits explicit unresolved warnings; `publish` blocks them |
| `generation_policy` | deprecated | — | compatibility alias: `draft` or legacy `strict`; controls delivery only |
| `parallel_units` | no | `auto` | `auto`, `off`, or `1..4` |
| `scope` | no | `private` | `public` or `private` |
| `owner_id` | private only | `local-user` | Isolation key; null for public sources |
| course identity | no | null | Trusted course ID, version, title, and known units |

Never accept provider, endpoint, model, API-key, or retry configuration as authoring inputs. The host Agent is the author.

## Build tree

```text
build/
├── result.json
├── run.json
├── manifest.yaml
├── batch-summary.json
├── ingestion/
│   ├── ingestion-report.json
│   ├── chunks.jsonl
│   ├── formula-candidates.json
│   └── page-images/
└── courses/<course-id>/units/<unit-id>/
    ├── 01-evidence-plan.json
    ├── 02-learning-content.json
    ├── 03-practice-flow.json
    ├── 04-quality-audit.json
    ├── 04-quality-audit.resolution.json
    ├── review-plan.json
    ├── metrics.json
    ├── 05-studykit.json
    ├── studykit.yaml
    ├── studykit.md
    └── validation.json
```

Use `unknown-course` only as a filesystem label; keep unknown identity fields null inside artifacts. Hash a canonical inventory, quality mode, page-selector version, parser version, schema version, prompt version, and pipeline version into `build_id`. Do not hash concurrency.

## Result statuses

| Status | Meaning |
| --- | --- |
| `awaiting_materials` | No source was supplied |
| `ingestion_failed` | No usable anchored content was extracted |
| `partial` | At least one source or unit succeeded and another did not finish |
| `failed` | Authoring or validation failed with no deliverable unit |
| `succeeded` | Every requested unit validates |

Every non-success result must include `failed_stage`, structured `issues`, `retry_count`, `recoverable`, and `next_action`. A structured issue has `code`, `message`, `source` or `location`, and optional remediation.

## Resume rules

Reuse only artifacts whose build fingerprint, schema version, pipeline version, prompt version, and upstream artifact hashes match. Resume at the first absent or failed stage. When any version or input differs, create a new build instead of editing the old run in place.

## Release interpretation

The v0.2.0 benchmark selected `standard` and is sufficient for release. Missing peripheral unresolved markers, LaTeX escaping defects, or omitted notation metadata should be repaired when detected, but benchmark point deductions alone do not invalidate an otherwise schema-valid build. Existing hard gates remain authoritative: fabricated or unverified formulas, missing citation anchors, hidden-text evidence, semantic divergence across final formats, and publish-policy unresolved blockers prevent successful delivery.
