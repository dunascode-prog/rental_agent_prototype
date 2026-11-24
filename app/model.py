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
    """Calls Claude on Bedrock through the Anthropic SDK's Mantle client (Messages API on Bedrock, AWS SigV4).

    Credentials come from the AWS profile or environment (never from project files).
    The IAM permission needed is bedrock-mantle:CreateInference only (decision D-01).
    Model IDs carry the anthropic. prefix, e.g. anthropic.claude-haiku-5-5.
    """

    def __init__(self, region: str | None, profile: str | None = None):
        self._region = region
        self._profile = profile
        self._client: anthropic.AnthropicBedrockMantle | None = None

    def _get_client(self) -> anthropic.AnthropicBedrockMantle:
        if self._client is None:
            if not self._region:
                raise ModelError("No AWS region configured (set aws_region in config.yaml or AWS_REGION).")
            self._client = anthropic.AnthropicBedrockMantle(aws_region=self._region, aws_profile=self._profile)
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
            # Prompt caching: an explicit breakpoint at the end of the static prefix (tools + system prompt
            # with the approved KB), plus top-level automatic caching for the growing conversation tail.
            kwargs["system"] = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
            kwargs["cache_control"] = {"type": "ephemeral"}
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
