"""Round-robin assignment and rep eligibility."""
from collections import defaultdict

from src.models import Account


def get_rep_eligibility(
    rep_accounts: list[Account],
    reps: list[str],
    workload_weights: dict,
    max_new_threshold: int,
    owner_key: str,
    prospect_status_key: str,
) -> dict:
    """
    Computes per-rep eligibility: workload (sum of weights) and ineligible if new_count >= max_new_threshold.
    Input: rep_accounts (list[Account]), reps (list[str]), workload_weights (dict), max_new_threshold (int), owner_key (str), prospect_status_key (str)
    Output: dict
    """
    grouped = defaultdict(list)
    for a in rep_accounts:
        owner = a.get(owner_key)
        if owner and owner in reps:
            grouped[owner].append(a)

    eligibility = {}
    for rep in reps:
        accounts = grouped.get(rep, [])
        new_count = sum(1 for a in accounts if a.get(prospect_status_key) == "New")
        workload = sum(workload_weights.get(a.get(prospect_status_key) or "", 0) for a in accounts)
        ineligible = new_count >= max_new_threshold
        eligibility[rep] = {
            "eligible": not ineligible,
            "new_count": new_count,
            "workload": workload,
            "assigned_this_run": 0,
            "reason": (
                f"Already owns {new_count} 'New' accounts (threshold: {max_new_threshold})"
                if ineligible else None
            ),
        }
    return eligibility


def assign_accounts(
    eligible: list[Account],
    rep_eligibility: dict,
    workload_weights: dict,
    max_new_threshold: int,
) -> tuple[list[Account], list[Account]]:
    """
    Assigns eligible companies to reps via workload-weighted round-robin; rep becomes ineligible when New count hits threshold.
    Input: eligible (list[Account]), rep_eligibility (dict), workload_weights (dict), max_new_threshold (int)
    Output: tuple[list[Account], list[Account]]
    """
    assigned = []
    unassigned = []

    for company in eligible:
        available = [rep for rep, info in rep_eligibility.items() if info["eligible"]]
        available.sort(key=lambda r: rep_eligibility[r]["workload"])
        available = [
            rep for rep in available
            if (rep_eligibility[rep]["new_count"] + rep_eligibility[rep]["assigned_this_run"]) < max_new_threshold
        ]

        if not available:
            company.skip_reason = "No eligible reps (all ineligible or hit 'New' threshold mid-run)"
            unassigned.append(company)
            continue

        chosen = available[0]
        company.assigned_to = chosen
        rep_eligibility[chosen]["assigned_this_run"] += 1
        rep_eligibility[chosen]["workload"] += workload_weights.get("New", 5)

        total_new = rep_eligibility[chosen]["new_count"] + rep_eligibility[chosen]["assigned_this_run"]
        if total_new >= max_new_threshold:
            rep_eligibility[chosen]["eligible"] = False
            rep_eligibility[chosen]["reason"] = (
                f"Hit {max_new_threshold} 'New' accounts mid-run "
                f"(started with {rep_eligibility[chosen]['new_count']}, "
                f"assigned {rep_eligibility[chosen]['assigned_this_run']} this run)"
            )
        assigned.append(company)

    return assigned, unassigned
