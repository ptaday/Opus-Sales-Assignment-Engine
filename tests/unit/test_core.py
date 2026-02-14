"""Unit tests for scoring and assignment."""
import pytest
from src.core.scoring import score_company
from src.core.assignment import get_rep_eligibility, assign_accounts
from src.models import Account


class TestScoreCompany:
    def test_zero_locations_returns_zero(self, sample_industry_weights):
        assert score_company(0, "Retail", sample_industry_weights) == 0.0

    def test_negative_locations_returns_zero(self, sample_industry_weights):
        assert score_company(-1, "Retail", sample_industry_weights) == 0.0

    def test_unknown_industry_uses_default_weight(self, sample_industry_weights):
        s = score_company(10, "Unknown", sample_industry_weights)
        assert isinstance(s, float) and s >= 0 and s <= 70

    def test_higher_location_higher_score(self, sample_industry_weights):
        s5 = score_company(5, "Retail", sample_industry_weights)
        s50 = score_company(50, "Retail", sample_industry_weights)
        assert s50 >= s5

    def test_returns_float_in_range(self, sample_industry_weights):
        s = score_company(25, "Restaurants", sample_industry_weights)
        assert isinstance(s, float) and 0 <= s <= 70


class TestGetRepEligibility:
    def test_eligible_when_under_threshold(self, sample_accounts, sample_reps, sample_workload_weights):
        accounts = [
            sample_accounts("r1", "Alice", "New"),
            sample_accounts("r2", "Alice", "Working"),
        ]
        el = get_rep_eligibility(
            accounts, sample_reps, sample_workload_weights,
            max_new_threshold=2, owner_key="owner", prospect_status_key="prospect_status",
        )
        assert el["Alice"]["eligible"] is True
        assert el["Alice"]["new_count"] == 1
        assert el["Alice"]["workload"] == 5 + 4

    def test_ineligible_when_at_threshold(self, sample_accounts, sample_reps, sample_workload_weights):
        accounts = [
            sample_accounts("r1", "Alice", "New"),
            sample_accounts("r2", "Alice", "New"),
        ]
        el = get_rep_eligibility(
            accounts, sample_reps, sample_workload_weights,
            max_new_threshold=2, owner_key="owner", prospect_status_key="prospect_status",
        )
        assert el["Alice"]["eligible"] is False
        assert el["Alice"]["new_count"] == 2


class TestAssignAccounts:
    def test_assigned_plus_unassigned_equals_eligible(self, sample_accounts, sample_industry_weights, sample_workload_weights):
        eligible = [
            sample_accounts("e1", None),
            sample_accounts("e2", None),
        ]
        rep_eligibility = get_rep_eligibility(
            [], ["Alice", "Bob"], sample_workload_weights,
            max_new_threshold=5, owner_key="owner", prospect_status_key="prospect_status",
        )
        assigned, unassigned = assign_accounts(
            eligible, rep_eligibility, sample_workload_weights, max_new_threshold=5,
        )
        assert len(assigned) + len(unassigned) == len(eligible)

    def test_each_assigned_has_one_rep(self, sample_accounts, sample_workload_weights):
        eligible = [sample_accounts("e1", None), sample_accounts("e2", None)]
        rep_eligibility = get_rep_eligibility(
            [], ["Alice", "Bob"], sample_workload_weights,
            max_new_threshold=5, owner_key="owner", prospect_status_key="prospect_status",
        )
        assigned, _ = assign_accounts(eligible, rep_eligibility, sample_workload_weights, max_new_threshold=5)
        for a in assigned:
            assert a.assigned_to in ("Alice", "Bob")

    def test_unassigned_when_no_eligible_reps(self, sample_accounts, sample_workload_weights):
        eligible = [sample_accounts("e1", None)]
        rep_eligibility = get_rep_eligibility(
            [
                sample_accounts("a1", "Alice", "New"),
                sample_accounts("a2", "Alice", "New"),
            ],
            ["Alice"], sample_workload_weights,
            max_new_threshold=2, owner_key="owner", prospect_status_key="prospect_status",
        )
        assigned, unassigned = assign_accounts(
            eligible, rep_eligibility, sample_workload_weights, max_new_threshold=2,
        )
        assert len(assigned) == 0
        assert len(unassigned) == 1
        assert "No eligible reps" in (unassigned[0].skip_reason or "")
