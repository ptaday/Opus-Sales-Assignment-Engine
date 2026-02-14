"""
CLI: seed | fetch | assign [--dry-run]
"""
import argparse
import csv
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path

from src.utils.config import load_seed_config, load_assign_config
from src.models import Account
from src.core.scoring import score_company
from src.core.assignment import get_rep_eligibility, assign_accounts
from src.services.attio import AttioService
from src.services.seed_service import run_seed


def cmd_seed() -> None:
    """
    Runs the seed command: generates company data via Claude API and appends to CSV.
    Input: None
    Output: None
    """
    run_seed()


def cmd_fetch() -> None:
    """
    Fetches eligible accounts from Attio API and appends new ones to the configured CSV (no assignment).
    Input: None
    Output: None
    """
    config = load_assign_config()
    api_token = os.environ.get("ATTIO_API_TOKEN", "")
    if not api_token:
        print("Set ATTIO_API_TOKEN in environment or .env")
        return
    svc = AttioService(config, api_token)
    eligible, _ = svc.fetch_eligible_candidates()
    csv_path = config["fetch_csv"]
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["record_id"] + list(config["attribute_mapping"].keys())
    file_exists = csv_path.exists()
    existing_ids = set()
    if file_exists:
        with open(csv_path, "r", newline="") as f:
            for row in csv.DictReader(f):
                existing_ids.add(row.get("record_id", ""))
    new_accounts = [a for a in eligible if a.record_id not in existing_ids]
    with open(csv_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        for a in new_accounts:
            row = {"record_id": a.record_id}
            for k in config["attribute_mapping"]:
                v = a.get(k)
                row[k] = "" if v is None else v
            writer.writerow(row)
    print(f"Saved {len(new_accounts)} new accounts to {csv_path}. (Skipped {len(eligible) - len(new_accounts)} duplicates.)")


def _print_summary(assigned, all_skipped, unassigned, rep_eligibility, dry_run: bool, display_name_key: str):
    """
    Prints an assignment summary to stdout: rep eligibility, assigned, skipped, and unassigned accounts.
    Input: assigned (list), all_skipped (list), unassigned (list), rep_eligibility (dict), dry_run (bool), display_name_key (str)
    Output: None
    """
    mode = "DRY RUN" if dry_run else "LIVE RUN"
    print(f"\n{'='*65}\n  ASSIGNMENT SUMMARY ({mode})\n{'='*65}")
    print("\n-- Rep Eligibility --")
    for rep, info in rep_eligibility.items():
        status = "Eligible" if info["eligible"] else "Ineligible"
        print(f"  {rep:8s} | {status:11s} | New: {info['new_count']} | Workload: {info['workload']} | Assigned this run: {info['assigned_this_run']}")
        if info["reason"]:
            print(f"           Reason: {info['reason']}")
    print(f"\n-- Assigned ({len(assigned)}) --")
    for a in assigned:
        name = (a.get(display_name_key) or "(unnamed)")[:30]
        print(f"  {name:30s} -> {a.assigned_to:8s} | Score: {a.score:6.2f} | Locations: {a.get('location_count')} | {a.get('industry')}")
    if not assigned:
        print("  (none)")
    print(f"\n-- Skipped ({len(all_skipped)}) --")
    for s in all_skipped[:20]:
        print(f"  {(s.get(display_name_key) or '(unnamed)'):30s} | {s.skip_reason}")
    if len(all_skipped) > 20:
        print(f"  ... and {len(all_skipped) - 20} more")
    if not all_skipped:
        print("  (none)")
    print(f"\n-- Unassigned ({len(unassigned)}) --")
    for u in unassigned:
        print(f"  {(u.get(display_name_key) or '(unnamed)'):30s} | Score: {u.score:6.2f} | {u.skip_reason}")
    if not unassigned:
        print("  (none)")
    print(f"\n{'='*65}\n")


def _save_run_log(assigned, all_skipped, unassigned, rep_eligibility, write_results, log_file: Path, dry_run: bool, display_name_key: str):
    """
    Appends a run entry (assignments, skipped, unassigned, rep eligibility, write results) to the JSON log file.
    Input: assigned (list), all_skipped (list), unassigned (list), rep_eligibility (dict), write_results (list), log_file (Path), dry_run (bool), display_name_key (str)
    Output: None
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "dry_run" if dry_run else "live",
        "summary": {"assigned_count": len(assigned), "skipped_count": len(all_skipped), "unassigned_count": len(unassigned)},
        "rep_eligibility": {rep: {k: info[k] for k in ["eligible", "new_count", "workload", "assigned_this_run", "reason"]} for rep, info in rep_eligibility.items()},
        "assignments": [{"record_id": a.record_id, "company_name": a.get(display_name_key), "assigned_to": a.assigned_to, "score": a.score} for a in assigned],
        "write_results": write_results,
        "skipped": [{"record_id": s.record_id, "company_name": s.get(display_name_key), "reason": s.skip_reason} for s in all_skipped],
        "unassigned": [{"record_id": u.record_id, "company_name": u.get(display_name_key), "score": u.score, "reason": u.skip_reason} for u in unassigned],
    }
    log = []
    if log_file.exists():
        try:
            log = json.loads(log_file.read_text())
        except (json.JSONDecodeError, IOError):
            pass
    log.append(entry)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text(json.dumps(log, indent=2))
    print(f"Run log saved to {log_file}")


def _save_summary_md(assigned, all_skipped, unassigned, rep_eligibility, write_results, summary_dir: Path, dry_run: bool, config: dict):
    """
    Writes a markdown summary file for the run (rep eligibility, assigned, skipped, unassigned, scoring reference).
    Input: assigned (list), all_skipped (list), unassigned (list), rep_eligibility (dict), write_results (list), summary_dir (Path), dry_run (bool), config (dict)
    Output: None
    """
    display_name_key = config["display_name_key"]
    location_count_key = config["location_count_key"]
    industry_key = config["industry_key"]
    summary_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    mode = "dry_run" if dry_run else "live"
    filepath = summary_dir / f"summary_{ts}_{mode}.md"
    lines = [
        f"# Assignment Summary ({'DRY RUN' if dry_run else 'LIVE RUN'})",
        f"**Run at:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n",
        "## Rep Eligibility\n",
        "| Rep | Status | Existing New | Workload | Assigned This Run | Notes |",
        "|-----|--------|-------------|----------|-------------------|-------|",
    ]
    for rep, info in rep_eligibility.items():
        status = "Eligible" if info["eligible"] else "Ineligible"
        reason = info["reason"] or "—"
        lines.append(f"| {rep} | {status} | {info['new_count']} | {info['workload']} | {info['assigned_this_run']} | {reason} |")
   
    lines.append(f"\n## Assigned Accounts ({len(assigned)})\n")
    if assigned:
        lines.append("| Company | Assigned To | Score | Locations | Industry |")
        lines.append("|---------|------------|-------|-----------|----------|")
        for a in assigned:
            lines.append(f"| {a.get(display_name_key) or '(unnamed)'} | {a.assigned_to} | {a.score:.2f} | {a.get(location_count_key)} | {a.get(industry_key)} |")
    else:
        lines.append("No accounts were assigned.\n")
    if write_results and not dry_run:
        lines.append("\n## Write Results\n| Company | Rep | Status | Notes |\n|---------|-----|--------|-------|")
        for wr in write_results:
            lines.append(f"| {wr['company']} | {wr['rep']} | {wr['status']} | {wr.get('reason', '—')} |")
    lines.append(f"\n## Skipped ({len(all_skipped)})\n")
    if all_skipped:
        lines.append("| Company | Reason |\n|---------|--------|")
        for s in all_skipped:
            lines.append(f"| {s.get(display_name_key) or '(unnamed)'} | {s.skip_reason} |")
    lines.append(f"\n## Unassigned ({len(unassigned)})\n")
    if unassigned:
        lines.append("| Company | Score | Reason |\n|---------|-------|--------|")
        for u in unassigned:
            lines.append(f"| {u.get(display_name_key) or '(unnamed)'} | {u.score:.2f} | {u.skip_reason} |")
    iw = config["industry_weights"]
    ww = config["workload_weights"]
    lines.append("\n---\n## Scoring Model Reference\n**Location Score:** `70 × ln(location_count) / ln(50)`\n| Locations | Score |\n|-----------|-------|")
    for loc in [5, 10, 15, 20, 25, 30, 35, 40, 45, 50]:
        lines.append(f"| {loc} | {round(70.0 * math.log(loc) / math.log(50), 2):.2f} |")
    lines.append(f"\n**Industry Weights:** {iw}\n**Workload Weights:** {ww}\n")
    filepath.write_text("\n".join(lines) + "\n")
    print(f"Summary saved to {filepath}")


def cmd_assign(dry_run: bool) -> None:
    """
    Runs the assign workflow: loads config, fetches candidates, scores, assigns to reps, optionally writes to Attio, and saves summary/log.
    Input: dry_run (bool)
    Output: None
    """
    config = load_assign_config()
    api_token = os.environ.get("ATTIO_API_TOKEN", "")
    if dry_run:
        print("DRY RUN MODE — no changes will be written to Attio\n")
    if not api_token:
        print("Warning: ATTIO_API_TOKEN not set. API calls will fail.\n")

    svc = AttioService(config, api_token)
    eligible, skipped_owned = svc.fetch_eligible_candidates()
    loc_key = config["location_count_key"]
    ind_key = config["industry_key"]
    for a in eligible:
        a.score = score_company(a.get(loc_key) or 0, a.get(ind_key) or "", config["industry_weights"])
    eligible.sort(key=lambda x: x.score, reverse=True)

    rep_accounts = svc.fetch_rep_accounts()
    if dry_run:
        skipped_unassigned = svc.fetch_skipped_unassigned()
    else:
        skipped_unassigned = []
    all_skipped = list(skipped_owned) + list(skipped_unassigned)
    seen_ids = {a.record_id for a in all_skipped}
    for a in rep_accounts:
        if a.record_id not in seen_ids:
            a.skip_reason = f"Already owned by {a.get(config['owner_key'])}"
            all_skipped.append(a)
            seen_ids.add(a.record_id)

    rep_eligibility = get_rep_eligibility(
        rep_accounts, config["reps"], config["workload_weights"], config["max_new_threshold"],
        config["owner_key"], config["prospect_status_key"],
    )
    eligible_reps = [r for r, info in rep_eligibility.items() if info["eligible"]]
    print(f"Eligible candidates: {len(eligible)} | Skipped: {len(all_skipped)} | Eligible reps: {eligible_reps}")

    dname = config["display_name_key"]
    if not eligible_reps:
        print("\nNo eligible reps — nothing to assign.")
        _print_summary([], all_skipped, eligible, rep_eligibility, dry_run, dname)
        _save_run_log([], all_skipped, eligible, rep_eligibility, [], config["log_file"], dry_run, dname)
        _save_summary_md([], all_skipped, eligible, rep_eligibility, [], config["summary_dir"], dry_run, config)
        return
    if not eligible:
        print("\nNo eligible companies to assign.")
        _print_summary([], all_skipped, [], rep_eligibility, dry_run, dname)
        _save_run_log([], all_skipped, [], rep_eligibility, [], config["log_file"], dry_run, dname)
        _save_summary_md([], all_skipped, [], rep_eligibility, [], config["summary_dir"], dry_run, config)
        return

    assigned, unassigned = assign_accounts(
        eligible, rep_eligibility, config["workload_weights"], config["max_new_threshold"]
    )
    write_results = []

    if assigned and not dry_run:
        print(f"\nWriting {len(assigned)} assignments to Attio...")
        for a in assigned:
            result = {"record_id": a.record_id, "company": a.get(dname), "rep": a.assigned_to}
            if not a.record_id:
                result["status"] = "skipped"
                result["reason"] = "No record_id"
                write_results.append(result)
                continue
            if not svc.verify_still_unassigned(a.record_id):
                result["status"] = "skipped"
                result["reason"] = "Record was assigned by another process"
                write_results.append(result)
                continue
            if svc.update_attio_record(a.record_id, a.assigned_to):
                result["status"] = "success"
                print(f"  {a.get(dname)} -> {a.assigned_to}")
            else:
                result["status"] = "failed"
                result["reason"] = "API write failed after retries"
            write_results.append(result)
    elif dry_run and assigned:
        write_results = [{"record_id": a.record_id, "company": a.get(dname), "rep": a.assigned_to, "status": "dry_run"} for a in assigned]

    _print_summary(assigned, all_skipped, unassigned, rep_eligibility, dry_run, dname)
    _save_run_log(assigned, all_skipped, unassigned, rep_eligibility, write_results, config["log_file"], dry_run, dname)
    _save_summary_md(assigned, all_skipped, unassigned, rep_eligibility, write_results, config["summary_dir"], dry_run, config)


def main() -> None:
    """
    Entry point: parses CLI (seed | fetch | assign [--dry-run]) and dispatches to the corresponding command.
    Input: None (reads sys.argv)
    Output: None
    """
    parser = argparse.ArgumentParser(description="Attio assignment & seed")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("seed", help="Generate seed data via Claude and append to CSV")
    sub.add_parser("fetch", help="Fetch eligible accounts from Attio to CSV (no assignment)")
    p_assign = sub.add_parser("assign", help="Score, assign, and optionally write to Attio")
    p_assign.add_argument("--dry-run", action="store_true", help="Preview only, no writes")
    args = parser.parse_args()

    if args.command == "seed":
        cmd_seed()
    elif args.command == "fetch":
        cmd_fetch()
    elif args.command == "assign":
        cmd_assign(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
