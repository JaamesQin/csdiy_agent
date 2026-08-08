# CoursePilot Repository Memory

## Architecture invariants

- `app/api/` and `app/protocol/` adapt OpenAI-compatible HTTP/JSON/SSE only. Domain logic belongs in `app/agent/` and capability modules.
- `StudyKitGenerator` is a slow offline authoring pipeline. Never call it from `/v1/chat/completions`.
- Online course facts must come from a validated `StudyKitStore` or future permission-filtered retrieval. Do not let a router or model invent course/version/unit identity.
- The current file store may read only Schema-valid, human-approved golden StudyKits. Do not mutate golden artifacts from online code.
- Preserve the response model ID `coursepilot-probe` and SSE order: role, content, one stop frame, then one `[DONE]`.

## Privacy and safety

- OpenAI `user` is an opaque logical identifier, not authorization. Persistent profiles are local/trusted-gateway only until the platform supplies verified identity.
- Profiles store minimal facts and evidence excerpts, never full conversations, code, tracebacks, secrets, or model reasoning.
- Explicit user statements may be confirmed. Model inferences remain expiring candidates until the user confirms them. Users must be able to inspect, correct, and delete profile data.
- Code tutoring is static-only in the current runtime. Keep `ran_code=false`; never claim execution or test results.
- Do not expose `expected_evidence`, evaluation rubrics, evidence controls, audit diagnostics, or hidden reasoning to learners.
- Refuse complete submit-ready coursework solutions while still offering diagnosis, tests, and layered hints.

## Development workflow

- Use the configured virtual environment: `.venv/bin/python` and `.venv/bin/pytest -q`.
- Tests must not require external model credentials or network access. Inject a fake `StructuredModel` for route/profile/tutor model paths.
- Real local HTTP tests bind a loopback port and may require sandbox approval: `.venv/bin/pytest -q tests/integration/test_local_http.py`.
- Keep generated/private data under ignored paths such as `storage/`, `data/private/`, `data/sources/`, and `data/regression/`.
- When capability status changes, update `README.md`, `PROJECT_STATUS.md`, `docs/project_status.md`, and `docs/developers_guide.md` together. Preserve explicitly dated historical validation records unless adding a newer section.
