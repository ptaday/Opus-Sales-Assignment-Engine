# Summary of Files

**CLI**
- **`src/main.py`** — Entry point. Subcommands: `seed`, `fetch`, `assign` (with `--dry-run`). Orchestrates config load, service calls, scoring/assignment, and writes summary + log + MD.

**Core**
- **`src/core/scoring.py`** — `score_company(location_count, industry, industry_weights)` → float. Log-scaled location score × industry weight.
- **`src/core/assignment.py`** — `get_rep_eligibility(...)` → per-rep workload/eligible; `assign_accounts(...)` → (assigned, unassigned). Workload-weighted round-robin.

**Services**
- **`src/services/attio.py`** — `AttioService`: fetch eligible/rep/skipped records, verify still unassigned, update owner + prospect_status. Paginated query, single PUT per update.
- **`src/services/seed_service.py`** — `run_seed()`: load config, prompt user overwrite/append, call Claude, append to CSV with dedupe by key. Helpers: `generate_companies`, `append_to_csv`, `load_existing_keys`.

**Utils**
- **`src/utils/config.py`** — `load_seed_config()` from `config/seed.txt` (KEY=value + PROMPT); `load_assign_config()` from `config/assign.txt` (KEY=value, defaults if missing). Path resolution, parse key:value and attribute mapping.

**Models**
- **`src/models/account.py`** — `Account` dataclass (record_id, score, skip_reason, assigned_to, data). `from_attio_record(record, attribute_mapping)`; `get(key)`. Helpers extract single value from Attio value lists.

**Config (inputs)**
- **`config/seed.txt`** — Output path, columns, duplicate key, num_rows, model, prompt.
- **`config/assign.txt`** — Object type, reps, thresholds, industries, locations, paths, weights, attribute mapping keys.

**Outputs** — `out/` (seed CSV, fetch CSV, assignment_log.json, summaries/*.md). See README.


