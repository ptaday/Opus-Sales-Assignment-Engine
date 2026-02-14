# Architecture Overview

Attio Account Assignment & Seed — a CLI application that seeds fictional company data via Claude and assigns unassigned Attio accounts to sales reps using workload-weighted round-robin.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│  CLI (main.py)                                                           │
│  seed | fetch | assign [--dry-run]                                       │
└───────────┬─────────────────────────┬───────────────────┬────────────────┘
            │                         │                   │
            ▼                         ▼                   ▼
┌───────────────────┐   ┌─────────────────────┐   ┌─────────────────────────┐
│  SeedService      │   │  AttioService       │   │  Assignment Pipeline    │
│  (seed_service)   │   │  (attio.py)         │   │  (assignment.py,        │
│                   │   │                     │   │   scoring.py)           │
│  • Claude API     │   │  • Fetch records    │   │                         │
│  • CSV append     │   │  • Update owner     │   │  • Rep eligibility      │
│                   │   │  • Verify unassigned│   │  • Workload sort        │
└────────┬──────────┘   └──────────┬──────────┘   │  • Round-robin assign   │
         │                         │              └────────────┬────────────┘
         │                         │                           │
         ▼                         ▼                           ▼
┌─────────────────┐   ┌─────────────────────┐   ┌─────────────────────────┐
│  config/seed.txt│   │  Attio API (HTTP)   │   │  config/assign.txt      │
│  CSV output     │   │  objects/*/records  │   │  (reps, thresholds,     │
└─────────────────┘   └─────────────────────┘   │   weights, mapping)     │
                                                └─────────────────────────┘
```

**Layers:**
- **CLI** — Entry point; dispatches to seed, fetch, or assign.
- **Services** — External I/O: Claude API, Attio API, file I/O.
- **Core** — Pure logic: scoring, rep eligibility, assignment algorithm.
- **Config** — Plain-text `config/*.txt` files (KEY = value).
- **Models** — `Account` dataclass; schema-agnostic via `data` dict + attribute mapping.

---

## Class Diagram

```mermaid
classDiagram
    class Account {
        +str record_id
        +float score
        +str skip_reason
        +str assigned_to
        +dict data
        +get(key, default)
        +from_attio_record(record, attribute_mapping)
    }

    class AttioService {
        -dict config
        -str token
        -str object_type
        -dict attribute_mapping
        +__init__(config, api_token)
        +fetch_eligible_candidates() (eligible, skipped_owned)
        +fetch_rep_accounts() list
        +fetch_skipped_unassigned() list
        +verify_still_unassigned(record_id) bool
        +update_attio_record(record_id, owner, retries) bool
    }

    class SeedService {
        <<module>>
        +generate_companies(api_key, config) list
        +append_to_csv(companies, csv_path, config) tuple
        +run_seed()
    }

    class ConfigUtils {
        <<module>>
        +load_seed_config() dict
        +load_assign_config() dict
        -_parse_key_value_pairs(s) dict
        -_parse_attribute_mapping(s) dict
    }

    class Scoring {
        <<module>>
        +score_company(location_count, industry, industry_weights) float
    }

    class Assignment {
        <<module>>
        +get_rep_eligibility(rep_accounts, reps, workload_weights, max_new_threshold, ...) dict
        +assign_accounts(eligible, rep_eligibility, workload_weights, max_new_threshold) tuple
    }

    class Main {
        <<CLI>>
        +cmd_seed()
        +cmd_fetch()
        +cmd_assign(dry_run)
    }

    Account --> AttioService : created from Attio records
    AttioService --> Account : returns
    SeedService --> ConfigUtils : load_seed_config
    Main --> SeedService : cmd_seed
    Main --> AttioService : cmd_fetch, cmd_assign
    Main --> ConfigUtils : load_assign_config
    Main --> Scoring : score_company
    Main --> Assignment : get_rep_eligibility, assign_accounts
    Assignment --> Account : consumes/updates
```

---

## Sequence Diagrams

### Seed Flow

```mermaid
sequenceDiagram
    participant User
    participant Main
    participant Config
    participant SeedService
    participant Claude
    participant CSV

    User->>Main: python -m src.main seed
    Main->>Config: load_seed_config()
    Config-->>Main: config (output_path, prompt, num_rows, ...)
    Main->>SeedService: run_seed()
    SeedService->>Config: load_seed_config()
    SeedService->>SeedService: _ask_overwrite_or_append()
    SeedService->>Claude: messages.create(prompt)
    Claude-->>SeedService: JSON companies
    SeedService->>SeedService: append_to_csv(companies)
    SeedService->>CSV: append rows (dedupe by company_name)
    SeedService-->>User: Summary (added, skipped, total)
```

### Fetch Flow

```mermaid
sequenceDiagram
    participant User
    participant Main
    participant Config
    participant AttioService
    participant AttioAPI
    participant CSV

    User->>Main: python -m src.main fetch
    Main->>Config: load_assign_config()
    Config-->>Main: config
    Main->>AttioService: fetch_eligible_candidates()
    AttioService->>AttioAPI: POST /objects/{type}/records/query
    AttioAPI-->>AttioService: records
    AttioService->>AttioService: filter owner empty (eligible vs skipped_owned)
    AttioService-->>Main: eligible, skipped_owned
    Main->>Main: append new accounts to FETCH_CSV
    Main-->>User: Saved N new accounts to out/record.csv
```

### Assign Flow

```mermaid
sequenceDiagram
    participant User
    participant Main
    participant Config
    participant AttioService
    participant Scoring
    participant Assignment
    participant AttioAPI

    User->>Main: python -m src.main assign [--dry-run]
    Main->>Config: load_assign_config()
    Main->>AttioService: fetch_eligible_candidates()
    AttioService->>AttioAPI: query records (filter location, industry)
    AttioAPI-->>AttioService: candidates
    AttioService-->>Main: eligible, skipped_owned

    Main->>AttioService: fetch_rep_accounts()
    AttioService->>AttioAPI: query all records
    AttioAPI-->>AttioService: records
    AttioService-->>Main: rep_accounts

    Main->>Scoring: score_company() for each
    Main->>Main: sort eligible by score desc

    Main->>Assignment: get_rep_eligibility(rep_accounts, ...)
    Assignment-->>Main: rep_eligibility (workload, new_count, eligible)

    Main->>Assignment: assign_accounts(eligible, rep_eligibility, ...)
    loop For each company
        Assignment->>Assignment: sort reps by workload, pick lowest
        Assignment->>Assignment: update rep_eligibility (workload, new_count)
    end
    Assignment-->>Main: assigned, unassigned

    alt not dry_run and assigned
        loop For each assigned
            Main->>AttioService: verify_still_unassigned(record_id)
            Main->>AttioService: update_attio_record(record_id, owner)
            AttioService->>AttioAPI: PUT /records/{id} (owner, prospect_status=New)
        end
    end

    Main->>Main: _print_summary, _save_run_log, _save_summary_md
    Main-->>User: Assignment summary
```

---

## File Layout

```
├── config/
│   ├── seed.txt       # Seed: output path, prompt, columns, row count
│   └── assign.txt     # Assign: reps, thresholds, weights, attribute mapping
├── docs/         
│   └── ARCHITECTURE.md       #Architecture overview, flows, project structure
│   ├── DESIGN_DECISIONS.md   #System goal, assumptions, scoring logic
│   └── ERROR_HANDLING.md     
│   ├── IDEMPOTENCY.md        
│   ├── IMPROVEMENTS.md      #Future improvements, tricky bits
│   └── SUMMARY_OF_FILES.md 
│   └── TESTING.md           #Unit tests, testing coverage
├── out/               # Outputs (gitignored)
│   ├── seed_companies.csv
│   ├── record.csv
│   ├── assignment_log.json
│   └── summaries/
├── scripts/
│   └── run_local.sh
├── simulations/
│   └── monte_carlo_simulation_round_robin_order.jsx
├── src/
│   ├── main.py        # CLI entry
│   ├── core/
│   │   ├── assignment.py   # Rep eligibility, round-robin assign
│   │   └── scoring.py      # location × industry score
│   ├── models/
│   │   └── account.py      # Account dataclass
│   ├── services/
│   │   ├── attio.py        # Attio API client
│   │   └── seed_service.py # Claude + CSV
│   └── utils/
│       └── config.py       # Load config/seed.txt, config/assign.txt
└── tests/
```
