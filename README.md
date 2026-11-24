# Rental Agent Prototype

A small FastAPI prototype that runs a configurable AI assistant for short-term rental businesses. The assistant answers from an approved knowledge base, counts free visitor messages, proposes rate changes that need human approval, keeps an append-only change log, and refuses requests to message guests. The model provider is Amazon Bedrock (Claude) using AWS credentials; storage is SQLite.

## Folder layout

```
app/                  FastAPI app and modules (config, db, agent, model, tools, guardrails, parity, changes, auth)
app/static/           Static front-end files
projects/rental-demo/ Demo project: config.yaml, kb/ (knowledge base), data/ (local data)
tests/                Acceptance tests (AC1-AC7)
```

## Setup

```bash
python -m venv .venv
# Windows (PowerShell): .venv\Scripts\Activate.ps1
# macOS/Linux:          source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in local values
```

## Run

TODO

## Test

TODO
