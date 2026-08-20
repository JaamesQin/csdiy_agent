# MIT 6.031 Spring 2022 source review

## Selection

The selected offering is MIT 6.031 Software Construction, Spring 2022, the
latest completed canonical 6.031 archive verified during this run:

- Homepage and official reading index: <https://web.mit.edu/6.031/www/sp22/>
- Research record: [mit-6-031-offering-research-20260812.md](research/mit-6-031-offering-research-20260812.md)
- Download inventory: `data/raw/mit-6.031/spring-2022/source-inventory.json`
- Prepared-material record: `data/raw/mit-6.031/spring-2022/prepared-materials.json`
- Catalog manifest: [mit-6-031-spring-2022.yaml](../data/manifests/mit-6-031-spring-2022.yaml)

The archive reports final grades submitted on 2022-05-19. Spring 2021 was
checked as an older fallback; MIT OCW 6.005 Spring 2016 was checked as a
licensed predecessor, not substituted for canonical 6.031.

## Evidence classification

The primary instructional evidence is a complete sequence of 29
staff-authored HTML readings, in the official homepage order. No separate
public lecture-video or slide corpus was established. The HTML pages are
ingested with heading anchors using `studykit-ingest-v0.1.0`; they are not
represented as PDF pages.

The source archive does not state an artifact-level redistribution licence.
Local processing is therefore retained with `license_status:
unknown_artifact_scope` and `redistribution_allowed: false`.

Problem sets, project code, quizzes/solutions, student submissions, grade
systems, and video binaries are metadata-only or excluded. No assessed answer
material is used as learner evidence.

## Automated reconciliation

- 29/29 official readings downloaded and hashed.
- 29/29 prepared HTML sources have one material set and one chunks file.
- 58 heading-anchored chunks generated; 0 empty chunks and 0 parser warnings.
- Inventory SHA-256: `082217fd13f0503d344ced350d851549fbc5b76be4e04f5ee467b8352d56f3aa`.
- StudyKit generation has not started in this source-review checkpoint.

The next checkpoint is a portable-v0.2.1 standard StudyKit build. Every new
unit must receive an independent semantic audit of its practices as well as
structural, citation, formula, hidden-text, and review validation.
