"""Guardrails enforced in code: intent check and message counter before the model, citation check after it."""
from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass

from app.changes import log_event
from app.config import Project

_CONTACT = (
    r"(?:message|messages|messaging|text|texting|sms|whats\s?app|e-?mail|emailing|contact|contacting|call|phone|"
    r"write\s+to|reach\s+out\s+to|notify|reply\s+to|dm)"
)
_GUEST = r"(?:guest|guests|guest's|tenant|tenants|booker|bookers|occupant|occupants)"
_GUEST_MESSAGING = (
    re.compile(rf"\b{_CONTACT}\b[\s\S]{{0,60}}?\b{_GUEST}\b", re.IGNORECASE),
    re.compile(rf"\bsend\b[\s\S]{{0,30}}?\b{_GUEST}\b[\s\S]{{0,30}}?\b(?:message|text|e-?mail|sms|note)\b", re.IGNORECASE),
)
CITATION_RE = re.compile(r"\[kb:([a-z0-9][a-z0-9-]*)\]")

REFUSAL_TEXT = (
    "I can't message, email or contact guests. Guest communication is handled by our team directly, "
    "and this request has been logged."
)
HANDOFF_OFFER = (
    "I don't have an approved answer to that. Would you like me to pass your question to a member of our team?"
)
FALLBACK_TEXT = (
    "Sorry, I can't complete that right now. Would you like me to pass this to a member of our team?"
)


def session_actor(session_id: str) -> str:
    """A log-safe label for a session: never write the cookie token itself into a log."""
    return "session:" + hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:12]


def registration_prompt(free_messages: int) -> str:
    return (
        f"You've used your {free_messages} free messages. "
        "Please register with your email and a password to keep chatting."
    )


@dataclass(frozen=True)
class Decision:
    action: str  # "allow", "refuse" or "register"
    reply: str | None = None


def is_guest_messaging_request(text: str) -> bool:
    return any(pattern.search(text or "") for pattern in _GUEST_MESSAGING)


def check_before_model(
    conn: sqlite3.Connection,
    project: Project,
    session: sqlite3.Row,
    text: str,
    *,
    limited: bool,
) -> Decision:
    """Stage 1 (intent check) then stage 2 (message counter). Neither stage calls the model."""
    if is_guest_messaging_request(text):
        with conn:
            log_event(conn, None, "refusal", None, None, session_actor(session["id"]), {"reason": "guest_messaging", "text": text})
        return Decision("refuse", REFUSAL_TEXT)
    if limited and session["message_count"] >= project.free_messages:
        with conn:
            conn.execute("UPDATE sessions SET message_count = message_count + 1 WHERE id = ?", (session["id"],))
        return Decision("register", registration_prompt(project.free_messages))
    return Decision("allow")


def cited_ids(reply: str) -> set[str]:
    return set(CITATION_RE.findall(reply or ""))


def has_approved_citation(reply: str, citable_ids: set[str]) -> bool:
    """Stage 6: the reply cites at least one approved entry and nothing that is not approved."""
    cited = cited_ids(reply)
    return bool(cited) and cited <= citable_ids
