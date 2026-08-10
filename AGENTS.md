# CoursePilot Repository Memory

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

## Compatibility and tests

- Preserve `/v1/models`, `/v1/chat/completions`, optional OpenAI `user`, model ID `coursepilot-probe`, JSON envelopes, and SSE order: role, content, one stop frame, then `[DONE]`.
- Tests must not require external model credentials or network access. Real HTTP tests bind loopback only.
- Use `.venv/bin/python` and `.venv/bin/pytest -q`.
- When capability status changes, update `README.md`, `PROJECT_STATUS.md`, `docs/project_status.md`, `docs/developers_guide.md`, release/validation docs, and this memory together.
