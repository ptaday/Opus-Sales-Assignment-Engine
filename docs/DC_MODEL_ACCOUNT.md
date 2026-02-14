# Design Document: Account Model

**Component:** `src/models/account.py` — Account dataclass and Attio record parsing.

---

## 1. Key decisions

- **Fixed + dynamic fields:** `Account` has fixed workflow fields (`record_id`, `score`, `skip_reason`, `assigned_to`) and a `data` dict for schema-dependent attributes (company_name, location_count, industry, owner, etc.). Callers use `a.get(key)` so code doesn’t depend on a fixed list of attributes.
- **Attribute mapping:** `from_attio_record(record, attribute_mapping)` uses a dict from “our” key to Attio slug so the same model works across different Attio schemas; only config changes when slugs change.
- **Single value extraction:** Attio often returns values as a list of entries (e.g. `[{ "value": 10 }]` or option/status objects). `_extract_entry_value` takes the first entry and normalizes option/status/value/full_name/title so the rest of the app sees a single value (str, int, float, or None).
- **record_id from record.id:** We read `record.get("id", {}).get("record_id", "")` so we’re compatible with Attio’s record identity shape. Empty string if missing.
- **Dataclass:** Using a dataclass keeps the type clear and allows default values (e.g. score 0, skip_reason None) so assignment and scoring can mutate in place without creating new instances for every change.

---

## 2. Error handling — API down, missing field, write fails, rate limiting / retry

No I/O or retry in this module:

| Scenario | Behavior |
|----------|----------|
| **Missing field in Attio record** | `values.get(slug, [])` → `[]` → `_extract_entry_value` returns `None`. So any missing attribute becomes `None` in `data`. Callers use `.get(key) or default`. No exception. |
| **Malformed entry shape** | We check `isinstance(entry, dict)` and use `.get()` for option, status, value, etc. Unexpected shapes (e.g. value as list) might return None or a wrong type; we don’t validate structure strictly. |
| **record_id missing** | `(record.get("id") or {}).get("record_id", "")` yields `""`. Main checks `if not a.record_id` before write and skips with reason "No record_id". |
| **attribute_mapping empty or wrong slug** | Every our_key gets a value from `_extract_from_values(values, slug)`; wrong slug → None. No crash; data may be sparse. |

**Summary:** Missing or malformed data is handled by returning None or empty string; no raises from the model for missing fields. Severe misuse (e.g. record not a dict) would still raise.

---

## 3. Idempotency — running the script twice

The model is **stateless**: it only converts a record → Account or returns a value from `data`. Idempotency of the app is determined by how Account instances are used (fetch, assign, write). Creating an Account from the same Attio record twice gives equivalent Account instances; no side effects in the model.

---

## 4. What you’d improve with more time / what tripped you up

- **Stricter parsing:** Optionally validate that critical fields (e.g. record_id, or configurable “required” keys) are present and non-empty after extraction; raise a clear error or a dedicated “invalid” flag so callers don’t rely on None everywhere.
- **Type hints for data:** `data: dict` could be `dict[str, Any]`; could add a TypedDict or a small schema for known keys so IDEs and callers know what to expect.
- **Handling multiple values:** Attio can return multiple entries for some attributes. We only use the first. If multi-value is ever required (e.g. multiple owners), we’d need a convention (e.g. list in data, or comma-separated string).
- **Gotchas:** Option/status objects use `title`; some Attio attributes might use a different field. The extraction order (option → status → full_name → value → title/name) is a heuristic that works for common cases but might need extension for new attribute types. Document that order so future schema changes don’t break silently.
