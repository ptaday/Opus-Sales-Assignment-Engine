"""Unit tests for Account model."""
import pytest
from src.models import Account


class TestAccountFromAttioRecord:
    def test_extracts_record_id_and_data(self, sample_attio_record):
        mapping = {
            "company_name": "company_name",
            "location_count": "location_count",
            "industry": "industry_6",
            "prospect_status": "prospect_status_6",
            "owner": "owner_6",
        }
        acc = Account.from_attio_record(sample_attio_record, mapping)
        assert acc.record_id == "rec-abc123"
        assert acc.get("company_name") == "Test Co"
        assert acc.get("location_count") == 15
        assert acc.get("industry") == "Retail"
        assert acc.get("owner") is None

    def test_missing_slug_returns_none(self):
        record = {"id": {"record_id": "r1"}, "values": {}}
        acc = Account.from_attio_record(record, {"company_name": "company_name"})
        assert acc.record_id == "r1"
        assert acc.get("company_name") is None

    def test_empty_record_id_when_id_missing(self):
        record = {"values": {}}
        acc = Account.from_attio_record(record, {})
        assert acc.record_id == ""


class TestAccountGet:
    def test_returns_default_when_key_missing(self):
        acc = Account(record_id="r1", data={"a": 1})
        assert acc.get("b") is None
        assert acc.get("b", 0) == 0

    def test_returns_value_when_present(self):
        acc = Account(record_id="r1", data={"a": 1})
        assert acc.get("a") == 1
