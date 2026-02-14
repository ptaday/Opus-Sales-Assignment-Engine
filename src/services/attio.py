"""Attio API: fetch records, update owner, verify."""
import os
import sys
import time
import requests
import dotenv

from src.models import Account

API_BASE = "https://api.attio.com/v2"
from dotenv import load_dotenv


class AttioService:
    def __init__(self, config: dict, api_token: str | None = None):
        """
        Initializes the Attio API service with config and token; sets object type, URLs, and attribute mappings.
        Input: config (dict), api_token (str | None)
        Output: None
        """
        self.config = config
        self.token = api_token or os.environ.get("ATTIO_API_TOKEN", "") or dotenv.get_key(".env", "ATTIO_API_TOKEN")
        self.object_type = config["object_type"]
        self.api_url = f"{API_BASE}/objects/{self.object_type}/records/query"
        self.min_locations = config["min_locations"]
        self.max_locations = config["max_locations"]
        self.eligible_industries = config["eligible_industries"]
        self.reps = config["reps"]
        self.attribute_mapping = config["attribute_mapping"]
        self.owner_key = config["owner_key"]
        self.industry_key = config["industry_key"]
        self.location_count_key = config["location_count_key"]
        self.owner_slug = self.attribute_mapping.get(self.owner_key, "owner_6")
        self.prospect_status_slug = self.attribute_mapping.get(config["prospect_status_key"], "prospect_status_6")
        self.industry_slug = self.attribute_mapping.get(self.industry_key, "industry_6")

    def _headers(self):
        """
        Returns HTTP headers for Attio API requests (Bearer token and JSON content-type).
        Input: None
        Output: dict
        """
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    def _paginated_fetch(self, payload: dict, description: str) -> list[Account]:
        """
        Fetches all records from Attio query API with pagination and maps them to Account objects.
        Input: payload (dict), description (str)
        Output: list[Account]
        """
        accounts = []
        offset = 0
        limit = payload.get("limit", 500)
        while True:
            payload["offset"] = offset
            try:
                r = requests.post(self.api_url, json=payload, headers=self._headers(), timeout=15)
            except requests.RequestException as e:
                print(f"✗ Network error during {description}: {e}")
                sys.exit(1)
            if r.status_code != 200:
                print(f"✗ API Error during {description}: {r.status_code} — {r.text}")
                sys.exit(1)
            data = r.json()
            records = data.get("data", [])
            if not records:
                break
            for record in records:
                accounts.append(Account.from_attio_record(record, self.attribute_mapping))
            if len(records) < limit:
                break
            offset += limit
        return accounts

    def fetch_eligible_candidates(self) -> tuple[list[Account], list[Account]]:
        """
        Fetches candidates from Attio with server-side location/industry filter; splits into eligible (no owner) and skipped_owned.
        Input: None
        Output: tuple[list[Account], list[Account]]
        """
        payload = {
            "filter": {
                "$and": [
                    {"location_count": {"value": {"$gte": self.min_locations, "$lte": self.max_locations}}},
                    {"$or": [{self.industry_slug: ind} for ind in self.eligible_industries]},
                ]
            },
            "sorts": [],
            "limit": 500,
            "offset": 0,
        }
        candidates = self._paginated_fetch(payload, "fetching eligible candidates")
        print(f"Fetched {len(candidates)} candidates from Attio (server-side filtered).")
        eligible = []
        skipped_owned = []
        for a in candidates:
            owner = a.get(self.owner_key)
            if owner:
                a.skip_reason = f"Already owned by {owner}"
                skipped_owned.append(a)
            else:
                eligible.append(a)
        return eligible, skipped_owned

    def fetch_rep_accounts(self) -> list[Account]:
        """
        Fetches all records from Attio and returns only those owned by configured reps (for workload).
        Input: None
        Output: list[Account]
        """
        payload = {"sorts": [], "limit": 500, "offset": 0}
        all_records = self._paginated_fetch(payload, "fetching rep accounts")
        owned = [a for a in all_records if a.get(self.owner_key) and a.get(self.owner_key) in self.reps]
        print(f"Fetched {len(all_records)} total records, {len(owned)} owned by reps.")
        return owned

    def fetch_skipped_unassigned(self) -> list[Account]:
        """
        Fetches unassigned records that fail eligibility (location/industry) for dry-run summary.
        Input: None
        Output: list[Account]
        """
        payload = {"sorts": [], "limit": 500, "offset": 0}
        all_records = self._paginated_fetch(payload, "fetching skipped accounts")
        skipped = []
        for a in all_records:
            if a.get(self.owner_key):
                continue
            loc = a.get(self.location_count_key)
            ind = a.get(self.industry_key)
            if loc is None:
                a.skip_reason = "Missing location_count"
                skipped.append(a)
            elif ind not in self.eligible_industries and (loc or 0) < self.min_locations:
                a.skip_reason = f"Industry '{ind}' not eligible AND too few locations ({loc} < {self.min_locations})"
                skipped.append(a)
            elif ind not in self.eligible_industries:
                a.skip_reason = f"Industry '{ind}' not eligible (need {self.eligible_industries})"
                skipped.append(a)
            elif (loc or 0) < self.min_locations:
                a.skip_reason = f"Too few locations ({loc} < {self.min_locations})"
                skipped.append(a)
            elif (loc or 0) > self.max_locations:
                a.skip_reason = f"Too many locations ({loc} > {self.max_locations})"
                skipped.append(a)
        return skipped

    def verify_still_unassigned(self, record_id: str) -> bool:
        """
        Checks via API whether the record still has no owner (to avoid overwriting concurrent assignment).
        Input: record_id (str)
        Output: bool
        """
        if not self.token:
            return True
        url = f"{API_BASE}/objects/{self.object_type}/records/{record_id}"
        try:
            r = requests.get(url, headers=self._headers(), timeout=10)
            if r.status_code != 200:
                print(f"  ⚠ Could not verify {record_id} (HTTP {r.status_code}) — proceeding")
                return True
            data = r.json()
            owner_values = data.get("data", {}).get("values", {}).get(self.owner_slug, [])
            if owner_values:
                print(f"  ⚠ Record {record_id} was assigned since last fetch — skipping")
                return False
            return True
        except requests.RequestException as e:
            print(f"  ⚠ Verification failed for {record_id}: {e} — proceeding")
            return True

    def update_attio_record(self, record_id: str, owner: str, retries: int = 3) -> bool:
        """
        Updates the Attio record's owner and prospect_status to New; retries on rate limit or network errors.
        Input: record_id (str), owner (str), retries (int)
        Output: bool
        """
        if not self.token:
            print(f"  ⚠ No API token — skipping update for {record_id}")
            return False
        url = f"{API_BASE}/objects/{self.object_type}/records/{record_id}"
        payload = {"data": {"values": {self.owner_slug: owner, self.prospect_status_slug: "New"}}}
        for attempt in range(1, retries + 1):
            try:
                r = requests.put(url, json=payload, headers=self._headers(), timeout=10)
                if r.status_code == 200:
                    return True
                if r.status_code == 429:
                    wait = 2 ** attempt
                    print(f"  ⏳ Rate limited. Retrying in {wait}s... ({attempt}/{retries})")
                    time.sleep(wait)
                else:
                    print(f"  ✗ Failed {record_id}: {r.status_code} — {r.text}")
                    return False
            except requests.RequestException as e:
                wait = 2 ** attempt
                print(f"  ✗ Network error for {record_id}: {e}. Retry in {wait}s... ({attempt}/{retries})")
                time.sleep(wait)
        print(f"  ✗ All {retries} retries failed for {record_id}")
        return False
