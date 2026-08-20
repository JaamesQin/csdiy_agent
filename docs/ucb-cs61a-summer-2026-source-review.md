# UCB CS 61A Summer 2026 source review

This is the tracked source review for the current Summer 2026 offering. It is
separate from the historical Spring 2026 catalog/builds and from the
historical Summer candidate root `d937eda9177bdf02f912ddfcac50f059682d16e693fac8dacb8aed6448adbfc`.

## Offering identity

- `course_id`: `ucb-cs61a-summer-2026`
- `course_version`: `summer-2026`
- Official homepage/snapshot: <https://cs61a.org/>
- Evidence kind: official course-hosted lecture slides; completeness: substantial
- Selection rationale: the local snapshot is the newest completed official CS 61A offering available for this repair. All 28 prepared PDFs visibly contain `CS 61A SU26`; raw and prepared files are byte-identical under `identity-copy-v1`.
- Source inventory: `data/raw/ucb-cs61a/summer-2026/source-inventory.json` (`5656812a6d43a49b0a206baf176f336a7dd60871fe7f319154b588651df5e247`)
- Prepared inventory: `data/raw/ucb-cs61a/summer-2026/prepared-materials.json` (`286695c5a0f6a4173df7ff06a555c3021c210e72715e336b708335ac919da066`)
- Catalog manifest: `data/manifests/ucb-cs61a-summer-2026.yaml` (`c5a72bad3199ee1c9be08ffe17acd059a4d97f876326f0d3fa27fd7cf8e597a7`)

The visible PDF cover dates are **2026-06-22 through 2026-08-10**, not
2026-06-24 through 2026-07-29. The narrower date statement was not used to
rewrite the offering. The per-unit dates below are taken from the visible
first page and are retained in the manifest.

## Selected source inventory

All 28 rows are one prepared PDF, one source ID, and one material set. The
homepage and Composing Programs textbook are metadata/supplemental sources;
they are not mixed into the one-source-per-lecture generation inputs.

| Unit | Visible date | Title | Pages | Prepared SHA-256 |
|---|---|---|---:|---|
| lecture-01 | 2026-06-22 | Welcome Coding Environment Functions and Exceptions I | 43 | `a9498cacab8ad2558351759684ef98d8d2ac192a71f08a71c6757f121c51d3f4` |
| lecture-02 | 2026-06-23 | Control | 32 | `73e92a38f23f1d24a959f3e2da3ca8055fa85ba40a49411b1428d71f3d5c810f` |
| lecture-03 | 2026-06-24 | Higher-Order Functions | 31 | `6cdb574d1bf6675802f59c5d0a091993bfcceb1320764ab88aab6ed40c69305d` |
| lecture-04 | 2026-06-25 | Environments | 21 | `992bc410b738dbe7fae75bc0e11485c5d3a1bf8f025bb0840941406ba1ad548b` |
| lecture-05 | 2026-06-29 | Recursion | 33 | `a8ecb6609d2bbdecf0c3951f88f667256754e9f723486592d14625de82a42aa3` |
| lecture-06 | 2026-06-30 | Tree Recursion | 29 | `e3a8f959d47f1b84017262c365a11ef1c515617add08ab4088d7cb86590b2cbe` |
| lecture-07 | 2026-07-01 | Sequences and Containers | 34 | `573bb5ca13ff888fe266fe955a051f5876c65437047d55707e12c2a159c700ae` |
| lecture-08 | 2026-07-02 | Mutability and Data Abstraction | 40 | `db9ae68a4b94b2270a0d048cffe5ff723d122756fafbd8b50d4388e6895cd4d0` |
| lecture-09 | 2026-07-06 | Trees | 29 | `e5d6767e450832f5006b2563fa69a6cd3c2e0de279b52d6f0a8eb3ca209a46be` |
| lecture-10 | 2026-07-07 | Iterators and Generators | 39 | `861c46cf02cf9732dc0f16410de755d452e849933acfa2358d00a0a2351bd6d5` |
| lecture-11 | 2026-07-08 | Exceptions II | 39 | `cbc1940c68bb5cb9fdd9a9dbcdd748e9492b04eaa7cbff12fae5cf57bc0138ea` |
| lecture-12 | 2026-07-09 | Midterm Review | 10 | `1d2e173bad45dbd89a07d371f87051a5d2fa08722ee61ff1709eb0a06187b7d5` |
| lecture-13 | 2026-07-14 | Objects and Attributes | 26 | `c87afc8d79f6c9d6a09b4b6ac6125fb7295c3f6f78d9b3ffc59e124c1f70bf2b` |
| lecture-14 | 2026-07-15 | Inheritance and String Representation | 30 | `a8cbe4f31499c11b569dac2c0ca168fcc4df78a3d59c0e8bf6d17d30d98f8333` |
| lecture-15 | 2026-07-16 | Mutable Trees | 27 | `d4c40a34382e7f3bcb96529a27dabd856116c63b2b6f07b5cd58da10979ea780` |
| lecture-16 | 2026-07-20 | Linked Lists | 26 | `c36e6d65c90deedf36969881a2db963abbd06c15ac3be5837099afef642838e0` |
| lecture-17 | 2026-07-21 | Efficiency | 31 | `05ef2a9f281f41c54e1ef165d2287fbc12a8dcd100c992fa6c32b367823fe63f` |
| lecture-18 | 2026-07-22 | Scheme | 38 | `1ffdf0a2a73da81e8d4e2cb14a107685f9c6240658554ae30dfa73a3bc7fe8f2` |
| lecture-19 | 2026-07-23 | Scheme Lists | 31 | `eebfb4dd8f0d4b437a3365aec92783c02a6ddab7bb02fa062cf8eae39f05b6be` |
| lecture-20 | 2026-07-27 | Interpreters | 30 | `e0ef5d9f5541c5c240bf4ca6c054a34b301d45bafb29a2767d23f7eae4e6b935` |
| lecture-21 | 2026-07-28 | Tail Calls and Macros | 42 | `ed79eb3c77958fea76c225e33cdc4c14ba734dc99e87b99996af2455b2fc9bda` |
| lecture-22 | 2026-07-29 | SQL and Tables | 41 | `42393ab40a5f6f42d5387d09499c2f5d9989d948fc78935288e8ead9ac8584d6` |
| lecture-23 | 2026-07-30 | Aggregation and Databases | 34 | `46b2a769a79dc02b155e54c88a5f8e5ba6841e51e8b6a0bb2c158928b6df8a33` |
| lecture-24 | 2026-08-03 | AI Coding Tools | 45 | `9c581f3665402944c55b559df12cd8a5830a1792919959ecebfdd37a2aff317d` |
| lecture-25 | 2026-08-04 | Web Applications | 43 | `22790cd2457f97ea2ef2b4007418235443f661717814f23c91d5d1121319fed4` |
| lecture-26 | 2026-08-05 | Computer Security | 62 | `99be9f26827cef4ec5be0a808f74e043824086df999ce97ada5c8570eee5a8cb` |
| lecture-27 | 2026-08-06 | Final Review | 6 | `a8ce094516a09b903fca432ec56263f2bc0b7cecec37a0b68be684b6440ad577` |
| lecture-28 | 2026-08-10 | Conclusion and Ask Me Anything | 38 | `b2c770da3841b79ca8288a6ecd778de01fdffbf0c4942109af9f9dabc4b1c173` |

Totals: 28 PDFs, 930 pages/chunks, 28/28 visible `SU26` identities, 28/28
raw/prepared hash matches, 0 source gaps, and no empty chunks. Excluded linked
resources remain video binaries, labs, homework, projects, exams, and
solutions. Course-hosted slide redistribution permission is unknown, so this
is local processing only.

## Build boundary

- Parser: `pdf-page-v0.2`; schema: `schemas/source_chunk.schema.json`.
- Every chunk uses `course_id=ucb-cs61a-summer-2026`, `course_version=summer-2026`, the matching lecture ID, matching Summer source ID/material set, and one-based contiguous page anchors.
- Visual review remains pending in the current build. Formula candidates were not emitted by `build_course_chunks.py`; this is recorded as `formula_candidate_status: not_generated_by_build_course_chunks`, not as evidence that no formulas exist.
- Practice content was not changed; `practice_semantic_review=deferred_by_scope`.
- Spring 2026 `cdc`/`bdc` builds and the Summer `d937`/`056f` roots are not modified or relabeled.
