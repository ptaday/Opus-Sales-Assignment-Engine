# Error Handling

**In place**
- Attio fetch/query: retry + backoff on 429/network (3 retries); rate limit 2s between pages (~30/min).
- Attio update: retries (3) and 1.5s delay between calls (~40/min). Verify: 2 retries, 0.5s delay.
- Anthropic seed: rate limit 5 req/min; retries (5) on rate limit/timeout/connection with backoff.
- Unit tests (core, models, config, seed, Attio with mocks) and API tests (live Attio query + optional no-op update; live Anthropic). See docs/TESTING.md.

## Additional Information:

**Attio (fetch/query)** — Retries on 429 or `RequestException` (exponential backoff, 3 retries). Then exit on failure. Rate limit: 2s delay between pagination pages (~30 req/min).

**Attio (update)** — Retries on 429 or `RequestException` (exponential backoff, 3 retries). Rate limit: 1.5s delay before each update (~40/min). Returns True/False; main records per-record success/failure and continues.

**Attio (verify)** — 0.5s delay before call; 2 retries on 429/network. On final failure we return True (proceed); might overwrite if record was assigned elsewhere.

**Missing fields** — Scoring: `get(loc_key) or 0`, `get(ind_key) or ""`. Assignment: `.get()` and workload default 0. Account parsing: missing slug → None. No crash.

**Seed (Anthropic)** — Rate limit: max 5 requests per minute. Retries (5) on rate limit, timeout, connection errors with backoff. Missing `ANTHROPIC_API_KEY`: raise before calling. Missing field in generated company: `ValueError` before CSV write.

**Config** — `seed.txt` missing: `FileNotFoundError`. `assign.txt` missing: use defaults. Invalid numeric value: `ValueError` when parsing.

**Log/summary** — Corrupt existing log: treat as empty, append. Write failure: can raise (e.g. permission).

