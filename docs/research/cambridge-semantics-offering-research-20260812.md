# Cambridge Semantics of Programming Languages offering research

- canonical candidate: `cambridge-semantics-of-programming-languages`
- retrieval date: `2026-08-12`
- institution: University of Cambridge, Department of Computer Science and Technology
- research scope: official Cambridge pages and their directly linked public materials; no login, paywall, DRM, or access-control bypass
- output: offering research only; no StudyKit was generated

## Recommendation

推荐选择 **2025–26 (Lent, Part IB CST)** 作为主 offering：这是检索日之前最新的已完成官方学期，课程主页明确标为 2025–26、Lent、12 hours、in-person lectures；官方 materials 页面可无登录下载完整 lecture notes 和 slides，且材料标题页显示当前版本日期为 2026-02-12。课程大纲给出完整的 12-lecture 顺序（8 个主题块，主题块 lecture 数为 2+2+2+2+1+1+1+1）。

建议保留 **2023–24** 作为录播补充候选：其官方 materials 页逐项链接 Lecture 1–12，并链接公开 YouTube playlist；但它比 2025–26 旧，且录播是 YouTube 外部托管、没有在 Cambridge 页面上给出明确许可。若后续 authoring 需要视频证据，优先以 2025–26 notes/slides 为主，只有在确认视频可稳定下载、内容可逐讲核验且版权范围可接受时才把 2023–24 录播作为补充，不用它替代主 offering 的课程身份。

## Candidate inventory

| candidate | candidate URL | final URL(s) checked | completed-term evidence | notes / slides | recordings | status and decision |
|---|---|---|---|---|---|---|
| 2025–26 | <https://www.cl.cam.ac.uk/teaching/2526/Semantics/> | same; materials: <https://www.cl.cam.ac.uk/teaching/2526/Semantics/materials.html>; notes: <https://www.cl.cam.ac.uk/teaching/2526/Semantics/notes.pdf>; slides: <https://www.cl.cam.ac.uk/teaching/2526/Semantics/slides.pdf>; recordings: <https://www.cl.cam.ac.uk/teaching/2526/Semantics/video/> | Official page says “Course pages 2025–26”, Term: Lent, Part IB CST, and copyright footer © 2026. Lent teaching and the 2026-02-12 material timestamp precede the 2026-08-12 retrieval date. | `notes_kind=full_lecture_notes`; `notes_completeness=complete`; public, directly downloadable PDF, 136 pages. `slides` are also public/downloadable, 301 pages, complete for the published 12-lecture outline. | Official page says “No recordings available yet”; Moodle/Panopto is mentioned but requires institutional access and is not used. | **Recommended primary offering.** |
| 2024–25 | <https://www.cl.cam.ac.uk/teaching/2425/Semantics/> | same; materials: <https://www.cl.cam.ac.uk/teaching/2425/Semantics/materials.html>; notes: <https://www.cl.cam.ac.uk/teaching/2425/Semantics/notes.pdf>; slides: <https://www.cl.cam.ac.uk/teaching/2425/Semantics/slides.pdf>; recordings: <https://www.cl.cam.ac.uk/teaching/2425/Semantics/video/> | Official page says “Course pages 2024–25”, Term: Michaelmas, Part IB CST, and © 2025. | `notes_kind=full_lecture_notes`; `notes_completeness=complete`; public/downloadable, 132 pages. Slides public/downloadable, 291 pages; course materials page exposes both. | Official recordings page says “No recordings available yet”; only Moodle/Panopto is suggested. | **Strong fallback**, but older than 2025–26 and no public recordings. |
| 2023–24 | <https://www.cl.cam.ac.uk/teaching/2324/Semantics/> | same; materials: <https://www.cl.cam.ac.uk/teaching/2324/Semantics/materials.html>; notes: <https://www.cl.cam.ac.uk/teaching/2324/Semantics/notes.pdf>; slides: <https://www.cl.cam.ac.uk/teaching/2324/Semantics/slides.pdf>; playlist: <https://www.youtube.com/playlist?list=PL-2hPK7m5S3hVagseKDPxCBZEqg0PqZhs> | Official page says “Course pages 2023–24”, Term: Michaelmas, Part IB CST, and © 2024. | `notes_kind=full_lecture_notes`; `notes_completeness=complete`; public/downloadable, 132 pages. Slides public/downloadable, 291 pages. | Cambridge materials page links Lecture 1 through Lecture 12 individually and to the public YouTube playlist. Cambridge recordings page is the official pointer; the actual videos are YouTube-hosted. | **Recording supplement candidate**, not preferred primary offering. |
| 2022–23 | <https://www.cl.cam.ac.uk/teaching/2223/Semantics/> | same official archive page checked; no newer evidence used for selection | Official archive page identifies Course pages 2022–23 and the same Part IB course. | Page was checked as a historical fallback; not selected because newer completed offerings have equivalent or broader public evidence. | Not used as evidence for recommendation. | Historical fallback only. |
| 2021–22 | <https://www.cl.cam.ac.uk/teaching/2122/Semantics/> | same official archive page checked | Official archive page identifies Course pages 2021–22, Part IB CST, Michaelmas. | Page was checked as an older archive; not selected. | The page describes video lectures and in-person Q&A, but this was not selected or treated as a current public source set. | Historical fallback only. |

## Recommended offering structure and source coverage

The 2025–26 official syllabus order is:

1. **Introduction** — transition systems; structural operational semantics; a simple imperative language; language-design options (**2 lectures**).
2. **Types** — formal type systems; typing the simple imperative language; desirable properties (**2 lectures**).
3. **Induction** — mathematical and structural induction; abstract syntax trees; rule-based inductive definitions and proofs; type-safety proofs (**2 lectures**).
4. **Functions** — call-by-name and call-by-value; semantics and typing; local recursive definitions (**2 lectures**).
5. **Data** — products, sums, records, and references (**1 lecture**).
6. **Subtyping** — record subtyping and simple object encoding (**1 lecture**).
7. **Semantic equivalence** — equivalence of phrases, congruence, examples of equivalence/non-equivalence (**1 lecture**).
8. **Concurrency** — shared-variable interleaving; simple mutexes; serializability (**1 lecture**).

Total published lecture coverage: **12 lectures**. The official notes table of contents has the corresponding core chapters and exercises, plus appendices with OCaml, SML, and Java interpreter/type-checker implementations and proof guidance. The slides explicitly expose the same progression, including the core, subtyping/objects, semantic equivalence, and concurrency. Therefore the source coverage for the recommended offering is:

| source role | 2025–26 coverage | downloadable without login | use in future authoring |
|---|---|---:|---|
| syllabus/course page | identity, term, aims, objectives, ordered topic blocks | yes | identity and unit ordering |
| full lecture notes | all published topics, exercises, proof guidance, implementations | yes | primary instructional source |
| full slide deck | all published lecture topics and examples | yes | secondary/visual source; useful for page anchors |
| recordings | none on official public page | no | unavailable; do not invent units |
| implementations | OCaml, Java, SML links from course materials | yes | optional code examples, not a replacement for lecture evidence |
| past exams / solution notes | separate exam archive | public page, but not teaching evidence | exclude from source coverage and StudyKit evidence |

For 2023–24, the official page gives the same 12-lecture topic order, full notes and slides, plus one public recording link per lecture (Lecture 1–12). This confirms useful recording breadth but does not improve the primary offering’s freshness. It also does not establish redistribution rights for the YouTube recordings.

## Public, license, and material classification

- `notes_kind`: `full_lecture_notes` for 2025–26, 2024–25, and 2023–24.
- `notes_completeness`: `complete` for the published course outline: each selected term exposes the full notes PDF and full slide deck, and the syllabus has 12 lectures. This means complete published lecture-note coverage, not a claim that every classroom interaction or supervision is archived.
- `notes_public_status`: `public_no_login` for the Cambridge HTML pages and linked PDF notes/slides. 2023–24 YouTube videos are publicly reachable from the official materials page; Moodle/Panopto links are not counted as public evidence.
- `notes_license_status`: `unknown_artifact_scope` for notes, slides, implementations, and recordings. The pages carry Cambridge copyright/footer information but do not state a redistribution licence covering each linked artifact. Public download is not treated as redistribution permission.
- `redistribution_allowed`: `false` pending an explicit artifact-level licence or written authorization. Future ingestion may process the public sources locally under the applicable authorization policy, but must not publish copied PDFs, slides, or recordings.
- `past exam solutions`: explicitly excluded. Cambridge’s past-paper page distinguishes solution notes, including restricted notes; exam questions and solutions are assessment artifacts, not lecture teaching evidence.

## Blockers and follow-up

1. **Repository guide blocker.** The requested local guide `docs/编程语言设计与分析/Cambridge-Semantics.md` is absent from this worktree, although the registry records that path and the upstream public page URL. This report therefore uses the registry’s canonical candidate and the official Cambridge pages, but cannot verify guide-specific local instructions or source aliases. Restore/provide the guide before authoring.
2. **License blocker.** No explicit licence covering the individual PDFs, slides, implementation files, or YouTube recordings was found on the checked official pages. Keep `license_status=unknown_artifact_scope` and `redistribution_allowed=false`; obtain authorization or an explicit licence before creating distributable artifacts.
3. **Recording blocker for the recommended term.** 2025–26 has no public recordings. Moodle/Panopto is an institutional route and is not usable under the no-login requirement. This does not block a notes/slides-based offering, but it blocks any claim of complete 2025–26 recording coverage.
4. **No StudyKit action taken.** This task stops at offering research. No files under registry, manifests, or outputs were changed.

## Source log

- Cambridge 2025–26 course page: <https://www.cl.cam.ac.uk/teaching/2526/Semantics/>
- Cambridge 2025–26 materials: <https://www.cl.cam.ac.uk/teaching/2526/Semantics/materials.html>
- Cambridge 2025–26 notes PDF: <https://www.cl.cam.ac.uk/teaching/2526/Semantics/notes.pdf>
- Cambridge 2025–26 slides PDF: <https://www.cl.cam.ac.uk/teaching/2526/Semantics/slides.pdf>
- Cambridge 2025–26 recordings page: <https://www.cl.cam.ac.uk/teaching/2526/Semantics/video/>
- Cambridge 2024–25 course page: <https://www.cl.cam.ac.uk/teaching/2425/Semantics/>
- Cambridge 2024–25 materials: <https://www.cl.cam.ac.uk/teaching/2425/Semantics/materials.html>
- Cambridge 2024–25 recordings page: <https://www.cl.cam.ac.uk/teaching/2425/Semantics/video/>
- Cambridge 2023–24 course page: <https://www.cl.cam.ac.uk/teaching/2324/Semantics/>
- Cambridge 2023–24 materials: <https://www.cl.cam.ac.uk/teaching/2324/Semantics/materials.html>
- Cambridge 2023–24 recordings page: <https://www.cl.cam.ac.uk/teaching/2324/Semantics/video/>
- Cambridge past-paper archive (not used as teaching evidence): <https://www.cl.cam.ac.uk/teaching/exams/pastpapers/t-SemanticsofProgrammingLanguages.html>
- Registry provenance for the missing guide path and original candidate link: `data/catalog/csdiy-course-registry.yaml` (read-only; not modified).
