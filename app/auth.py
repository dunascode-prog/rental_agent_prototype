"""Registration, login and password hashing (argon2, or bcrypt if argon2 is not available)."""
from __future__ import annotations

import re
import sqlite3

from passlib.context import CryptContext
from passlib.hash import argon2

from app.db import now

_pwd = CryptContext(schemes=["argon2"] if argon2.has_backend() else ["bcrypt"], deprecated="auto")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def hash_password(password: str) -> str:
    return _pwd.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _pwd.verify(password, password_hash)
    except ValueError:
        return False


def normalise_email(email: str) -> str:
    return (email or "").strip().lower()


def register(conn: sqlite3.Connection, email: str, password: str, min_length: int) -> sqlite3.Row:
    email = normalise_email(email)
    if not EMAIL_RE.match(email):
        raise AuthError(400, "invalid email")
    if len(password or "") < min_length:
        raise AuthError(400, f"password must be at least {min_length} characters")
    if conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
        raise AuthError(409, "email exists")
    with conn:
        cur = conn.execute(
            "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
            (email, hash_password(password), now()),
        )
    return conn.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()


def authenticate(conn: sqlite3.Connection, email: str, password: str) -> sqlite3.Row | None:
    row = conn.execute("SELECT * FROM users WHERE email = ?", (normalise_email(email),)).fetchone()
    if row is None or not verify_password(password or "", row["password_hash"]):
        return None
    return row


def ensure_staff_user(conn: sqlite3.Connection, email: str, password: str) -> None:
    """Create the project's single staff login, or reset its password to the configured one."""
    email = normalise_email(email)
    row = conn.execute("SELECT id, password_hash FROM users WHERE email = ?", (email,)).fetchone()
    with conn:
        if row is None:
            conn.execute(
                "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
                (email, hash_password(password), now()),
            )
        elif not verify_password(password, row["password_hash"]):
            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(password), row["id"]))
