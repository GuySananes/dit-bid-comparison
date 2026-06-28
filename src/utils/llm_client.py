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


def _strip_fences(text: str) -> str:
    """Remove markdown code fences the model occasionally wraps JSON in."""
    stripped = text.strip()
    if stripped.startswith("```"):
        # Drop opening fence line (```json or ```)
        stripped = stripped.split("\n", 1)[-1]
        # Drop closing fence
        if stripped.endswith("```"):
            stripped = stripped[: stripped.rfind("```")]
    return stripped.strip()


def call_llm(
    system: str,
    user: str,
    expect_json: bool = True,
    timeout: float | None = None,
) -> dict | str:
    """Call the LLM and return parsed JSON (if expect_json) or raw text.

    Args:
        timeout: per-API-call timeout in seconds (None = SDK default of 600s).
    """

    def _call() -> tuple[str, int, int]:
        try:
            response = _client.messages.create(
                model=LLM_MODEL,
                max_tokens=LLM_MAX_TOKENS,
                system=system,
                messages=[{"role": "user", "content": user}],
                timeout=timeout,
            )
        except anthropic.APITimeoutError as exc:
            raise LLMError(f"LLM call timed out after {timeout}s", "") from exc
        text = response.content[0].text
        return text, response.usage.input_tokens, response.usage.output_tokens

    start = time.monotonic()
    raw, input_tokens, output_tokens = _call()
    duration = time.monotonic() - start

    logger.info(
        "LLM call model=%s input_tokens=%d output_tokens=%d duration=%.2fs",
        LLM_MODEL, input_tokens, output_tokens, duration,
    )
    logger.debug("LLM raw response (attempt 1): %r", raw[:500] if raw else "<empty>")

    if not expect_json:
        return raw

    try:
        return json.loads(_strip_fences(raw))
    except json.JSONDecodeError:
        logger.warning(
            "JSON parse failed on first attempt (output_tokens=%d), raw[:200]=%r, retrying",
            output_tokens,
            raw[:200] if raw else "<empty>",
        )

    start = time.monotonic()
    raw, input_tokens, output_tokens = _call()
    duration = time.monotonic() - start

    logger.info(
        "LLM retry model=%s input_tokens=%d output_tokens=%d duration=%.2fs",
        LLM_MODEL, input_tokens, output_tokens, duration,
    )
    logger.debug("LLM raw response (attempt 2): %r", raw[:500] if raw else "<empty>")

    try:
        return json.loads(_strip_fences(raw))
    except json.JSONDecodeError as exc:
        logger.error(
            "LLM returned invalid JSON after two attempts. "
            "output_tokens=%d raw[:500]=%r",
            output_tokens,
            raw[:500] if raw else "<empty>",
        )
        raise LLMError(
            f"LLM returned invalid JSON after two attempts: {exc}", raw
        ) from exc
