"""AdaL: the harness for the Trader's daily review (T6 Journal & Lessons).

AdaL runs headless (`adal -q ... -o json`) with:
  personality  agents_harness/trader/SYSTEM.md        (--system-prompt-file)
  skills       .adal/skills/<module>/SKILL.md          (one per OpenRange module, loaded on demand)
  memory       the same AdaL session is resumed every day (-r <session_id>), so it remembers past reviews

Setup (once): install AdaL (https://adal.sylph.ai), run `adal` and log in, then set platform.trader_llm: adal
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from pydantic import BaseModel

from openrange.core.config import PROJECT_ROOT, AdalSettings
from openrange.core.db import Database
from openrange.core.llm import LLMClient, LLMError, extract_json, with_json_instructions

HARNESS_DIR = PROJECT_ROOT / "agents_harness"
SESSION_FILE = PROJECT_ROOT / "data" / "adal_session.txt"


class AdalClient(LLMClient):
    provider = "adal"

    def __init__(self, cfg: AdalSettings, role: str, db: Database | None = None):
        if shutil.which(cfg.command) is None:
            raise LLMError(f"AdaL CLI '{cfg.command}' not found. Install from https://adal.sylph.ai")
        super().__init__({"fast": "adal", "smart": "adal"}, db)
        self.cfg = cfg
        self.system_prompt = HARNESS_DIR / role / "SYSTEM.md"

    def _call(self, prompt: str, schema: type[BaseModel], model: str) -> str:
        command = [self.cfg.command, "-q", with_json_instructions(prompt, schema), "-o", "json",
                   "--system-prompt-file", str(self.system_prompt)]
        session = _read_session()
        if session:
            command += ["-r", session]                   # memory: continue yesterday's review session

        done = subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True,
                              timeout=self.cfg.timeout_s, check=False)
        if done.returncode != 0:
            raise LLMError(f"adal exited {done.returncode}: {done.stderr[:300]}")
        result = json.loads(done.stdout)
        if not result.get("success", True):
            raise LLMError(f"adal failed: {result}")
        if result.get("session_id"):
            _write_session(result["session_id"])
        return extract_json(str(result.get("answer", "")))


def _read_session() -> str:
    return SESSION_FILE.read_text(encoding="utf-8").strip() if SESSION_FILE.exists() else ""


def _write_session(session_id: str) -> None:
    Path(SESSION_FILE).parent.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(session_id, encoding="utf-8")
