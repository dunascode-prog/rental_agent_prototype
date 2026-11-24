# Claude change log

Every change Claude makes to this repository is recorded here, newest first. Each entry names the PR it ships in.
Architectural decisions are listed under "Decisions awaiting your review" until you approve or reject them.

Rules for this repository (set by the project owner, 2026-11-24):

- Nothing is pushed to `main`. Every change goes through a pull request that the owner reviews and merges.
- Architectural decisions are asked about before they are made.
- Every change is logged in this file.
- Every change, including the owner's own, is also appended to the append-only `CHANGELOG.md`; CI enforces it (added 2026-11-24).

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
| D-14 | Prompt caching uses the default 5-minute cache and is on by default (`prompt_caching: true`). Proposed in PR #6. | 1-hour cache (costs 2x on writes), or off by default. | Chat turns in one visit usually come within minutes; a 1-hour cache only pays off for long pauses. |
| D-15 | `traces.input_tokens` counts uncached + cache-written + cache-read tokens. Proposed in PR #6. | Count uncached tokens only, or add cache columns to `traces` (a Fig. 4 schema change). | Keeps the Fig. 4 schema and keeps the column meaning "all input processed". |
| D-16 | The hosted demo runs exactly one task: desired count 1, deployment minimum 0% and maximum 100%. Proposed in PR #7. | Two or more tasks, or rolling deploys with overlap. | SQLite on EFS is only safe with one writer; the cost is a short downtime on each deploy. |
| D-17 | CloudFront adds a secret `X-Origin-Verify` header and the load balancer forwards only requests carrying it (403 otherwise). Proposed in PR #7. | Rely on the CloudFront IP prefix list alone. | The prefix list admits any CloudFront distribution; the header ties access to this one. |
| D-18 | The session cookie's `Secure` flag comes from `SESSION_COOKIE_SECURE` (off by default). Proposed in PR #7. | Detect HTTPS from forwarded headers. | Behind CloudFront → HTTP load balancer the app can't see the original scheme reliably; an explicit switch is simpler. |
| D-19 | **Decided by the owner (2026-11-24): switch fully from Mantle to InvokeModel (`AnthropicBedrock`), replacing D-01.** IAM is `bedrock:InvokeModel` + `bedrock:InvokeModelWithResponseStream` on the two models. Model IDs can come from `BEDROCK_MODEL_CHAT` / `BEDROCK_MODEL_BACKOFFICE` in `.env`. Caching uses explicit breakpoints only (system prompt + newest message). Proposed in PR #9. | Stay on Mantle and ask AWS to enable Claude for the account; or keep both behind a config switch. | The new account gets `403 not available for this account` for every Claude model on Mantle; the console-enabled models (Haiku 4.5, Sonnet 4.6) only work through InvokeModel. |

---

## 2026-11-24 — Bedrock client back to InvokeModel (PR #9, `claude/bedrock-invokemodel`)

- Live check (2026-11-24, account set up by the owner, SSO profile with the `RentalAgentDev` permission set, `us-east-1`): sign-in and SigV4 worked, but Mantle returned `404 does not exist` for the console model IDs and `403 not available for this account` for `anthropic.claude-haiku-4-5`, `anthropic.claude-sonnet-5` and `anthropic.claude-opus-5-5`. The owner chose to switch fully to InvokeModel (D-19).
- `app/model.py`: `AnthropicBedrock` instead of `AnthropicBedrockMantle`. Caching drops the top-level `cache_control` (InvokeModel rejects it) and adds an explicit breakpoint on the newest message's last block, without changing the caller's list.
- `app/config.py`: `model_chat` / `model_backoffice` fall back to `BEDROCK_MODEL_CHAT` / `BEDROCK_MODEL_BACKOFFICE` when they are placeholders, so real IDs stay out of git.
- Tests: `tests/test_model.py` updated for the new caching shape, plus tests for the env fallback; `tests/test_live_bedrock.py` adds a back-office live test (staff login, parity check through tools). 35 passed, 2 skipped (live).
- Docs: README, `.env.example`, `config.yaml` comments, ARCHITECTURE, SECURITY, REQUIREMENTS, DECISIONS (ADR-06 amendment), DEPLOYMENT (task role policy, task definition env vars).
- Not verified yet: the live run itself (waits on the permission-set update); whether Sonnet 4.6 needs a `us.` inference-profile ID. Haiku 4.5 only caches prefixes of 4,096+ tokens, so the visitor prompt (about 600 tokens) will not be cached; Sonnet 4.6's minimum is 1,024.

## 2026-11-24 — Landing PRs #4 to #7 on main (PR #8, `claude/land-stacked-prs`)

- PRs #4 to #7 were stacked and each merged into the branch below it (`claude/docs-sync`, `claude/changelog`, `claude/ci-tests`, `claude/prompt-caching`), not into `main`. GitHub retargets a stacked PR to `main` only when its base branch is deleted on merge, and "Automatically delete head branches" is off in this repository.
- This PR merges `claude/prompt-caching` (which holds #4 to #7) into `main`. No other content changes.
- Lesson: before stacking PRs again, either turn on automatic branch deletion or merge each PR into `main` before opening the next.

## 2026-11-24 — Docker image and hosted demo guide (PR #7, `claude/docker`)

- Owner decisions (asked 2026-11-24): ECS Fargate + EFS; Dockerfile plus a step-by-step guide, no infrastructure as code; no domain yet, so CloudFront's default HTTPS URL; a public load balancer that only CloudFront can reach (not VPC origins + NAT). The live Bedrock check is postponed until AWS is ready.
- `Dockerfile`: `python:3.12-slim`, installs `requirements.txt`, copies `app/` and `projects/`, runs as uid 1000, `DATABASE_PATH=/data/app.db`, health check on `/health`, `uvicorn` on port 8000.
- `.dockerignore`: excludes `.git`, `.github`, `.venv`, caches, `*.db`, `.env`, `docs`, `tests`, `scripts`.
- `.github/workflows/docker.yml`: builds the image, runs it, checks `/health` and that `/data/app.db` was created by uid 1000. Docker isn't installed on the dev machine, so CI is where the image is tested.
- `app/main.py`: the session cookie is `Secure` when `SESSION_COOKIE_SECURE` is set (D-18); test in `tests/test_rules.py`.
- `docs/DEPLOYMENT.md`: ECR, Secrets Manager, security groups (CloudFront origin-facing prefix list), EFS access point (uid/gid 1000, root `/rental-agent`, 755), IAM (execution role + `secretsmanager:GetSecretValue`; task role `bedrock-mantle:CreateInference` only), task definition JSON, load balancer with the secret-header rule (D-17), single-task service (D-16), CloudFront settings (CachingDisabled, AllViewer, all methods, redirect to HTTPS), checks and teardown. Facts were checked against AWS docs. Not verified: the model ARN format, and whether the steps work end to end.
- README: Docker commands and a link to the guide. `docs/INDEX.md`: lists the guide. `.env.example`: `SESSION_COOKIE_SECURE`.
- Stacked on PR #6.

## 2026-11-24 — Prompt caching (PR #6, `claude/prompt-caching`)

- Owner chose prompt caching (2026-11-24). Bedrock supports both explicit and automatic prompt caching (SDK docs, platform availability table).
- `app/model.py`: `complete(..., cache=True)` sends the system prompt as a text block with `cache_control: {type: ephemeral}`, and sets top-level `cache_control` for the conversation tail. With `cache=False`, the request is unchanged from before.
- `app/agent.py`: passes `project.prompt_caching`; sums cache read and write tokens into `traces.input_tokens` (D-15); logs cache read/write per call at debug level.
- `app/config.py` and `config.yaml`: new `prompt_caching` key (default `true`, D-14).
- `tests/test_model.py`: 4 tests: the request shape with caching on and off, a placeholder model ID is refused with no request sent, and the agent passes the flag and counts cached tokens.
- `docs/AI_PIPELINE.md`: stage 4 notes caching.
- The system prompt holds no timestamps or per-request values, and tools are sent in a fixed order, so the cached prefix stays stable across requests.
- Stacked on PR #5.

## 2026-11-24 — CI test workflow (PR #5, `claude/ci-tests`)

- Owner chose a CI test workflow (2026-11-24).
- Added `.github/workflows/tests.yml`: Python 3.12, pip cache keyed on `requirements.txt`, `python -m pytest -q`, on every pull request and push to `main`, read-only permissions. The live Bedrock test is skipped in CI.
- README "Test" section mentions the CI checks.
- Stacked on PR #4.

## 2026-11-24 — Append-only CHANGELOG.md with a CI check (PR #4, `claude/changelog`)

- Owner decisions (asked 2026-11-24): entries appended in each PR and enforced by CI; file `CHANGELOG.md` at the repo root; keep this file updated as well.
- Added `CHANGELOG.md`, oldest first, backfilled with every commit and PR so far, including the owner's direct pushes. Authors are GitHub usernames; no emails, since the repo is public.
- Added `scripts/check_changelog.py`: compares `CHANGELOG.md` at the merge base with the head. It fails if any existing line changed, or if other files changed without a new `## ` entry appended.
- Added `.github/workflows/changelog.yml`: runs the check on every pull request and every push to `main` (read-only permissions).
- Added `tests/test_check_changelog.py` (7 unit tests for the check).
- Stacked on PR #3 so the two log files don't conflict.

## 2026-11-24 — Docs synced with the implementation (PR #3, `claude/docs-sync`)

- PR #1 and PR #2 were merged by the owner with no review comments. D-02 to D-13 shipped as written; they stay listed above so any of them can still be revisited.
- `docs/ACCEPTANCE_TESTS.md`: "Current status" now describes the implemented tests instead of skipped placeholders.
- `docs/API.md`: added the implemented request bodies and the D-02 routes.
- `docs/ASSUMPTIONS.md`: added a "Resolution status" table for every SR, PA and A item touched by the implementation. Still open: SR-13 (Dockerfile) and A-13 (`APP_SECRET_KEY`).
- `docs/INDEX.md`: links to this log.

## 2026-11-24 — Repository and PR workflow

- The owner connected `origin` (github.com/dunascode-prog/rental_agent_prototype) and pushed the scaffold and docs commits to `main` directly, so they have no PRs.
- PR #1 (`claude/gitattributes`, merged): `.gitattributes` marks `*.pdf`, `*.png`, `*.jpg`, `*.db` as binary so `core.autocrlf` can't corrupt the architecture PDF on checkout.
- Added this file and recorded the repository rules above.

## 2026-11-24 — First implementation pass (PR #2, merged)

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
