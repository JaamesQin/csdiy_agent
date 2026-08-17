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

Code tutoring creates an ephemeral `CodeArtifact`, performs static-only analysis, parses supplied
toolchain diagnostics, binds hypotheses to actual artifact line ranges, and keeps `ran_code=false`.
Course advice metadata is accepted only from an approved sidecar; unknown fields remain unknown, and
target fit is scored separately from online StudyKit readiness.

Deferred work: private upload/MaterialSet registration and authorization, Qingxiaoda identity mapping,
cross-session per-candidate profile UI/schema, and reviewed vector artifacts. Offline StudyKit practice
semantic audit and archive human approval remain separate mandatory gates.

Provider-backed acceptance is opt-in and uses only invented evidence; see
[`platform_validation.md`](platform_validation.md#opt-in-provider-backed-acceptance). The normal pytest
suite remains deterministic, offline, and credential-free.

The 2026-08-17 `deepseek-v4-flash` acceptance run passed 6/6 checks: full-history multi-intent
planning, negation-aware profile review, material generation with independent support audit, labeled
general knowledge, minimum-projection practice feedback, and artifact-bound static code tutoring.
It exposed and led to fixes for planner Schema retry/fallback, reviewer usage aggregation, rubric
removal from the external feedback prompt, and ambient-key isolation in test mode. Run it manually
with `.venv/bin/python scripts/run_live_agent_acceptance.py`; the script prints only verdict metadata.
