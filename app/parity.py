"""Parity engine (Fig. 7): compares PMS and channel rates in plain code, writes gaps, never changes rates."""
from __future__ import annotations

import sqlite3
import threading
import uuid
from datetime import date as date_type, timedelta
from typing import Any

from app.config import Project
from app.db import now

MAX_RANGE_DAYS = 366
_active_runs: set[str] = set()
_lock = threading.Lock()


class ParityError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def _parse_range(start: Any, end: Any) -> tuple[date_type, date_type]:
    try:
        start_date = start if isinstance(start, date_type) else date_type.fromisoformat(str(start))
        end_date = end if isinstance(end, date_type) else date_type.fromisoformat(str(end))
    except ValueError as exc:
        raise ParityError(400, "start and end must be YYYY-MM-DD") from exc
    if end_date < start_date:
        raise ParityError(400, "end must not be before start")
    if (end_date - start_date).days >= MAX_RANGE_DAYS:
        raise ParityError(400, f"date range must be under {MAX_RANGE_DAYS} days")
    return start_date, end_date


def run_parity_check(
    conn: sqlite3.Connection, project: Project, listing_id: str, start: Any, end: Any
) -> dict[str, Any]:
    listing = project.listing(listing_id)
    if listing is None:
        raise ParityError(404, "unknown listing")
    start_date, end_date = _parse_range(start, end)
    key = f"{project.slug}:{listing_id}"
    with _lock:
        if key in _active_runs:
            raise ParityError(409, "run already active")
        _active_runs.add(key)
    try:
        return _run(conn, project, listing, start_date, end_date)
    finally:
        with _lock:
            _active_runs.discard(key)


def _run(
    conn: sqlite3.Connection, project: Project, listing: dict[str, Any], start: date_type, end: date_type
) -> dict[str, Any]:
    listing_id = listing["listing_id"]
    span = (start.isoformat(), end.isoformat())
    pms = {
        row["date"]: float(row["rate"])
        for row in conn.execute(
            "SELECT date, rate FROM pms_rates WHERE listing_id = ? AND date BETWEEN ? AND ?", (listing_id, *span)
        )
    }
    channel_rows = conn.execute(
        "SELECT channel, date, rate FROM channel_rates WHERE listing_id = ? AND date BETWEEN ? AND ?",
        (listing_id, *span),
    ).fetchall()
    channel = {(row["channel"], row["date"]): float(row["rate"]) for row in channel_rows}
    channels = sorted(set(listing.get("channels", [])) | {row["channel"] for row in channel_rows})

    run_id = uuid.uuid4().hex[:12]
    found_at = now()
    gaps: list[dict[str, Any]] = []
    no_data: list[dict[str, Any]] = []
    compared = 0
    day = start
    while day <= end:
        iso = day.isoformat()
        for name in channels:
            pms_rate, channel_rate = pms.get(iso), channel.get((name, iso))
            if pms_rate is None or channel_rate is None:
                no_data.append({"channel": name, "date": iso, "pms_rate": pms_rate, "channel_rate": channel_rate})
                continue
            compared += 1
            if abs(pms_rate - channel_rate) > project.parity_tolerance:
                gaps.append(
                    {"run_id": run_id, "listing_id": listing_id, "channel": name, "date": iso,
                     "pms_rate": pms_rate, "channel_rate": channel_rate, "found_at": found_at}
                )
        day += timedelta(days=1)

    with conn:
        conn.executemany(
            "INSERT INTO gaps (run_id, listing_id, channel, date, pms_rate, channel_rate, found_at) "
            "VALUES (:run_id, :listing_id, :channel, :date, :pms_rate, :channel_rate, :found_at)",
            gaps,
        )
    return {
        "run_id": run_id,
        "listing_id": listing_id,
        "start": span[0],
        "end": span[1],
        "compared": compared,
        "gap_count": len(gaps),
        "no_data_count": len(no_data),
        "gaps": gaps,
        "no_data": no_data,
    }


def list_open_gaps(conn: sqlite3.Connection, project: Project, listing_id: str) -> list[dict[str, Any]]:
    """Latest recorded gap per (channel, date) whose PMS and channel rates still differ today."""
    if project.listing(listing_id) is None:
        raise ParityError(404, "unknown listing")
    rows = conn.execute(
        """
        SELECT g.* , p.rate AS current_pms_rate, c.rate AS current_channel_rate
        FROM gaps g
        JOIN (SELECT channel, date, MAX(id) AS max_id FROM gaps WHERE listing_id = ? GROUP BY channel, date) latest
          ON latest.max_id = g.id
        LEFT JOIN pms_rates p ON p.listing_id = g.listing_id AND p.date = g.date
        LEFT JOIN channel_rates c ON c.listing_id = g.listing_id AND c.channel = g.channel AND c.date = g.date
        ORDER BY g.date, g.channel
        """,
        (listing_id,),
    ).fetchall()
    open_gaps = []
    for row in rows:
        pms_rate, channel_rate = row["current_pms_rate"], row["current_channel_rate"]
        if pms_rate is not None and channel_rate is not None and abs(pms_rate - channel_rate) > project.parity_tolerance:
            open_gaps.append(dict(row))
    return open_gaps
