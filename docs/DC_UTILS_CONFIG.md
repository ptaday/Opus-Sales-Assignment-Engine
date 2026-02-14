# Design Document: Config Utils

**Component:** `src/utils/config.py` — Loading and parsing `config/seed.txt` and `config/assign.txt`.

---

## 1. Key decisions

- **Plain-text config:** KEY=value format and a special PROMPT section for seed. No YAML/JSON so non-developers can edit without syntax worries and the repo stays readable in diff.
- **Repo-relative paths:** `_REPO_ROOT` is derived from this file’s location (`__file__`); all relative paths in config are resolved against repo root. Absolute paths in config are left as-is; empty/missing path defaults to `repo/out`.
- **Seed config: PROMPT section:** Everything after a line that equals `PROMPT` is treated as the prompt body (including newlines). Rest is KEY=value. Allows multi-line prompt without escaping.
- **Assign config: defaults in code:** Full set of defaults is defined in `load_assign_config()`; file overrides only the keys present. Missing file is OK — we use all defaults. So assign works out-of-the-box if `assign.txt` is missing.
- **Seed config: file required:** `load_seed_config()` raises `FileNotFoundError` if `config/seed.txt` is missing. Seed is optional for assign-only use; when you run seed we require the file.
- **Parsing helpers:** `_parse_key_value_pairs` for "Key:number, ..." (workload/industry weights); `_parse_attribute_mapping` for "key:slug, ...". Invalid or missing values are skipped (e.g. non-numeric values in key_value_pairs); empty mapping falls back to defaults for assign.

---

## 2. Error handling — API down, missing field, write fails, rate limiting / retry

Config is file-only; no API or retry:

| Scenario | Behavior |
|----------|----------|
| **seed.txt missing** | `load_seed_config()` raises `FileNotFoundError` with path. |
| **assign.txt missing** | `load_assign_config()` uses all defaults; no error. |
| **Missing key in seed** | Required keys have defaults (e.g. OUTPUT_PATH → "out/seed_companies.csv", NUM_ROWS → 30). Optional keys use `.get(key, default)`. Missing PROMPT section → prompt is empty string. |
| **Missing key in assign** | Every key has a default in the `defaults` dict. So missing key never raises; we always return a full config. |
| **Invalid value (e.g. non-numeric)** | `int(settings.get(...))` can raise `ValueError` if user puts non-numeric string (e.g. `MAX_NEW_THRESHOLD=abc`). Not caught. `_parse_key_value_pairs` catches `ValueError` per-part and skips that part; rest of dict still returned. |
| **Invalid path** | We don’t check existence or writability; invalid path will surface when main or services try to read/write. |

**Summary:** Seed fails fast if file missing. Assign is permissive; bad values can cause ValueError when parsed as int or when used later. No retry (not applicable).

---

## 3. Idempotency — running the script twice

Config loading is **stateless**: each run reads files again. So:

- **Run twice:** Same config files → same config dict. No process state. Idempotent.
- **Editing config between runs:** Second run sees new values. No caching.

---

## 4. What you’d improve with more time / what tripped you up

- **Validation layer:** After loading, validate types and value ranges (e.g. `max_new_threshold > 0`, `min_locations <= max_locations`, `reps` non-empty) and raise a single `ConfigError` with all issues listed.
- **Schema/documentation:** Document every key, type, and default (e.g. in README or in comments at top of assign.txt/seed.txt) so new keys or renames don’t break silently when code expects a key that was renamed.
- **Path existence (optional):** For paths we write to (e.g. log_file, summary_dir, fetch_csv), optionally check parent is writable or create dirs at load time so we fail fast instead of mid-run.
- **PROMPT placeholder escaping:** Seed prompt is `.format(num_rows=..., fieldnames=...)`. If the prompt contains `{other}` it can raise. Use a safe substitute (e.g. replace `{num_rows}` and `{fieldnames}` only) or a different templating syntax.
- **Gotchas:** `CONFIG_DIR` is relative to `config.py` (three parents up = repo root). If the package is run from another location or installed as a package, `__file__` is still the source file, so this is usually correct. Repo root must be the project root where `config/` lives.
