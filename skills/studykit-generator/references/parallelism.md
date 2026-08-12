# Capability-aware unit and build-coordinator execution

Ingestion, course identification, inventory hashing, and build fingerprinting
are coordinator-only. A build coordinator owns one isolated build root. Units
inside that build may run concurrently, while stages within a unit remain
ordered `01 → 02 → 03 → 04 → 05` (fast may create 01–03 in one semantic pass
but checkpoints all three).

`parallel_units` is scoped to one build coordinator and accepts `auto`, `off`, or
`1..4`. The four-worker ceiling protects unit namespace isolation and keeps a
coordinator slot available. With known capacity, `auto` uses
`min(unit_count, coordinator_slots - 1, 4)`; with unknown capacity it uses two
workers. Fall back to one worker when isolated native subtasks are unavailable.
Never emulate workers using nested `codex exec`.

The session may run multiple fully isolated build coordinators concurrently.
The global coordinator allocates the session budget before launch. Each build
coordinator receives a disjoint slot budget and a unique `coordinator_id`; its
manifest, build root, source namespace, unit directories, course review files,
and handoff record must not overlap another coordinator. A 16-slot session can,
for example, run three coordinators with five slots each (four unit workers
plus one coordinator) and retain one global coordination slot. The per-build
four-worker ceiling still applies.

Each unit worker writes only its assigned unit directory. Its build coordinator
writes only that build's `manifest.yaml`, `run.json`, `result.json`,
`batch-summary.json`, course index, and handoff. The global coordinator alone
writes the catalog registry, global status projection, and aggregate audit.
Reject duplicate unit IDs and overlapping coordinator namespaces before
starting. A stage has a 600-second hard timeout; retry a transient failure once,
resuming from the latest complete checkpoint. A failed unit does not cancel
other units or isolated coordinators.

Report `succeeded` only if all units in that build succeeded, `partial` if at
least one succeeded, otherwise `failed`. For each failed unit record
`failed_stage`, retry count, last valid checkpoint, and recovery action. Worker
count, coordinator ID, and session allocation are recorded in execution
metadata but excluded from the resumability fingerprint.

`scripts/plan_execution.py` creates deterministic worker groups, coordinator
allocation metadata, and output paths without invoking a model or reading
provider credentials.
