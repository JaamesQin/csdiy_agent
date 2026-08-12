# Private data submodule

The repository's `data/` directory is the private Git submodule
`JaamesQin/csdiy_agent-data`. Git LFS stores the StudyKit SQLite archive and
anchored JSONL chunks.

Initialize a checkout with:

```bash
git submodule update --init --recursive
git -C data lfs pull
```

The retrieval archive is `data/archive/studykits.sqlite3`. Its imported
records retain their review status: `validated_draft` is not online-ready,
and only separately approved records may be exposed by a future online
StudyKit store.

The private remote intentionally contains only retrieval-relevant data:

- the catalog and course manifests;
- human-approved golden fixtures required by the current file store and
  offline tests;
- anchored chunks and associated ingestion/provenance metadata;
- source inventories and prepared-material provenance;
- the latest archived StudyKit SQLite database.

Raw PDFs, ZIP files, mirrored sites, prepared binaries, rendered pages,
reviewed-package duplicates, and regression runs are not uploaded. Existing
copies may remain ignored in a local submodule worktree. Public accessibility
of a source does not imply redistribution permission.

The pre-migration local snapshot is retained temporarily at
`storage/data-before-private-submodule/`; it is ignored and is not part of the
submodule or a commit.
