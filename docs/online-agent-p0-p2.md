# Online Agent P0–P2 contracts

Status: runtime foundations enabled; private MaterialSet and cross-system identity remain deferred.

The default `/v1/chat/completions` runtime now plans a bounded acyclic `TaskPlan` from the complete
message history. Only capability help, profile management, and authoring denial bypass model planning.
Tasks execute in dependency order; independent successes survive another task's failure, and blocked
tasks request only their missing fields. Catalog identities remain separate from online-ready StudyKit
identities.

Learner-visible claims use four provenance kinds: `course_material`, `catalog_metadata`,
`static_analysis`, and `general_knowledge`. An invalid course citation removes the complete course
material claim partition. A separately generated general explanation may remain, but is labeled
“通用知识（不代表当前课程材料）” and cannot establish course, version, unit, page, or quotation facts.

The public SourceChunk interface applies scope, course, unit, and page predicates in the FTS5 query
before BM25 ranking. Offline indexes accept only hash-valid, public, index-allowed chunks bound to
approved/succeeded metadata. The runtime does not traverse arbitrary local source files. Vector
retrieval is not advertised or enabled.

`coursepilot_context` is an optional, HMAC-authenticated, short-lived compatibility extension. A
non-stream response returns it at the top level; an SSE response includes it only on the single stop
frame, preserving role → content → stop → `[DONE]`. It contains identity/digest continuity only—never
answers, code, scores, profile data, authorization scopes, or secrets—and is not an authorization
credential.

Code tutoring accepts a structured mode for example generation, explanation, diagnosis, review,
repair, refactoring, or test design. Learner or explicitly referenced recent code creates an ephemeral
`CodeArtifact`; generated blocks remain non-persistent and are checked with the same offline parser
where available. Toolchain diagnostics stay bound to real artifact line ranges, model-only languages
are labeled, and every path keeps `ran_code=false`.
Course advice metadata is accepted only from an approved sidecar; unknown fields remain unknown, and
target fit is scored separately from online StudyKit readiness.

Deferred work: private upload/MaterialSet registration and authorization, Qingxiaoda identity mapping,
cross-session per-candidate profile UI/schema, and reviewed vector artifacts. Offline StudyKit practice
semantic audit and archive human approval remain separate mandatory gates.

Provider-backed acceptance is opt-in and uses only invented evidence; see
[`platform_validation.md`](platform_validation.md#opt-in-provider-backed-acceptance). The normal pytest
suite remains deterministic, offline, and credential-free.

Online model calls follow a request-local budget: TaskPlan is counted separately, and each concrete
capability may call the model at most once. Profile extraction and material generation no longer run
a second online reviewer; SourceChunk recall is deterministic before the material answer call.
Deterministic schemas, exact evidence quotes, provenance ID allowlists, hidden-control scans, and
transparent fallbacks enforce the online boundary. Independent semantic audit remains mandatory for
offline StudyKit authoring and archive approval.

Practice selection automatically uses its one model call to produce a `structured_rewrite` with
explicit givens, question, constraints, deliverable, and estimated time. The model receives a minimal
intent projection but not the complete evaluation/rubric. Invalid output falls back to the approved
original. Context-token v2 binds the active presentation kind and digest without storing the question
or answer; v1 tokens remain accepted. `grounded_variant` remains disabled until an approved public
SourceChunk index is actually available.

The final opt-in `deepseek-v4-flash` acceptance passed 7/7 checks with 4,310 reported tokens. Every
concrete model-backed capability reported one call per request; all three practice-presentation samples
produced validated `structured_rewrite` results with zero fallbacks.
