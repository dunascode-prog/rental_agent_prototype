# Handover

Full project documentation: [docs/INDEX.md](docs/INDEX.md). Change history: [CLAUDE_CHANGELOG.md](CLAUDE_CHANGELOG.md).

## How to run

1. Create the virtual environment and install requirements (see [README.md](README.md#setup)).
2. Copy `.env.example` to `.env` and set `AWS_PROFILE`, `AWS_REGION` and `STAFF_PASSWORD`.
3. Put the Bedrock model IDs in `projects/rental-demo/config.yaml`.
4. Start the app: `uvicorn app.main:app --env-file .env`, then open http://localhost:8000.

The SQLite file is created at `projects/rental-demo/data/app.db` (or `DATABASE_PATH`) and seeded from `data/*.json` on first start. Delete it to reset the demo.

## How to test

`python -m pytest -q` runs AC-1 to AC-7 and the supporting rule tests with a scripted fake model. Set `RUN_LIVE_BEDROCK=1` to also run the live Bedrock test.

## How to change the knowledge base and config

- **Knowledge base:** add a Markdown file to `projects/rental-demo/kb/` with front matter:

  ```markdown
  ---
  id: late-checkout
  title: Late check-out
  status: approved
  ---
  Answer text here.
  ```

  Only entries whose `status` equals `kb_status_required` (`approved`) reach the model, and replies must cite them as `[kb:<id>]`. Use `status: draft` to keep an entry out. Restart the app after editing.
- **Prices:** edit `projects/rental-demo/data/price_sheet.json`. It is cited as `[kb:price-sheet]`.
- **Mock PMS and channel rates:** edit `data/pms_rates.json` and `data/channel_rates.json`, then delete the database file so it is reseeded.
- **Config:** `projects/rental-demo/config.yaml` sets the persona, free messages, tools per role, model IDs, region, parity tolerance and the staff email. The app validates it at start-up and refuses to start on errors.
