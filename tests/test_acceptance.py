"""Acceptance tests AC-1 to AC-7 (PDF section 10, docs/ACCEPTANCE_TESTS.md). The model is a scripted fake."""
import sqlite3

import pytest

from app import guardrails
from tests.conftest import text, tool_call


def test_ac1(client, fake_model, db):
    """AC-1: knowledge question returns a cited answer (Fig. 5 stages 3 to 7)."""
    fake_model.script = [
        tool_call("search_kb", {"query": "check-in time"}),
        text("Check-in is from 3 pm and check-out is by 11 am [kb:check-in]."),
    ]
    response = client.post("/api/chat", json={"message": "What time is check-in?"})

    assert response.status_code == 200
    body = response.json()
    assert "[kb:check-in]" in body["reply"]
    assert body["state"]["messages_used"] == 1
    assert len(fake_model.calls) == 2
    # The tool result went back to the model and carried the approved entry.
    tool_result = fake_model.calls[1]["messages"][-1]["content"][0]
    assert tool_result["type"] == "tool_result" and "check-in" in tool_result["content"]
    traces = db("SELECT * FROM traces")
    assert len(traces) == 1 and traces[0]["tools_called"] == '["search_kb"]'


def test_ac2(client, fake_model, db):
    """AC-2: unknown question returns a hand-off, no guess (Fig. 5 stage 6)."""
    fake_model.script = [text("Yes, there is a swimming pool on site.")]
    response = client.post("/api/chat", json={"message": "Is there a swimming pool?"})

    assert response.status_code == 200
    assert response.json()["reply"] == guardrails.HANDOFF_OFFER
    handoffs = db("SELECT * FROM handoffs")
    assert len(handoffs) == 1
    assert handoffs[0]["reason"] == "no_approved_citation"


def test_ac3(client, fake_model):
    """AC-3: sixth visitor message returns the registration prompt; model not called (Fig. 5 stage 2, Fig. 9)."""
    fake_model.default = text("Pets are welcome at the Garden Cottage [kb:pets].")
    for number in range(1, 6):
        response = client.post("/api/chat", json={"message": f"Question {number} about pets"})
        assert response.json()["reply"] != guardrails.registration_prompt(5)
    assert len(fake_model.calls) == 5

    sixth = client.post("/api/chat", json={"message": "Question 6 about pets"})
    assert sixth.status_code == 200
    assert sixth.json()["reply"] == guardrails.registration_prompt(5)
    assert sixth.json()["state"]["model_called"] is False
    assert len(fake_model.calls) == 5

    # A visitor who registers gets unlimited chat for their account.
    assert client.post("/api/register", json={"email": "visitor@example.com", "password": "a-long-password"}).status_code == 201
    after = client.post("/api/chat", json={"message": "Question 7 about pets"})
    assert "[kb:pets]" in after.json()["reply"]
    assert len(fake_model.calls) == 6


def test_ac4(staff_client, db):
    """AC-4: seeded rate mismatch is reported, nothing changes (Fig. 7)."""
    rates_before = [tuple(row) for row in db("SELECT * FROM pms_rates ORDER BY listing_id, date")]
    response = staff_client.post("/api/parity/run", json={"listing_id": "L-100", "start": "2026-12-01", "end": "2026-12-07"})

    assert response.status_code == 200
    summary = response.json()
    assert summary["gap_count"] == 1
    assert summary["no_data_count"] == 1  # 2026-12-07 has no channel rate: reported, not a gap
    gaps = db("SELECT * FROM gaps WHERE listing_id = 'L-100'")
    assert [(g["channel"], g["date"], g["pms_rate"], g["channel_rate"]) for g in gaps] == [
        ("channel_a", "2026-12-05", 180.0, 175.0)
    ]
    assert [tuple(row) for row in db("SELECT * FROM pms_rates ORDER BY listing_id, date")] == rates_before
    assert staff_client.get("/api/parity", params={"listing_id": "L-100"}).json()["gaps"][0]["date"] == "2026-12-05"


def test_ac5(staff_client, db):
    """AC-5: change has no effect until approved; then applied and logged (Fig. 6, Fig. 8)."""
    def rate() -> float:
        return db("SELECT rate FROM pms_rates WHERE listing_id = 'L-100' AND date = '2026-12-05'")[0]["rate"]

    proposed = staff_client.post(
        "/api/changes",
        json={"type": "rate_update", "target": {"listing_id": "L-100", "date": "2026-12-05"}, "before": 180, "after": 175},
    )
    assert proposed.status_code == 201
    change = proposed.json()["change"]
    assert change["state"] == "awaiting_approval"
    assert rate() == 180.0

    assert staff_client.post(f"/api/changes/{change['id']}/approve", json={"approver_name": ""}).status_code == 403
    assert rate() == 180.0

    approved = staff_client.post(
        f"/api/changes/{change['id']}/approve", json={"approver_name": "Ada Manager", "change_hash": change["change_hash"]}
    )
    assert approved.status_code == 200
    assert approved.json()["change"]["state"] == "verified"
    assert rate() == 175.0

    log = db("SELECT from_state, to_state FROM change_log WHERE change_id = ? ORDER BY id", (change["id"],))
    assert [(row["from_state"], row["to_state"]) for row in log] == [
        (None, "proposed"),
        ("proposed", "awaiting_approval"),
        ("awaiting_approval", "approved"),
        ("approved", "applied"),
        ("applied", "verified"),
    ]
    assert db("SELECT approver_name FROM approvals WHERE change_id = ?", (change["id"],))[0]["approver_name"] == "Ada Manager"
    assert staff_client.post(f"/api/changes/{change['id']}/approve", json={"approver_name": "Ada"}).status_code == 409


@pytest.mark.parametrize("as_staff", [False, True])
def test_ac6(client, fake_model, db, as_staff):
    """AC-6: guest-messaging request is refused and logged; model not called (Fig. 5 stage 1, Fig. 6)."""
    if as_staff:
        client.post("/api/login", json={"email": "staff@example.com", "password": "test-staff-password"})
    response = client.post("/api/chat", json={"message": "Please email the guest in R-5001 about late check-out."})

    assert response.status_code == 200
    assert response.json()["reply"] == guardrails.REFUSAL_TEXT
    assert fake_model.calls == []
    refusals = db("SELECT * FROM change_log WHERE event = 'refusal'")
    assert len(refusals) == 1 and refusals[0]["change_id"] is None


def test_ac7(staff_client, db_path):
    """AC-7: change_log rows cannot be updated or deleted (Fig. 4, Fig. 10)."""
    staff_client.post(
        "/api/changes",
        json={"type": "rate_update", "target": {"listing_id": "L-200", "date": "2026-12-02"}, "before": 95, "after": 99},
    )
    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM change_log").fetchone()[0] >= 2
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            conn.execute("UPDATE change_log SET actor = 'someone else'")
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            conn.execute("DELETE FROM change_log")
    finally:
        conn.close()
