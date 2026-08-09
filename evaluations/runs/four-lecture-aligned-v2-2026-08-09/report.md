# Four-lecture aligned Codex evaluation

All 12 Codex StudyKits were independently regenerated for Lectures 2, 3, 4, and 8 under fast, standard, and strict workflows. Generation workers did not receive the gold rubric or prior scores. All candidate/final/YAML consistency, citation, schema, and review-contract checks passed after legacy metadata fields were normalized.

| Mode | L2 | L3 | L4 | L8 | Mean | Decision time |
|---|---:|---:|---:|---:|---:|---:|
| fast | 91 | 74 | 69 | 89.667 | 80.917 | 710.304 s |
| standard | 96 | 82 | 75 | 98 | 87.750 | 702.961 s |
| strict | 84 | 91 | 71 | 97 | 85.750 | 847.342 s |

Fast L8 is the mean of three blind attempts (74, 97, 98). Attempt 1 had one confirmed Critical omission; attempts 2 and 3 had zero Critical, so the majority result is eligible. Decision timing likewise uses the mean of the three L8 attempts. Coordinator timing includes queue and message overhead and is summed unit cost, not parallel batch makespan.

The default is **standard**. Fast fails the quality non-inferiority thresholds (mean is 6.833 points below standard; L3 and L4 exceed the per-lecture margin), fails the 30% speed requirement, and produced a non-majority but real formula omission in one attempt. Strict remains available explicitly for submission/publish use.

## Release decision

v0.2.0 is approved for release with `standard` as its bundled default. Standard's remaining deductions are non-blocking improvement targets: prevent decoded LaTeX double escaping, emit page-specific `formula_unresolved` records, retain EvidencePlan indexing conventions, and explicitly distinguish visible slides from hidden overlay text. The authoring and audit instructions were updated for these cases without increasing the standard page-review set.

The initial aligned run is excluded because several modes were authored inside a shared worker turn, making its per-mode timings invalid. Only V2 independent-turn outputs are authoritative.
