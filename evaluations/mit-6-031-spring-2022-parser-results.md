# MIT 6.031 Spring 2022 parser results

## Input and parser

The 29 official Spring 2022 staff-authored HTML readings were copied
verbatim into `data/raw/mit-6.031/spring-2022/prepared/` and ingested with
the portable StudyKit material ingester (`studykit-ingest-v0.1.0`). The source
type is HTML, so anchors are headings rather than PDF pages.

## Results

| Metric | Result |
| --- | ---: |
| Official reading units | 29 |
| Prepared sources | 29 |
| Chunk files | 29 |
| Chunks | 58 |
| Empty chunks | 0 |
| Parser warnings | 0 |
| Formula candidates | 0 |
| Failed ingestion reports | 0 |

All ingestion reports under
`data/sources/mit-6-031-spring-2022/lecture-*/ingestion-report.json` report
`status: succeeded`. The catalog manifest and source inventory record the
same unit order, source hashes, chunk paths, and counts.

## Scope and follow-up

This is an automated parser/preparation result, not a StudyKit quality pass.
The standard build must still validate candidate/final/YAML parity, source
anchors, review plans, and hidden-text/formula handling. A distinct auditor
must also review every new practice item for concrete answerability,
content-grounding, formative scope, and real heading anchors. Existing
practice defects in older builds are outside this round's repair scope.
