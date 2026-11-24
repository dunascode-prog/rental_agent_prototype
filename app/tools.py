"""Tool schemas, implementations and the per-role allowlist (PDF section 8). There is no messaging tool."""
from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app import changes, parity
from app.config import BACKOFFICE_ROLE, VISITOR_ROLE, Project
from app.db import now


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SearchKbInput(_Input):
    query: str = Field(min_length=1, max_length=500, description="What the visitor asked, in a few words.")


class GetPriceSheetInput(_Input):
    plan: str = Field(min_length=1, max_length=50, description="Plan name, or 'all' to list every plan.")


class HandoffToSalesInput(_Input):
    summary: str = Field(min_length=1, max_length=1000, description="Short summary of what the visitor needs.")


class GetListingInput(_Input):
    listing_id: str = Field(min_length=1, max_length=50)


class GetReservationInput(_Input):
    reservation_id: str = Field(min_length=1, max_length=50)


class RunParityCheckInput(_Input):
    listing_id: str = Field(min_length=1, max_length=50)
    start: date
    end: date


class ListGapsInput(_Input):
    listing_id: str = Field(min_length=1, max_length=50)


class ChangeTarget(_Input):
    listing_id: str = Field(min_length=1, max_length=50)
    date: date
    channel: str | None = Field(default=None, description="Omit to change the PMS rate; set to change a channel rate.")


class ProposeChangeInput(_Input):
    type: Literal["rate_update"]
    target: ChangeTarget
    before: float = Field(description="The rate as it is now. The proposal is rejected if this is stale.")
    after: float = Field(gt=0, description="The proposed new rate.")


class GetChangeStatusInput(_Input):
    change_id: int = Field(ge=1)


class HandoffToHumanInput(_Input):
    reason: str = Field(min_length=1, max_length=1000)


@dataclass
class ToolContext:
    conn: sqlite3.Connection
    project: Project
    session_id: str
    actor: str
    allowed: frozenset[str]
    pending_changes: list[dict[str, Any]] = field(default_factory=list)
    handoff_written: bool = False


@dataclass(frozen=True)
class ToolOutcome:
    content: str
    is_error: bool = False


@dataclass(frozen=True)
class ToolSpec:
    name: str
    role: str
    description: str
    input_model: type[_Input]
    run: Callable[[ToolContext, Any], Any]


class ToolFailure(Exception):
    """A tool ran but could not do what was asked; the message goes back to the model."""


_STOPWORDS = {"the", "and", "for", "are", "you", "your", "can", "what", "when", "how", "is", "do", "does", "with", "about"}


def _search_kb(ctx: ToolContext, args: SearchKbInput) -> Any:
    words = {w for w in re.findall(r"[a-z0-9]+", args.query.lower()) if len(w) >= 3 and w not in _STOPWORDS}
    scored = []
    for entry in ctx.project.kb:
        haystack = f"{entry.title} {entry.body}".lower()
        score = sum(1 for word in words if word in haystack)
        if score >= ctx.project.retrieval_min_score:
            scored.append((score, entry))
    scored.sort(key=lambda item: -item[0])
    results = [{"id": e.id, "cite_as": f"[kb:{e.id}]", "title": e.title, "text": e.body} for _, e in scored[:3]]
    if not results:
        return {"results": [], "note": "No approved entry matches. Do not guess; offer a hand-off."}
    return {"results": results}


def _get_price_sheet(ctx: ToolContext, args: GetPriceSheetInput) -> Any:
    sheet = ctx.project.price_sheet
    if not sheet or sheet.get("status") != ctx.project.kb_status_required:
        raise ToolFailure("No approved price sheet is available.")
    plans = sheet.get("plans", {})
    base = {"cite_as": f"[kb:{sheet['id']}]", "currency": sheet.get("currency"), "rules": sheet.get("rules", [])}
    if args.plan.lower() == "all":
        return {**base, "plans": plans}
    plan = plans.get(args.plan.lower())
    if plan is None:
        raise ToolFailure(f"Unknown plan {args.plan!r}. Available plans: {sorted(plans)}")
    return {**base, "plan": args.plan.lower(), "details": plan}


def _write_handoff(ctx: ToolContext, reason: str, summary: str) -> Any:
    with ctx.conn:
        cur = ctx.conn.execute(
            "INSERT INTO handoffs (session_id, reason, summary, created_at) VALUES (?, ?, ?, ?)",
            (ctx.session_id, reason, summary, now()),
        )
    ctx.handoff_written = True
    return {"handoff_id": cur.lastrowid, "status": "A member of the team will follow up."}


def _handoff_to_sales(ctx: ToolContext, args: HandoffToSalesInput) -> Any:
    return _write_handoff(ctx, "sales", args.summary)


def _handoff_to_human(ctx: ToolContext, args: HandoffToHumanInput) -> Any:
    return _write_handoff(ctx, "staff", args.reason)


def _get_listing(ctx: ToolContext, args: GetListingInput) -> Any:
    listing = ctx.project.listing(args.listing_id)
    if listing is None:
        raise ToolFailure(f"Unknown listing {args.listing_id}")
    rates = ctx.conn.execute(
        "SELECT date, rate FROM pms_rates WHERE listing_id = ? ORDER BY date", (args.listing_id,)
    ).fetchall()
    return {**listing, "pms_rates": [dict(r) for r in rates]}


def mask_payment(reservation: dict[str, Any]) -> dict[str, Any]:
    masked = dict(reservation)
    for key in ("card_number", "payment_card", "card"):
        if masked.get(key):
            digits = re.sub(r"\D", "", str(masked[key]))
            masked[key] = f"**** **** **** {digits[-4:]}" if len(digits) >= 4 else "****"
    return masked


def _get_reservation(ctx: ToolContext, args: GetReservationInput) -> Any:
    reservation = next(
        (r for r in ctx.project.reservations if r.get("reservation_id") == args.reservation_id), None
    )
    if reservation is None:
        raise ToolFailure(f"Unknown reservation {args.reservation_id}")
    return mask_payment(reservation)


def _run_parity_check(ctx: ToolContext, args: RunParityCheckInput) -> Any:
    result = parity.run_parity_check(ctx.conn, ctx.project, args.listing_id, args.start, args.end)
    return {k: result[k] for k in ("run_id", "listing_id", "start", "end", "compared", "gap_count", "no_data_count", "gaps")}


def _list_gaps(ctx: ToolContext, args: ListGapsInput) -> Any:
    return {"open_gaps": parity.list_open_gaps(ctx.conn, ctx.project, args.listing_id)}


def _propose_change(ctx: ToolContext, args: ProposeChangeInput) -> Any:
    change = changes.propose(
        ctx.conn,
        ctx.project,
        type=args.type,
        listing_id=args.target.listing_id,
        channel=args.target.channel,
        date=args.target.date.isoformat(),
        before=args.before,
        after=args.after,
        actor=ctx.actor,
    )
    ctx.pending_changes.append(change)
    return {
        "change_id": change["id"],
        "state": change["state"],
        "note": "Nothing has changed yet. A named person must approve this on the approval card.",
    }


def _get_change_status(ctx: ToolContext, args: GetChangeStatusInput) -> Any:
    change = changes.get_change(ctx.conn, args.change_id)
    if change is None:
        raise ToolFailure(f"Unknown change {args.change_id}")
    return {"change": change, "history": changes.history(ctx.conn, args.change_id)}


TOOLS: dict[str, ToolSpec] = {
    spec.name: spec
    for spec in (
        ToolSpec("search_kb", VISITOR_ROLE, "Search the approved knowledge base. Returns entries with IDs to cite as [kb:ID].", SearchKbInput, _search_kb),
        ToolSpec("get_price_sheet", VISITOR_ROLE, "Get prices from the approved price sheet. The only source of prices.", GetPriceSheetInput, _get_price_sheet),
        ToolSpec("handoff_to_sales", VISITOR_ROLE, "Pass the visitor to the sales team when the knowledge base has no answer.", HandoffToSalesInput, _handoff_to_sales),
        ToolSpec("get_listing", BACKOFFICE_ROLE, "Read a listing and its PMS rates from the mock PMS.", GetListingInput, _get_listing),
        ToolSpec("get_reservation", BACKOFFICE_ROLE, "Read a reservation. Payment details are masked.", GetReservationInput, _get_reservation),
        ToolSpec("run_parity_check", BACKOFFICE_ROLE, "Compare PMS and channel rates for a listing and date range. Records gaps; never changes rates.", RunParityCheckInput, _run_parity_check),
        ToolSpec("list_gaps", BACKOFFICE_ROLE, "List open rate gaps for a listing.", ListGapsInput, _list_gaps),
        ToolSpec("propose_change", BACKOFFICE_ROLE, "Propose a rate change. It does nothing until a named person approves it.", ProposeChangeInput, _propose_change),
        ToolSpec("get_change_status", BACKOFFICE_ROLE, "Show a change's current state and its history.", GetChangeStatusInput, _get_change_status),
        ToolSpec("handoff_to_human", BACKOFFICE_ROLE, "Pass the request to a person on the team.", HandoffToHumanInput, _handoff_to_human),
    )
}


def _inline_refs(schema: dict[str, Any]) -> dict[str, Any]:
    defs = schema.pop("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                return resolve(dict(defs[node["$ref"].split("/")[-1]]))
            return {k: resolve(v) for k, v in node.items() if k != "title"}
        if isinstance(node, list):
            return [resolve(item) for item in node]
        return node

    return resolve(schema)


def tool_definitions(names: tuple[str, ...] | frozenset[str]) -> list[dict[str, Any]]:
    """Tool definitions for the Messages API, in a stable order (keeps the request prefix cacheable)."""
    return [
        {"name": spec.name, "description": spec.description, "input_schema": _inline_refs(spec.input_model.model_json_schema())}
        for spec in TOOLS.values()
        if spec.name in names
    ]


def execute(name: str, raw_input: Any, ctx: ToolContext) -> ToolOutcome:
    """Stage 5: allowlist and schema check, then run. A rejected request has no side effects."""
    spec = TOOLS.get(name)
    if spec is None or name not in ctx.allowed:
        return ToolOutcome(f"Tool {name!r} is not allowed.", is_error=True)
    try:
        args = spec.input_model.model_validate(raw_input if isinstance(raw_input, dict) else {})
    except ValidationError as exc:
        return ToolOutcome(f"Invalid input for {name}: {exc.errors(include_url=False)}", is_error=True)
    try:
        result = spec.run(ctx, args)
    except ToolFailure as exc:
        return ToolOutcome(str(exc), is_error=True)
    except changes.ChangeError as exc:
        return ToolOutcome(f"{exc.message}", is_error=True)
    except parity.ParityError as exc:
        return ToolOutcome(f"{exc.message}", is_error=True)
    return ToolOutcome(json.dumps(result, default=str))
