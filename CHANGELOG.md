# Change log (append-only)

Every change to this repository is recorded here, oldest first. New entries are only ever added at the bottom; existing lines are never edited or deleted. The `changelog` CI check enforces this on every pull request and every push to `main`.

To add an entry, append a block at the end of this file in the same pull request as the change:

```
## YYYY-MM-DD · PR #<n> (or commit <sha>) · <author>
- What changed and why.
- Decisions: any decision made, with its ID from CLAUDE_CHANGELOG.md.
```

Claude also keeps `CLAUDE_CHANGELOG.md`, which holds the decision records in detail.

---

## 2026-11-24 · commit d4559db · dunascode-prog with Claude
- Scaffolded the project: folder structure, placeholder modules, `GET /health`, minimal `index.html`, placeholder `config.yaml`, seven skipped acceptance tests, `requirements.txt`, `.env.example`, `.gitignore`, README, HANDOVER.
- Pushed directly to `main` (no PR) when the remote was connected.

## 2026-11-24 · commit 7eeef92 · dunascode-prog with Claude
- Added the documentation set under `docs/` from the architecture PDF: the PDF itself, extracted text and ten figures, PRD, FRD, ARCHITECTURE, AI_PIPELINE, API, TOOLS, DATA_FLOWS, SECURITY, ACCEPTANCE_TESTS, REQUIREMENTS, DECISIONS, ASSUMPTIONS, INDEX.
- This commit also captured a `# rental_agent_prototype` line appended to README in UTF-16 (removed later in PR #2).
- Pushed directly to `main` (no PR).

## 2026-11-24 · PR #1 · Claude, merged by dunascode-prog
- Added `.gitattributes` marking `*.pdf`, `*.png`, `*.jpg`, `*.db` as binary so line-ending conversion can't corrupt the architecture PDF.

## 2026-11-24 · PR #2 · Claude, merged by dunascode-prog
- Implemented the prototype: project loader, SQLite schema with append-only `change_log` triggers, auth, guardrails, the ten tools, parity engine, change state machine with hash-checked approval, agent loop, API routes, browser UI.
- Tests: AC-1 to AC-7 with a scripted fake model, 13 supporting rule tests, optional live Bedrock test.
- Decisions: D-01 (Bedrock Mantle client, chosen by the owner); D-02 to D-13 recorded in `CLAUDE_CHANGELOG.md`, shipped as written.
- Removed the UTF-16 line from README; filled README "Run"/"Test" and HANDOVER; added `CLAUDE_CHANGELOG.md`.

## 2026-11-24 · PR #3 · Claude
- Documentation only: synced `docs/` with the merged implementation (test status, implemented request bodies, D-02 routes, resolution status for every scaffold mismatch, PDF ambiguity and assumption).

## 2026-11-24 · PR #4 · Claude
- Added this append-only `CHANGELOG.md`, backfilled with every change so far.
- Added `scripts/check_changelog.py` and the `changelog` GitHub Actions workflow. The check fails when an existing line of `CHANGELOG.md` is edited or deleted, or when other files change without a new entry appended.
- Decisions (owner, 2026-11-24): one entry appended per PR, enforced by CI; `CHANGELOG.md` at the repo root; `CLAUDE_CHANGELOG.md` kept and updated alongside it.

## 2026-11-24 · PR #5 · Claude
- Added the `tests` GitHub Actions workflow: installs `requirements.txt` on Python 3.12 and runs `python -m pytest -q` on every pull request and push to `main`. The live Bedrock test stays skipped in CI (no AWS credentials).
- Decisions: CI workflow chosen by the owner (2026-11-24).

## 2026-11-24 · PR #6 · Claude
- Added prompt caching for Bedrock calls: an explicit cache breakpoint at the end of the static system prompt (persona, rules, approved KB) plus top-level automatic caching for the conversation tail. Controlled by `prompt_caching` in `config.yaml` (default `true`).
- `traces.input_tokens` now includes tokens written to and read from the cache, so it still shows all input processed.
- Decisions: prompt caching chosen by the owner (2026-11-24); D-14 (5-minute cache, on by default) and D-15 (token counting in traces) proposed for review.

## 2026-11-24 · PR #7 · Claude
- Added a `Dockerfile` (Python 3.12 slim, non-root uid 1000, SQLite at `/data/app.db`, health check) and `.dockerignore` (keeps `.env`, `*.db`, `.git`, docs and tests out of the image).
- Added the `docker` GitHub Actions workflow: builds the image, starts it and checks `/health` and that `/data/app.db` is created.
- Added `docs/DEPLOYMENT.md`: step-by-step hosted demo on ECS Fargate + EFS behind a public load balancer that only CloudFront can reach, using CloudFront's default HTTPS address.
- `SESSION_COOKIE_SECURE=1` marks the session cookie Secure for HTTPS deployments (new in `.env.example`); test added.
- Decisions: owner chose ECS Fargate + EFS, Dockerfile plus a guide (no infrastructure as code), CloudFront's default HTTPS URL (no domain yet), and a public load balancer limited to CloudFront; D-16 (exactly one task) and D-17 (secret origin header) proposed for review.
