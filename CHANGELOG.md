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

## 2026-11-24 · PR #8 · Claude
- Brings PRs #4 to #7 into `main`. They were stacked PRs; each one merged into the branch below it instead of `main`, because GitHub only retargets a stacked PR when the branch below it is deleted on merge, and automatic branch deletion is off in this repository. No content changes beyond this entry and the matching note in `CLAUDE_CHANGELOG.md`.

## 2026-11-24 · PR #9 · Claude
- Bedrock client switched from Mantle (`AnthropicBedrockMantle`) back to InvokeModel (`AnthropicBedrock`), because the AWS account can't use Claude through Mantle. IAM permissions are now `bedrock:InvokeModel` and `bedrock:InvokeModelWithResponseStream` on the two models.
- Model IDs can be set in `.env` as `BEDROCK_MODEL_CHAT` and `BEDROCK_MODEL_BACKOFFICE` (used when `config.yaml` keeps its placeholders).
- Prompt caching now uses explicit breakpoints only: the system prompt and the newest message.
- Added a back-office live test; updated README, `.env.example`, `config.yaml` comments and the docs.
- Decisions: D-19 (switch fully to InvokeModel) decided by the owner.
- Live check passed (2026-11-24) for both roles. Sonnet 4.6 must be called through its `us.` inference profile. Tests ran from the management account while AWS enables Bedrock for the project account.

## 2026-11-24 · PR #10 · Claude
- Documentation only: recorded the live Bedrock results in `docs/ASSUMPTIONS.md` (A-01 and A-06 resolved, SR-13 resolved), `docs/ACCEPTANCE_TESTS.md` (both live tests passed) and `docs/REQUIREMENTS.md` (ENV-05 confirmed; full list of environment variables).

## 2026-11-26 · PR #11 · Claude
- Hosted demo moved to one EC2 t3.micro behind CloudFront (decision D-20 by the owner, to cut cost from about $45-50 to about $12 a month). Added `deploy/ec2-userdata.sh` and an EC2 section in `docs/DEPLOYMENT.md`; the ECS Fargate plan is kept as the alternative. Updated `docs/INDEX.md` and `docs/ASSUMPTIONS.md` (SR-13); `.gitattributes` keeps shell scripts LF.
- Deployed and checked on 2026-11-26: health, HTTPS redirect, direct access blocked, a cited visitor answer, staff login and a back-office parity check. The Fargate resources created earlier the same day were removed.
