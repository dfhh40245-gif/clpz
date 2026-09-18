"""Trusted local provisioning CLI (task 04).

Grants or revokes the admin role on the LOCAL SQLite database. This is a
maintenance command that must be run by the machine owner — there is no HTTP
route that can change roles, and a configured email string never grants
anything.

Usage (from the repository root, with the app's environment):
    python -m scripts.provision_admin <user_id_or_email> [--revoke] [--data-dir <path>]

Examples:
    python -m scripts.provision_admin owner@example.com
    python -m scripts.provision_admin 1a2b3c4d5e6f --revoke
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision or revoke the local admin role")
    parser.add_argument("identity", help="user id or email of the account")
    parser.add_argument("--revoke", action="store_true", help="revoke admin (set role=user)")
    parser.add_argument("--data-dir", default="", help="CLIPFORGE_DATA path to operate on")
    args = parser.parse_args()

    if args.data_dir:
        os.environ["CLIPFORGE_DATA"] = args.data_dir

    sys.path.insert(0, str(BACKEND_DIR))
    import database as db  # noqa: E402  (after env is set)

    identity = args.identity.strip().lower()
    user = db.get_user_by_id(identity) or db.get_user_by_email(identity)
    if not user:
        # Users created before the role migration still exist; get_user_by_*
        # never returns password fields, so a second lookup by raw id/email:
        print(f"No user found for {args.identity!r}. "
              "Create the account first, then provision it.")
        return 1

    role = "user" if args.revoke else "admin"
    try:
        db.set_user_role(user["id"], role)
    except ValueError as exc:
        print(f"error: {exc}")
        return 1

    action = "revoked admin from" if args.revoke else "granted admin to"
    print(f"OK: {action} {user['email']} (id {user['id']}). "
          "The change takes effect immediately; existing admin sessions keep "
          "working until they expire or are destroyed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
