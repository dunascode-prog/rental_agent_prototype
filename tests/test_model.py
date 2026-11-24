"""Tests for the Bedrock request built by model.py (no network) and cache-aware token counting."""
from types import SimpleNamespace

import pytest

from app.model import BedrockModel, ModelError
from tests.conftest import text


def _capturing_model() -> tuple[BedrockModel, list[dict]]:
    sent: list[dict] = []
    model = BedrockModel(region="test-region")
    model._client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: sent.append(kw) or text("ok")))
    return model, sent


def _complete(model: BedrockModel, cache: bool) -> None:
    model.complete(
        model_id="anthropic.test-model",
        system="SYSTEM PROMPT",
        messages=[{"role": "user", "content": "hi"}],
        tools=[],
        max_tokens=100,
        cache=cache,
    )


def test_cache_on_marks_system_prompt_and_conversation():
    model, sent = _capturing_model()
    _complete(model, cache=True)
    request = sent[0]
    assert request["system"] == [{"type": "text", "text": "SYSTEM PROMPT", "cache_control": {"type": "ephemeral"}}]
    assert request["cache_control"] == {"type": "ephemeral"}


def test_cache_off_sends_plain_request():
    model, sent = _capturing_model()
    _complete(model, cache=False)
    assert sent[0]["system"] == "SYSTEM PROMPT"
    assert "cache_control" not in sent[0]


def test_placeholder_model_id_is_refused():
    model, sent = _capturing_model()
    with pytest.raises(ModelError):
        model.complete(model_id="<bedrock-model-id>", system="s", messages=[], tools=[], max_tokens=10)
    assert sent == []


def test_agent_passes_cache_flag_and_counts_cached_tokens(client, fake_model, db):
    reply = text("Check-in is from 3 pm [kb:check-in].")
    reply.usage = SimpleNamespace(input_tokens=10, output_tokens=5, cache_read_input_tokens=900, cache_creation_input_tokens=100)
    fake_model.script = [reply]
    client.post("/api/chat", json={"message": "When is check-in?"})
    assert fake_model.calls[0]["cache"] is True
    trace = db("SELECT input_tokens, output_tokens FROM traces")[0]
    assert (trace["input_tokens"], trace["output_tokens"]) == (1010, 5)
