# MIT 6.031 offering research

审核日期：2026-08-12
Canonical candidate：`mit-6-031`
输入指南：`docs/软件工程/6031.md`（仓库中未找到；本次不补建、不推断其内容）
范围：offering research only；不生成 StudyKit，不修改 registry、manifests 或 outputs。

## 结论

建议将 **Spring 2022 (`sp22`)** 作为 `mit-6-031` 的首选已完成官方 offering 候选：MIT 的 canonical short URL [`https://mit.edu/6.031`](https://mit.edu/6.031) 当前重定向到 [`https://web.mit.edu/6.031/www/sp22/`](https://web.mit.edu/6.031/www/sp22/)，归档首页明确写有 Spring 2022、课程 staff、MWF 课时，并记录了 2022-05-19 的 project、Quiz 2 与 final grades 状态。这里选择的是“最新可验证已完成学期”，不是依据 `latest` 字样臆测当前学期。

Spring 2021 (`sp21`) 是可访问且已完成的次选对照；Spring 2016 的 6.005 是前身课程，并由 MIT OCW 提供较清晰的再分发许可，但课程编号、语言和模块顺序已明显不同，不应作为 `mit-6-031` 的 canonical offering。

## Offering comparison

| offering | notes_kind | completeness | public access | license status | recommendation |
| --- | --- | --- | --- | --- | --- |
| 6.031 Spring 2022 | MIT staff-authored HTML readings plus course pages; TypeScript | `complete` for the published reading/module sequence (29 readings, PS0–PS4, Star Battle, quizzes); no lecture-video/slide inventory established | Public archive pages and reading links resolve without course login; Google Calendar link is public-facing but not a stable text inventory | `unconfirmed/restricted`: staff archive does not state a reuse license; collaboration policy says starter problem-set/project code is staff copyright and derived solutions may not be publicly redistributed | **Primary candidate** |
| 6.031 Spring 2021 | MIT staff-authored HTML readings plus course pages; Java | `complete` for the published reading/module sequence (30 readings, PS0–PS4, Star Battle, quizzes); no lecture-video/slide inventory established | Public archive pages and reading links resolve; some historical live-class links are not needed for the self-study source set | `unconfirmed/restricted`: same no-public-sharing and staff-copyright restriction is explicit | Secondary comparison / fallback |
| 6.005 Spring 2016 (MIT OCW) | MIT staff-authored HTML readings and OCW course pages; Java | `complete` for OCW-published course sequence (27 sessions, PS0–PS4, ABC Music Player project, two quizzes); not a 6.031-semester identity | Public OCW course, syllabus, calendar, readings, assignments and quizzes pages | `confirmed at OCW course level`: CC BY-NC-SA 4.0; linked/embedded third-party material and staff-course restrictions must still be checked separately | Licensed fallback/reference, not canonical |

Evidence: [Spring 2022 archive](https://web.mit.edu/6.031/www/sp22/), [Spring 2021 archive](https://web.mit.edu/6.031/www/sp21/), [semester archive index](https://web.mit.edu/6.031/www/sp22/general/previous-semesters.html), [OCW 6.005 course page](https://ocw.mit.edu/courses/6-005-software-construction-spring-2016/), [OCW license link](https://creativecommons.org/licenses/by-nc-sa/4.0/).

## Spring 2022: primary candidate

### Identity and completion evidence

- Official title: **6.031: Software Construction**, Spring 2022; course staff and MWF 11:00–12:30 are stated on the archive homepage.
- The homepage reports that project grades/feedback were available, Quiz 2 had been graded, and final grades had been submitted on 2022-05-19. This is sufficient evidence that the offering is completed.
- The archive index lists Spring 2022 above Spring 2021 and older 6.031/6.005 offerings. The canonical short URL resolves to this same Spring 2022 archive; no newer completed 6.031 semester was found in the official archive during this review.

### Module / reading order and coverage

The published order is 29 staff-authored readings:

1. Static Checking; 2. Basic TypeScript; 3. Testing; 4. Code Review; 5. Version Control; 6. Specifications; 7. Designing Specifications; 8. Mutability & Immutability; 9. Avoiding Debugging; 10. Abstract Data Types; 11. Abstraction Functions & Rep Invariants; 12. Interfaces, Generics, & Enums; 13. Debugging; 14. Recursion; 15. Equality; 16. Map, Filter, Reduce; 17. Recursive Data Types; 18. Regular Expressions & Grammars; 19. Parsers; 20. Callbacks & Graphical User Interfaces; 21. Concurrency; 22. Promises; 23. Mutual Exclusion; 24. Message Passing; 25. Networking; 26. Little Languages I; 27. Little Languages II; 28. Ethical Software Engineering; 29. Team Version Control.

The same page exposes Getting Started material, Problem Sets 0–4 (Turtle Graphics, Flashcards, Cityscape, Memely, Memory Scramble), the **Star Battle** project, Quiz 1/2 and a quiz archive. Thus the public HTML is broad enough for a module-indexed self-study source inventory, but it is not evidence of a complete lecture-recording or slide corpus. The linked calendar redirects to a Google Calendar and should be captured as schedule metadata only, not treated as a stable lecture transcript.

### Public access and redistribution boundary

The archive pages and reading pages are publicly reachable. Public reachability is not a redistribution license. The [Spring 2022 collaboration policy](https://web.mit.edu/6.031/www/sp22/general/collaboration.html) states that course staff code may be used by students but may not be publicly shared without permission; it specifically says starter problem-set and project code is copyrighted by course staff and that derived solutions may not be publicly distributed. Therefore:

- include only staff-authored explanatory HTML/readings in a future source review, subject to attribution and a separate copyright decision;
- do not ingest or reproduce student solutions, submitted code, answer keys, or derived project implementations;
- keep problem/project metadata only as excluded metadata (title, existence, and high-level learning role), not as copied graded content;
- mark the offering `public_access: yes`, `license: unconfirmed`, `redistribution: restricted/permission required`.

### Exclusions

Excluded from any future StudyKit source set: quiz solutions and answer keys, problem-set solutions or student submissions, project starter/solution code, grade reports, Piazza/Gradescope/Omnivore content, and authenticated course-service links. The archive itself visibly links to quiz solutions and grade systems, so link presence must not be confused with approval to reproduce them.

## Spring 2021: comparison offering

The [Spring 2021 archive](https://web.mit.edu/6.031/www/sp21/) is also a completed official offering: its homepage records final grades submitted on 2021-05-28 and identifies the term as Spring 2021. Its published order has 30 readings and differs materially from 2022: Java rather than TypeScript, and separate readings for Programming with ADTs, Thread Safety, Locks & Synchronization, Queues & Message-Passing, and Sockets & Networking. It exposes PS0–PS4, the Star Battle project, and Quiz 1/2/archive.

The [Spring 2021 collaboration policy](https://web.mit.edu/6.031/www/sp21/general/collaboration.html) has the same essential boundary: student/coursework materials are not to be publicly shared, and staff copyright does not permit public redistribution of derived problem-set or project solutions without permission. Record this offering as `public_access: yes`, `notes_kind: staff_authored_html`, `completeness: complete_for_published_reading_sequence`, `license: unconfirmed`, and `redistribution: restricted`.

## OCW Spring 2016: licensed predecessor/reference

MIT’s [OCW 6.005 Software Construction page](https://ocw.mit.edu/courses/6-005-software-construction-spring-2016/) identifies the course as Spring 2016, taught by Robert Miller and Max Goldman. The [OCW syllabus](https://ocw.mit.edu/courses/6-005-software-construction-spring-2016/pages/syllabus/) describes two 90-minute meetings plus one one-hour meeting weekly, readings with no textbook, weekly programming exercises, and a larger group project. The [OCW calendar](https://ocw.mit.edu/courses/6-005-software-construction-spring-2016/pages/calendar/) gives the ordered 27-session sequence, from Static Checking and Basic Java through Team Version Control; the OCW [homepage HTML](https://ocw.mit.edu/ans7870/6/6.005/s16/index.html) exposes the corresponding reading pages.

Coverage is complete for the OCW-published sequence: 27 sessions, five problem sets, the ABC Music Player project, and two quizzes. The [OCW quizzes page](https://ocw.mit.edu/courses/6-005-software-construction-spring-2016/pages/quizzes/) explicitly lists quiz PDFs and separate solution PDFs. Those solution PDFs, problem-set answers, project implementations, and any answer-bearing artifacts are excluded from future learner content.

The OCW page links to the [Creative Commons BY-NC-SA 4.0 license](https://creativecommons.org/licenses/by-nc-sa/4.0/). That permits sharing and adaptation with attribution, noncommercial use, and ShareAlike, but the license page itself cautions that other rights can apply. Apply the license only to material covered by OCW’s own notice; do not assume that external readings, embedded third-party works, or course-staff restrictions inherit OCW’s permission. This makes OCW suitable as a licensed fallback/reference, not a reason to collapse the 2016 predecessor into the 2022 `mit-6-031` identity.

## Source-selection record

For a later offline authoring run, the safe first-pass source scope is the public, staff-authored explanatory reading HTML from Spring 2022, with the course page used for identity and ordering. Preserve source URLs and term identity separately. Do not use the `latest` redirect as a version field without retaining the resolved URL and completion evidence. Do not fetch or redistribute graded solutions, student work, project code, grade systems, or third-party linked readings unless their permissions are independently established.

No StudyKit, manifest, registry entry, or output artifact was generated by this research.
