"""One LLM client interface for the whole project.

    client.generate(prompt, schema, tier="fast" | "smart") -> instance of `schema`

Providers here: FakeLLM (tests, fake mode), GeminiClient, ClaudeClient.
Sponsor providers (same interface): LyzrClient (platform/lyzr.py), AdalClient (platform/adal.py).
Every call is logged to the `llm_calls` table. The factory that picks one is orchestrator/wiring.py.

The LLM is only used by Analyst modules (M2, M3, M4, M6) and the Trader's journal (T6).
Trader modules T1-T5 must never import this file (a test checks it).
"""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Literal, TypeVar

from pydantic import BaseModel

from openrange.core.db import Database
from openrange.core.log import get_logger

log = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)
Tier = Literal["fast", "smart"]


class LLMError(RuntimeError):
    pass


def with_json_instructions(prompt: str, schema: type[BaseModel]) -> str:
    """For providers without native structured output: ask for JSON matching the schema."""
    instruction = "Reply with ONLY one JSON object (no extra text) that matches this JSON schema:"
    return f"{prompt}\n\n{instruction}\n{json.dumps(schema.model_json_schema())}"


def extract_json(text: str) -> str:
    """Take the JSON object out of a reply that may have extra text or ``` fences around it."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end < start:
        raise LLMError(f"No JSON object in reply: {text[:200]!r}")
    return text[start : end + 1]


class LLMClient(ABC):
    provider: str = "base"

    def __init__(self, models: dict[str, str] | None = None, db: Database | None = None):
        self.models = models or {"fast": "fake-fast", "smart": "fake-smart"}
        self.db = db

    def generate(self, prompt: str, schema: type[T], tier: Tier = "fast") -> T:
        """Ask the model for JSON matching `schema`. Raises LLMError on any failure."""
        model = self.models[tier]
        started = time.perf_counter()
        ok, error = True, None
        try:
            raw = self._call(prompt, schema, model)
            return schema.model_validate_json(raw)
        except Exception as exc:  # noqa: BLE001 - every failure becomes LLMError
            ok, error = False, str(exc)
            raise LLMError(error) from exc
        finally:
            self._log_call(model, schema.__name__, ok, error, time.perf_counter() - started)

    @abstractmethod
    def _call(self, prompt: str, schema: type[BaseModel], model: str) -> str:
        """Return the model's raw JSON text."""

    def _log_call(self, model: str, schema_name: str, ok: bool, error: str | None, seconds: float) -> None:
        record = {"provider": self.provider, "model": model, "schema": schema_name,
                  "ok": ok, "error": error, "latency_s": round(seconds, 3)}
        if self.db:
            self.db.save("llm_calls", record, datetime.now())
        if not ok:
            log.warning("LLM call failed (%s): %s", schema_name, error)


class FakeLLM(LLMClient):
    """Returns canned answers so the whole system runs with no API key.

    `responses` maps a schema class name to a dict; anything missing gets a simple default.
    Set `fail=True` to test that every module falls back to its code score.
    """

    provider = "fake"

    def __init__(self, responses: dict[str, dict] | None = None, fail: bool = False, db: Database | None = None):
        super().__init__(db=db)
        self.responses = responses or {}
        self.fail = fail

    def _call(self, prompt: str, schema: type[BaseModel], model: str) -> str:
        if self.fail:
            raise LLMError("FakeLLM set to fail")
        answer = self.responses.get(schema.__name__, _DEFAULT_ANSWERS.get(schema.__name__, {}))
        return json.dumps(answer)


_DEFAULT_ANSWERS: dict[str, dict] = {
    "MacroNarrative": {"narrative": "[fake LLM] Macro picture is mixed; see drivers."},
    "RegimeExplanation": {"explanation": "[fake LLM] Regime chosen from SPY trend and volatility."},
    "SentimentLLMOutput": {"band": "Slightly Bullish", "score": 6.0, "confidence": "low", "catalyst": None},
    "PickReason": {"reason": "[fake LLM] In play on high opening volume, trend agrees with the 200 EMA."},
    "LessonsLLMOutput": {"lessons": ["[fake LLM] Keep following the rulebook; sample is too small to change it."]},
}


class GeminiClient(LLMClient):
    provider = "gemini"

    def __init__(self, api_key: str, models: dict[str, str], db: Database | None = None):
        super().__init__(models, db)
        if not api_key:
            raise LLMError("GEMINI_API_KEY is empty. Add it to .env or use fake for this agent (settings.yaml)")
        from google import genai  # imported here so the package is only needed when used

        self._client = genai.Client(api_key=api_key)

    def _call(self, prompt: str, schema: type[BaseModel], model: str) -> str:
        response = self._client.models.generate_content(
            model=model,
            contents=prompt,
            config={"response_mime_type": "application/json", "response_schema": schema},
        )
        return response.text


class ClaudeClient(LLMClient):
    provider = "claude"

    def __init__(self, api_key: str, models: dict[str, str], db: Database | None = None):
        super().__init__(models, db)
        if not api_key:
            raise LLMError("ANTHROPIC_API_KEY is empty. Add it to .env or use fake for this agent (settings.yaml)")
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)

    def _call(self, prompt: str, schema: type[BaseModel], model: str) -> str:
        # Force a single tool call whose input must match the schema -> structured JSON.
        tool = {"name": "answer", "description": "Return the answer.", "input_schema": schema.model_json_schema()}
        response = self._client.messages.create(
            model=model,
            max_tokens=1024,
            tools=[tool],
            tool_choice={"type": "tool", "name": "answer"},
            messages=[{"role": "user", "content": prompt}],
        )
        for block in response.content:
            if block.type == "tool_use":
                return json.dumps(block.input)
        raise LLMError("Claude returned no tool_use block")

