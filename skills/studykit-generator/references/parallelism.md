# Capability-aware unit execution

Ingestion, course identification, inventory hashing, and build fingerprinting are coordinator-only. Units may run concurrently, while stages within a unit remain ordered `01 → 02 → 03 → 04 → 05` (fast may create 01–03 in one semantic pass but checkpoints all three).

`parallel_units` accepts `auto`, `off`, or `1..4`. Auto reserves one coordinator slot: with known capacity use `min(unit_count, available_slots - 1, 4)`; with unknown capacity use two workers. Fall back to one worker when isolated native subtasks are unavailable. Never emulate workers using nested `codex exec`.

Each worker writes only its assigned unit directories. The coordinator owns `manifest.yaml`, `run.json`, `result.json`, and `batch-summary.json`. Reject duplicate unit IDs before starting. A stage has a 600-second hard timeout; retry a transient failure once, resuming from the latest complete checkpoint. A failed unit does not cancel others.

Report `succeeded` only if all units succeeded, `partial` if at least one succeeded, otherwise `failed`. For each failed unit record `failed_stage`, retry count, last valid checkpoint, and recovery action. Worker count is recorded in metrics but excluded from the resumability fingerprint.

`scripts/plan_execution.py` creates deterministic worker groups and output paths without invoking a model or reading provider credentials.
