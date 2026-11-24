# Claude change log

Every change Claude makes to this repository is recorded here, newest first. Each entry names the PR it ships in.
Architectural decisions are listed under "Decisions awaiting your review" until you approve or reject them.

Rules for this repository (set by the project owner, 2026-11-24):

- Nothing is pushed to `main`. Every change goes through a pull request that the owner reviews and merges.
- Architectural decisions are asked about before they are made.
- Every change is logged in this file.

---

## Decisions awaiting your review

These were made during the first implementation pass (2026-11-24), before the "ask first" rule was set. Each is reversible. D-01 has been decided; please approve or reject D-02 to D-13 in the review of the implementation PR.

| ID | Decision | Alternative | Why it was chosen |
|----|----------|-------------|-------------------|
| D-01 | **Decided by the owner (2026-11-24): use `AnthropicBedrockMantle`.** Mantle's IAM action is `bedrock-mantle:CreateInference`, replacing the PDF's `bedrock:InvokeModel`. | `AnthropicBedrock` (InvokeModel). | Owner's choice; the SDK recommends Mantle for new code. Docs amended (ARCHITECTURE, SECURITY, REQUIREMENTS, DECISIONS ADR-06). |
| D-02 | Added routes not in the PDF: `POST /api/login`, `POST /api/logout`, `GET /api/session`, `GET /api/listings`, `GET /api/changes`. | Keep only the nine PDF routes. | Staff routes need a login; approval cards need to list pending changes after a page reload; the UI needs the session state. |
| D-03 | The staff user is the account whose email equals `staff_email` in `config.yaml`; its password comes from `STAFF_PASSWORD` in `.env`. | Add a role column to `users` (not in Fig. 4). | Keeps the Fig. 4 schema unchanged; matches "single staff login per project" (A-02, A-11). |
| D-04 | Chat history ("last N turns") is kept in memory only, per session; lost on restart. | A transcripts table (not in Fig. 4). | Fig. 4 has no transcript table; retention is unspecified (A-04, A-08). |
| D-05 | Refusals are `change_log` rows with `event = 'refusal'` and no `change_id`; the actor is a hash of the session, never the cookie token. | A separate refusals table. | Fig. 5 and Fig. 6 say refusals go to `change_log` (PA-02). |
| D-06 | Message counter: the sixth message is blocked by checking `message_count >= free_messages` before answering; blocked messages also count, so a visitor who leaves stays at 6. | Literal Fig. 5 reading (`>= 6`), which would answer message 6. | Matches §1, Fig. 9 and AC-3 (PA-01). |
| D-07 | Stage 6 accepts a reply without a citation when the model already called `handoff_to_sales` in that turn. | Always replace uncited replies. | Avoids a second hand-off row and a contradictory reply (A-17 area). |
| D-08 | The price sheet is citable as `[kb:price-sheet]` and lives in `data/price_sheet.json`. | Put prices in a KB Markdown file. | `get_price_sheet` is "the only source of prices" yet replies must cite an approved entry (A-17). |
| D-09 | "Open gaps" = the latest recorded gap per (channel, date) whose PMS and channel rates still differ now. | Gaps of the latest run only. | Fig. 4 has no runs table, so a run with zero gaps cannot be told apart from no run. |
| D-10 | Default database location is `projects/<project>/data/app.db`, overridable by `DATABASE_PATH`. | Repository-level `data/app.db`. | Keeps each project self-contained (PA-11). |
| D-11 | `config.yaml` restructured: `enabled_tools` is per role; added `staff_email`, `max_tokens`, `history_turns`, optional `effort`, `password_min_length`, `retrieval_min_score`, `chat_rate_limit_per_minute`. | Keep the scaffold's flat keys. | Resolves SR-01 to SR-04 in docs/ASSUMPTIONS.md. |
| D-12 | `POST /api/chat` returns 429 after 20 requests a minute per session (in memory). | No rate limit. | The PDF lists 429 for chat without a trigger (PA-08). |
| D-13 | Defaults: password at least 8 characters; KB search needs at least 1 matching word; `max_tokens` 8000. | Other values. | The PDF says these are defaults but gives no values (A-04). |

---

## 2026-11-24 — Repository and PR workflow

- The owner connected `origin` (github.com/dunascode-prog/rental_agent_prototype) and pushed the scaffold and docs commits to `main` directly, so they have no PRs.
- PR #1 (`claude/gitattributes`): `.gitattributes` marks `*.pdf`, `*.png`, `*.jpg`, `*.db` as binary so `core.autocrlf` can't corrupt the architecture PDF on checkout.
- Added this file and recorded the repository rules above.

## 2026-11-24 — First implementation pass (PR: `claude/implementation`)

Status: code complete for the prototype scope; 20 tests pass, 1 live test skipped.

Changes in this PR beyond the file list below:

- D-01 applied: `app/model.py` switched from `AnthropicBedrock` to `AnthropicBedrockMantle`; docs amended where the PDF says `bedrock:InvokeModel` (ARCHITECTURE, SECURITY, REQUIREMENTS, DECISIONS ADR-06); `config.yaml` comment on the `anthropic.` model ID prefix.
- `.env.example`: added `PROJECT_NAME`, `STAFF_PASSWORD`, `RUN_LIVE_BEDROCK`, and notes on each variable.
- README: setup steps for Bedrock, "Run" and "Test" sections, folder layout, link to this log. HANDOVER: filled all three sections.
- README: removed a trailing `# rental_agent_prototype` line that was written in UTF-16 (PowerShell `echo >>`), which made GitHub render the file's end as garbled text. The README already has its title.
- `/api/chat` reports `outcome: "fallback"` when the model could not be reached.

Files:

- `app/config.py`: project loader. Reads `config.yaml`, validates it, loads approved KB entries (front matter `id`, `title`, `status`), the price sheet and the JSON seeds.
- `app/db.py`: Fig. 4 schema, the two `change_log` triggers that reject UPDATE and DELETE, seeding of `pms_rates` and `channel_rates`.
- `app/auth.py`: registration, login, argon2 hashing (bcrypt fallback), staff user setup.
- `app/guardrails.py`: stage 1 guest-messaging check (refuse and log), stage 2 message counter, stage 6 citation check.
- `app/tools.py`: the ten PDF tools with pydantic input schemas, per-role allowlist, payment masking. No messaging tool.
- `app/parity.py`: Fig. 7 parity engine, 409 when a run is already active, open-gap listing.
- `app/changes.py`: Fig. 8 state machine, `change_hash`, approval gate, apply in one transaction, re-read verification, reject, change log.
- `app/model.py`: Bedrock client wrapper with one `complete()` function and typed error handling (see D-01).
- `app/agent.py`: agent loop (8-call limit, safe fallback, tool dispatch, traces row, stage 6 replacement), system prompts per role, in-memory transcripts (D-04).
- `app/main.py`: all API routes, session cookie, staff checks, 400 for bad input, rate limit (D-02, D-12).
- `app/static/index.html`: chat panel, register and login dialog, approval cards, parity panel, change log view; light and dark themes.
- `projects/rental-demo/config.yaml`: restructured (D-11). Model IDs and region stay placeholders.
- `projects/rental-demo/kb/*.md`: three approved entries and one draft (to prove drafts are excluded).
- `projects/rental-demo/data/*.json`: listings, PMS and channel rates with seeded mismatches, reservations with test card numbers, price sheet.
- `tests/conftest.py`: scripted fake model and fixtures.
- `tests/test_acceptance.py`: AC-1 to AC-7 implemented (were skipped placeholders).
- `tests/test_rules.py`: step limit, allowlist, schema errors, draft citations, stale proposals, reject, hash mismatch, masking, auth and error codes.
- `tests/test_live_bedrock.py`: optional live test, skipped unless `RUN_LIVE_BEDROCK=1`.
- Removed `projects/rental-demo/kb/.gitkeep` and `data/.gitkeep` (folders now have files).

## 2026-11-22 — Documentation set (on `main`, commit 7eeef92, pushed by the owner)

- Moved `Rental_Agent_Prototype_Architecture.pdf` to `docs/source/`; extracted `architecture.txt` and `diagrams/figure_01.png` to `figure_10.png`.
- Added `docs/` PRD, FRD, ARCHITECTURE, AI_PIPELINE, API, TOOLS, DATA_FLOWS, SECURITY, ACCEPTANCE_TESTS, REQUIREMENTS, DECISIONS, ASSUMPTIONS, INDEX.
- README: added a "Documentation" section. HANDOVER: added a link to `docs/INDEX.md`.

## 2026-11-22 — Project scaffold (on `main`, commit d4559db, pushed by the owner)

- Created the folder structure, placeholder modules, `GET /health`, minimal `index.html`, placeholder `config.yaml`, seven skipped acceptance tests, `requirements.txt`, `.env.example`, `.gitignore`, `README.md`, `HANDOVER.md`.
- Created `.venv` and installed requirements; ran `git init`.
