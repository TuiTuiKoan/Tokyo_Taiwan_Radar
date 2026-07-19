"""Operator CLI for the Admin Reports (#204) cleanup maintenance lock.

Decision-16a / 16b. This is the SOLE operator of the reserved
`app_settings['admin_reports_cleanup_maintenance']` key. It runs with a
service-role client (which bypasses RLS), so it can seed / acquire / release
the lock even after migration 094 makes the key immutable to `authenticated`.

Subcommands:
  status         Read + print the current lock row (or "absent").
  seed-inactive  Insert the lock row as {"active": false} iff absent.
  acquire        Atomically flip inactive -> active (compare-and-set).
  release        Atomically flip active -> inactive iff caller holds window_id.

Atomicity model (no takeover, exactly-one-row):
  * The lock's `updated_at` timestamp is the optimistic-lock TOKEN.
  * `acquire` reads the token, then issues ONE conditional UPDATE guarded by
    (key = LOCK_KEY) AND (value->>'active' = 'false') AND (updated_at = token).
    Postgres applies the UPDATE atomically; the update must touch EXACTLY ONE
    row. Two racers reading the same token both filter on it, but the first
    commit rewrites `updated_at`, so the loser matches ZERO rows and aborts.
    A stale token, an already-active row, or a malformed value all fail closed.
  * `release` is guarded by (value->>'active' = 'true') AND
    (value->>'window_id' = <caller window_id>); a foreign window_id matches
    zero rows and errors WITHOUT clearing the lock.

Safety: this script is NEVER run against production outside an approved
decision-16b bring-up. It performs real writes only when invoked with a live
service-role client; the acquire/release primitives are import-safe and
unit-tested with an in-memory Supabase double.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import socket
import uuid
from datetime import datetime, timedelta, timezone

LOCK_KEY = "admin_reports_cleanup_maintenance"

# Module-local monotonic guard so two transitions in the same process can never
# mint an identical `updated_at` token (which would defeat the CAS).
_last_token: str | None = None


def _fresh_token() -> str:
    """Return a strictly-increasing ISO-8601 UTC timestamp string."""
    global _last_token
    now = datetime.now(timezone.utc)
    if _last_token is not None:
        prev = datetime.fromisoformat(_last_token)
        if now <= prev:
            now = prev + timedelta(microseconds=1)
    _last_token = now.isoformat()
    return _last_token


def _default_actor() -> str:
    try:
        user = getpass.getuser()
    except Exception:
        user = "unknown"
    try:
        host = socket.gethostname()
    except Exception:
        host = "unknown"
    return f"{user}@{host}"


def _supabase_client():
    from dotenv import load_dotenv

    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))
    from supabase import create_client

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set. This CLI "
            "requires the service-role key (RLS bypass) to operate the lock."
        )
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Low-level primitives (testable seams — take an injected `sb` client)
# ---------------------------------------------------------------------------

def _read_lock(sb) -> dict | None:
    rows = (
        sb.table("app_settings")
        .select("key,value,updated_at,updated_by")
        .eq("key", LOCK_KEY)
        .execute()
    ).data or []
    return rows[0] if rows else None


def _cas_acquire(
    sb,
    *,
    prior_token: str,
    window_id: str,
    reason: str,
    actor: str,
    opened_at: str,
    new_token: str,
) -> list[dict]:
    """Conditional flip inactive -> active. Returns the updated rows (0 or 1)."""
    new_value = {
        "active": True,
        "window_id": window_id,
        "reason": reason,
        "opened_at": opened_at,
        "actor": actor,
    }
    return (
        sb.table("app_settings")
        .update({"value": new_value, "updated_at": new_token})
        .eq("key", LOCK_KEY)
        .eq("value->>active", "false")
        .eq("updated_at", prior_token)
        .execute()
    ).data or []


def _cas_release(sb, *, window_id: str, new_token: str) -> list[dict]:
    """Conditional flip active -> inactive iff caller owns window_id."""
    return (
        sb.table("app_settings")
        .update({"value": {"active": False}, "updated_at": new_token})
        .eq("key", LOCK_KEY)
        .eq("value->>active", "true")
        .eq("value->>window_id", window_id)
        .execute()
    ).data or []


# ---------------------------------------------------------------------------
# Subcommand implementations
# ---------------------------------------------------------------------------

def status(sb) -> dict | None:
    row = _read_lock(sb)
    if row is None:
        print(f"lock key '{LOCK_KEY}': ABSENT (run seed-inactive first)")
        return None
    value = row.get("value") or {}
    active = value.get("active")
    print(f"lock key '{LOCK_KEY}':")
    print(f"  active       = {active!r}")
    print(f"  window_id    = {value.get('window_id')!r}")
    print(f"  reason       = {value.get('reason')!r}")
    print(f"  actor        = {value.get('actor')!r}")
    print(f"  opened_at    = {value.get('opened_at')!r}")
    print(f"  updated_at   = {row.get('updated_at')!r}")
    return row


def seed_inactive(sb) -> dict:
    existing = _read_lock(sb)
    if existing is not None:
        print(f"lock key '{LOCK_KEY}' already present; leaving untouched")
        print(json.dumps(existing, ensure_ascii=False, default=str))
        return existing
    token = _fresh_token()
    inserted = (
        sb.table("app_settings")
        .insert({"key": LOCK_KEY, "value": {"active": False}, "updated_at": token})
        .execute()
    ).data or []
    row = inserted[0] if inserted else _read_lock(sb)
    print(f"seeded lock key '{LOCK_KEY}' as inactive")
    print(json.dumps(row, ensure_ascii=False, default=str))
    return row


def acquire(sb, *, reason: str, actor: str | None = None) -> dict:
    actor = actor or _default_actor()
    prior = _read_lock(sb)
    if prior is None:
        raise RuntimeError(
            f"cannot acquire: lock key '{LOCK_KEY}' is ABSENT. Run seed-inactive first."
        )
    prior_value = prior.get("value") or {}
    if prior_value.get("active") is not False:
        raise RuntimeError(
            "cannot acquire: lock is not inactive "
            f"(active={prior_value.get('active')!r}, window_id={prior_value.get('window_id')!r}). "
            "Refusing to take over an active or malformed lock."
        )
    prior_token = prior.get("updated_at")
    window_id = uuid.uuid4().hex
    new_token = _fresh_token()
    opened_at = new_token
    updated = _cas_acquire(
        sb,
        prior_token=prior_token,
        window_id=window_id,
        reason=reason,
        actor=actor,
        opened_at=opened_at,
        new_token=new_token,
    )
    if len(updated) != 1:
        raise RuntimeError(
            f"acquire CAS matched {len(updated)} rows (expected exactly 1); "
            "another operator likely won the race or the lock changed. Aborting — no takeover."
        )
    audit = {
        "action": "acquire",
        "window_id": window_id,
        "actor": actor,
        "reason": reason,
        "prior_row": prior,
        "prior_token": prior_token,
        "new_token": new_token,
        "row_count": len(updated),
        "new_row": updated[0],
    }
    print(f"ACQUIRED lock '{LOCK_KEY}'")
    print(f"  window_id  = {window_id}")
    print(f"  prior_token= {prior_token!r}")
    print(f"  new_token  = {new_token!r}")
    print(f"  row_count  = {len(updated)}")
    print(json.dumps(audit, ensure_ascii=False, default=str))
    return audit


def release(sb, *, window_id: str, actor: str | None = None) -> dict:
    actor = actor or _default_actor()
    prior = _read_lock(sb)
    new_token = _fresh_token()
    updated = _cas_release(sb, window_id=window_id, new_token=new_token)
    if len(updated) != 1:
        raise RuntimeError(
            f"release CAS matched {len(updated)} rows (expected exactly 1); the "
            f"lock is not held by window_id={window_id!r} (mismatch or already released). "
            "Lock left untouched."
        )
    audit = {
        "action": "release",
        "window_id": window_id,
        "actor": actor,
        "prior_row": prior,
        "new_token": new_token,
        "row_count": len(updated),
        "new_row": updated[0],
    }
    print(f"RELEASED lock '{LOCK_KEY}'")
    print(f"  window_id  = {window_id}")
    print(f"  new_token  = {new_token!r}")
    print(f"  row_count  = {len(updated)}")
    print(json.dumps(audit, ensure_ascii=False, default=str))
    return audit


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Operate the Admin Reports #204 cleanup maintenance lock (service-role only)."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Print the current lock row (or absent).")
    sub.add_parser("seed-inactive", help="Insert the lock row as inactive iff absent.")

    p_acq = sub.add_parser("acquire", help="Atomically acquire the maintenance lock.")
    p_acq.add_argument("--reason", required=True, help="Why the maintenance window is opening.")
    p_acq.add_argument("--actor", default=None, help="Operator identity (default: user@host).")

    p_rel = sub.add_parser("release", help="Atomically release a lock you hold.")
    p_rel.add_argument("--window-id", required=True, help="The window_id returned by acquire.")
    p_rel.add_argument("--actor", default=None, help="Operator identity (default: user@host).")

    args = parser.parse_args(argv)
    sb = _supabase_client()

    if args.command == "status":
        status(sb)
    elif args.command == "seed-inactive":
        seed_inactive(sb)
    elif args.command == "acquire":
        acquire(sb, reason=args.reason, actor=args.actor)
    elif args.command == "release":
        release(sb, window_id=args.window_id, actor=args.actor)


if __name__ == "__main__":
    main()
