# StudyKit offline benchmark

This repository-side tool compares Codex fast, standard, strict, and existing DeepSeek artifacts without entering the skill's generation path. It never calls a model or reads provider credentials.

Normalize each artifact with its source PDF SHA256 and lecture ID. Store the private mapping from anonymous ID to system/mode separately from scorer inputs. The anonymous object exposes only common semantic fields: claims, formulas, objectives, practice, limitations, anchors, duration, and tokens.

Score all anonymous samples against `gold-rubric.json`. Category maxima total 100. Record Critical/Major/Minor separately; any Critical makes a sample ineligible regardless of score. An independent model scores all samples. Humans review every Critical, every inter-rater difference over 10 points, and a reproducible 20% sample.

Run each mode once. Only generation failures, Critical findings, or fast/standard boundary cases may receive up to two additional lecture/mode runs. Aggregate reruns by majority outcome and mean metrics, then feed one aggregate record per lecture/mode to `benchmark.py decide`. Do not create a default decision until all four fast and standard lecture records are present.

The authoritative v0.2.0 run is `runs/four-lecture-aligned-v2-2026-08-09`. It selected `standard` as the release default. Its remaining deductions are primarily representation quality—decoded LaTeX escaping, page-specific unresolved records, retained index conventions, and explicit visible-versus-hidden evidence boundaries—not a release veto. Critical precedence and the skill's deterministic delivery gates remain unchanged.
