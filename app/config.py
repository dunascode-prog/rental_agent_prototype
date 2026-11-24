"""Project loader: reads projects/<name>/config.yaml, the approved KB files and the JSON seed data."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

PROJECTS_ROOT = Path(__file__).resolve().parent.parent / "projects"

VISITOR_ROLE = "visitor_chat"
BACKOFFICE_ROLE = "back_office"
ROLE_TOOLS: dict[str, tuple[str, ...]] = {
    VISITOR_ROLE: ("search_kb", "get_price_sheet", "handoff_to_sales"),
    BACKOFFICE_ROLE: (
        "get_listing",
        "get_reservation",
        "run_parity_check",
        "list_gaps",
        "propose_change",
        "get_change_status",
        "handoff_to_human",
    ),
}
REQUIRED_KEYS = (
    "name",
    "persona",
    "free_messages",
    "enabled_tools",
    "model_chat",
    "model_backoffice",
    "aws_region",
    "parity_tolerance",
    "kb_status_required",
    "staff_email",
)
KB_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
EFFORT_LEVELS = {"low", "medium", "high", "xhigh", "max"}


class ConfigError(ValueError):
    """Raised when a project folder fails validation."""


@dataclass(frozen=True)
class KBEntry:
    id: str
    title: str
    status: str
    body: str


@dataclass
class Project:
    slug: str
    root: Path
    name: str
    persona: str
    free_messages: int
    tools: dict[str, tuple[str, ...]]
    models: dict[str, str]
    aws_region: str | None
    effort: dict[str, str | None]
    max_tokens: int
    history_turns: int
    prompt_caching: bool
    parity_tolerance: float
    kb_status_required: str
    staff_email: str
    password_min_length: int
    retrieval_min_score: int
    chat_rate_limit_per_minute: int
    kb: list[KBEntry]
    price_sheet: dict[str, Any]
    listings: list[dict[str, Any]]
    reservations: list[dict[str, Any]]
    pms_rates: list[dict[str, Any]]
    channel_rates: list[dict[str, Any]]

    @property
    def citable_ids(self) -> set[str]:
        """IDs a visitor reply may cite as [kb:ID]: approved KB entries plus the approved price sheet."""
        ids = {entry.id for entry in self.kb}
        if self.price_sheet.get("id") and self.price_sheet.get("status") == self.kb_status_required:
            ids.add(self.price_sheet["id"])
        return ids

    def listing(self, listing_id: str) -> dict[str, Any] | None:
        return next((item for item in self.listings if item.get("listing_id") == listing_id), None)


def is_placeholder(value: Any) -> bool:
    text = str(value or "").strip()
    return not text or (text.startswith("<") and text.endswith(">")) or text.upper().startswith("TODO")


def load_project_config(project_name: str, projects_root: Path | None = None) -> Project:
    root = (projects_root or PROJECTS_ROOT) / project_name
    config_path = root / "config.yaml"
    if not config_path.is_file():
        raise ConfigError(f"{config_path} not found")
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ConfigError("config.yaml must be a mapping")
    missing = [key for key in REQUIRED_KEYS if key not in raw]
    if missing:
        raise ConfigError(f"config.yaml is missing keys: {', '.join(missing)}")

    kb_status = str(raw["kb_status_required"])
    data_dir = root / "data"
    return Project(
        slug=project_name,
        root=root,
        name=str(raw["name"]),
        persona=str(raw["persona"]).strip(),
        free_messages=_int(raw, "free_messages", minimum=0),
        tools=_parse_tools(raw["enabled_tools"]),
        models={VISITOR_ROLE: str(raw["model_chat"]), BACKOFFICE_ROLE: str(raw["model_backoffice"])},
        aws_region=None if is_placeholder(raw["aws_region"]) else str(raw["aws_region"]),
        effort=_parse_effort(raw.get("effort")),
        max_tokens=_int(raw, "max_tokens", default=8000, minimum=256),
        history_turns=_int(raw, "history_turns", default=6, minimum=0),
        prompt_caching=_bool(raw, "prompt_caching", default=True),
        parity_tolerance=_number(raw, "parity_tolerance"),
        kb_status_required=kb_status,
        staff_email=str(raw["staff_email"]).strip().lower(),
        password_min_length=_int(raw, "password_min_length", default=8, minimum=8),
        retrieval_min_score=_int(raw, "retrieval_min_score", default=1, minimum=1),
        chat_rate_limit_per_minute=_int(raw, "chat_rate_limit_per_minute", default=20, minimum=1),
        kb=_load_kb(root / "kb", kb_status),
        price_sheet=_load_json(data_dir / "price_sheet.json", default={}),
        listings=_load_json(data_dir / "listings.json", default=[]),
        reservations=_load_json(data_dir / "reservations.json", default=[]),
        pms_rates=_load_json(data_dir / "pms_rates.json", default=[]),
        channel_rates=_load_json(data_dir / "channel_rates.json", default=[]),
    )


def _int(raw: dict, key: str, default: int | None = None, minimum: int = 0) -> int:
    value = raw.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ConfigError(f"{key} must be an integer >= {minimum}")
    return value


def _bool(raw: dict, key: str, default: bool) -> bool:
    value = raw.get(key, default)
    if not isinstance(value, bool):
        raise ConfigError(f"{key} must be true or false")
    return value


def _number(raw: dict, key: str) -> float:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ConfigError(f"{key} must be a number >= 0")
    return float(value)


def _parse_tools(value: Any) -> dict[str, tuple[str, ...]]:
    if not isinstance(value, dict):
        raise ConfigError("enabled_tools must map each role (visitor_chat, back_office) to a list of tools")
    tools: dict[str, tuple[str, ...]] = {}
    for role, allowed in ROLE_TOOLS.items():
        names = value.get(role, [])
        if not isinstance(names, list):
            raise ConfigError(f"enabled_tools.{role} must be a list")
        unknown = [name for name in names if name not in allowed]
        if unknown:
            raise ConfigError(f"enabled_tools.{role} has tools not available to that role: {unknown}")
        tools[role] = tuple(names)
    return tools


def _parse_effort(value: Any) -> dict[str, str | None]:
    value = value or {}
    if not isinstance(value, dict):
        raise ConfigError("effort must map roles to an effort level")
    effort: dict[str, str | None] = {}
    for role in ROLE_TOOLS:
        level = value.get(role)
        if level is not None and level not in EFFORT_LEVELS:
            raise ConfigError(f"effort.{role} must be one of {sorted(EFFORT_LEVELS)}")
        effort[role] = level
    return effort


def _load_kb(kb_dir: Path, required_status: str) -> list[KBEntry]:
    entries: list[KBEntry] = []
    seen: set[str] = set()
    for path in sorted(kb_dir.glob("*.md")):
        meta, body = _split_front_matter(path)
        entry_id = str(meta.get("id", "")).strip()
        if not KB_ID_RE.match(entry_id):
            raise ConfigError(f"{path.name}: front matter needs an id of lowercase letters, digits and dashes")
        if entry_id in seen:
            raise ConfigError(f"{path.name}: duplicate KB id {entry_id!r}")
        seen.add(entry_id)
        if not meta.get("title") or not meta.get("status"):
            raise ConfigError(f"{path.name}: front matter needs title and status")
        if str(meta["status"]) == required_status:
            entries.append(KBEntry(entry_id, str(meta["title"]), str(meta["status"]), body.strip()))
    return entries


def _split_front_matter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ConfigError(f"{path.name}: missing front matter")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ConfigError(f"{path.name}: front matter is not closed")
    meta = yaml.safe_load(parts[1]) or {}
    if not isinstance(meta, dict):
        raise ConfigError(f"{path.name}: front matter must be a mapping")
    return meta, parts[2]


def _load_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{path.name}: invalid JSON ({exc})") from exc
