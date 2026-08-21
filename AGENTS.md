# CoursePilot Repository Memory

## Online Agent P0–P2 contracts

- Default online routing uses a bounded acyclic TaskPlan and preserves independent task success.
- Learner claims keep course material, catalog metadata, static analysis, and labeled general
  knowledge provenance separate; invalid course evidence drops the whole course-material partition.
- Public SourceChunk retrieval filters scope and identity before FTS5/BM25 ranking. Exact cited
  evidence resolution never uses FTS/BM25: it resolves `chunk_id` first or exact
  `source_id + anchor`, filters public scope, course/version/unit, succeeded build, approved review,
  and index eligibility in SQL, then verifies the chunk content hash. Parser-generated `chunk_id`
  values are local/truncated identifiers, not global keys; every supplied source/anchor qualifier
  remains conjunctive, and a bare ambiguous ID fails closed. Signed
  `coursepilot_context` and server-side `sessionId` state are continuity only, never authorization
  or answer storage. Gateway state is minimal, namespace-bound, HMAC-indexed, and expires after a
  30-day sliding TTL; missing or empty `sessionId` never reuses a prior conversation.
- Model semantic candidates may refine or explicitly replace a verified StudyKit identity, but omitted
  fields must not downgrade a signed current-unit context. Only an explicit unit-list request may
  intentionally move the same course from unit scope to course scope.
- Code tutoring supports bounded example generation, explanation, diagnosis, review, repair,
  refactoring, and test design. It binds input diagnostics to ephemeral CodeArtifacts, validates
  generated blocks with available static parsers, uses at most one capability-model call per request,
  never persists generated code bodies, and always keeps `ran_code=false`.
- Private MaterialSet authorization, cross-system identity, profile-management expansion, and reviewed
  vector artifacts remain deferred.

## Architecture invariants

- `app/api/` and `app/protocol/` adapt OpenAI-compatible HTTP/JSON/SSE only. Domain logic belongs in `app/agent/` and capability modules.
- `StudyKitGenerator` is a slow offline authoring pipeline. Never call it from `/v1/chat/completions`.
- StudyKit practice quality is established by content-grounded author prompts plus a separate
  independent audit of every practice item; do not replace this semantic contract with a
  domain-specific hard-coded validator. Keep this review offline and source-anchored.
- Selective practice repair is offline-only: create a new fingerprinted build from the direct
  parent snapshot, bind the rich audit to the current build and repair plan, and require exact
  per-practice coverage with no missing, duplicate, or stale IDs. Any mismatch blocks completion
  and false-complete; deterministic Schema validation alone is insufficient. Do not claim the
  six-course repair is globally complete without every gate passing.
- Online course facts must come from a validated `StudyKitStore` or future permission-filtered retrieval. Do not let a router or model invent course/version/unit identity.
- The current file store may read only Schema-valid, human-approved golden StudyKits. Do not mutate golden artifacts from online code.
- `CourseCatalogStore` keeps catalog IDs separate from Manifest/StudyKit identities. Catalog, authoring, and online-ready status must be rendered separately; unreviewed candidate offerings are not official links.
- Database-backed StudyKit storage must preserve the current `get_ready`, `list_ready`, `resolve_context`, and `match_context` semantics and review gates.
- `data/` is the private `JaamesQin/csdiy_agent-data` submodule. Git LFS stores
  `data/archive/studykits.sqlite3` and anchored JSONL chunks; initialize it before running
  data-dependent tests. The archive remains separate from the account/profile SQLite database.
  Imports retain an explicit review status; `validated_draft` records are not online-ready, and
  only `approved` build and document records may satisfy the online store.
- SourceChunk indexing requires hash-bound per-unit source metadata. An explicitly
  `legacy_reviewed` build without `run.fingerprint_payload.units` remains an approved StudyKit input
  but is excluded from the SourceChunk index; a non-legacy approved build missing that fingerprint
  fails the index build closed.
- Human archive approval must run through `scripts/approve_studykit_archive.py`: require archive
  integrity, portable Schema, per-unit validation/review validation, exact requested/completed/
  validated/audited/document identity, and matching independent registry audit coverage. Explicit
  reviewed-legacy owner approvals must retain their waived-gate audit trail. Identity repairs must
  create a fingerprinted child bound to the direct parent, repair plan, and current exact-set audit.
  The 2026-08-17 approval released 9 builds/220 documents; 3 partial builds/66 documents remain draft.
- Portable StudyKit v0.2.2 requires every practice to declare `feedback_mode`. `course_grounded`
  requires at least one exact-resolvable visible citation; `general_only` requires an empty citation
  set and is publishable only with an explicit learner warning. Declaration mismatch or unresolved
  grounded evidence blocks validation/publication. Older approved v0.2.1/legacy artifacts remain
  readable and infer their runtime mode without in-place mutation; single-source legacy
  `source_pages` are converted to exact `source_id + page` references before resolution.

## Identity and persistence

- Local account identity is established only by a valid server-side session and maps to `account:<uuid>`.
- OpenAI `user` remains an untrusted logical identifier. Under the server API key it maps only to `legacy:<user>` and must never address an `account:` subject.
- Cookie-authenticated chat ignores the request-body `user`; capability modules receive only the trusted subject from `app/security.py`.
- Schema v3 stores accounts, hashed auth-session tokens, minimal profile facts, and minimized
  conversation continuity in the shared SQLite database. Preserve forward migration, do not
  re-prefix v2 subjects during v2→v3 migration, and reject unknown versions.

## Password, session, and browser safety

- Passwords use Argon2id; never store or log plaintext passwords, cookies, CSRF tokens, API keys, or password hashes.
- Raw session tokens live only in HttpOnly, SameSite=Strict cookies. SQLite stores SHA-256 token digests and server-side expiry/revocation state.
- Cookie-authenticated writes require the session-bound `X-CSRF-Token`. Browser auth writes must pass the Origin allowlist.
- Production requires HTTPS, `COURSEPILOT_COOKIE_SECURE=true`, an explicit Origin allowlist, a protected persistent database volume, and shared proxy-level auth rate limiting.
- `frontend/` is the source of truth for the Vite/React/TypeScript browser client; `app/static/` is generated and committed deployment output. Rebuild it with `npm run build` instead of editing generated files directly.
- Assistant Markdown is untrusted: keep raw HTML disabled, sanitize rendered output, forbid model-supplied images and active content, and use dimension-bounded MathML-only equations under the existing strict CSP. User messages, usernames, and errors remain text-only, including when a queued stream render is cancelled by an error.
- Keep raw assistant Markdown in in-memory conversation history; never reconstruct request history from rendered DOM, which contains MathML and local copy controls.
- Bound browser-side SSE frames, non-stream JSON, assistant output, rich streaming previews, and total in-memory conversation size; cancel oversized readers and keep resulting errors text-only.

## Learner data

- Persist only minimal, user-confirmed learner facts and short evidence excerpts. Do not persist full conversations, code, tracebacks, secrets, or model reasoning.
- Conversation continuity may persist only verified course/unit identity, bounded practice pointers,
  presentation/code digests, and minimal follow-up metadata. Never persist raw gateway session IDs,
  messages, code bodies, answers, scores, or reasoning. State-store failure degrades continuity and
  must not block the current chat response.
- Users must be able to inspect and delete their profile. Do not claim or attach old anonymous/legacy data to an account without verified ownership.
- Keep account, legacy, public course, and future private MaterialSet namespaces separate in every repository query.

## Online privacy and tutoring safety

- Explicit user statements may be confirmed. Model inferences remain expiring candidates until the user confirms them. Users must be able to inspect, correct, and delete profile data.
- Code tutoring is static-only in the current runtime. Generated examples may describe expected
  behavior, but keep `ran_code=false` and never claim compilation, execution, or test results.
- `app/code_tutor/languages.py` is the source of truth for supported language aliases and parser strategies. Never default an unlabelled fence to Python, invoke a compiler/interpreter, or add runtime grammar downloads.
- `app/agent/capabilities.py` is the source of truth for learner-visible capability status and help. General help lists only available capabilities and must return before profile observation or persistence.
- Unavailable capabilities are help/status metadata only and must never remain executable Router or
  TaskPlan targets. Explicit natural-language requests for them normalize to `general_assistance`;
  the general response receives only the matching sanitized capability boundary and must state that
  it is unavailable without implying another online capability can access the missing backend data.
- `general_assistance` is the terminal fallback only when no specialized capability applies. It may receive at most the latest 30 messages/48,000 characters, confirmed profile values, minimized verified continuity, and the sanitized bounded course-registry projection. Model prose remains general knowledge; selected catalog IDs are validated and rendered as a separate catalog-metadata partition. It must never claim course-material citations, code execution, or submit-ready coursework solutions.
- Personalized `course_navigation` must consume all confirmed learner constraints, including negative background facts, and may use one structured non-thinking model call to choose only validated registry IDs. Invalid JSON is retried by the model adapter; contract-invalid selections fail closed. Exact lookup and listing remain deterministic; model failure must be labeled as unpersonalized rather than silently presenting readiness ranking as learner fit.
- Natural-language formatting is the server's responsibility: shared deterministic understanding must accept recognizable inline/flattened code and Chinese unit/page references before model routing. Never require Markdown when an ephemeral artifact can be identified safely.
- Within trusted current-unit continuity, Chinese practice ordinals, bare `ex-N` display aliases, and short natural questions such as “ex7 是什么” route deterministically to the reviewed practice order. A StudyKit practice index is not evidence that those practices were presented.
- Do not expose `expected_evidence`, evaluation rubrics, evidence controls, audit diagnostics, or hidden reasoning to learners.
- Refuse complete submit-ready coursework solutions while still offering diagnosis, tests, and layered hints.
- Material answers and concept explanations may use only ready StudyKit fields or permission-first,
  identity-filtered public SourceChunks. An arbitrary page request without evidence must fail transparently.
- Practice selection prefers exact-resolvable `course_grounded` items over otherwise matching
  `general_only` items. Practice feedback may use at most 16 exact references/16,000 evidence
  characters. If the whole course-evidence partition is valid, feedback must cite only supplied IDs;
  otherwise it must use one general-knowledge model call and display
  `通用反馈（未按当前课程材料核验）` plus the fixed non-course-verification notice.
- Practice selection and feedback are stateless. Do not persist answers, scores, aggregate accuracy,
  or mastery; do not expose hidden evaluation fields. Model failure must not trigger a second model
  call and must degrade to the original hint plus verified source labels when available.
- TaskPlan model calls are counted separately; each concrete online capability may call the model at most once per request. Do not add online generator→reviewer chains. Practice presentation may use one controlled structured rewrite and must fall back to the approved original on validation failure.

## Compatibility and tests

- Preserve `/v1/models`, `/v1/chat/completions`, optional OpenAI `user`, model ID `coursepilot-probe`, JSON envelopes, and SSE order: role, content, one stop frame, then `[DONE]`.
- Tests must not require external model credentials or network access. Real HTTP tests bind loopback only.
- Use `.venv/bin/python` and `.venv/bin/pytest -q`.
- Use Node 24 with `npm run check` and `npm run test:e2e`; Playwright must reuse the installed Chrome channel and must not install browsers or OS dependencies.
- Inject a fake `StructuredModel` for route/profile/tutor model paths.
- Keep account/profile databases and temporary backups under ignored `storage/`. Within the
  private data submodule, raw binaries, reviewed-package duplicates, regression data, rendered
  pages, and other excluded local checkpoints must remain ignored; do not add them merely because
  the submodule is private.
- When capability status changes, update `README.md`, `PROJECT_STATUS.md`, `docs/project_status.md`, `docs/developers_guide.md`, release/validation docs, and this memory together.
