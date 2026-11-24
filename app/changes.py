"""Change state machine (PDF section 9, Fig. 8): propose, approve with hash check, apply, verify, reject, log."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date as date_type
from typing import Any

from app.config import Project
from app.db import now, payload_hash

SUPPORTED_TYPES = {"rate_update"}
TRANSITIONS: dict[str, set[str]] = {
    "proposed": {"awaiting_approval", "rejected_at_proposal"},
    "awaiting_approval": {"approved", "rejected"},
    "approved": {"applied"},
    "applied": {"verified", "failed"},
}
EPSILON = 1e-9
_HASH_FIELDS = ("type", "listing_id", "channel", "date", "before", "after", "created_by")


class ChangeError(Exception):
    def __init__(self, status: int, message: str, change: dict[str, Any] | None = None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.change = change


def change_hash(change: dict[str, Any] | sqlite3.Row) -> str:
    payload = {field: change[field] for field in _HASH_FIELDS}
    payload["before"] = float(payload["before"])
    payload["after"] = float(payload["after"])
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def log_event(
    conn: sqlite3.Connection,
    change_id: int | None,
    event: str,
    from_state: str | None,
    to_state: str | None,
    actor: str,
    payload: Any,
) -> None:
    conn.execute(
        "INSERT INTO change_log (change_id, event, from_state, to_state, actor, payload_hash, at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (change_id, event, from_state, to_state, actor, payload_hash(payload), now()),
    )


def get_change(conn: sqlite3.Connection, change_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM changes WHERE id = ?", (change_id,)).fetchone()
    if row is None:
        return None
    change = dict(row)
    approval = conn.execute(
        "SELECT approver_name, approved_at FROM approvals WHERE change_id = ?", (change_id,)
    ).fetchone()
    change["approval"] = dict(approval) if approval else None
    return change


def list_changes(conn: sqlite3.Connection, state: str | None = None) -> list[dict[str, Any]]:
    if state:
        rows = conn.execute("SELECT id FROM changes WHERE state = ? ORDER BY id DESC", (state,)).fetchall()
    else:
        rows = conn.execute("SELECT id FROM changes ORDER BY id DESC LIMIT 100").fetchall()
    return [get_change(conn, row["id"]) for row in rows]


def history(conn: sqlite3.Connection, change_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT event, from_state, to_state, actor, at FROM change_log WHERE change_id = ? ORDER BY id",
        (change_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def read_log(conn: sqlite3.Connection, limit: int = 200) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM change_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(row) for row in rows]


def current_rate(conn: sqlite3.Connection, listing_id: str, channel: str | None, date: str) -> float | None:
    if channel:
        row = conn.execute(
            "SELECT rate FROM channel_rates WHERE channel = ? AND listing_id = ? AND date = ?",
            (channel, listing_id, date),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT rate FROM pms_rates WHERE listing_id = ? AND date = ?", (listing_id, date)
        ).fetchone()
    return None if row is None else float(row["rate"])


def _transition(
    conn: sqlite3.Connection, change_id: int, from_state: str, to_state: str, actor: str, payload: Any
) -> None:
    if to_state not in TRANSITIONS.get(from_state, set()):
        raise ChangeError(409, f"wrong state: cannot move from {from_state} to {to_state}")
    cur = conn.execute(
        "UPDATE changes SET state = ? WHERE id = ? AND state = ?", (to_state, change_id, from_state)
    )
    if cur.rowcount != 1:
        raise ChangeError(409, "wrong state")
    log_event(conn, change_id, "transition", from_state, to_state, actor, payload)


def propose(
    conn: sqlite3.Connection,
    project: Project,
    *,
    type: str,
    listing_id: str,
    channel: str | None,
    date: str,
    before: float,
    after: float,
    actor: str,
) -> dict[str, Any]:
    """Create a change row. Valid proposals wait for approval; stale before values end in rejected_at_proposal."""
    if type not in SUPPORTED_TYPES:
        raise ChangeError(400, f"invalid: only {sorted(SUPPORTED_TYPES)} changes are supported")
    listing = project.listing(listing_id)
    if listing is None:
        raise ChangeError(400, f"invalid: unknown listing {listing_id}")
    if channel and channel not in listing.get("channels", []):
        raise ChangeError(400, f"invalid: listing {listing_id} is not on channel {channel}")
    try:
        date = date_type.fromisoformat(str(date)).isoformat()
    except ValueError as exc:
        raise ChangeError(400, "invalid: date must be YYYY-MM-DD") from exc
    if after <= 0:
        raise ChangeError(400, "invalid: after must be greater than 0")
    current = current_rate(conn, listing_id, channel or None, date)
    if current is None:
        raise ChangeError(400, "invalid: no current rate for that listing, channel and date")

    fields = {
        "type": type,
        "listing_id": listing_id,
        "channel": channel or None,
        "date": date,
        "before": float(before),
        "after": float(after),
        "created_by": actor,
    }
    digest = change_hash(fields)
    stale = abs(current - float(before)) > EPSILON
    with conn:
        cur = conn.execute(
            'INSERT INTO changes (type, listing_id, channel, date, "before", "after", state, change_hash, '
            "created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, 'proposed', ?, ?, ?)",
            (type, listing_id, fields["channel"], date, fields["before"], fields["after"], digest, actor, now()),
        )
        change_id = cur.lastrowid
        log_event(conn, change_id, "proposed", None, "proposed", actor, fields)
        if stale:
            _transition(conn, change_id, "proposed", "rejected_at_proposal", "system", {"current": current})
        else:
            _transition(conn, change_id, "proposed", "awaiting_approval", "system", {"current": current})
    change = get_change(conn, change_id)
    if stale:
        raise ChangeError(409, f"before value is stale: current value is {current}", change=change)
    return change


def approve(
    conn: sqlite3.Connection,
    change_id: int,
    approver_name: str,
    actor: str,
    expected_hash: str | None = None,
) -> dict[str, Any]:
    """Approval gate: record the named approver, apply in one transaction, then re-read to verify."""
    name = (approver_name or "").strip()
    if not name:
        raise ChangeError(403, "approver name is required")
    change = get_change(conn, change_id)
    if change is None:
        raise ChangeError(404, "unknown change")
    if change["state"] != "awaiting_approval":
        raise ChangeError(409, f"wrong state: change is {change['state']}", change=change)
    recomputed = change_hash(change)
    if recomputed != change["change_hash"] or (expected_hash and expected_hash != recomputed):
        raise ChangeError(409, "hash mismatch: the change differs from the one shown for approval", change=change)

    with conn:
        conn.execute(
            "INSERT INTO approvals (change_id, approver_name, change_hash, approved_at) VALUES (?, ?, ?, ?)",
            (change_id, name, recomputed, now()),
        )
        _transition(conn, change_id, "awaiting_approval", "approved", name, {"actor": actor, "hash": recomputed})
        _apply(conn, change)
        _transition(conn, change_id, "approved", "applied", "system", {"after": change["after"]})

    with conn:
        reread = current_rate(conn, change["listing_id"], change["channel"], change["date"])
        ok = reread is not None and abs(reread - float(change["after"])) <= EPSILON
        _transition(conn, change_id, "applied", "verified" if ok else "failed", "system", {"reread": reread})
    return get_change(conn, change_id)


def reject(conn: sqlite3.Connection, change_id: int, actor: str) -> dict[str, Any]:
    change = get_change(conn, change_id)
    if change is None:
        raise ChangeError(404, "unknown change")
    if change["state"] != "awaiting_approval":
        raise ChangeError(409, f"wrong state: change is {change['state']}", change=change)
    with conn:
        _transition(conn, change_id, "awaiting_approval", "rejected", actor, {"rejected_by": actor})
    return get_change(conn, change_id)


def _apply(conn: sqlite3.Connection, change: dict[str, Any]) -> None:
    if change["channel"]:
        cur = conn.execute(
            "UPDATE channel_rates SET rate = ? WHERE channel = ? AND listing_id = ? AND date = ?",
            (change["after"], change["channel"], change["listing_id"], change["date"]),
        )
    else:
        cur = conn.execute(
            "UPDATE pms_rates SET rate = ? WHERE listing_id = ? AND date = ?",
            (change["after"], change["listing_id"], change["date"]),
        )
    if cur.rowcount != 1:
        raise ChangeError(409, "apply failed: rate row not found; nothing was written")
