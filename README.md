# Attio Account Assignment & Seed Data

Seed fictional company data (Claude) and assign unassigned Attio accounts to reps (round-robin, workload-weighted).

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set ATTIO_API_TOKEN and ANTHROPIC_API_KEY
```

## Config

- **config/seed.txt** — output path, CSV columns, prompt, row count for seed data.
- **config/assign.txt** — reps, attio records, location range, workload weights for assignment.

Edit these plain-text files; no code required.

## Commands

From project root:

```bash
# Seed: generate companies via Claude and append to CSV
python -m src.main seed

# Fetch: fetch eligible accounts from Attio into CSV (no assignment)
python -m src.main fetch

# Assign: score, round-robin assign, optionally write to Attio
python -m src.main assign           # live
python -m src.main assign --dry-run # preview only
```

Or use the script:

```bash
./scripts/run_local.sh seed
./scripts/run_local.sh fetch
./scripts/run_local.sh assign
./scripts/run_local.sh assign --dry-run
```

## Outputs

- **out/seed_companies.csv** — seed run output (configurable in config/seed.txt).
- **out/record.csv** — fetch run output.
- **out/assignment_log.json** — per-run audit log for assign.
- **out/summaries/** — timestamped markdown summaries for assign.

## License

MIT
