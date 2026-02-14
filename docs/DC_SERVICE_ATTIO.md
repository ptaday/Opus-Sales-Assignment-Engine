# Design Document: Attio Service

**Component:** `src/services/attio.py` — Attio API client: fetch records, update owner, verify unassigned.

---

## 1. Key decisions

- **Single service class:** `AttioService` holds config, token, and derived settings (URLs, slugs). All Attio calls go through it so token and object type are consistent.
- **Attribute mapping:** Config maps logical keys (e.g. `company_name`, `owner`) to Attio attribute slugs. The service uses these to build filters and read/write values, so schema changes mostly stay in config.
- **Paginated fetch:** `_paginated_fetch` loops with offset/limit until no more records; all pages are merged into one list of `Account`. Limit 500 per request to match typical API limits.
- **Server-side filter for candidates:** Eligible-candidates query uses Attio filter for `location_count` range and industry (via slug), reducing payload and keeping one place for eligibility rules that match assign config.
- **Verification before write:** Before updating a record we call `verify_still_unassigned(record_id)` so we don’t overwrite if another process assigned it. On verification failure (e.g. HTTP error) we currently “proceed” (return True) to avoid blocking on transient errors; the record might already be assigned.
- **Owner + prospect_status in one PUT:** Update sets both owner and prospect_status to "New" in a single PUT so the record state is consistent.

---

## 2. Error handling — API down, missing field, write fails partway, rate limiting / retry

| Scenario | Behavior |
|----------|----------|
| **API down / network error (fetch)** | `_paginated_fetch` catches `requests.RequestException`, prints message, and calls `sys.exit(1)`. No retry; process exits. |
| **Non-200 on query** | Same path: print status and body, `sys.exit(1)`. |
| **Missing field in record** | `Account.from_attio_record` uses `_extract_from_values`; missing slug returns `None`. Callers (main, scoring) use `.get(key) or default`. No exception from service for missing attributes. |
| **Write fails (single record)** | `update_attio_record` returns `False` after exhausting retries. Main records that in `write_results` and continues with the next record. No rollback of previous successful updates. |
| **Write fails partway through batch** | Each record is updated one-by-one. Some succeed, some fail; main collects all results. No transactional “all or nothing.” |
| **Rate limiting (429)** | Only in `update_attio_record`: on 429 we sleep `2 ** attempt` seconds and retry, up to `retries` (default 3). Other methods do not retry on 429. |
| **Retry logic** | Retries only for `update_attio_record`: on 429 or `RequestException`, exponential backoff and retry. Fetch/query/verify have no retry. |

**Summary:** Fetch/query fail fast (exit). Update retries with backoff and returns success/failure per record; main continues and logs failures.

---

## 3. Idempotency — running the script twice

- **Fetch:** Each run fetches current data from Attio. Main appends only new `record_id`s to CSV. Second run: same API response conceptually; CSV append is deduplicated by record_id → idempotent for “what’s in the CSV.”
- **Assign:** 
  - Eligible list excludes already-owned records (server-side or client-side filter).
  - Before each write, `verify_still_unassigned(record_id)` is called; if the record was assigned in between, we skip and don’t overwrite.
  - So running assign twice doesn’t double-assign the same record; second run only writes records that are still unassigned.

---

## 4. What you’d improve with more time / what tripped you up

- **Retry for fetch/query:** Add retries with backoff for `_paginated_fetch` (and thus `fetch_eligible_candidates`, `fetch_rep_accounts`, `fetch_skipped_unassigned`) so transient network or 429s don’t kill the process.
- **Rate limiting on read:** If Attio rate-limits query endpoints, we don’t currently back off; we’d exit. Adding 429 handling and backoff to the query path would make long runs more robust.
- **Configurable timeouts/retries:** Timeouts (15s query, 10s get/put) and retry count are hardcoded; moving them to config would help for slow or flaky networks.
- **Verification on failure:** When `verify_still_unassigned` can’t reach the API we return True (“proceed”). That can overwrite an already-assigned record in theory. Alternative: return False on any verification error and skip the write (safer but more skips on transient errors). Document the current choice.
- **Pagination edge:** If the API ever returns exactly `limit` records every time and has a bug (e.g. same page), we could loop forever. Defensive cap on total pages or records would prevent that.
- **Gotchas:** Filter uses `location_count` by name; if your Attio object uses a different slug for that attribute, the filter might be wrong. Attribute mapping is used for industry and response parsing but the filter in the code uses the key name — worth confirming or making filter keys configurable from the same mapping.
