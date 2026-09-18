"""CLPZ ledger reconciliation — task 08 deliverable.

Verifies that every credit balance equals the sum of its transaction
amounts (the ledger is the audit authority; every atomic mutation logs
the ACTUAL delta). Run periodically or after an incident:

    python scripts/reconcile_ledger.py [--data-dir PATH] [--json] [--quiet]

Exit codes: 0 = all balances reconcile; 1 = at least one mismatch;
2 = usage/environment error.

Local credits are desktop development/legacy accounting (decision
register D2/D3): this tool audits the local ledger only. Cloud
entitlements live in Supabase and are audited separately (task 14/15).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Allow running from a bare `python scripts/reconcile_ledger.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reconcile the CLPZ local credit ledger")
    parser.add_argument("--data-dir", default=None,
                        help="Application data directory containing clpz.db "
                             "(default: CLIPFORGE_DATA or the app's default)")
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    parser.add_argument("--quiet", action="store_true", help="Only print mismatches")
    args = parser.parse_args(argv)

    data_dir = args.data_dir or os.environ.get("CLIPFORGE_DATA")
    if data_dir:
        os.environ["CLIPFORGE_DATA"] = str(data_dir)

    try:
        import database as db  # noqa: E402  (import after env is set)
        report = db.reconcile_ledger()
    except Exception as e:  # pragma: no cover - environment error
        print(f"error: cannot open ledger database: {e}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        if not args.quiet or not report["ok"]:
            print(f"users checked : {len(report['users'])}")
            print(f"mismatches    : {report['mismatched']}")
            for u in report["users"]:
                if u["ok"] and not args.quiet:
                    continue
                status = "OK " if u["ok"] else "BAD"
                print(f"  [{status}] {u['user_id']}: balance={u['balance']} "
                      f"ledger_sum={u['ledger_sum']} delta={u['delta']}")
            if report["ok"]:
                print("All balances reconcile with the transaction ledger.")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
