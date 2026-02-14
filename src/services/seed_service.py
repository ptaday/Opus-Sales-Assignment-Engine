"""Seed data: Claude API + CSV append."""
import os
import json
import csv
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

try:
    import anthropic
except ImportError:
    anthropic = None

from src.utils.config import load_seed_config

# Anthropic: max 5 requests per minute; retries for rate limit / transient errors
ANTHROPIC_MAX_REQUESTS_PER_MINUTE = 5
ANTHROPIC_RETRIES = 5
_anthropic_call_times: list[float] = []


def _anthropic_rate_limit() -> None:
    """Enforce max 5 Anthropic API calls per minute."""
    now = time.monotonic()
    window = 60.0
    _anthropic_call_times[:] = [t for t in _anthropic_call_times if now - t < window]
    if len(_anthropic_call_times) >= ANTHROPIC_MAX_REQUESTS_PER_MINUTE:
        sleep_until = _anthropic_call_times[0] + window - now
        if sleep_until > 0:
            time.sleep(sleep_until)
        _anthropic_call_times.pop(0)
    _anthropic_call_times.append(time.monotonic())


def _format_cell(value, key: str):
    """
    Normalizes a cell value for CSV: empty to empty string, strings stripped.
    Input: value (any), key (str)
    Output: str or original type
    """
    if value is None or value == "":
        return ""
    if isinstance(value, str):
        return value.strip()
    return value


def load_existing_keys(csv_path: Path, key_field: str) -> set:
    """
    Loads existing values for the given key field from CSV into a set (for duplicate detection).
    Input: csv_path (Path), key_field (str)
    Output: set
    """
    existing = set()
    if not csv_path.exists():
        return existing
    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            val = row.get(key_field, "").strip().lower()
            if val:
                existing.add(val)
    return existing


def generate_companies(api_key: str, config: dict) -> list[dict]:
    """
    Calls Claude API with the seed prompt to generate a list of company dicts; validates required fields.
    Rate-limited to 5 req/min; retries on rate limit or transient errors.
    Input: api_key (str), config (dict)
    Output: list[dict]
    """
    if not anthropic:
        raise RuntimeError("anthropic package required for seed. pip install anthropic")
    client = anthropic.Anthropic(api_key=api_key)
    prompt = config["prompt"].format(
        num_rows=config["num_rows"],
        fieldnames=", ".join(config["fieldnames"]),
    )
    print("Calling Claude API to generate company data...")
    for attempt in range(1, ANTHROPIC_RETRIES + 1):
        _anthropic_rate_limit()
        try:
            message = client.messages.create(
                model=config["model"],
                max_tokens=config["max_tokens"],
                messages=[{"role": "user", "content": prompt}],
            )
            raw = message.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1]
                raw = raw.rsplit("```", 1)[0]
            companies = json.loads(raw)
            for c in companies:
                for field in config["fieldnames"]:
                    if field not in c:
                        raise ValueError(f"Missing field '{field}' in generated company: {c}")
            print(f"Generated {len(companies)} companies from Claude API.")
            return companies
        except Exception as e:
            msg = str(e).lower()
            is_retryable = (
                "rate" in msg or "429" in msg or "timeout" in msg or "connection" in msg
                or isinstance(e, (ConnectionError, TimeoutError, OSError))
            )
            try:
                if getattr(anthropic, "RateLimitError", None) and isinstance(e, anthropic.RateLimitError):
                    is_retryable = True
            except Exception:
                pass
            if is_retryable:
                if attempt < ANTHROPIC_RETRIES:
                    wait = 2 ** attempt
                    print(f"⏳ Claude API error ({e}). Retrying in {wait}s... ({attempt}/{ANTHROPIC_RETRIES})")
                    time.sleep(wait)
                else:
                    raise
            else:
                raise


def append_to_csv(companies: list[dict], csv_path: Path, config: dict) -> tuple[int, int]:
    """
    Appends company rows to CSV, skipping duplicates by duplicate_key; creates file/header if needed.
    Input: companies (list[dict]), csv_path (Path), config (dict)
    Output: tuple[int, int]
    """
    fieldnames = config["fieldnames"]
    duplicate_key = config["duplicate_key"]
    existing = load_existing_keys(csv_path, duplicate_key)
    file_exists = csv_path.exists()
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    added = skipped = 0
    duplicates = []
    with open(csv_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        for company in companies:
            key_val = (company.get(duplicate_key) or "").strip().lower()
            if key_val in existing:
                skipped += 1
                duplicates.append(company.get(duplicate_key, ""))
                continue
            existing.add(key_val)
            row = {k: _format_cell(company.get(k), k) for k in fieldnames}
            writer.writerow(row)
            added += 1
    if duplicates:
        print(f"\nDuplicates skipped: {duplicates}")
    return added, skipped


def _ask_overwrite_or_append(output_path: Path) -> bool:
    """
    Prompts user to choose overwrite or append when output file exists; returns True for overwrite, False for append.
    Input: output_path (Path)
    Output: bool
    """
    if not output_path.exists():
        return False
    while True:
        reply = input(
            f"The file '{output_path}' already exists. "
            "Overwrite (replace entire file) or append (add new rows)? [o/a]: "
        ).strip().lower()
        if reply in ("o", "overwrite"):
            return True
        if reply in ("a", "append"):
            return False
        print("Please enter 'o' for overwrite or 'a' for append.")


def run_seed() -> None:
    """
    Orchestrates seed: loads config, asks overwrite/append, generates companies via Claude, appends to CSV, prints summary.
    Input: None
    Output: None
    """
    config = load_seed_config()
    overwrite = _ask_overwrite_or_append(config["output_path"])
    if overwrite:
        config["output_path"].unlink(missing_ok=True)
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key or not api_key.strip():
        raise ValueError(
             "ANTHROPIC_API_KEY is missing or empty. "
            "Please set it in your .env file."
            )

    companies = generate_companies(api_key, config)
    added, skipped = append_to_csv(companies, config["output_path"], config)
    total = 0
    if config["output_path"].exists():
        with open(config["output_path"], "r", newline="") as f:
            total = sum(1 for _ in csv.DictReader(f))
    print(f"\n--- Summary ---")
    print(f"Generated:  {len(companies)}")
    print(f"Added:      {added}")
    print(f"Duplicates: {skipped}")
    print(f"Total in {config['output_path']}: {total}")
