# Design Document: CLI / Main Entry

**Component:** `src/main.py` — CLI entry point and assign/fetch orchestration.

---

## 1. Key decisions

- **Subcommands:** Single entry `main()` with subparsers for `seed`, `fetch`, and `assign`. Keeps one script to run and one place to add new commands.
- **Assign flow in main:** Assign pipeline (fetch → score → assign → write) is orchestrated in `cmd_assign()` rather than a separate service so config, Attio service, and file I/O stay in one place; core logic remains in `core/assignment` and `core/scoring`.
- **Dry-run as a flag:** `assign --dry-run` skips all Attio writes but still runs scoring, assignment algorithm, and summary/log/md output so users can preview safely.
- **Summary outputs:** Three outputs per assign run: stdout summary (`_print_summary`), append-only JSON log (`_save_run_log`), and timestamped Markdown file (`_save_summary_md`) for audit and sharing.
- **Fetch writes only new rows:** Fetch loads existing `record_id`s from CSV and appends only accounts not already in the file to avoid duplicate rows when re-running.
- **No Attio write on missing token in assign:** If `ATTIO_API_TOKEN` is unset, assign still runs (scores, assigns, saves summary/log) but prints a warning and skips API writes so dry-run-style behavior is possible without a token.

---

## 2. Error handling — API down, missing field, write fails partway, rate limiting / retry

| Scenario | Behavior |
|----------|----------|
| **API down (fetch/assign)** | Attio calls are in `AttioService._paginated_fetch` and `update_attio_record`. Network/request errors there: fetch/query exits process with `sys.exit(1)`; update uses retries (see DC_SERVICE_ATTIO). Main does not catch these — process exits. |
| **Missing field** | Scoring uses `a.get(loc_key) or 0` and `a.get(ind_key) or ""` so missing location/industry don’t crash; they just score low. Display names use `a.get(display_name_key) or "(unnamed)"`. Missing config keys would surface when config is loaded (see DC_UTILS_CONFIG). |
| **Write fails partway (Attio)** | Each assignment is written one-by-one. A failed write is recorded in `write_results` as `status: "failed"` with reason; the loop continues. No rollback of already-written records; log and summary show which succeeded vs failed. |
| **Write fails (log/summary file)** | `_save_run_log`: if existing log file is corrupt, we treat as empty and append (no exit). Writing the new log can still raise (e.g. permission). `_save_summary_md`: `summary_dir.mkdir(parents=True, exist_ok=True)` then `filepath.write_text(...)` — failures would propagate and exit. |
| **Rate limiting / retry** | Not implemented in main. Retries and 429 handling are only in `AttioService.update_attio_record` (exponential backoff). Fetch/query paths do not retry; they exit on first failure. |

**Summary:** Main assumes services raise or exit on hard failures. It records per-record write success/failure for assign and continues; it does not retry fetch or query.

---

## 3. Idempotency — running the script twice

| Command | Run 1 | Run 2 | Idempotent? |
|---------|--------|--------|--------------|
| **seed** | Depends on user (overwrite vs append). Append: adds new rows; duplicate key skips. | Same. Append again adds only new companies. | **Append: yes.** Overwrite: replaces file. |
| **fetch** | Appends new eligible accounts to CSV (by `record_id`). | Only accounts not already in CSV are appended. | **Yes.** Duplicate `record_id`s are skipped. |
| **assign** | Fetches eligible (no owner), scores, assigns, then for each assigned: verify still unassigned → update owner. | Same. Already-owned records are in `skipped_owned`; verification step skips if another process assigned. | **Yes.** Re-run assigns only still-unassigned records; no double-assignment of same record. Log/summary are appended/added, not replaced. |

**Caveats:** (1) Assign run 2 may assign different companies than run 1 if the set of unassigned or rep workloads changed. (2) Log and summary files grow (append/new file) — no automatic pruning.

---

## 4. What you’d improve with more time / what tripped you up

- **Structured logging:** Replace `print()` with a logger and optional JSON log for easier tooling and debugging.
- **Retries for fetch/query:** Add retry with backoff in Attio fetch/query so transient API/network failures don’t exit the process immediately.
- **Config validation up front:** Validate assign config (e.g. required keys, path writability) once at start of `cmd_assign`/`cmd_fetch` and fail fast with clear messages.
- **Write results to a single transaction or checkpoint:** Document or implement “resume from last successful write” so partial assign runs can be resumed instead of re-running the full list (optional, for very large runs).
- **Gotchas:** Distinguishing “dry-run” (no writes) from “live but no token” (writes skipped with warning) can be confusing — could add an explicit `--no-write` or clarify in docs. CSV append in fetch assumes `record_id` is the dedupe key; if Attio ever returned duplicate IDs we’d still append — consider documenting or enforcing uniqueness.
