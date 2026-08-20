# CMU 15-213 Summer 2026 StudyKit results

Evaluation date: 2026-08-11

## Canonical result

| Check | Result |
| --- | ---: |
| Canonical build | `40bd4156f8432f731a6dce34d04cd3cdf7e198a7c754d1533131b7e7754938f6` |
| Portable pipeline | `portable-studykit-pipeline-v0.2.0` |
| Quality mode / delivery | `fast` / `draft` |
| Source-supported units | 24 |
| Validated units | 24/24 |
| Portable audit/review passed | 24/24 |
| Failed or pending units | 0 / 0 |
| Page chunks | 1,441 |
| Final selected/actual review pages | 1,020 |
| Provider/model API calls | 0 |

The canonical result is based only on this build’s 24 units; standard and fast checkpoints are not added together. Fast mode uses the contract’s single targeted audit/repair pass. Where a unit reused an already-authorized, hash-matched checkpoint, its provenance and prior audit history were preserved and the unit was not regenerated in place; selected units also received separate independent cross-audits.

## Validation and audit gates

Every unit has candidate and final StudyKit artifacts, candidate/final validation, `review-validation.json`, and `metrics.json`. The course-level `course-summary.json`, `batch-summary.json`, `result.json`, and `finalization-report.json` all report `succeeded`, with no failed or pending units. Candidate/final/YAML semantic equality, citation anchors, practice policy, hidden-text leakage checks, and formula provenance were checked by the portable skill workflow. The root legacy-schema differences documented by the unit audits are compatibility notes, not portable-v0.2 failures.

## Source limitations

The official schedule has two instructional rows without public lecture decks: May 15 has no linked material, and May 21 exposes only an activity and solution. They remain explicit source gaps in the tracked manifest/source review and were not fabricated into lecture units. The 24 generated units are exactly the public lecture-deck scope.

## Reproducibility links

- Catalog manifest: `data/manifests/cmu-15.213-summer-2026.yaml`
- Source review: `docs/cmu-15.213-summer-2026-source-review.md`
- Parser/preflight: `evaluations/cmu-15.213-summer-2026-parser-results.md`
- Local StudyKit index: `outputs/cmu-15.213-summer-2026/40bd4156f8432f731a6dce34d04cd3cdf7e198a7c754d1533131b7e7754938f6/STUDYKIT_INDEX.md`
- Course result: `outputs/cmu-15.213-summer-2026/40bd4156f8432f731a6dce34d04cd3cdf7e198a7c754d1533131b7e7754938f6/result.json`
- Registry audit: `evaluations/csdiy-catalog-registry-audit.json`
