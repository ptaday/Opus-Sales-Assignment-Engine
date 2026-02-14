# Testing

How to run tests and what they cover.

## Quick start

From project root with venv activated:

```bash
./scripts/run_tests.sh              # unit only (default)
./scripts/run_tests.sh unit --coverage
./scripts/run_tests.sh api          # live API tests
./scripts/run_tests.sh all          # unit + API
./scripts/run_tests.sh all --coverage
```

Or run pytest directly:

```bash
pytest tests/unit/ -v
pytest tests/unit/ -v --cov=src --cov-report=term-missing
pytest tests/api/ -v -m api
pytest tests/ -v
```

## Layout

| Path | Purpose |
|------|--------|
| **tests/unit/** | Unit tests. No live APIs; Attio/Claude mocked. Fast. |
| **tests/api/** | Live API tests. Require credentials; skip if unset. |
| **tests/conftest.py** | Shared fixtures (config, accounts, Attio response shapes). |
| **pytest.ini** | `testpaths`, `pythonpath`, marker `api`. |

## Unit tests

- **test_core.py** — `score_company` (zero, range, monotonicity), `get_rep_eligibility`, `assign_accounts` (invariants: assigned + unassigned = eligible, each has one rep).
- **test_models.py** — `Account.from_attio_record` (record_id, data from values), `Account.get`.
- **test_utils_config.py** — `_parse_key_value_pairs`, `_parse_attribute_mapping`, `_resolve_path`; `load_seed_config` (missing file raises); `load_assign_config` (defaults / file override).
- **test_seed_service.py** — `_format_cell`, `load_existing_keys`, `append_to_csv` (create, dedupe); `generate_companies` (mocked Claude: parsing, validation, code-fence strip).
- **test_attio_service.py** — Attio HTTP mocked with **responses**. Fetch eligible/rep accounts, verify still unassigned, update record (payload shape, success/failure).

Dependencies: `pytest`, `responses`, `pytest-cov` (optional). No env vars required.

## API tests

Marked with `@pytest.mark.api`. Run with `pytest tests/api/ -v -m api` or `./scripts/run_tests.sh api`.

| Test | Env | What it does |
|------|-----|----------------|
| **test_attio_live.py** | `ATTIO_API_TOKEN` | POST query → 200 and `data` list. Optional: `ATTIO_TEST_RECORD_ID` → GET record then PUT same values (no-op; confirms update endpoint is live). |
| **test_anthropic_live.py** | `ANTHROPIC_API_KEY` | One `messages.create` call; asserts non-empty content. |

If a credential is missing, that test (or file) is skipped. CI can run `pytest tests/unit/` or `pytest -m "not api"` to avoid needing secrets.

## Coverage

```bash
pytest tests/unit/ --cov=src --cov-report=term-missing
# or
./scripts/run_tests.sh unit --coverage
```

Coverage is over `src/`; API tests are excluded when measuring so results don’t depend on credentials.

## CI

- Default: run unit tests only: `pytest tests/unit/ -v`.
- With secrets: run all: `pytest tests/ -v` or `pytest tests/api/ -v -m api`.

## Result

<img width="908" height="281" alt="Screenshot 2026-02-14 at 5 47 52 PM" src="https://github.com/user-attachments/assets/292e8f26-7f43-410f-903e-442fbcea7abe" />
