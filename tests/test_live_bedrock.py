"""Optional live tests against Bedrock (PDF section 10). Run only when RUN_LIVE_BEDROCK=1 and AWS is configured."""
import os
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import guardrails
from app.main import create_app

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_BEDROCK") != "1",
    reason="live Bedrock test: set RUN_LIVE_BEDROCK=1 with AWS credentials and BEDROCK_MODEL_* (or model IDs in config.yaml)",
)

STAFF_EMAIL = "staff@example.com"
STAFF_PASSWORD = "live-test-staff-password"


def test_live_visitor_answer_is_cited_or_handed_off(tmp_path):
    app = create_app(project_name="rental-demo", database_path=str(tmp_path / "live.db"))
    with TestClient(app) as client:
        body = client.post("/api/chat", json={"message": "What time is check-in?"}).json()
    assert body["state"]["model_called"] is True
    assert body["state"]["outcome"] != "fallback", "model call failed: check model ID, region and IAM"
    assert "[kb:check-in]" in body["reply"] or body["reply"] == guardrails.HANDOFF_OFFER


def test_live_back_office_runs_parity_check_with_tools(tmp_path):
    db_path = tmp_path / "live.db"
    app = create_app(project_name="rental-demo", database_path=str(db_path), staff_password=STAFF_PASSWORD)
    with TestClient(app) as client:
        assert client.post("/api/login", json={"email": STAFF_EMAIL, "password": STAFF_PASSWORD}).status_code == 200
        body = client.post(
            "/api/chat",
            json={"message": "Run a parity check for listing L-100 from 2026-12-01 to 2026-12-07 and list the gaps."},
        ).json()
    assert body["state"]["model_called"] is True
    assert body["state"]["outcome"] != "fallback", "model call failed: check model ID, region and IAM"
    with sqlite3.connect(db_path) as conn:
        tools_called = conn.execute("SELECT tools_called FROM traces").fetchone()[0]
        gaps = conn.execute("SELECT COUNT(*) FROM gaps WHERE listing_id = 'L-100'").fetchone()[0]
    assert "run_parity_check" in tools_called
    assert gaps >= 1
