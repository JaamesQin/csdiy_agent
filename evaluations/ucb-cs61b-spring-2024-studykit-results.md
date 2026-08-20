# UCB CS61B Spring 2024 StudyKit results

Evaluation date: 2026-08-11

## Canonical result

| Check | Result |
| --- | ---: |
| Canonical build | `a748c428609e7a5bc9f0697a06ae0d7fbd56e2469aaaba8f5b034121f2479ab1` |
| Portable pipeline | `portable-studykit-pipeline-v0.2.0` |
| Quality mode / delivery | `fast` / `draft` |
| Source-supported units | 40 |
| Validated units | 40/40 |
| Portable audit/review passed | 40/40 |
| Failed or pending units | 0 / 0 |
| Page chunks | 2,860 |
| Final selected/actual review pages | 1,314 |
| Provider/model API calls | 0 |

The canonical result is based only on this build’s 40 units; standard and fast checkpoints are not added together. Fast mode uses the contract’s single targeted audit/repair pass. Already-authorized, hash-matched units were adopted without duplicate authoring, while conflict/partial attempts remain preserved under ignored attempt directories for provenance; selected units also received separate independent cross-audits.

## Validation and audit gates

Every unit has candidate and final StudyKit artifacts, candidate/final validation, `review-validation.json`, and `metrics.json`. The course-level `course-summary.json`, `batch-summary.json`, `result.json`, and `finalization-report.json` all report `succeeded`, with no failed or pending units. Candidate/final/YAML semantic equality, citation anchors, practice policy, hidden-text leakage checks, formula provenance, and selected/actual page accounting were checked by the portable skill workflow. The root legacy-schema differences documented by the unit audits are compatibility notes, not portable-v0.2 failures.

## Source limitations

Lecture 34’s scheduled Google Slides deck requires authentication for anonymous access. It is represented by a clearly labeled deterministic PDF derived from the official Spring 2024 recording’s uncorrected English ASR captions; the missing deck was not bypassed or relabeled. Its derivation and hashes are recorded in the manifest and source review. Assessed materials, solutions, labs, and homework remain metadata-only/excluded.

## Reproducibility links

- Catalog manifest: `data/manifests/ucb-cs61b-spring-2024.yaml`
- Source review: `docs/ucb-cs61b-spring-2024-source-review.md`
- Parser/preflight: `evaluations/ucb-cs61b-spring-2024-parser-results.md`
- Local StudyKit index: `outputs/ucb-cs61b-spring-2024/a748c428609e7a5bc9f0697a06ae0d7fbd56e2469aaaba8f5b034121f2479ab1/STUDYKIT_INDEX.md`
- Course result: `outputs/ucb-cs61b-spring-2024/a748c428609e7a5bc9f0697a06ae0d7fbd56e2469aaaba8f5b034121f2479ab1/result.json`
- Registry audit: `evaluations/csdiy-catalog-registry-audit.json`
