# CoursePilot Repository Memory

## Architecture invariants

- `app/api/` and `app/protocol/` adapt OpenAI-compatible HTTP/JSON/SSE only. Domain logic belongs in `app/agent/` and capability modules.
- `StudyKitGenerator` is a slow offline authoring pipeline. Never call it from `/v1/chat/completions`.
- Online course facts must come from a validated `StudyKitStore` or future permission-filtered retrieval. Do not let a router or model invent course/version/unit identity.
- The current file store may read only Schema-valid, human-approved golden StudyKits. Do not mutate golden artifacts from online code.

## Identity and persistence

- Local account identity is established only by a valid server-side session and maps to `account:<uuid>`.
- OpenAI `user` remains an untrusted logical identifier. Under the server API key it maps only to `legacy:<user>` and must never address an `account:` subject.
- Cookie-authenticated chat ignores the request-body `user`; capability modules receive only the trusted subject from `app/security.py`.
- Schema v2 stores accounts, hashed session tokens, and minimal profile facts in the shared SQLite database. Preserve the forward migration and reject unknown versions.

## Password, session, and browser safety

- Passwords use Argon2id; never store or log plaintext passwords, cookies, CSRF tokens, API keys, or password hashes.
- Raw session tokens live only in HttpOnly, SameSite=Strict cookies. SQLite stores SHA-256 token digests and server-side expiry/revocation state.
- Cookie-authenticated writes require the session-bound `X-CSRF-Token`. Browser auth writes must pass the Origin allowlist.
- Production requires HTTPS, `COURSEPILOT_COOKIE_SECURE=true`, an explicit Origin allowlist, a protected persistent database volume, and shared proxy-level auth rate limiting.

## Learner data

- Persist only minimal, user-confirmed learner facts and short evidence excerpts. Do not persist full conversations, code, tracebacks, secrets, or model reasoning.
- Users must be able to inspect and delete their profile. Do not claim or attach old anonymous/legacy data to an account without verified ownership.
- Keep account, legacy, public course, and future private MaterialSet namespaces separate in every repository query.

## Online privacy and tutoring safety

- Explicit user statements may be confirmed. Model inferences remain expiring candidates until the user confirms them. Users must be able to inspect, correct, and delete profile data.
- Code tutoring is static-only in the current runtime. Keep `ran_code=false`; never claim execution or test results.
- Do not expose `expected_evidence`, evaluation rubrics, evidence controls, audit diagnostics, or hidden reasoning to learners.
- Refuse complete submit-ready coursework solutions while still offering diagnosis, tests, and layered hints.

## Compatibility and tests

- Preserve `/v1/models`, `/v1/chat/completions`, optional OpenAI `user`, model ID `coursepilot-probe`, JSON envelopes, and SSE order: role, content, one stop frame, then `[DONE]`.
- Tests must not require external model credentials or network access. Real HTTP tests bind loopback only.
- Use `.venv/bin/python` and `.venv/bin/pytest -q`.
- Inject a fake `StructuredModel` for route/profile/tutor model paths.
- Keep generated/private data under ignored paths such as `storage/`, `data/private/`, `data/sources/`, and `data/regression/`.
- When capability status changes, update `README.md`, `PROJECT_STATUS.md`, `docs/project_status.md`, `docs/developers_guide.md`, release/validation docs, and this memory together.
