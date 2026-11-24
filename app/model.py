"""Amazon Bedrock (Claude) client wrapper with one complete() function. AWS credentials stay here."""
from __future__ import annotations

import logging
from typing import Any, Protocol

import anthropic
from botocore.exceptions import BotoCoreError, ClientError

from app.config import is_placeholder

log = logging.getLogger(__name__)


class ModelError(Exception):
    """The model call failed; the agent answers with a safe fallback."""


class ModelClient(Protocol):
    def complete(
        self,
        *,
        model_id: str,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int,
        effort: str | None = None,
        cache: bool = False,
    ) -> Any: ...


class BedrockModel:
    """Calls Claude on Bedrock through the Anthropic SDK's Bedrock client (InvokeModel API, AWS SigV4).

    Credentials come from the AWS profile or environment (never from project files).
    The IAM permissions needed are bedrock:InvokeModel and bedrock:InvokeModelWithResponseStream
    on the configured models only (decision D-19, which replaced the Mantle client of D-01).
    Model IDs are Bedrock model or inference-profile IDs as shown in the console,
    e.g. us.anthropic.<model-name>-v1:0.
    """

    def __init__(self, region: str | None, profile: str | None = None):
        self._region = region
        self._profile = profile
        self._client: anthropic.AnthropicBedrock | None = None

    def _get_client(self) -> anthropic.AnthropicBedrock:
        if self._client is None:
            if not self._region:
                raise ModelError("No AWS region configured (set aws_region in config.yaml or AWS_REGION).")
            self._client = anthropic.AnthropicBedrock(aws_region=self._region, aws_profile=self._profile)
        return self._client

    def complete(
        self,
        *,
        model_id: str,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int,
        effort: str | None = None,
        cache: bool = False,
    ) -> Any:
        if is_placeholder(model_id):
            raise ModelError("No Bedrock model ID configured in config.yaml.")
        kwargs: dict[str, Any] = {
            "model": model_id,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
            "tools": tools,
        }
        if cache:
            # Prompt caching with explicit breakpoints only (InvokeModel rejects top-level cache_control):
            # one at the end of the static prefix (tools + system prompt with the approved KB) and one on
            # the newest user message, so later calls in the same turn reuse the conversation so far.
            # Prefixes shorter than the model's minimum are simply not cached (no error).
            kwargs["system"] = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
            kwargs["messages"] = _mark_last_message(messages)
        if effort:
            kwargs["output_config"] = {"effort": effort}
        try:
            return self._get_client().messages.create(**kwargs)
        except anthropic.RateLimitError as exc:
            log.warning("Bedrock rate limited: %s", exc)
            raise ModelError("rate limited") from exc
        except anthropic.APIStatusError as exc:
            log.error("Bedrock returned %s: %s", exc.status_code, exc)
            raise ModelError(f"model error {exc.status_code}") from exc
        except anthropic.APIConnectionError as exc:
            log.error("Bedrock connection failed: %s", exc)
            raise ModelError("connection failed") from exc
        except (BotoCoreError, ClientError) as exc:
            log.error("AWS credentials or client error: %s", exc)
            raise ModelError("AWS credentials error") from exc


def _mark_last_message(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Copy of messages with a cache breakpoint on the last block of the last message (inputs untouched)."""
    if not messages:
        return messages
    last = dict(messages[-1])
    content = last.get("content")
    if isinstance(content, str):
        last["content"] = [{"type": "text", "text": content, "cache_control": {"type": "ephemeral"}}]
    elif isinstance(content, list) and content and isinstance(content[-1], dict):
        last["content"] = [*content[:-1], {**content[-1], "cache_control": {"type": "ephemeral"}}]
    else:
        return messages
    return [*messages[:-1], last]
