# CSDIY selected course status

This file is generated from `data/catalog/csdiy-course-registry.yaml`; the registry is the source of truth. It records reproducible catalog progress, not authorization to publish materials into the online StudyKitStore.

> 2026-08-12 archive note: ignored `outputs/` checkpoints were consolidated into the separate ignored `storage/studykits.sqlite3` archive and then removed. The tracked import/prune records are `evaluations/studykit-archive-import-20260812.json` and `evaluations/studykit-outputs-prune-20260812.json`. Existing output-index links below are historical provenance, not live files; all 286 archived documents remain `validated_draft`, not online-ready.

- Pinned upstream commit: `81d874ee0fb37b2289839847026ba7651f3725d5`
- Retrieval time: `2026-08-09T22:00:48+00:00`
- Markdown nav leaves: **135**
- Course nav leaves: **112**
- Excluded nav leaves: **23**
- Canonical course-target denominator: **119**
- Last registry reconciliation: `2026-08-12T11:48:18+00:00`
- Reconciliation command: `.venv/bin/python scripts/audit_csdiy_registry.py --registry data/catalog/csdiy-course-registry.yaml --repository-root . --report evaluations/csdiy-catalog-registry-audit.json --update`
- Tracked records: registry, manifests, source reviews, evaluations, reviewed packages and this status projection. Ignored local checkpoints: `data/raw/`, `data/sources/`, `outputs/` and private data.

## State counts

| State | Targets |
| --- | ---: |
| `authoring` | 11 |
| `chunked` | 1 |
| `classified` | 106 |
| `complete` | 1 |

## Direction coverage

| Direction | Targets |
| --- | ---: |
| `architecture` | 4 |
| `artificial_intelligence` | 7 |
| `compilers` | 6 |
| `data_structures_algorithms` | 6 |
| `databases` | 5 |
| `discrete_mathematics_probability` | 9 |
| `distributed_systems` | 3 |
| `graphics_vision` | 6 |
| `machine_learning` | 25 |
| `networks` | 2 |
| `numerical_scientific_computing` | 2 |
| `operating_systems` | 4 |
| `other_computing` | 4 |
| `programming_foundations` | 17 |
| `programming_languages` | 4 |
| `security` | 6 |
| `software_engineering` | 3 |
| `systems` | 6 |

## Selected courses and leading candidate

| ID | Direction | State | Term/build | Units/chunks | Gaps/visual | Validation/review | Records | Next action |
| --- | --- | --- | --- | ---: | --- | --- | --- | --- |
| `cambridge-semantics-of-programming-languages` | `programming_languages` | `complete` | 2025-26 / `ff5d60747dbcc5327685c3d81764165550c388874a7472ed478882443ead9c01` | 12 / 96 | 0 / `not recorded` | `12/12 units validated; 12/12 audited; registry_reconciliation` | [manifest](../data/manifests/cambridge-semantics-of-programming-languages-2025-26.yaml) · [review](cambridge-semantics-of-programming-languages-2025-26-source-review.md) · [parser](../evaluations/cambridge-semantics-of-programming-languages-2025-26-parser-results.md) · [StudyKit index](../outputs/cambridge-semantics-of-programming-languages-2025-26/ff5d60747dbcc5327685c3d81764165550c388874a7472ed478882443ead9c01) | complete |
| `cmu-15-213` | `systems` | `authoring` | summer-2026 / `40bd4156f8432f731a6dce34d04cd3cdf7e198a7c754d1533131b7e7754938f6` | 24 / 1441 | 24 / `not recorded` | `24/24 units validated; 18/24 audited; registry_reconciliation` | [manifest](../data/manifests/cmu-15.213-summer-2026.yaml) · [review](cmu-15.213-summer-2026-source-review.md) · [parser](../evaluations/cmu-15.213-summer-2026-parser-results.md) · [StudyKit index](../outputs/cmu-15.213-summer-2026/40bd4156f8432f731a6dce34d04cd3cdf7e198a7c754d1533131b7e7754938f6) | complete_independent_audit_for_units:lecture-01,lecture-02,lecture-05,lecture-08,lecture-22,lecture-23 |
| `mit-6-031` | `software_engineering` | `authoring` | spring-2022 / `41c40de8c5e32a2fc6d4243c8e130a76e75640f0d2352980a395db1f99f8af1e` | 29 / 58 | 113 / `not recorded` | `2/29 units validated; 1/29 audited; registry_reconciliation` | [manifest](../data/manifests/mit-6-031-spring-2022.yaml) · [review](mit-6-031-spring-2022-source-review.md) · [parser](../evaluations/mit-6-031-spring-2022-parser-results.md) | complete_independent_audit_for_units:lecture-02,lecture-03,lecture-04,lecture-05,lecture-06,lecture-07,lecture-08,lecture-09,lecture-10,lecture-11,lecture-12,lecture-13,lecture-14,lecture-15,lecture-16,lecture-17,lecture-18,lecture-19,lecture-20,lecture-21,lecture-22,lecture-23,lecture-24,lecture-25,lecture-26,lecture-27,lecture-28,lecture-29 |
| `mit-6-042j` | `discrete_mathematics_probability` | `authoring` | spring-2024 / `1db4a3a7fee047565818f331b9bc809fd00b9036ce97826a0cafcf29049c53ce` | 24 / 217 | 55 / `no_parser_risk_pages` | `24/24 units validated; 0/24 audited; registry_reconciliation` | [manifest](../data/manifests/mit-6-042j-spring-2024.yaml) · [review](mit-6-042j-spring-2024-source-review.md) · [parser](../evaluations/mit-6-042j-spring-2024-parser-results.md) · [StudyKit index](../outputs/mit-6-042j-spring-2024/1db4a3a7fee047565818f331b9bc809fd00b9036ce97826a0cafcf29049c53ce) | create_fingerprinted_practice_repair_build |
| `mit-6-7960` | `machine_learning` | `authoring` | fall-2024 / `portable-v0.1.0` | 23 / 1420 | 115 / `not recorded` | `23/23 units validated; 0/23 audited; registry_reconciliation` | [manifest](../data/manifests/mit-6.7960-fall-2024.yaml) · [review](mit-6.7960-fall-2024-source-review.md) · [parser](../evaluations/mit-6.7960-fall-2024-parser-results.md) · [StudyKit index](../data/reviewed/mit-6.7960-fall-2024/portable-v0.1.0) | complete_independent_audit_for_units:lecture-01,lecture-02,lecture-03,lecture-04,lecture-05,lecture-06,lecture-07,lecture-08,lecture-09,lecture-10,lecture-11,lecture-12,lecture-13,lecture-14,lecture-15,lecture-16,lecture-17,lecture-18,lecture-19,lecture-20,lecture-21,lecture-23,lecture-24 |
| `mit-6-824` | `distributed_systems` | `chunked` | spring-2026 / `—` | 21 / 183 | 21 / `not recorded` | `0/21 units validated; 0/21 audited; registry_reconciliation` | [manifest](../data/manifests/mit-6-824-spring-2026.yaml) · [review](mit-6-824-spring-2026-source-review.md) · [parser](../evaluations/mit-6-824-spring-2026-parser-results.md) | complete_independent_audit_for_units:lecture-01,lecture-02,lecture-03,lecture-04,lecture-05,lecture-06,lecture-07,lecture-08,lecture-09,lecture-10,lecture-11,lecture-12,lecture-13,lecture-14,lecture-15,lecture-16,lecture-17,lecture-18,lecture-19,lecture-20,lecture-21 |
| `mit-6-s081` | `operating_systems` | `authoring` | fall-2021 / `portable-v0.2.0` | 24 / 587 | 96 / `not recorded` | `24/24 units validated; 0/24 audited; registry_reconciliation` | [manifest](../data/manifests/mit-6.s081-fall-2021.yaml) · [review](mit-6.s081-fall-2021-source-review.md) · [parser](../evaluations/mit-6.s081-fall-2021-parser-results.md) · [StudyKit index](../data/reviewed/mit-6.s081-fall-2021/portable-v0.2.0) | complete_independent_audit_for_units:lecture-01,lecture-02,lecture-03,lecture-04,lecture-05,lecture-06,lecture-07,lecture-08,lecture-09,lecture-10,lecture-11,lecture-12,lecture-13,lecture-14,lecture-15,lecture-16,lecture-17,lecture-18,lecture-19,lecture-20,lecture-21,lecture-22,lecture-23,lecture-24 |
| `ucb-cs168` | `networks` | `authoring` | spring-2026 / `d194c537857777cc12747610d694519d43545a1928ff50daa93f66051deaa8d0` | 26 / 1890 | 10 / `risk_pages_passed_final_citation_review_pending` | `26/26 units validated; 23/26 audited; registry_reconciliation` | [manifest](../data/manifests/ucb-cs168-spring-2026.yaml) · [review](ucb-cs168-spring-2026-source-review.md) · [parser](../evaluations/ucb-cs168-spring-2026-parser-results.md) · [StudyKit index](../outputs/ucb-cs168-spring-2026/d194c537857777cc12747610d694519d43545a1928ff50daa93f66051deaa8d0) | create_fingerprinted_practice_repair_build |
| `ucb-cs186` | `databases` | `authoring` | spring-2026 / `7e26cbe86e81324985a46ea0d9cfd694ce0d077351605da080d4eecd612c2fe0` | 20 / 293 | 16 / `no_parser_risk_pages` | `20/20 units validated; 14/20 audited; registry_reconciliation` | [manifest](../data/manifests/ucb-cs186-spring-2026.yaml) · [review](ucb-cs186-spring-2026-source-review.md) · [parser](../evaluations/ucb-cs186-spring-2026-parser-results.md) · [StudyKit index](../outputs/ucb-cs186-spring-2026/7e26cbe86e81324985a46ea0d9cfd694ce0d077351605da080d4eecd612c2fe0) | create_fingerprinted_practice_repair_build |
| `ucb-cs188` | `artificial_intelligence` | `authoring` | spring-2026 / `132fad020d624070614235f6b2378fd5d9d5cd412a9acf00c4a6be8d6987c0f4` | 28 / 1204 | 16 / `risk_pages_passed_final_citation_review_pending` | `27/28 units validated; 21/28 audited; registry_reconciliation` | [manifest](../data/manifests/ucb-cs188-spring-2026.yaml) · [review](ucb-cs188-spring-2026-source-review.md) · [parser](../evaluations/ucb-cs188-spring-2026-parser-results.md) · [StudyKit index](../outputs/ucb-cs188-spring-2026/132fad020d624070614235f6b2378fd5d9d5cd412a9acf00c4a6be8d6987c0f4) | create_fingerprinted_practice_repair_build |
| `ucb-cs61a` | `programming_foundations` | `authoring` | summer-2026 / `09e38a57a95cfa256b6c3270013dc6fb6bf4dcba08d2191d11a7879b43a9b933` | 28 / 930 | 3 / `risk_pages_passed_final_citation_review_complete` | `28/28 units validated; 27/28 audited; registry_reconciliation` | [manifest](../data/manifests/ucb-cs61a-summer-2026.yaml) · [review](ucb-cs61a-summer-2026-source-review.md) · [parser](../evaluations/ucb-cs61a-summer-2026-parser-results.md) · [StudyKit index](../outputs/ucb-cs61a-summer-2026/09e38a57a95cfa256b6c3270013dc6fb6bf4dcba08d2191d11a7879b43a9b933) | create_fingerprinted_practice_repair_build |
| `ucb-cs61b` | `data_structures_algorithms` | `authoring` | spring-2024 / `a748c428609e7a5bc9f0697a06ae0d7fbd56e2469aaaba8f5b034121f2479ab1` | 40 / 2860 | 3 / `not recorded` | `40/40 units validated; 39/40 audited; registry_reconciliation` | [manifest](../data/manifests/ucb-cs61b-spring-2024.yaml) · [review](ucb-cs61b-spring-2024-source-review.md) · [parser](../evaluations/ucb-cs61b-spring-2024-parser-results.md) · [StudyKit index](../outputs/ucb-cs61b-spring-2024/a748c428609e7a5bc9f0697a06ae0d7fbd56e2469aaaba8f5b034121f2479ab1) | complete_independent_audit_for_units:lecture-20 |
| `ucb-cs61c` | `architecture` | `authoring` | spring-2026 / `12b1704ea45e2daca9b589b480185850638ca311835eede3f1cfc6ecffc82fd5` | 35 / 1240 | 13 / `no_parser_risk_pages` | `35/35 units validated; 31/35 audited; registry_reconciliation` | [manifest](../data/manifests/ucb-cs61c-spring-2026.yaml) · [review](ucb-cs61c-spring-2026-source-review.md) · [parser](../evaluations/ucb-cs61c-spring-2026-parser-results.md) · [StudyKit index](../outputs/ucb-cs61c-spring-2026/12b1704ea45e2daca9b589b480185850638ca311835eede3f1cfc6ecffc82fd5) | create_fingerprinted_practice_repair_build |

## Priority rationale

Execution order is breadth-first after the current work: finish the four seed courses, validate UCB CS61A as the programming on-ramp, then cover networks, databases, architecture, programming languages/compilers, security and foundational mathematics before adding near-duplicates.

| Cohort | Meaning |
| --- | --- |
| `batch-0-current-work` | MIT 6.7960, MIT 6.S081, CMU 15.213 and UCB CS61B; reuse existing evidence and builds. |
| `batch-1-programming-onramp` | UCB CS61A; candidate only until a completed official semester and public evidence are verified. |
| `breadth-before-depth` | Representative courses in currently uncovered directions. |
| `later-depth` | Additional courses after direction coverage improves. |

## All course targets

| Canonical ID | Direction | Cohort | State | Priority reason |
| --- | --- | --- | --- | --- |
| `aics` | `machine_learning` | `later-depth` | `classified` | 方向 machine_learning 已有代表课程，待完成宽度覆盖后再增加近邻课程。 |
| `amirkabir-university-of-technology-ap1400-2-advanced-programming` | `programming_foundations` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：programming_foundations；优先寻找稳定官方公开材料。 |
| `asu-cse365` | `security` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：security；优先寻找稳定官方公开材料。 |
| `asu-cse466` | `security` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：security；优先寻找稳定官方公开材料。 |
| `caltech-cs122` | `databases` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：databases；优先寻找稳定官方公开材料。 |
| `cambridge-semantics-of-programming-languages` | `programming_languages` | `breadth-before-depth` | `complete` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：programming_languages；优先寻找稳定官方公开材料。 |
| `cmu-10-414` | `machine_learning` | `later-depth` | `classified` | 方向 machine_learning 已有代表课程，待完成宽度覆盖后再增加近邻课程。 |
| `cmu-10-708` | `machine_learning` | `later-depth` | `classified` | 方向 machine_learning 已有代表课程，待完成宽度覆盖后再增加近邻课程。 |
| `cmu-10-714` | `machine_learning` | `later-depth` | `classified` | 方向 machine_learning 已有代表课程，待完成宽度覆盖后再增加近邻课程。 |
| `cmu-11-667` | `artificial_intelligence` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：artificial_intelligence；优先寻找稳定官方公开材料。 |
| `cmu-11-711` | `artificial_intelligence` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：artificial_intelligence；优先寻找稳定官方公开材料。 |
| `cmu-11-785` | `machine_learning` | `later-depth` | `classified` | 方向 machine_learning 已有代表课程，待完成宽度覆盖后再增加近邻课程。 |
| `cmu-11-868` | `artificial_intelligence` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：artificial_intelligence；优先寻找稳定官方公开材料。 |
| `cmu-15-213` | `systems` | `batch-0-current-work` | `authoring` | 已存在可复用的官方学期、manifest、分块或 reviewed/build checkpoint。 |
| `cmu-15-418` | `distributed_systems` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：distributed_systems；优先寻找稳定官方公开材料。 |
| `cmu-15-442` | `machine_learning` | `later-depth` | `classified` | 方向 machine_learning 已有代表课程，待完成宽度覆盖后再增加近邻课程。 |
| `cmu-15-445` | `databases` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：databases；优先寻找稳定官方公开材料。 |
| `cmu-15-462` | `graphics_vision` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：graphics_vision；优先寻找稳定官方公开材料。 |
| `cmu-15-642` | `machine_learning` | `later-depth` | `classified` | 方向 machine_learning 已有代表课程，待完成宽度覆盖后再增加近邻课程。 |
| `cmu-15-799` | `databases` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：databases；优先寻找稳定官方公开材料。 |
| `cmu-17-803` | `software_engineering` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：software_engineering；优先寻找稳定官方公开材料。 |
| `columbia-stat8201` | `machine_learning` | `later-depth` | `classified` | 方向 machine_learning 已有代表课程，待完成宽度覆盖后再增加近邻课程。 |
| `cornell-cs3110` | `programming_foundations` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：programming_foundations；优先寻找稳定官方公开材料。 |
| `cs571` | `other_computing` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：other_computing；优先寻找稳定官方公开材料。 |
| `cse234` | `machine_learning` | `later-depth` | `classified` | 方向 machine_learning 已有代表课程，待完成宽度覆盖后再增加近邻课程。 |
| `duke-duke-university-introductory-c-programming-specialization` | `programming_foundations` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：programming_foundations；优先寻找稳定官方公开材料。 |
| `ethz-ethz-computer-architecture` | `architecture` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：architecture；优先寻找稳定官方公开材料。 |
| `ethz-ethz-digital-design-and-computer-architecture` | `architecture` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：architecture；优先寻找稳定官方公开材料。 |
| `games101` | `graphics_vision` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：graphics_vision；优先寻找稳定官方公开材料。 |
| `games103` | `graphics_vision` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：graphics_vision；优先寻找稳定官方公开材料。 |
| `games202` | `graphics_vision` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：graphics_vision；优先寻找稳定官方公开材料。 |
| `harvard-cs50-ai` | `artificial_intelligence` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：artificial_intelligence；优先寻找稳定官方公开材料。 |
| `harvard-cs50p` | `programming_foundations` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：programming_foundations；优先寻找稳定官方公开材料。 |
| `harvard-cs50x` | `programming_foundations` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：programming_foundations；优先寻找稳定官方公开材料。 |
| `helsinki-haskell-mooc` | `programming_foundations` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：programming_foundations；优先寻找稳定官方公开材料。 |
| `helsinki-university-of-helsinki-full-stack-open-2022` | `other_computing` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：other_computing；优先寻找稳定官方公开材料。 |
| `hit-os-operating-system` | `operating_systems` | `later-depth` | `classified` | 方向 operating_systems 已有代表课程，待完成宽度覆盖后再增加近邻课程。 |
| `kaist-cs220` | `programming_foundations` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：programming_foundations；优先寻找稳定官方公开材料。 |
| `kaist-cs420` | `compilers` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：compilers；优先寻找稳定官方公开材料。 |
| `kaist-cs431` | `programming_foundations` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：programming_foundations；优先寻找稳定官方公开材料。 |
| `machine-learning-compilation` | `machine_learning` | `later-depth` | `classified` | 方向 machine_learning 已有代表课程，待完成宽度覆盖后再增加近邻课程。 |
| `mit-18-01` | `discrete_mathematics_probability` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：discrete_mathematics_probability；优先寻找稳定官方公开材料。 |
| `mit-18-02` | `discrete_mathematics_probability` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：discrete_mathematics_probability；优先寻找稳定官方公开材料。 |
| `mit-18-06` | `discrete_mathematics_probability` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：discrete_mathematics_probability；优先寻找稳定官方公开材料。 |
| `mit-18-330` | `numerical_scientific_computing` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：numerical_scientific_computing；优先寻找稳定官方公开材料。 |
| `mit-6-006` | `data_structures_algorithms` | `later-depth` | `classified` | 方向 data_structures_algorithms 已有代表课程，待完成宽度覆盖后再增加近邻课程。 |
| `mit-6-007` | `systems` | `later-depth` | `classified` | 方向 systems 已有代表课程，待完成宽度覆盖后再增加近邻课程。 |
| `mit-6-031` | `software_engineering` | `breadth-before-depth` | `authoring` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：software_engineering；优先寻找稳定官方公开材料。 |
| `mit-6-042j` | `discrete_mathematics_probability` | `breadth-before-depth` | `authoring` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：discrete_mathematics_probability；优先寻找稳定官方公开材料。 |
| `mit-6-046` | `data_structures_algorithms` | `later-depth` | `classified` | 方向 data_structures_algorithms 已有代表课程，待完成宽度覆盖后再增加近邻课程。 |
| `mit-6-050j` | `discrete_mathematics_probability` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：discrete_mathematics_probability；优先寻找稳定官方公开材料。 |
| `mit-6-092` | `programming_foundations` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：programming_foundations；优先寻找稳定官方公开材料。 |
| `mit-6-100l` | `programming_foundations` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：programming_foundations；优先寻找稳定官方公开材料。 |
| `mit-6-1600` | `security` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：security；优先寻找稳定官方公开材料。 |
| `mit-6-5940` | `machine_learning` | `later-depth` | `classified` | 方向 machine_learning 已有代表课程，待完成宽度覆盖后再增加近邻课程。 |
| `mit-6-7960` | `machine_learning` | `batch-0-current-work` | `authoring` | 已存在可复用的官方学期、manifest、分块或 reviewed/build checkpoint。 |
| `mit-6-824` | `distributed_systems` | `breadth-before-depth` | `chunked` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：distributed_systems；优先寻找稳定官方公开材料。 |
| `mit-6-858` | `security` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：security；优先寻找稳定官方公开材料。 |
| `mit-6-s081` | `operating_systems` | `batch-0-current-work` | `authoring` | 已存在可复用的官方学期、manifest、分块或 reviewed/build checkpoint。 |
| `mit-6-s184` | `artificial_intelligence` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：artificial_intelligence；优先寻找稳定官方公开材料。 |
| `mit-mit-missing-semester` | `programming_foundations` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：programming_foundations；优先寻找稳定官方公开材料。 |
| `mit-mit-web-development-course` | `other_computing` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：other_computing；优先寻找稳定官方公开材料。 |
| `mit-sysadmin-decal` | `programming_foundations` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：programming_foundations；优先寻找稳定官方公开材料。 |
| `neural-networks-zero-to-hero` | `artificial_intelligence` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：artificial_intelligence；优先寻找稳定官方公开材料。 |
| `nju-nju-compilers` | `compilers` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：compilers；优先寻找稳定官方公开材料。 |
| `nju-nju-os-operating-system-design-and-implementation` | `operating_systems` | `later-depth` | `classified` | 方向 operating_systems 已有代表课程，待完成宽度覆盖后再增加近邻课程。 |
| `nju-nju-softwareanalysis` | `programming_languages` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：programming_languages；优先寻找稳定官方公开材料。 |
| `nju-pku` | `programming_languages` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：programming_languages；优先寻找稳定官方公开材料。 |
| `ntu-lhy` | `machine_learning` | `later-depth` | `classified` | 方向 machine_learning 已有代表课程，待完成宽度覆盖后再增加近邻课程。 |
| `nyu-dlsp21-nyu-deep-learning-spring-2021` | `machine_learning` | `later-depth` | `classified` | 方向 machine_learning 已有代表课程，待完成宽度覆盖后再增加近邻课程。 |
| `pku-coursera-nand2tetris` | `architecture` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：architecture；优先寻找稳定官方公开材料。 |
| `pku-pku-compilers` | `compilers` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：compilers；优先寻找稳定官方公开材料。 |
| `princeton-algorithms-i` | `data_structures_algorithms` | `later-depth` | `classified` | 方向 data_structures_algorithms 已有代表课程，待完成宽度覆盖后再增加近邻课程。 |
| `princeton-algorithms-ii` | `data_structures_algorithms` | `later-depth` | `classified` | 方向 data_structures_algorithms 已有代表课程，待完成宽度覆盖后再增加近邻课程。 |
| `sjtu-sjtu-compilers` | `compilers` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：compilers；优先寻找稳定官方公开材料。 |
| `sta4273` | `machine_learning` | `later-depth` | `classified` | 方向 machine_learning 已有代表课程，待完成宽度覆盖后再增加近邻课程。 |
| `stanford-coursera-machine-learning` | `machine_learning` | `later-depth` | `classified` | 方向 machine_learning 已有代表课程，待完成宽度覆盖后再增加近邻课程。 |
| `stanford-cs106b` | `programming_foundations` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：programming_foundations；优先寻找稳定官方公开材料。 |
| `stanford-cs106l` | `programming_foundations` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：programming_foundations；优先寻找稳定官方公开材料。 |
| `stanford-cs106x` | `programming_foundations` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：programming_foundations；优先寻找稳定官方公开材料。 |
| `stanford-cs110` | `systems` | `later-depth` | `classified` | 方向 systems 已有代表课程，待完成宽度覆盖后再增加近邻课程。 |
| `stanford-cs110l` | `programming_foundations` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：programming_foundations；优先寻找稳定官方公开材料。 |
| `stanford-cs142` | `other_computing` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：other_computing；优先寻找稳定官方公开材料。 |
| `stanford-cs143` | `compilers` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：compilers；优先寻找稳定官方公开材料。 |
| `stanford-cs144` | `networks` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：networks；优先寻找稳定官方公开材料。 |
| `stanford-cs148` | `graphics_vision` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：graphics_vision；优先寻找稳定官方公开材料。 |
| `stanford-cs149` | `distributed_systems` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：distributed_systems；优先寻找稳定官方公开材料。 |
| `stanford-cs224n` | `machine_learning` | `later-depth` | `classified` | 方向 machine_learning 已有代表课程，待完成宽度覆盖后再增加近邻课程。 |
| `stanford-cs224w` | `machine_learning` | `later-depth` | `classified` | 方向 machine_learning 已有代表课程，待完成宽度覆盖后再增加近邻课程。 |
| `stanford-cs229` | `machine_learning` | `later-depth` | `classified` | 方向 machine_learning 已有代表课程，待完成宽度覆盖后再增加近邻课程。 |
| `stanford-cs229m` | `machine_learning` | `later-depth` | `classified` | 方向 machine_learning 已有代表课程，待完成宽度覆盖后再增加近邻课程。 |
| `stanford-cs230` | `machine_learning` | `later-depth` | `classified` | 方向 machine_learning 已有代表课程，待完成宽度覆盖后再增加近邻课程。 |
| `stanford-cs231n` | `machine_learning` | `later-depth` | `classified` | 方向 machine_learning 已有代表课程，待完成宽度覆盖后再增加近邻课程。 |
| `stanford-cs242` | `programming_languages` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：programming_languages；优先寻找稳定官方公开材料。 |
| `stanford-cs346` | `databases` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：databases；优先寻找稳定官方公开材料。 |
| `stanford-ee364a` | `discrete_mathematics_probability` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：discrete_mathematics_probability；优先寻找稳定官方公开材料。 |
| `su-seed-labs` | `security` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：security；优先寻找稳定官方公开材料。 |
| `the-information-theory-pattern-recognition-and-neural-networks` | `discrete_mathematics_probability` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：discrete_mathematics_probability；优先寻找稳定官方公开材料。 |
| `ucb-cs126` | `discrete_mathematics_probability` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：discrete_mathematics_probability；优先寻找稳定官方公开材料。 |
| `ucb-cs161` | `security` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：security；优先寻找稳定官方公开材料。 |
| `ucb-cs162` | `operating_systems` | `later-depth` | `classified` | 方向 operating_systems 已有代表课程，待完成宽度覆盖后再增加近邻课程。 |
| `ucb-cs168` | `networks` | `breadth-before-depth` | `authoring` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：networks；优先寻找稳定官方公开材料。 |
| `ucb-cs169` | `software_engineering` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：software_engineering；优先寻找稳定官方公开材料。 |
| `ucb-cs170` | `data_structures_algorithms` | `later-depth` | `classified` | 方向 data_structures_algorithms 已有代表课程，待完成宽度覆盖后再增加近邻课程。 |
| `ucb-cs186` | `databases` | `breadth-before-depth` | `authoring` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：databases；优先寻找稳定官方公开材料。 |
| `ucb-cs188` | `artificial_intelligence` | `breadth-before-depth` | `authoring` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：artificial_intelligence；优先寻找稳定官方公开材料。 |
| `ucb-cs189` | `machine_learning` | `later-depth` | `classified` | 方向 machine_learning 已有代表课程，待完成宽度覆盖后再增加近邻课程。 |
| `ucb-cs285` | `machine_learning` | `later-depth` | `classified` | 方向 machine_learning 已有代表课程，待完成宽度覆盖后再增加近邻课程。 |
| `ucb-cs61a` | `programming_foundations` | `batch-1-programming-onramp` | `authoring` | 编程基础与抽象入口，能补足 CS61B 前置并连接后续课程；需先验证完成学期和公开证据。 |
| `ucb-cs61b` | `data_structures_algorithms` | `batch-0-current-work` | `authoring` | 已存在可复用的官方学期、manifest、分块或 reviewed/build checkpoint。 |
| `ucb-cs61c` | `architecture` | `breadth-before-depth` | `authoring` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：architecture；优先寻找稳定官方公开材料。 |
| `ucb-cs70` | `discrete_mathematics_probability` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：discrete_mathematics_probability；优先寻找稳定官方公开材料。 |
| `ucb-ee120` | `systems` | `later-depth` | `classified` | 方向 systems 已有代表课程，待完成宽度覆盖后再增加近邻课程。 |
| `ucb-ee16a` | `systems` | `later-depth` | `classified` | 方向 systems 已有代表课程，待完成宽度覆盖后再增加近邻课程。 |
| `ucb-ee16b` | `systems` | `later-depth` | `classified` | 方向 systems 已有代表课程，待完成宽度覆盖后再增加近邻课程。 |
| `ucb-ucb-data100-principles-and-techniques-of-data-science` | `numerical_scientific_computing` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：numerical_scientific_computing；优先寻找稳定官方公开材料。 |
| `umich-eecs498-007` | `machine_learning` | `later-depth` | `classified` | 方向 machine_learning 已有代表课程，待完成宽度覆盖后再增加近邻课程。 |
| `ustc-ustc-cg` | `graphics_vision` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：graphics_vision；优先寻找稳定官方公开材料。 |
| `ustc-ustc-compilers` | `compilers` | `breadth-before-depth` | `classified` | 代表当前四门课程尚未覆盖或覆盖较弱的方向：compilers；优先寻找稳定官方公开材料。 |

## Classification and global gate

- Independent classification audit: `succeeded`.
- Current global gate: `partial`; it cannot be `succeeded` while any real course target remains unresearched, incomplete, blocked or unaudited.
- Source gaps, access failures, vintage mismatches, license limits and academic-integrity exclusions belong in the registry target, manifest and course review; they must not be silently removed from the denominator.
