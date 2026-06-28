from __future__ import annotations

import json
import logging
import time

import anthropic

from config.settings import ANTHROPIC_API_KEY, LLM_MAX_TOKENS, LLM_MODEL

logger = logging.getLogger(__name__)

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


class LLMError(Exception):
    def __init__(self, message: str, raw_response: str):
        super().__init__(message)
        self.raw_response = raw_response


def call_llm(system: str, user: str, expect_json: bool = True) -> dict | str:
    """Call the LLM and return parsed JSON (if expect_json) or raw text."""

    def _call() -> tuple[str, int, int]:
        response = _client.messages.create(
            model=LLM_MODEL,
            max_tokens=LLM_MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = response.content[0].text
        return text, response.usage.input_tokens, response.usage.output_tokens

    start = time.monotonic()
    raw, input_tokens, output_tokens = _call()
    duration = time.monotonic() - start

    logger.info(
        "LLM call model=%s input_tokens=%d output_tokens=%d duration=%.2fs",
        LLM_MODEL, input_tokens, output_tokens, duration,
    )

    if not expect_json:
        return raw

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("JSON parse failed on first attempt, retrying")

    start = time.monotonic()
    raw, input_tokens, output_tokens = _call()
    duration = time.monotonic() - start

    logger.info(
        "LLM retry model=%s input_tokens=%d output_tokens=%d duration=%.2fs",
        LLM_MODEL, input_tokens, output_tokens, duration,
    )

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMError(
            f"LLM returned invalid JSON after two attempts: {exc}", raw
        ) from exc
