# Design Document: Core (Scoring & Assignment)

**Component:** `src/core/scoring.py`, `src/core/assignment.py` — scoring model and round-robin assignment logic.

---

## 1. Key decisions

- **Scoring formula:** `score = location_score × industry_weight`. Location score is `70 × ln(location_count) / ln(50)` clamped to [0, 70] so it’s log-scaled and capped; industry weight comes from config (default 1.0). Pure function: no I/O, easy to test and document.
- **Assignment algorithm:** Workload-weighted round-robin. For each company we consider only reps that are still eligible (under `max_new_threshold` “New” accounts), sort them by current workload (ascending), pick the first, then update that rep’s workload and “assigned_this_run” and optionally mark them ineligible when they hit the threshold. This balances load and caps new accounts per rep.
- **Eligibility in one place:** `get_rep_eligibility()` computes per-rep: existing accounts, new_count, workload, and eligible flag. Assignment then uses and mutates this same structure so “assigned_this_run” and workload stay in sync during the run.
- **No Attio/API in core:** Core only receives and returns in-memory data (lists of `Account`, dicts). All I/O and config live in main/services so core stays testable and portable.
- **Unassigned list:** Companies that can’t be assigned (no eligible reps) get a `skip_reason` and are returned in the second element of the tuple so callers can report and log them.

---

## 2. Error handling — API down, missing field, write fails, rate limiting / retry

Core does **no** I/O, so:

- **API down / write fails / rate limiting:** Not applicable here; those are handled in `AttioService` and main.
- **Missing field:**
  - **Scoring:** `score_company(location_count, industry, industry_weights)` is called from main with `a.get(loc_key) or 0` and `a.get(ind_key) or ""`. So missing location → 0 (location_score 0); missing industry → `industry_weights.get("", 1.0)` (default 1.0). No exception from core for missing data.
  - **Assignment:** Uses `a.get(owner_key)`, `a.get(prospect_status_key)` etc. Missing values become `None` or empty; workload uses `workload_weights.get(a.get(prospect_status_key) or "", 0)`. No crash; rep may get workload 0 or not be grouped.
- **Invalid types:** If `location_count` were a string or `industry_weights` had non-numeric values, scoring could raise (e.g. `math.log` or multiplication). Assignment assumes list/dict structure; wrong types would raise in Python. Defensive improvement: validate inputs at core boundary or in main.

---

## 3. Idempotency — running the script twice

Core is **stateless**: it only computes from the inputs it’s given. Idempotency of the overall script is determined by:

- How often you run assign and what data you pass (eligible list, rep_accounts).
- Main’s behavior: re-run fetches fresh data; already-owned records are skipped; verification before write avoids overwriting.

So “run twice” doesn’t break things inside core; the same inputs produce the same outputs. Different runs can give different results only if the inputs (e.g. who’s eligible, rep workloads) change.

---

## 4. What you’d improve with more time / what tripped you up

- **Tests:** Unit tests for `score_company` (edge cases: zero/negative locations, unknown industry, clamp at 50). Unit tests for `get_rep_eligibility` and `assign_accounts` (e.g. all reps ineligible, one rep, tie-break order).
- **Tie-breaking:** When multiple reps have the same workload, we take `available[0]`. Order could be made deterministic (e.g. sort by rep name) so runs are reproducible.
- **Configurable “New” weight:** Workload increment for a newly assigned account is `workload_weights.get("New", 5)`. Ensuring this matches the weight used in eligibility (same config) is already the case; documenting it in config helps.
- **Stability under small input changes:** Adding one new unassigned account can change which rep gets which company later in the list (workload order changes). Acceptable for this design but worth documenting.
- **Gotchas:** Mutating `rep_eligibility` in place inside `assign_accounts` is efficient but means the same dict can’t be reused for a second call without resetting; callers (main) only call once per run, so this is fine.
