"""Optional live test against Bedrock (PDF section 10). Runs only when RUN_LIVE_BEDROCK=1 and AWS is configured."""
import os

import pytest
from fastapi.testclient import TestClient

from app import guardrails
from app.main import create_app

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_BEDROCK") != "1",
    reason="live Bedrock test: set RUN_LIVE_BEDROCK=1 with AWS credentials and model IDs in config.yaml",
)


def test_live_visitor_answer_is_cited_or_handed_off(tmp_path):
    app = create_app(project_name="rental-demo", database_path=str(tmp_path / "live.db"))
    with TestClient(app) as client:
        body = client.post("/api/chat", json={"message": "What time is check-in?"}).json()
    assert body["state"]["model_called"] is True
    assert "[kb:check-in]" in body["reply"] or body["reply"] == guardrails.HANDOFF_OFFER
