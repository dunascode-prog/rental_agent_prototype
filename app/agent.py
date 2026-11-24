"""Agent loop for both roles: build context, call the model, run allowed tools, step limit, output check, trace."""
from __future__ import annotations

import json
import logging
import sqlite3
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from app import guardrails, tools
from app.config import BACKOFFICE_ROLE, VISITOR_ROLE, Project
from app.db import now
from app.model import ModelClient, ModelError

log = logging.getLogger(__name__)

MAX_MODEL_CALLS = 8

VISITOR_RULES = """Rules:
- Answer only from the approved knowledge-base entries and the price sheet below. Never guess.
- Cite every entry you rely on as [kb:ID], for example [kb:{example}]. Prices come only from the price sheet; cite it as [kb:{price_id}].
- If the answer is not in the approved content, say so and offer a hand-off to a person (use handoff_to_sales if the visitor agrees).
- You cannot message, email or contact guests, and you have no tool for it.
- Keep replies short and friendly."""

BACKOFFICE_RULES = """You are the back-office assistant for {name}, helping property staff.
Rules:
- Use the tools to read listings, reservations, rate gaps and change status. Never invent data.
- You can only propose rate changes with propose_change. Nothing changes until a named person approves the change on its approval card; say so clearly.
- You cannot message, email or contact guests, and you have no tool for it.
- Payment details are always masked; never ask for them.
- When you cannot help, use handoff_to_human.
- Summarise what happened in a few lines."""


@dataclass
class TurnResult:
    reply: str
    model_called: bool
    tools_called: list[str] = field(default_factory=list)
    pending_changes: list[dict[str, Any]] = field(default_factory=list)
    handoff: bool = False
    fallback: bool = False


class TranscriptStore:
    """Last N turns per session, kept in memory only (transcripts are not persisted; see docs/ASSUMPTIONS.md)."""

    def __init__(self, max_turns: int):
        self._max_turns = max_turns
        self._turns: dict[str, deque[tuple[str, str]]] = {}

    def messages(self, session_id: str) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for user_text, reply in self._turns.get(session_id, ()):
            result.append({"role": "user", "content": user_text})
            result.append({"role": "assistant", "content": reply})
        return result

    def add(self, session_id: str, user_text: str, reply: str) -> None:
        if self._max_turns == 0:
            return
        self._turns.setdefault(session_id, deque(maxlen=self._max_turns)).append((user_text, reply))


def build_system_prompt(project: Project, role: str) -> str:
    if role == BACKOFFICE_ROLE:
        return BACKOFFICE_RULES.format(name=project.name)
    sheet = project.price_sheet
    price_id = sheet.get("id", "price-sheet")
    example = project.kb[0].id if project.kb else "entry-id"
    parts = [project.persona, VISITOR_RULES.format(example=example, price_id=price_id), "Approved knowledge base:"]
    for entry in project.kb:
        parts.append(f"[kb:{entry.id}] {entry.title}\n{entry.body}")
    if sheet.get("status") == project.kb_status_required:
        rules = "\n".join(f"- {rule}" for rule in sheet.get("rules", []))
        parts.append(f"Price sheet [kb:{price_id}] rules (call get_price_sheet for figures):\n{rules}")
    return "\n\n".join(parts)


def _text_of(response: Any) -> str:
    return "".join(getattr(block, "text", "") for block in response.content if block.type == "text").strip()


def run_turn(
    conn: sqlite3.Connection,
    project: Project,
    model: ModelClient,
    *,
    session_id: str,
    actor: str,
    role: str,
    text: str,
    history: list[dict[str, Any]],
) -> TurnResult:
    """Stages 3 to 7 of Fig. 5 (visitor) or the model part of Fig. 6 (back-office)."""
    model_id = project.models[role]
    ctx = tools.ToolContext(
        conn=conn, project=project, session_id=session_id, actor=actor, allowed=frozenset(project.tools[role])
    )
    definitions = tools.tool_definitions(ctx.allowed)
    system = build_system_prompt(project, role)
    messages: list[dict[str, Any]] = [*history, {"role": "user", "content": text}]

    calls = input_tokens = output_tokens = 0
    tools_called: list[str] = []
    reply: str | None = None
    started = time.monotonic()
    while calls < MAX_MODEL_CALLS:
        try:
            response = model.complete(
                model_id=model_id,
                system=system,
                messages=messages,
                tools=definitions,
                max_tokens=project.max_tokens,
                effort=project.effort.get(role),
                cache=project.prompt_caching,
            )
        except ModelError as exc:
            log.warning("model call failed: %s", exc)
            break
        calls += 1
        usage = getattr(response, "usage", None)
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
        # traces.input_tokens holds all input processed: uncached + written to cache + read from cache.
        input_tokens += (getattr(usage, "input_tokens", 0) or 0) + cache_read + cache_write
        output_tokens += getattr(usage, "output_tokens", 0) or 0
        log.debug("model call %d: cache read %d, cache write %d tokens", calls, cache_read, cache_write)

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                tools_called.append(block.name)
                outcome = tools.execute(block.name, block.input, ctx)
                result: dict[str, Any] = {"type": "tool_result", "tool_use_id": block.id, "content": outcome.content}
                if outcome.is_error:
                    result["is_error"] = True
                results.append(result)
            messages.append({"role": "user", "content": results})
            continue
        if response.stop_reason in ("end_turn", "stop_sequence"):
            reply = _text_of(response) or None
        else:
            log.warning("model stopped with %s; using fallback", response.stop_reason)
        break

    fallback = reply is None
    if fallback:
        reply = guardrails.FALLBACK_TEXT
    elif role == VISITOR_ROLE and not ctx.handoff_written and not guardrails.has_approved_citation(reply, project.citable_ids):
        reply = guardrails.HANDOFF_OFFER
        with conn:
            conn.execute(
                "INSERT INTO handoffs (session_id, reason, summary, created_at) VALUES (?, ?, ?, ?)",
                (session_id, "no_approved_citation", text[:1000], now()),
            )
        ctx.handoff_written = True

    with conn:
        conn.execute("UPDATE sessions SET message_count = message_count + 1 WHERE id = ?", (session_id,))
        if calls:
            conn.execute(
                "INSERT INTO traces (session_id, role, model_id, tools_called, input_tokens, output_tokens, elapsed_ms, at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (session_id, role, model_id, json.dumps(tools_called), input_tokens, output_tokens,
                 int((time.monotonic() - started) * 1000), now()),
            )
    return TurnResult(
        reply=reply,
        model_called=calls > 0,
        tools_called=tools_called,
        pending_changes=[c for c in ctx.pending_changes if c["state"] == "awaiting_approval"],
        handoff=ctx.handoff_written,
        fallback=fallback,
    )
