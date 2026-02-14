"""Shared fixtures for unit and API tests."""
from typing import Optional
import pytest
from pathlib import Path

from src.models import Account


@pytest.fixture
def sample_industry_weights():
    return {"Restaurants": 1.0, "Retail": 1.0, "Other": 0.8}


@pytest.fixture
def sample_workload_weights():
    return {"New": 5, "Working": 4, "Nurture": 3}


@pytest.fixture
def sample_reps():
    return ["Alice", "Bob", "Carol"]


@pytest.fixture
def sample_accounts(sample_reps):
    """Accounts with owner and prospect_status for eligibility tests."""
    def _account(record_id: str, owner: Optional[str] = None, prospect_status: str = "New", location_count: int = 10, industry: str = "Retail"):
        a = Account(record_id=record_id, data={
            "owner": owner,
            "prospect_status": prospect_status,
            "location_count": location_count,
            "industry": industry,
            "company_name": f"Co_{record_id}",
        })
        return a
    return _account


@pytest.fixture
def sample_attio_record():
    """Minimal Attio record shape for from_attio_record tests."""
    return {
        "id": {"record_id": "rec-abc123"},
        "values": {
            "company_name": [{"value": "Test Co"}],
            "location_count": [{"value": 15}],
            "industry_6": [{"option": {"title": "Retail"}}],
            "prospect_status_6": [{"status": {"title": "New"}}],
            "owner_6": [],
        },
    }


@pytest.fixture
def sample_attio_query_response(sample_attio_record):
    """Response for POST .../records/query (single record)."""
    return {"data": [sample_attio_record]}


@pytest.fixture
def sample_assign_config(sample_reps, sample_workload_weights, sample_industry_weights, tmp_path):
    """Minimal assign config for AttioService tests."""
    return {
        "object_type": "companies",
        "reps": sample_reps,
        "max_new_threshold": 2,
        "eligible_industries": {"Restaurants", "Retail"},
        "min_locations": 5,
        "max_locations": 50,
        "attribute_mapping": {
            "company_name": "company_name",
            "location_count": "location_count",
            "industry": "industry_6",
            "prospect_status": "prospect_status_6",
            "owner": "owner_6",
        },
        "owner_key": "owner",
        "industry_key": "industry",
        "location_count_key": "location_count",
        "prospect_status_key": "prospect_status",
        "log_file": tmp_path / "log.json",
        "summary_dir": tmp_path / "summaries",
        "fetch_csv": tmp_path / "fetch.csv",
        "workload_weights": sample_workload_weights,
        "industry_weights": sample_industry_weights,
        "display_name_key": "company_name",
    }


@pytest.fixture
def sample_seed_config(tmp_path):
    """Minimal seed config for generate_companies / append_to_csv tests."""
    return {
        "output_path": tmp_path / "seed.csv",
        "fieldnames": ["company_name", "location_count", "industry"],
        "duplicate_key": "company_name",
        "num_rows": 2,
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 1024,
        "prompt": "Generate {num_rows} companies with fields: {fieldnames}.",
    }
