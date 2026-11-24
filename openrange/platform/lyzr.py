"""Lyzr: the Analyst's LLM calls go through Lyzr agents, so Lyzr applies its guardrails
(PII, toxicity, prompt-injection filters) and keeps an audit log of every call.

Setup (once, in Lyzr Agent Studio, studio.lyzr.ai):
  1. Create two agents: "openrange-fast" (cheap model) and "openrange-smart" (strong model).
     Role: "Financial analyst. Answer only with the JSON requested. Never invent numbers."
  2. Turn on Responsible AI (guardrails) for both.
  3. Put their agent ids in config/settings.yaml (platform.lyzr) and LYZR_API_KEY in .env.
  4. Set platform.analyst_llm: lyzr
"""

from __future__ import annotations

import uuid

import requests
from pydantic import BaseModel

from openrange.core.config import LyzrSettings
from openrange.core.db import Database
from openrange.core.llm import LLMClient, LLMError, extract_json, with_json_instructions

CHAT_PATH = "/v3/inference/chat/"


class LyzrClient(LLMClient):
    provider = "lyzr"

    def __init__(self, api_key: str, cfg: LyzrSettings, db: Database | None = None, user_id: str = "openrange"):
        if not api_key:
            raise LLMError("LYZR_API_KEY is empty. Add it to .env or set platform.analyst_llm: fake")
        if not (cfg.fast_agent_id and cfg.smart_agent_id):
            raise LLMError("Set platform.lyzr.fast_agent_id and smart_agent_id in config/settings.yaml")
        super().__init__({"fast": cfg.fast_agent_id, "smart": cfg.smart_agent_id}, db)
        self.api_key = api_key
        self.url = cfg.base_url.rstrip("/") + CHAT_PATH
        self.user_id = user_id
        self.session_id = f"openrange-{uuid.uuid4().hex[:8]}"     # one session per run = one audit trail

    def _call(self, prompt: str, schema: type[BaseModel], model: str) -> str:
        """`model` is the Lyzr agent id for the requested tier."""
        response = requests.post(
            self.url,
            headers={"x-api-key": self.api_key, "Content-Type": "application/json"},
            json={"user_id": self.user_id, "agent_id": model, "session_id": self.session_id,
                  "message": with_json_instructions(prompt, schema)},
            timeout=60,
        )
        response.raise_for_status()
        body = response.json()
        return extract_json(body.get("response", "") if isinstance(body, dict) else str(body))
