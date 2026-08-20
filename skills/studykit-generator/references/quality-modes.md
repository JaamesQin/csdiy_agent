# Quality modes and review contract

`quality_mode` controls authoring and visual-review depth. `delivery_policy` controls whether explicit unresolved items can be delivered. They are independent.

| Mode | Semantic passes | Visual pages | Audit and repair |
| --- | --- | --- | --- |
| `fast` | At most two: jointly author 01–03, then audit/repair 04 | identity, every final formula, theorem/strong-claim, and risk pages (hidden text, garbling, replacement characters, low extraction); do not scan unrelated candidates | one targeted audit/repair pass |
| `standard` | separate 01, 02, 03, 04 stages | fast set, EvidencePlan candidates, plus a source-hash deterministic 20% sample of remaining candidates (min 3, max 10) | one independent audit; at most one repair per affected stage |
| `strict` | full separate stages | every `needs_host_vision` page and every final formula page | independent audit; re-audit all repaired blockers; remaining blocker fails delivery |

All modes share hard gates:

- visually verify every formula retained in the final StudyKit;
- represent uncertainty as `formula_unresolved` with its image and anchor;
- require every citation anchor to exist;
- keep candidate JSON, final JSON, and YAML semantically equal;
- require successful validation and review-validation reports fingerprint-bound to the current artifacts;
- never use hidden text as evidence for a learner-facing claim.

The selector is `review-pages-v1`. Run `scripts/plan_execution.py` before authoring and populate `review-plan.json` with `scripts/workflow_policy.py` semantics. The bundled completed decision selects `standard`; callers may provide a newer decision artifact or explicitly override the mode.

## Standard authoring emphasis

The release benchmark showed that more page review was not the main opportunity. In the standard prompt and independent audit, explicitly check:

1. decoded LaTeX uses a single command backslash and remains renderable after JSON round-trip;
2. EvidencePlan formula and notation requirements survive into structured final fields, including channel/tensor indices;
3. ambiguous handwriting has a page-specific `formula_unresolved` object rather than only a prose caveat;
4. any detected hidden overlay produces an explicit visible-source boundary statement and never supports a claim;
5. exercises cover source-specific notation when it is a learning objective.

6. every practice question is checked against its mapped requirement/concept
   and source chunks: the setting is specified, the task is directly
   answerable, the expected result is observable, and the question is not a
   generic invitation for the learner to invent an example;
7. `hint`, `expected_evidence`, and evaluation criteria are specific to that
   question, and any transfer or boundary condition is supported by the cited
   material and clearly labeled as a teaching transfer when appropriate.

For standard authoring, the coordinator must complete this content-to-practice
checkpoint before accepting `03-practice-flow.json`. The independent auditor
then rechecks every practice item after reading the relevant content and
chunks. This is a semantic review requirement, not a requirement to render all
source pages visually.

Treat these as targeted representation improvements. Do not expand standard into strict or review extra unrelated pages merely to satisfy them.

`generation_policy` remains a deprecated compatibility alias: `draft` maps to `delivery_policy: draft`; legacy `strict` maps to `delivery_policy: publish`. It never selects visual-review depth.
