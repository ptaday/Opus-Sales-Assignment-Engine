"""Live Attio API tests. Run only when ATTIO_API_TOKEN is set. Read-only + no-op update check."""
import os
import pytest
from src.utils.config import load_assign_config
from src.services.attio import AttioService, API_BASE
import requests


pytestmark = pytest.mark.api


@pytest.fixture(scope="module")
def api_token():
    token = os.environ.get("ATTIO_API_TOKEN", "").strip()
    if not token:
        pytest.skip("ATTIO_API_TOKEN not set")
    return token


@pytest.fixture(scope="module")
def config():
    return load_assign_config()


def test_attio_query_live(api_token, config):
    """POST query returns 200 and list of records (live)."""
    url = f"{API_BASE}/objects/{config['object_type']}/records/query"
    payload = {"sorts": [], "limit": 5, "offset": 0}
    headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
    r = requests.post(url, json=payload, headers=headers, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "data" in data
    assert isinstance(data["data"], list)


def test_attio_update_endpoint_live_without_writing(api_token, config):
    """Verify update endpoint is live: GET a record, then PUT same values back (no-op). Skips if ATTIO_TEST_RECORD_ID not set."""
    record_id = os.environ.get("ATTIO_TEST_RECORD_ID", "").strip()
    if not record_id:
        pytest.skip("Set ATTIO_TEST_RECORD_ID to run no-op update check")
    base = f"{API_BASE}/objects/{config['object_type']}/records/{record_id}"
    headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
    # GET current record
    r_get = requests.get(base, headers=headers, timeout=10)
    assert r_get.status_code == 200, r_get.text
    current = r_get.json().get("data", {}).get("values", {})
    owner_slug = config["attribute_mapping"].get("owner", "owner_6")
    prospect_slug = config["attribute_mapping"].get("prospect_status", "prospect_status_6")
    # Build payload with same values (no-op)
    payload = {"data": {"values": {}}}
    if owner_slug in current and current[owner_slug]:
        payload["data"]["values"][owner_slug] = current[owner_slug]
    if prospect_slug in current and current[prospect_slug]:
        payload["data"]["values"][prospect_slug] = current[prospect_slug]
    if not payload["data"]["values"]:
        pytest.skip("Record has no owner/status to send back (empty no-op)")
    r_put = requests.put(base, json=payload, headers=headers, timeout=10)
    assert r_put.status_code == 200, r_put.text
