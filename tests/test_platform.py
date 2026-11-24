"""Sponsor-tool integrations, tested with fake HTTP responses (no keys or internet needed)."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from openrange.core.config import BandSettings, LyzrSettings
from openrange.core.db import Database
from openrange.core.llm import FakeLLM
from openrange.core.schemas import MacroNarrative, Watchlist
from openrange.orchestrator.scheduler import jobs_for
from openrange.orchestrator.wiring import build_system
from openrange.platform import bus as bus_module
from openrange.platform import lyzr as lyzr_module
from openrange.platform import skills
from openrange.platform.bus import BandBus, LocalBus, Topic

TS = datetime(2026, 11, 20, 9, 35)
BAND = BandSettings(base_url="https://band.test", room_id="room1", analyst_agent_id="A", trader_agent_id="T")


class FakeResponse:
    def __init__(self, status: int = 200, body=None):
        self.status_code = status
        self._body = body if body is not None else {}

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise bus_module.requests.HTTPError(str(self.status_code))


def watchlist() -> Watchlist:
    return Watchlist(date=TS.date(), regime="BULL", macro_bias="RISK_ON", size_multiplier=1.0, picks=[])


# ------------------------------------------------------------------ BAND

def test_band_publish_posts_to_room_with_mention(tmp_path, monkeypatch):
    sent = {}
    monkeypatch.setattr(bus_module.requests, "post",
                        lambda url, **kw: sent.update(url=url, **kw) or FakeResponse())
    db = Database(tmp_path / "a.db", "run", "fake")
    BandBus(LocalBus(db), BAND, "key-A", me="A", other="T").publish(Topic.WATCHLIST, watchlist(), TS)

    assert sent["url"] == "https://band.test/api/v1/agent/chats/room1/messages"
    assert sent["headers"]["X-API-Key"] == "key-A"
    message = sent["json"]["message"]
    assert message["mentions"] == [{"id": "T"}]
    assert message["content"].startswith("@T [openrange:watchlist] {")


def test_band_latest_pulls_message_from_other_agent(tmp_path, monkeypatch):
    content = f"@T [openrange:watchlist] {watchlist().model_dump_json()}"
    replies = iter([FakeResponse(200, {"data": {"id": "m1", "content": content}}), FakeResponse(204)])
    monkeypatch.setattr(bus_module.requests, "get", lambda url, **kw: next(replies))
    db = Database(tmp_path / "t.db", "run", "fake")                 # the Trader's own, empty database

    message = BandBus(LocalBus(db), BAND, "key-T", me="T", other="A").latest(Topic.WATCHLIST)
    assert message["regime"] == "BULL" and message["date"] == "2026-11-20"


def test_band_needs_keys():
    with pytest.raises(ValueError):
        BandBus(LocalBus.__new__(LocalBus), BAND, "", me="A", other="T")


# ------------------------------------------------------------------ Lyzr

def test_lyzr_client_sends_agent_id_and_parses_json(monkeypatch):
    sent = {}

    def fake_post(url, **kw):
        sent.update(url=url, **kw)
        return FakeResponse(200, {"response": 'Sure:\n```json\n{"narrative": "Rates are falling."}\n```'})

    monkeypatch.setattr(lyzr_module.requests, "post", fake_post)
    cfg = LyzrSettings(base_url="https://lyzr.test", fast_agent_id="fast-1", smart_agent_id="smart-1")
    answer = lyzr_module.LyzrClient("key", cfg).generate("macro?", MacroNarrative, tier="smart")

    assert answer.narrative == "Rates are falling."
    assert sent["url"] == "https://lyzr.test/v3/inference/chat/"
    assert sent["json"]["agent_id"] == "smart-1"
    assert sent["headers"]["x-api-key"] == "key"


# ------------------------------------------------------------------ wiring fallbacks

def test_missing_sponsor_keys_fall_back_to_local(settings):
    settings.platform.bus = "band"
    settings.platform.analyst_llm = "lyzr"
    settings.platform.trader_llm = "adal"
    settings.secrets.lyzr_api_key = ""
    system = build_system(settings)
    assert isinstance(system.analyst.bus, LocalBus)
    assert isinstance(system.analyst_llm, FakeLLM) and isinstance(system.trader_llm, FakeLLM)
    system.db.close()


def test_each_role_runs_only_its_own_jobs():
    assert set(jobs_for("analyst")) == {"weekly", "premarket", "open"}
    assert set(jobs_for("trader")) == {"open", "intraday", "close", "review"}
    assert set(jobs_for("both")) == {"weekly", "premarket", "open", "intraday", "close", "review"}


# ------------------------------------------------------------------ skills (AdaL + Finch)

def test_skill_export_writes_one_package_per_module(tmp_path, monkeypatch):
    monkeypatch.setattr(skills, "PROJECT_ROOT", tmp_path)
    files = skills.export()
    assert len(files) == 2 * len(skills.SKILLS) == 24
    first = skills.SKILLS[0]
    text = (tmp_path / ".adal" / "skills" / first.slug / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith(f"---\nname: {first.slug}\n")
    manifest = json.loads((tmp_path / "skills" / first.slug / "skill.json").read_text(encoding="utf-8"))
    assert manifest["module"] == first.module


def test_fake_llm_works_with_per_agent_wiring(settings):
    system = build_system(settings, llm=FakeLLM())
    assert system.analyst_llm is system.trader_llm
    system.db.close()
