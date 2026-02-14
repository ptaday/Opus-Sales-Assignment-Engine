"""Unit tests for Attio service (HTTP mocked with responses)."""
import pytest
import responses
from unittest.mock import patch
from src.services.attio import AttioService, API_BASE


@patch("src.services.attio.time.sleep")
@responses.activate
def test_fetch_eligible_candidates_returns_accounts(mock_sleep, sample_assign_config, sample_attio_query_response):
    config = {**sample_assign_config, "prospect_status_key": "prospect_status"}
    svc = AttioService(config, api_token="test-token")
    url = f"{API_BASE}/objects/{config['object_type']}/records/query"
    responses.add(responses.POST, url, json=sample_attio_query_response)
    eligible, skipped = svc.fetch_eligible_candidates()
    assert len(eligible) == 1
    assert eligible[0].record_id == "rec-abc123"
    assert eligible[0].get("company_name") == "Test Co"
    assert len(skipped) == 0


@patch("src.services.attio.time.sleep")
@responses.activate
def test_fetch_rep_accounts_filters_by_owner(mock_sleep, sample_assign_config, sample_attio_record):
    config = {**sample_assign_config, "prospect_status_key": "prospect_status"}
    # Record with owner Alice
    rec = {**sample_attio_record, "values": {**sample_attio_record["values"], "owner_6": [{"option": {"title": "Alice"}}]}}
    responses.add(
        responses.POST,
        f"{API_BASE}/objects/{config['object_type']}/records/query",
        json={"data": [rec]},
    )
    svc = AttioService(config, api_token="test-token")
    owned = svc.fetch_rep_accounts()
    assert len(owned) == 1
    assert owned[0].get("owner") == "Alice"


@patch("src.services.attio.time.sleep")
@responses.activate
def test_verify_still_unassigned_returns_true_when_no_owner(mock_sleep, sample_assign_config):
    config = {**sample_assign_config, "prospect_status_key": "prospect_status"}
    record_id = "rec-xyz"
    url = f"{API_BASE}/objects/{config['object_type']}/records/{record_id}"
    responses.add(responses.GET, url, json={"data": {"values": {}}})
    svc = AttioService(config, api_token="test-token")
    result = svc.verify_still_unassigned(record_id)
    assert result is True


@patch("src.services.attio.time.sleep")
@responses.activate
def test_verify_still_unassigned_returns_false_when_has_owner(mock_sleep, sample_assign_config):
    config = {**sample_assign_config, "prospect_status_key": "prospect_status"}
    record_id = "rec-xyz"
    owner_slug = config["attribute_mapping"].get("owner", "owner_6")
    url = f"{API_BASE}/objects/{config['object_type']}/records/{record_id}"
    responses.add(responses.GET, url, json={"data": {"values": {owner_slug: [{"option": {"title": "Bob"}}]}}})
    svc = AttioService(config, api_token="test-token")
    result = svc.verify_still_unassigned(record_id)
    assert result is False


@patch("src.services.attio.time.sleep")
@responses.activate
def test_update_attio_record_sends_put_with_owner_and_status(mock_sleep, sample_assign_config):
    config = {**sample_assign_config, "prospect_status_key": "prospect_status"}
    record_id = "rec-update"
    url = f"{API_BASE}/objects/{config['object_type']}/records/{record_id}"
    responses.add(responses.PUT, url, json={}, status=200)
    svc = AttioService(config, api_token="test-token")
    result = svc.update_attio_record(record_id, "Alice")
    assert result is True
    assert len(responses.calls) >= 1
    put_call = [c for c in responses.calls if c.request.method == "PUT"][0]
    body = put_call.request.body
    assert b"Alice" in body or "Alice" in (body.decode() if isinstance(body, bytes) else str(body))
    assert b"New" in body or "New" in (body.decode() if isinstance(body, bytes) else str(body))


@patch("src.services.attio.time.sleep")
@responses.activate
def test_update_attio_record_returns_false_on_non_200(mock_sleep, sample_assign_config):
    config = {**sample_assign_config, "prospect_status_key": "prospect_status"}
    record_id = "rec-bad"
    url = f"{API_BASE}/objects/{config['object_type']}/records/{record_id}"
    responses.add(responses.PUT, url, json={"error": "bad"}, status=400)
    svc = AttioService(config, api_token="test-token")
    result = svc.update_attio_record(record_id, "Alice")
    assert result is False
