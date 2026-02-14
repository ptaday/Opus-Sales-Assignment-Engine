"""Load plain-text config files from config/ (key = value; PROMPT section for seed)."""
import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = _REPO_ROOT / "config"


def _parse_key_value_pairs(s: str) -> dict:
    """Parse 'Key:number, Key:number' into a dict."""
    out = {}
    for part in (s or "").split(","):
        part = part.strip()
        if ":" in part:
            k, _, v = part.partition(":")
            k, v = k.strip(), v.strip()
            try:
                n = float(v)
                out[k] = int(n) if n == int(n) else n
            except ValueError:
                pass
    return out


def _parse_attribute_mapping(s: str) -> dict[str, str]:
    """Parse 'key:slug, key:slug' into dict (our key -> Attio slug)."""
    out = {}
    for part in (s or "").split(","):
        part = part.strip()
        if ":" in part:
            k, _, v = part.partition(":")
            k, v = k.strip(), v.strip()
            if k and v:
                out[k] = v
    return out


def _resolve_path(path_str: str) -> Path:
    """Resolve path relative to repo root; absolute stays as-is."""
    path_str = (path_str or "").strip()
    if not path_str:
        return _REPO_ROOT / "out"
    if os.path.isabs(path_str):
        return Path(path_str)
    return _REPO_ROOT / path_str


def load_seed_config() -> dict:
    """Load config/seed.txt. KEY = value; then line PROMPT and rest is prompt text."""
    config_path = CONFIG_DIR / "seed.txt"
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    text = config_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    settings = {}
    prompt_lines = []
    seen_prompt = False

    for line in lines:
        stripped = line.strip()
        if seen_prompt:
            prompt_lines.append(line)
            continue
        if stripped == "PROMPT":
            seen_prompt = True
            continue
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        settings[key.strip()] = value.strip()

    output_path = _resolve_path(settings.get("OUTPUT_PATH", "out/seed_companies.csv"))
    columns_raw = settings.get("COLUMNS", "company_name, location_count, industry, prospect_status, owner")
    columns = [c.strip() for c in columns_raw.split(",") if c.strip()]

    return {
        "output_path": output_path,
        "fieldnames": columns or ["company_name", "location_count", "industry", "prospect_status", "owner"],
        "duplicate_key": settings.get("DUPLICATE_KEY", "company_name").strip(),
        "num_rows": int(settings.get("NUM_ROWS", "30")),
        "model": settings.get("MODEL", "claude-opus-4-6").strip(),
        "max_tokens": int(settings.get("MAX_TOKENS", "4096")),
        "prompt": "\n".join(prompt_lines).strip(),
    }


def load_assign_config() -> dict:
    """Load config/assign.txt. KEY = value only."""
    config_path = CONFIG_DIR / "assign.txt"
    defaults = {
        "OBJECT_TYPE": "unassigned_accounts",
        "REPS": "Alice, Bob, Carol",
        "MAX_NEW_THRESHOLD": "2",
        "ELIGIBLE_INDUSTRIES": "Restaurants, Retail",
        "MIN_LOCATIONS": "5",
        "MAX_LOCATIONS": "50",
        "LOG_FILE": "out/assignment_log.json",
        "SUMMARY_DIR": "out/summaries",
        "FETCH_CSV": "out/record.csv",
        "WORKLOAD_WEIGHTS": "New:5, Working:4, Nurture:3",
        "INDUSTRY_WEIGHTS": "Restaurants:1.0, Retail:1.0",
        "ATTRIBUTE_MAPPING": "company_name:company_name, location_count:location_count, industry:industry_6, prospect_status:prospect_status_6, owner:owner_6",
        "DISPLAY_NAME_KEY": "company_name",
        "INDUSTRY_KEY": "industry",
        "LOCATION_COUNT_KEY": "location_count",
        "OWNER_KEY": "owner",
        "PROSPECT_STATUS_KEY": "prospect_status",
    }
    settings = dict(defaults)
    if config_path.exists():
        text = config_path.read_text(encoding="utf-8")
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            settings[key.strip()] = value.strip()

    reps_list = [r.strip() for r in settings.get("REPS", defaults["REPS"]).split(",") if r.strip()]
    industries_set = {i.strip() for i in settings.get("ELIGIBLE_INDUSTRIES", defaults["ELIGIBLE_INDUSTRIES"]).split(",") if i.strip()}
    attr_mapping = _parse_attribute_mapping(settings.get("ATTRIBUTE_MAPPING", defaults["ATTRIBUTE_MAPPING"]))
    if not attr_mapping:
        attr_mapping = _parse_attribute_mapping(defaults["ATTRIBUTE_MAPPING"])

    return {
        "object_type": settings.get("OBJECT_TYPE", defaults["OBJECT_TYPE"]).strip(),
        "reps": reps_list or ["Alice", "Bob", "Carol"],
        "max_new_threshold": int(settings.get("MAX_NEW_THRESHOLD", defaults["MAX_NEW_THRESHOLD"])),
        "eligible_industries": industries_set or {"Restaurants", "Retail"},
        "min_locations": int(settings.get("MIN_LOCATIONS", defaults["MIN_LOCATIONS"])),
        "max_locations": int(settings.get("MAX_LOCATIONS", defaults["MAX_LOCATIONS"])),
        "log_file": _resolve_path(settings.get("LOG_FILE", defaults["LOG_FILE"])),
        "summary_dir": _resolve_path(settings.get("SUMMARY_DIR", defaults["SUMMARY_DIR"])),
        "fetch_csv": _resolve_path(settings.get("FETCH_CSV", defaults["FETCH_CSV"])),
        "workload_weights": _parse_key_value_pairs(settings.get("WORKLOAD_WEIGHTS", defaults["WORKLOAD_WEIGHTS"])) or {"New": 5, "Working": 4, "Nurture": 3},
        "industry_weights": _parse_key_value_pairs(settings.get("INDUSTRY_WEIGHTS", defaults["INDUSTRY_WEIGHTS"])) or {"Restaurants": 1.0, "Retail": 1.0},
        "attribute_mapping": attr_mapping,
        "display_name_key": settings.get("DISPLAY_NAME_KEY", defaults["DISPLAY_NAME_KEY"]).strip(),
        "industry_key": settings.get("INDUSTRY_KEY", defaults["INDUSTRY_KEY"]).strip(),
        "location_count_key": settings.get("LOCATION_COUNT_KEY", defaults["LOCATION_COUNT_KEY"]).strip(),
        "owner_key": settings.get("OWNER_KEY", defaults["OWNER_KEY"]).strip(),
        "prospect_status_key": settings.get("PROSPECT_STATUS_KEY", defaults["PROSPECT_STATUS_KEY"]).strip(),
    }
