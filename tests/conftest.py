"""Shared test fixtures: settings that write to a temporary database, and a ready-built system."""

from __future__ import annotations

from datetime import date

import pytest

from openrange.core.config import load_settings
from openrange.core.llm import FakeLLM
from openrange.orchestrator.wiring import build_system

TEST_DAY = date(2026, 11, 20)


@pytest.fixture
def settings(tmp_path):
    s = load_settings()
    s.db_path = tmp_path / "test.db"
    s.cache_dir = tmp_path / "cache"
    s.mode = "fake"
    return s


@pytest.fixture
def system(settings):
    sys_ = build_system(settings, llm=FakeLLM())
    yield sys_
    sys_.db.close()
