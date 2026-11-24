"""FastAPI app: HTTP routes, request validation and the session cookie (PDF section 7)."""
from __future__ import annotations

import logging
import os
import secrets
import sqlite3
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Any, Iterator

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from app import agent, auth, changes, guardrails, parity
from app.config import BACKOFFICE_ROLE, VISITOR_ROLE, Project, load_project_config
from app.db import connect, init_db, now
from app.model import BedrockModel, ModelClient

log = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).resolve().parent / "static"
COOKIE_NAME = "rap_session"


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChatIn(_Body):
    message: str = Field(min_length=1, max_length=4000)


class CredentialsIn(_Body):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class ParityRunIn(_Body):
    listing_id: str = Field(min_length=1, max_length=50)
    start: date
    end: date


class ChangeTargetIn(_Body):
    listing_id: str = Field(min_length=1, max_length=50)
    date: date
    channel: str | None = None


class ChangeIn(_Body):
    type: str = Field(min_length=1, max_length=50)
    target: ChangeTargetIn
    before: float
    after: float


class ApproveIn(_Body):
    approver_name: str = Field(default="", max_length=100)
    change_hash: str | None = Field(default=None, max_length=64)


class RateLimiter:
    """Per-session request limit for /api/chat (429). Separate from the free-message counter."""

    def __init__(self, per_minute: int):
        self._per_minute = per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        cutoff = time.monotonic() - 60
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] < cutoff:
                hits.popleft()
            if len(hits) >= self._per_minute:
                return False
            hits.append(time.monotonic())
            return True


def create_app(
    *,
    project_name: str | None = None,
    database_path: str | None = None,
    model: ModelClient | None = None,
    staff_password: str | None = None,
) -> FastAPI:
    name = project_name or os.getenv("PROJECT_NAME") or "rental-demo"

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        project = load_project_config(name)
        db_path = database_path or os.getenv("DATABASE_PATH") or str(project.root / "data" / "app.db")
        init_db(db_path, project)
        app.state.project = project
        app.state.db_path = db_path
        region = project.aws_region or os.getenv("AWS_REGION")
        app.state.model = model or BedrockModel(region=region, profile=os.getenv("AWS_PROFILE") or None)
        app.state.limiter = RateLimiter(project.chat_rate_limit_per_minute)
        app.state.transcripts = agent.TranscriptStore(project.history_turns)
        # Behind CloudFront the app sees plain HTTP, so HTTPS deployments turn this on explicitly.
        app.state.cookie_secure = os.getenv("SESSION_COOKIE_SECURE", "").strip().lower() in ("1", "true", "yes")
        password = staff_password if staff_password is not None else os.getenv("STAFF_PASSWORD")
        if password:
            conn = connect(db_path)
            try:
                auth.ensure_staff_user(conn, project.staff_email, password)
            finally:
                conn.close()
        else:
            log.warning("STAFF_PASSWORD is not set: the staff login is disabled.")
        yield

    app = FastAPI(title="Rental Agent Prototype", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.exception_handler(RequestValidationError)
    async def _bad_input(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [{"loc": list(e.get("loc", ())), "msg": str(e.get("msg", ""))} for e in exc.errors()]
        return JSONResponse(status_code=400, content={"detail": "bad input", "errors": errors})

    @app.exception_handler(changes.ChangeError)
    async def _change_error(_: Request, exc: changes.ChangeError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content={"detail": exc.message, "change": exc.change})

    @app.exception_handler(parity.ParityError)
    async def _parity_error(_: Request, exc: parity.ParityError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content={"detail": exc.message})

    @app.exception_handler(auth.AuthError)
    async def _auth_error(_: Request, exc: auth.AuthError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content={"detail": exc.message})

    _register_routes(app)
    return app


# ---- dependencies -------------------------------------------------------------------------------

def get_conn(request: Request) -> Iterator[sqlite3.Connection]:
    conn = connect(request.app.state.db_path)
    try:
        yield conn
    finally:
        conn.close()


def get_session(request: Request, response: Response, conn: sqlite3.Connection = Depends(get_conn)) -> sqlite3.Row:
    project: Project = request.app.state.project
    token = request.cookies.get(COOKIE_NAME)
    row = None
    if token:
        row = conn.execute("SELECT * FROM sessions WHERE id = ? AND project = ?", (token, project.slug)).fetchone()
    if row is None:
        token = secrets.token_urlsafe(32)
        with conn:
            conn.execute(
                "INSERT INTO sessions (id, project, message_count, user_id, created_at) VALUES (?, ?, 0, NULL, ?)",
                (token, project.slug, now()),
            )
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (token,)).fetchone()
        response.set_cookie(
            COOKIE_NAME,
            token,
            httponly=True,
            samesite="lax",
            secure=request.app.state.cookie_secure,
            max_age=60 * 60 * 24 * 30,
        )
    return row


def _user(conn: sqlite3.Connection, session: sqlite3.Row) -> sqlite3.Row | None:
    if session["user_id"] is None:
        return None
    return conn.execute("SELECT id, email FROM users WHERE id = ?", (session["user_id"],)).fetchone()


def _is_staff(project: Project, user: sqlite3.Row | None) -> bool:
    return user is not None and user["email"] == project.staff_email


def require_staff(
    request: Request,
    session: sqlite3.Row = Depends(get_session),
    conn: sqlite3.Connection = Depends(get_conn),
) -> sqlite3.Row:
    user = _user(conn, session)
    if user is None:
        raise HTTPException(status_code=401, detail="staff login required")
    if not _is_staff(request.app.state.project, user):
        raise HTTPException(status_code=403, detail="staff only")
    return user


def _state(project: Project, session: sqlite3.Row, user: sqlite3.Row | None) -> dict[str, Any]:
    staff = _is_staff(project, user)
    return {
        "role": BACKOFFICE_ROLE if staff else VISITOR_ROLE,
        "registered": user is not None,
        "email": user["email"] if user else None,
        "messages_used": session["message_count"],
        "free_messages": project.free_messages,
        "limited": user is None,
    }


# ---- routes -------------------------------------------------------------------------------------

def _register_routes(app: FastAPI) -> None:
    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/session")
    def session_info(
        request: Request,
        session: sqlite3.Row = Depends(get_session),
        conn: sqlite3.Connection = Depends(get_conn),
    ) -> dict[str, Any]:
        project: Project = request.app.state.project
        return {"project": project.name, "state": _state(project, session, _user(conn, session))}

    @app.post("/api/chat")
    def chat(
        body: ChatIn,
        request: Request,
        session: sqlite3.Row = Depends(get_session),
        conn: sqlite3.Connection = Depends(get_conn),
    ) -> dict[str, Any]:
        project: Project = request.app.state.project
        if not request.app.state.limiter.allow(session["id"]):
            raise HTTPException(status_code=429, detail="too many requests")
        user = _user(conn, session)
        role = BACKOFFICE_ROLE if _is_staff(project, user) else VISITOR_ROLE

        decision = guardrails.check_before_model(conn, project, session, body.message, limited=user is None)
        extra: dict[str, Any] = {"model_called": False, "pending_changes": [], "outcome": decision.action}
        if decision.action != "allow":
            reply = decision.reply
        else:
            transcripts: agent.TranscriptStore = request.app.state.transcripts
            actor = user["email"] if user else guardrails.session_actor(session["id"])
            result = agent.run_turn(
                conn,
                project,
                request.app.state.model,
                session_id=session["id"],
                actor=actor,
                role=role,
                text=body.message,
                history=transcripts.messages(session["id"]),
            )
            transcripts.add(session["id"], body.message, result.reply)
            reply = result.reply
            extra = {
                "model_called": result.model_called,
                "pending_changes": result.pending_changes,
                "outcome": "fallback" if result.fallback else "handoff" if result.handoff else "answered",
            }
        session = conn.execute("SELECT * FROM sessions WHERE id = ?", (session["id"],)).fetchone()
        return {"reply": reply, "state": {**_state(project, session, user), **extra}}

    @app.post("/api/register", status_code=201)
    def register(
        body: CredentialsIn,
        request: Request,
        session: sqlite3.Row = Depends(get_session),
        conn: sqlite3.Connection = Depends(get_conn),
    ) -> dict[str, Any]:
        project: Project = request.app.state.project
        if auth.normalise_email(body.email) == project.staff_email:
            raise auth.AuthError(409, "email exists")
        user = auth.register(conn, body.email, body.password, project.password_min_length)
        with conn:
            conn.execute("UPDATE sessions SET user_id = ? WHERE id = ?", (user["id"], session["id"]))
        return {"user": {"id": user["id"], "email": user["email"]}}

    @app.post("/api/login")
    def login(
        body: CredentialsIn,
        request: Request,
        session: sqlite3.Row = Depends(get_session),
        conn: sqlite3.Connection = Depends(get_conn),
    ) -> dict[str, Any]:
        project: Project = request.app.state.project
        user = auth.authenticate(conn, body.email, body.password)
        if user is None:
            raise HTTPException(status_code=401, detail="wrong email or password")
        with conn:
            conn.execute("UPDATE sessions SET user_id = ? WHERE id = ?", (user["id"], session["id"]))
        session = conn.execute("SELECT * FROM sessions WHERE id = ?", (session["id"],)).fetchone()
        return {"state": _state(project, session, user)}

    @app.post("/api/logout")
    def logout(response: Response, session: sqlite3.Row = Depends(get_session), conn: sqlite3.Connection = Depends(get_conn)) -> dict[str, str]:
        with conn:
            conn.execute("UPDATE sessions SET user_id = NULL WHERE id = ?", (session["id"],))
        return {"status": "logged out"}

    @app.get("/api/parity")
    def get_parity(
        listing_id: str,
        request: Request,
        _: sqlite3.Row = Depends(require_staff),
        conn: sqlite3.Connection = Depends(get_conn),
    ) -> dict[str, Any]:
        return {"listing_id": listing_id, "gaps": parity.list_open_gaps(conn, request.app.state.project, listing_id)}

    @app.post("/api/parity/run")
    def run_parity(
        body: ParityRunIn,
        request: Request,
        _: sqlite3.Row = Depends(require_staff),
        conn: sqlite3.Connection = Depends(get_conn),
    ) -> dict[str, Any]:
        return parity.run_parity_check(conn, request.app.state.project, body.listing_id, body.start, body.end)

    @app.get("/api/listings")
    def listings(request: Request, _: sqlite3.Row = Depends(require_staff)) -> dict[str, Any]:
        return {"listings": request.app.state.project.listings}

    @app.get("/api/changes")
    def list_changes(
        state: str | None = None,
        _: sqlite3.Row = Depends(require_staff),
        conn: sqlite3.Connection = Depends(get_conn),
    ) -> dict[str, Any]:
        return {"changes": changes.list_changes(conn, state)}

    @app.post("/api/changes", status_code=201)
    def propose_change(
        body: ChangeIn,
        request: Request,
        user: sqlite3.Row = Depends(require_staff),
        conn: sqlite3.Connection = Depends(get_conn),
    ) -> dict[str, Any]:
        change = changes.propose(
            conn,
            request.app.state.project,
            type=body.type,
            listing_id=body.target.listing_id,
            channel=body.target.channel,
            date=body.target.date.isoformat(),
            before=body.before,
            after=body.after,
            actor=user["email"],
        )
        return {"change": change}

    @app.post("/api/changes/{change_id}/approve")
    def approve_change(
        change_id: int,
        body: ApproveIn,
        user: sqlite3.Row = Depends(require_staff),
        conn: sqlite3.Connection = Depends(get_conn),
    ) -> dict[str, Any]:
        return {"change": changes.approve(conn, change_id, body.approver_name, user["email"], body.change_hash)}

    @app.post("/api/changes/{change_id}/reject")
    def reject_change(
        change_id: int,
        user: sqlite3.Row = Depends(require_staff),
        conn: sqlite3.Connection = Depends(get_conn),
    ) -> dict[str, Any]:
        return {"change": changes.reject(conn, change_id, user["email"])}

    @app.get("/api/changelog")
    def changelog(
        _: sqlite3.Row = Depends(require_staff),
        conn: sqlite3.Connection = Depends(get_conn),
    ) -> dict[str, Any]:
        return {"rows": changes.read_log(conn)}


app = create_app()
