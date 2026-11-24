"""SQLite schema (Fig. 4), append-only triggers on change_log, and seeding from data/*.json."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import Project

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    project TEXT NOT NULL,
    message_count INTEGER NOT NULL DEFAULT 0,
    user_id INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pms_rates (
    listing_id TEXT NOT NULL,
    date TEXT NOT NULL,
    rate REAL NOT NULL,
    PRIMARY KEY (listing_id, date)
);
CREATE TABLE IF NOT EXISTS channel_rates (
    channel TEXT NOT NULL,
    listing_id TEXT NOT NULL,
    date TEXT NOT NULL,
    rate REAL NOT NULL,
    PRIMARY KEY (channel, listing_id, date)
);
CREATE TABLE IF NOT EXISTS gaps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    listing_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    date TEXT NOT NULL,
    pms_rate REAL NOT NULL,
    channel_rate REAL NOT NULL,
    found_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    listing_id TEXT NOT NULL,
    channel TEXT,
    date TEXT NOT NULL,
    "before" REAL NOT NULL,
    "after" REAL NOT NULL,
    state TEXT NOT NULL,
    change_hash TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    change_id INTEGER NOT NULL UNIQUE REFERENCES changes(id),
    approver_name TEXT NOT NULL,
    change_hash TEXT NOT NULL,
    approved_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS change_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    change_id INTEGER REFERENCES changes(id),
    event TEXT NOT NULL,
    from_state TEXT,
    to_state TEXT,
    actor TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS handoffs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    reason TEXT NOT NULL,
    summary TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS traces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    model_id TEXT NOT NULL,
    tools_called TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    elapsed_ms INTEGER NOT NULL,
    at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS change_log_no_update BEFORE UPDATE ON change_log
BEGIN SELECT RAISE(ABORT, 'change_log is append-only'); END;
CREATE TRIGGER IF NOT EXISTS change_log_no_delete BEFORE DELETE ON change_log
BEGIN SELECT RAISE(ABORT, 'change_log is append-only'); END;
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def payload_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def connect(database_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(database_path), timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(database_path: str | Path, project: Project | None = None) -> None:
    """Create tables and triggers, then seed mock PMS and channel rates if the rate tables are empty."""
    Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    conn = connect(database_path)
    try:
        conn.executescript(SCHEMA)
        if project is not None:
            _seed(conn, project)
    finally:
        conn.close()


def _seed(conn: sqlite3.Connection, project: Project) -> None:
    if conn.execute("SELECT COUNT(*) FROM pms_rates").fetchone()[0]:
        return
    with conn:
        conn.executemany(
            "INSERT INTO pms_rates (listing_id, date, rate) VALUES (?, ?, ?)",
            [(r["listing_id"], r["date"], float(r["rate"])) for r in project.pms_rates],
        )
        conn.executemany(
            "INSERT INTO channel_rates (channel, listing_id, date, rate) VALUES (?, ?, ?, ?)",
            [(r["channel"], r["listing_id"], r["date"], float(r["rate"])) for r in project.channel_rates],
        )
