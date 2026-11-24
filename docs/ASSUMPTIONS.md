# Assumptions Register

Source: [Rental_Agent_Prototype_Architecture.pdf](source/Rental_Agent_Prototype_Architecture.pdf). The PDF refers to "the assumptions register in the docs folder"; this is that register.

- A-01 to A-06 are the items marked [ASSUMPTION] in the PDF.
- A-07 onwards are gaps found while writing these docs: facts the PDF does not state. They are marked [ASSUMPTION] where they are used.
- The "Scaffold reconciliation" section lists differences between the scaffold and the PDF (SR-xx) and ambiguities in the PDF itself (PA-xx).

## Register

| ID | Assumption | Reason | Impact if wrong |
|----|------------|--------|-----------------|
| A-01 | The model choice (Claude Haiku for visitor chat, Claude Sonnet for back-office) may change after testing. | PDF §3, marked [ASSUMPTION]. | Model IDs in `config.yaml` change; cost and latency change; no code change expected because IDs come from config. |
| A-02 | Staff accounts are created by the project owner in config, not by self-service registration. | PDF §7, marked [ASSUMPTION]. | If staff self-register, `POST /api/register` would need a role and an approval path; the single staff login model changes. |
| A-03 | Mock data stands in for the property management system and booking channels. Real connectors are a later phase. | PDF §11, marked [ASSUMPTION]. | Real connectors would replace `data/*.json` seeding and add network failure handling to parity and apply. |
| A-04 | The retrieval threshold, password length and transcript retention are defaults. The PDF gives no values. | PDF §11, marked [ASSUMPTION]; values not stated. | Values must be chosen before AC-1/AC-2 and registration validation can be finalised. |
| A-05 | Local development is the default. A hosted demo is optional and needs a persistent volume or another database. | PDF §11, marked [ASSUMPTION]; Fig. 3. | A shared demo without a volume loses all SQLite data on restart. |
| A-06 | Claude models on Bedrock are available in the chosen region and enabled for the account. | PDF §11, marked [ASSUMPTION]. | Model calls fail; a different region or model must be configured. |
| A-07 | Request and response body shapes for the API are not specified; docs reuse tool input names and Fig. 4 columns. | PDF §7 gives only purpose, auth, success and errors. | Client and tests must be adjusted when shapes are defined. |
| A-08 | The value of N in "last N turns of this session" is not specified. | Fig. 5 stage 3. | Context size, cost and answer quality change. |
| A-09 | "Max tokens from config" (Fig. 5 stage 4) has no named config key. | Fig. 5 stage 4; see SR-01. | Default SDK limit used unintentionally. |
| A-10 | How `propose_change` input `target` maps to `changes.listing_id`, `channel`, `date` is not specified. | PDF §8 vs Fig. 4. | Tool schema and endpoint body must be defined before AC-5. |
| A-11 | How a staff user is distinguished from a registered visitor is not specified; `users` has no role column. | Fig. 4, §7. | Staff-only routes could be reachable by visitors if not designed. |
| A-12 | Whether a `traces` row is written when stages 1 or 2 short-circuit (model not called) is not specified. | §3 "each turn writes one traces row" vs Fig. 5 (stage 7 only on the model path). | Trace counts in tests and monitoring differ. |
| A-13 | The use of `APP_SECRET_KEY` is not stated; Fig. 10 lists it only as a secret. | Fig. 10. | Session cookie or other signing design must be decided. |
| A-14 | Python 3.12 is a scaffold requirement, not a PDF requirement. | Scaffold instructions; PDF silent. | None expected. |
| A-15 | The optional live Bedrock test's name, location and skip condition, and the scripted fake model's design, are not specified. | PDF §10. | Test layout decided at implementation. |
| A-16 | The listing parameter of `GET /api/parity` is not named; docs use `listing_id`. | PDF §7. | Client parameter name changes. |
| A-17 | Where the price sheet lives, and how a price answer from `get_price_sheet` passes the stage 6 `[kb:ID]` citation check, is not specified. | Fig. 1, Fig. 5, §8. | Correct price answers could be replaced by hand-off offers. |
| A-18 | Whether the output citation check applies to the back-office role is not specified; Fig. 6 shows no output check. | §3 "each role has its own guardrails"; Fig. 6. | Back-office replies could be wrongly replaced, or uncited replies allowed. |
| A-19 | The KB file format, status field and `[kb:ID]` ID scheme are not specified beyond `kb/*.md` and "status: approved". | Fig. 2, Fig. 5. | `config.py` validation and AC-1 depend on it. |

## Scaffold reconciliation

Comparison of the PDF with `README.md`, `HANDOVER.md`, `tests/test_acceptance.py`, `projects/rental-demo/config.yaml`, `.env.example`, `requirements.txt` and the file list in `app/`. The scaffold was not edited.

### Matches (no action)

- `app/` contains every component in PDF §6: `main.py`, `config.py`, `db.py`, `guardrails.py`, `agent.py`, `model.py`, `tools.py`, `parity.py`, `changes.py`, `auth.py`, `static/index.html`.
- `GET /health` in `app/main.py` returns `{"status": "ok"}`, as in §7.
- `tests/test_acceptance.py` has seven functions `test_ac1` to `test_ac7`, one per AC-1 to AC-7, as in §10.
- `config.yaml`: `free_messages: 5` (§1), `parity_tolerance: 0` (Fig. 7), `kb_status_required: "approved"` (Fig. 5 stage 3).
- `.gitignore` excludes `.env` (§5) and `*.db`.
- `.env.example` includes `APP_SECRET_KEY` (Fig. 10) and AWS profile and region (Fig. 3).

### Scaffold mismatches

| ID | File | Scaffold value | PDF value | Recommended change |
|----|------|----------------|-----------|--------------------|
| SR-01 | `projects/rental-demo/config.yaml` | No max tokens key | Fig. 5 stage 4: "max tokens from config" | Add a placeholder key, e.g. `max_tokens`, with a comment. |
| SR-02 | `projects/rental-demo/config.yaml` | No staff account entry | §7: staff accounts are created by the project owner in config (A-02) | Add a placeholder staff section (email only; password hash supplied via environment, never plain text). |
| SR-03 | `projects/rental-demo/config.yaml` | `enabled_tools: ["TODO: tool_name"]`, one flat list | §3, §8: separate tool lists per role, with exact names | Replace with per-role lists using the ten exact tool names from [TOOLS.md](TOOLS.md). |
| SR-04 | `projects/rental-demo/config.yaml` | No price sheet location and no "last N turns" value | Fig. 1 (project owner edits price sheet), §8 `get_price_sheet`, Fig. 5 stage 3 | Add placeholder keys once A-08 and A-17 are decided. |
| SR-05 | `projects/rental-demo/config.yaml` | Key names `model_chat`, `model_backoffice`, `aws_region`, etc. | PDF names no config keys; it says model is "set in config.yaml" | No change required; treat scaffold key names as the reference and keep docs in sync. |
| SR-06 | `.env.example` / `projects/rental-demo/data/` | `DATABASE_PATH=` (empty); `data/` folder lives under the project | Fig. 3: `data/app.db`; §6 and Fig. 2: project `data/` holds `data/*.json` mock seeds | Decide the database location (see PA-11) and add it as a commented default in `.env.example`. |
| SR-07 | `tests/test_acceptance.py` | Seven skipped tests only | §10: plus one optional live test against Bedrock when AWS credentials are present; scripted fake model elsewhere | Add a live test that skips when credentials are absent, and a fake-model fixture, when tests are implemented. |
| SR-08 | `README.md` | "Run" is TODO | Fig. 3: `uvicorn app.main:app`, `localhost:8000` | Fill "Run" with that command when the app is implemented. |
| SR-09 | `README.md` | "Test" is TODO | §10: `tests/test_acceptance.py`; scripted fake model | Fill "Test" with `python -m pytest -q` and the live-test note. |
| SR-10 | `HANDOVER.md` | All sections TODO | §2, §10, Fig. 1 (project owner edits KB, config, price sheet) | Fill from [ARCHITECTURE.md](ARCHITECTURE.md) and [ACCEPTANCE_TESTS.md](ACCEPTANCE_TESTS.md) once implemented. |
| SR-11 | `requirements.txt` | `passlib[argon2]` only | §5: argon2, or bcrypt if argon2 is not available | Optionally add a bcrypt extra as the fallback. |
| SR-12 | `requirements.txt` | `boto3`, `httpx`, `pydantic` listed | Not named in the PDF; §6 names "anthropic SDK, AWS credentials" | No conflict. Keep; record as scaffold choices. |
| SR-13 | Repository root | No Dockerfile | Fig. 3 Option B: Docker image of the app | Add only if Option B is pursued (A-05). |
| SR-14 | `app/static/index.html` | Title and heading only | Fig. 2: Chat panel, Parity panel, Approval cards, Change log view, Register form | Expected; build in the UI step. |

### PDF ambiguities

| ID | Location | Ambiguity or contradiction | Reading used in these docs |
|----|----------|----------------------------|----------------------------|
| PA-01 | Fig. 5 stage 2 vs stage 7 vs Fig. 9 | Stage 2 blocks when `message_count >= 6`, but stage 7 increments only after an answered message; after five answers the count is 5, so a literal reading would answer message 6. Fig. 9 says message 6 gets the prompt and the counter "stays at 6". | Message 6 returns the registration prompt (§1, Fig. 9, AC-3). The count must reach 6 on the sixth message, e.g. by counting the incoming message before the check. |
| PA-02 | Fig. 5 stage 1, Fig. 6 vs Fig. 4 | Refusals are "written to `change_log`", but `change_log` rows carry `change_id` and state columns that a refusal does not have. | A refusal is a `change_log` row with an `event` describing the refusal and no change; `change_id` nullable. [ASSUMPTION] |
| PA-03 | §7, §8 vs §9 | "pending change" / "changes row (pending)" is used, but there is no state named `pending`. | "pending" means `proposed` or `awaiting_approval`. Docs use exact state names. |
| PA-04 | Fig. 6 caption vs §8 | Caption: "Write tools only create pending rows or gap rows", but `handoff_to_human` (a write tool in Fig. 6) writes a `handoffs` row. | Tool table (§8) is authoritative. |
| PA-05 | Fig. 2 vs §2, Fig. 1 | Fig. 2 draws `kb/*.md` and `data/*.json` inside the "External (AWS)" box, while §2 says the process reads the project folder. | KB and data are local files in the project folder; only Bedrock is external. |
| PA-06 | Fig. 8 vs §9 | Fig. 8 labels the state "rejected at proposal"; §9 names it `rejected_at_proposal`. | `rejected_at_proposal`. |
| PA-07 | §6 component table | `config.py` input is printed as `projects//` (name missing). | `projects/<project>/`, e.g. `projects/rental-demo/`. |
| PA-08 | §7 `POST /api/chat` | 429 too many requests is listed, but no rate limit is described; the free-message limit returns a prompt, not an error (AC-3). | 429 is a request-rate limit separate from the message counter; its threshold is undefined. [ASSUMPTION] |
| PA-09 | §7 approve endpoint vs §9 | Success is "200 approved, then applied", but end states after apply are `verified` or `failed`. | The endpoint approves, applies and verifies, and reports the resulting state. [ASSUMPTION] |
| PA-10 | Fig. 3 | Option A puts the region in `.env`; Option B says Bedrock is in the "same region as config"; the scaffold has both `AWS_REGION` and `aws_region`. | `config.yaml` `aws_region` selects the Bedrock region; `.env` must match it. Recommend one source of truth. |
| PA-11 | Fig. 3 vs §6 | Fig. 3 shows the database at `data/app.db`; §6 uses the project `data/` folder for JSON seeds. It is not stated whether `data/` is the repo root or the project folder. | Location undecided; set via `DATABASE_PATH` (SR-06). |
| PA-12 | Fig. 7 caption vs §8 | "Nothing is changed by this flow", yet the flow writes `gaps` rows. | "Nothing" means no rates; `gaps` rows are written. |

Reconciliation items recorded: 14 scaffold mismatches (SR-01 to SR-14) and 12 PDF ambiguities (PA-01 to PA-12).

## Resolution status

Updated after PR #2 (implementation) was merged on 2026-11-24, and again after the live Bedrock check (PR #9, 2026-11-24). Decision IDs (D-xx) refer to [CLAUDE_CHANGELOG.md](../CLAUDE_CHANGELOG.md).

| Item | Status | How |
|------|--------|-----|
| SR-01 | Resolved | `max_tokens` key in `config.yaml` (D-11) |
| SR-02 | Resolved | `staff_email` in `config.yaml`, password from `STAFF_PASSWORD` in `.env` (D-03) |
| SR-03 | Resolved | `enabled_tools` per role with the exact tool names (D-11) |
| SR-04 | Resolved | `history_turns` key; price sheet at `data/price_sheet.json` (D-08) |
| SR-05 | No change | Scaffold key names kept |
| SR-06 | Resolved | Default `projects/<project>/data/app.db`, override with `DATABASE_PATH` (D-10) |
| SR-07 | Resolved | `tests/test_live_bedrock.py`; `FakeModel` in `tests/conftest.py` |
| SR-08, SR-09, SR-10 | Resolved | README "Run" and "Test", HANDOVER filled in |
| SR-11 | Resolved in code | `auth.py` falls back to bcrypt when argon2 is unavailable; no bcrypt package added |
| SR-12 | No change | Scaffold choices kept |
| SR-13 | Resolved | `Dockerfile` and `docs/DEPLOYMENT.md` added for Option B (PR #7); not yet deployed |
| SR-14 | Resolved | UI built: chat, register/login, approval cards, parity panel, change log |
| PA-01 | Resolved | D-06 |
| PA-02 | Resolved | D-05 |
| PA-07, PA-11 | Resolved | `load_project_config(project_name)` reads `projects/<project>/`; D-10 |
| PA-08 | Resolved | D-12 |
| PA-09 | Resolved | Approve returns the final state (`verified` or `failed`) |
| PA-10 | Resolved | `aws_region` in `config.yaml` wins; `AWS_REGION` is used when it is a placeholder |
| A-01 | Resolved (tested) | Live check used Claude Haiku 4.5 (visitor) and Claude Sonnet 4.6 (back-office), the newest Haiku and Sonnet the account could enable; IDs come from `.env`, no code change (D-19) |
| A-04 | Resolved (defaults) | D-13: password at least 8, KB search threshold 1; transcripts not persisted (D-04) |
| A-06 | Resolved (us-east-1) | Both models answer through InvokeModel with the `us.` inference-profile IDs; both live tests pass. Caveat: the project's own AWS account still returns `Operation not allowed` (AWS-side), so the check ran from the organization's management account |
| A-07, A-10, A-16 | Resolved | Request bodies in [API.md](API.md#implemented-request-bodies-resolves-a-07) |
| A-08, A-09 | Resolved | `history_turns: 6`, `max_tokens: 8000` |
| A-11 | Resolved | D-03 |
| A-12 | Resolved | A `traces` row is written only when the model was called |
| A-13 | Open | `APP_SECRET_KEY` is still unused |
| A-15 | Resolved | See SR-07 |
| A-17 | Resolved | D-07, D-08 |
| A-18 | Resolved | The citation check applies to the visitor role only |
| A-19 | Resolved | KB front matter: `id`, `title`, `status`; ids are lowercase letters, digits and dashes |
