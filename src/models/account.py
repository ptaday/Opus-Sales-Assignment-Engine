"""Account model: fixed fields (record_id, score, skip_reason, assigned_to) + dynamic data dict."""
from dataclasses import dataclass, field
from typing import Any, Optional


def _extract_entry_value(entries: list) -> Any:
    """
    Extracts a single value from Attio's value list (first entry)
    Input: entries (list)
    Output: Any
    """
    if not entries:
        return None
    entry = entries[0]
    if isinstance(entry, dict):
        opt = entry.get("option")
        if opt and isinstance(opt, dict):
            return (opt.get("title") or "").strip() or None
        st = entry.get("status")
        if st and isinstance(st, dict):
            return (st.get("title") or "").strip() or None
        if "full_name" in entry:
            return (entry.get("full_name") or "").strip() or None
        val = entry.get("value")
        if val is not None:
            if isinstance(val, (int, float)):
                return round(val) if isinstance(val, float) and val == int(val) else val
            return str(val).strip() if isinstance(val, str) else val
        return (entry.get("title") or entry.get("name") or "").strip() or None
    return None


def _extract_from_values(values: dict, slug: str) -> Any:
    """
    Gets the value for one Attio slug from record['values'].
    Input: values (dict), slug (str)
    Output: Any
    """
    entries = values.get(slug, [])
    return _extract_entry_value(entries)


@dataclass
class Account:
    """Fixed workflow fields + data dict for schema-dependent attributes."""

    record_id: str
    score: float = 0.0
    skip_reason: Optional[str] = None
    assigned_to: Optional[str] = None
    data: dict = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Returns the value for key from the account's data dict, or default if missing.
        Input: key (str), default (Any, optional)
        Output: Any
        """
        return self.data.get(key, default)

    @staticmethod
    def from_attio_record(record: dict, attribute_mapping: dict[str, str]) -> "Account":
        """
        Builds an Account from an Attio record using attribute_mapping (our_key -> attio_slug); mapped attributes go into data.
        Input: record (dict), attribute_mapping (dict[str, str])
        Output: Account
        """
        values = record.get("values", {})
        record_id = (record.get("id") or {}).get("record_id", "")
        data = {}
        for our_key, slug in attribute_mapping.items():
            raw = _extract_from_values(values, slug)
            if our_key == "company_name" and isinstance(raw, str):
                raw = raw.strip()
            data[our_key] = raw
        return Account(record_id=record_id, data=data)
