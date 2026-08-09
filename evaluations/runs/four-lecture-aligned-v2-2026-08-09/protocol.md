# Coordinator-timed aligned regeneration v2

This run supersedes `four-lecture-aligned-2026-08-09`, whose workers prepared multiple modes in one turn and therefore did not measure model authoring time per mode.

All source, information-isolation, shared-authoring, artifact, formula, and validation rules in `../four-lecture-aligned-2026-08-09/alignment-protocol.md` apply, except:

- one agent turn generates exactly one lecture and one quality mode;
- the worker must not read any prior run, sibling mode, gold rubric, score, report, or learner-facing artifact;
- the worker writes only `codex-<mode>/<unit>/` in this v2 directory;
- no learner content or stage artifact may be shared or copied between modes;
- coordinator dispatch and completion timestamps are authoritative and include the entire independent model turn;
- worker metrics still record internal checkpoints, but default-mode timing uses coordinator elapsed seconds;
- the coordinator rejects missing/failed outputs rather than substituting estimates.

Modes run in three rounds (fast, then standard, then strict), with four isolated lecture workers in parallel per round. This makes timing comparable within a round while retaining unit isolation.
