# Design Decisions

## System Goal

Distribute new prospects across sales reps in Attio fairly, prevent overload, reflect effort differences across pipeline stages, and scale with team size.

## Assumptions

- `prospect_status` is never empty for any named owner and vice versa.
- Effort hierarchy: `New > Working > Nurture`.
- Retail and Restaurants weighted equally.
- Workforce volatility (leave, exits) is out of scope.

## Architecture

- **CLI:** One script, subparsers for `seed`/`fetch`/`assign`. Dry-run skips Attio writes only; summary/log/MD still written.
- **Assign pipeline:** `fetch → score → assign → write` lives in `cmd_assign`; core modules do pure logic only. Config and I/O stay in main/services.
- **Attio as DB layer:** Workspace seeded with company records via CSV. Attio serves as both CRM and structured database (records, attributes, relationships).

## Scoring

- **Company scoring:** Pure function, no I/O. Location weight: `70 × ln(location_count) / ln(50)` (log-scaled, 0–70). Industry multiplier (Retail/Restaurants = 1.0; extensible). Log scaling prevents large-location outliers from dominating.

## Rep Assignment (Workload-weighted Round Robin Ordering)

Three models evaluated; scoring model chosen:

- **Hierarchical sort** (fewest New → Working → Nurture): Simple but ignores workload magnitude. A rep with 0 New but 54 Working still gets assigned.
- **Threshold caps** (New ≤ 5, Working ≤ 10, Nurture ≤ 20): Strong overload protection but binary eligibility; controls inflow, not fairness.
- **Scoring model (chosen):** `score = 2×New + 1×Working + 0.5×Nurture`. Rep must satisfy `New < NEW_CAP`. Lowest score among eligible reps wins. Deterministic tie-breakers. Workload-weighted round-robin; one eligibility dict, mutated during assign.

Scoring + thresholds together handle both scale-up (variance/edge cases) and scale-down (overload risk). Monte Carlo Simulation was run to help make this decision. Scoring model had consistent low average deviations indicating the load to be distributed more evenly across reps.

## Attio Integration

- Single service class; config-driven attribute mapping.
- Verify-before-write to avoid overwriting concurrent assigns.
- Update = one PUT (owner + prospect_status).

## Data Model

- **Pipeline states:** New → Working → Nurture. Ownership preserved across transitions; transfer logic out of scope.
- **Account:** Fixed workflow fields + `data` dict. `from_attio_record` + mapping so schema changes stay in config. Attio multi-value → single value (first entry).

## Seed

- Claude one-shot generates structured CSV via Anthropic API; prompt in config.
- Append dedupes by key (e.g. `company_name`). Overwrite vs append chosen at runtime via prompt.

## Scaling Considerations

- **Team scales up:** As team size grows, workload variance and edge cases grow. Scoring is magnitude-aware and naturally smooths distribution without ordering artifacts. Thresholds serve as guardrails.
- **Team scales down:** With fewer reps, overload risk is higher. Thresholds protect capacity; scoring keeps assignments fair among those still eligible.
- **Hierarchical sort** works for small teams with tight workload ranges but becomes less fair as complexity and variance increase.

## Config

- Plain `KEY=value` files. Seed config has `PROMPT` section; assign config has full defaults so missing file is OK.