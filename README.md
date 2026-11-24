# Rental Agent Prototype

A small FastAPI prototype that runs a configurable AI assistant for short-term rental businesses. The assistant answers from an approved knowledge base, counts free visitor messages, proposes rate changes that need human approval, keeps an append-only change log, and refuses requests to message guests. The model provider is Amazon Bedrock (Claude) using AWS credentials; storage is SQLite.

## Folder layout

```
app/                  FastAPI app and modules (config, db, agent, model, tools, guardrails, parity, changes, auth)
app/static/           Browser UI: chat, register/login, approval cards, parity panel, change log
projects/rental-demo/ Demo project: config.yaml, kb/ (knowledge base), data/ (mock PMS and channel data)
tests/                Acceptance tests AC-1 to AC-7, supporting rule tests, optional live Bedrock test
docs/                 Project documentation and the architecture PDF
```

## Documentation

- [Documentation index](docs/INDEX.md): all project documents and a suggested reading order.
- [Architecture PDF (source of truth)](docs/source/Rental_Agent_Prototype_Architecture.pdf)

## Setup

```bash
python -m venv .venv
# Windows (PowerShell): .venv\Scripts\Activate.ps1
# macOS/Linux:          source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in local values
```

For live model answers:

1. In the Amazon Bedrock console, enable a Claude Haiku model (visitor chat) and a Claude Sonnet model (back-office).
2. Put their model IDs (`anthropic.<model-name>`) and your region in `projects/rental-demo/config.yaml` (`model_chat`, `model_backoffice`, `aws_region`), or set `AWS_REGION` in `.env`.
3. Give your AWS profile (`AWS_PROFILE` in `.env`) the `bedrock-mantle:CreateInference` permission on those models.
4. Set `STAFF_PASSWORD` in `.env` to enable the staff login (`staff_email` in `config.yaml`).

Without model IDs or AWS credentials the app still runs: guardrails, registration, parity and approvals all work, and chat turns that need the model return a safe fallback reply.

## Run

```bash
uvicorn app.main:app --env-file .env
```

Open http://localhost:8000. Visitors get 5 free messages, then a registration prompt. Log in with the staff email and `STAFF_PASSWORD` to see the approval cards, the parity panel and the change log.

With Docker:

```bash
docker build -t rental-agent-prototype .
docker run -p 8000:8000 --env-file .env -v rental-agent-data:/data \
  -v ~/.aws:/home/appuser/.aws:ro rental-agent-prototype
```

The `~/.aws` mount (read-only) lets the container use the `AWS_PROFILE` from `.env`; leave it out if you don't need live model answers.

For a hosted demo on AWS (ECS Fargate + EFS behind CloudFront), follow [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Test

```bash
python -m pytest -q
```

The model is replaced by a scripted fake, so tests need no AWS access. The optional live test runs against Bedrock when `RUN_LIVE_BEDROCK=1` and AWS credentials and model IDs are configured.

GitHub Actions runs two checks on every pull request and push to `main`: `tests` (the suite above) and `changelog` (see below).

## Change log

- [CHANGELOG.md](CHANGELOG.md): append-only record of every change to the repository. Every pull request appends an entry at the end; the `changelog` check fails if an existing line is edited or an entry is missing.
- [CLAUDE_CHANGELOG.md](CLAUDE_CHANGELOG.md): Claude's detailed change notes and decision records.
