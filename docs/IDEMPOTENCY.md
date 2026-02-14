# Idempotency

**Seed** — Append: existing keys in CSV are skipped; re-run only adds new keys. Overwrite: replaces file (by design). No duplicate rows when using append. Does not update any changes fields assocated with the key.

**Fetch** — Existing `record_id`s in CSV are skipped; only new IDs appended. Re-run safe.

**Assign** — Eligible list excludes already-owned records. Before each write we verify record still unassigned; if assigned by another process we skip. Re-run does not double-assign. Log and summary are append/new file (no overwrite of prior runs).

**Caveats** — Second assign run can assign different companies if data or rep workloads changed. Log/summary files grow; no pruning.

**Config** — Stateless load each run; same files → same config.

**Core / model** — Stateless; same inputs → same outputs.
