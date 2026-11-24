"""Message bus between the two agents. This is the only way they talk to each other.

    Analyst --(Topic.WATCHLIST)--> Trader      at 09:35
    Trader  --(Topic.LESSONS)----> Analyst     at 16:15, read the next morning

LocalBus = stores messages in the database `events` table (works offline, survives restarts).
BandBus  = sends every message through a BAND room as well, and pulls the other agent's messages from BAND.
           Each agent is its own BAND "remote agent" (own id + API key), so the room shows the two talking.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime
from enum import StrEnum

import requests
from pydantic import BaseModel

from openrange.core.config import BandSettings
from openrange.core.db import Database
from openrange.core.log import get_logger

log = get_logger(__name__)


class Topic(StrEnum):
    WATCHLIST = "watchlist"
    LESSONS = "lessons"


class MessageBus(ABC):
    @abstractmethod
    def publish(self, topic: Topic, message: BaseModel, ts: datetime) -> None: ...

    @abstractmethod
    def latest(self, topic: Topic) -> dict | None:
        """Most recent message on a topic, as a dict (None if nothing was sent yet)."""


class LocalBus(MessageBus):
    """`share_across_runs=True`: tomorrow's run reads today's lessons (fake/live mode).
    `share_across_runs=False`: messages stay inside one run (backtests must not leak into each other)."""

    def __init__(self, db: Database, share_across_runs: bool = True):
        self.db = db
        self.share_across_runs = share_across_runs

    def publish(self, topic: Topic, message: BaseModel, ts: datetime) -> None:
        self.db.save("events", {"topic": str(topic), "message": message.model_dump(mode="json")}, ts,
                     symbol=str(topic))

    def latest(self, topic: Topic) -> dict | None:
        scope_column, scope_value = ("mode", self.db.mode) if self.share_across_runs else ("run_id", self.db.run_id)
        row = self.db.conn.execute(
            f"SELECT payload FROM events WHERE symbol = ? AND {scope_column} = ? ORDER BY id DESC LIMIT 1",
            (str(topic), scope_value),
        ).fetchone()
        return json.loads(row[0])["message"] if row else None


class BandBus(MessageBus):
    """BAND Agent API (https://docs.band.ai). Messages look like:

        @Trader [openrange:watchlist] {"date": "2026-11-20", "picks": [...]}

    publish -> saved locally AND posted to the room, @mentioning the other agent.
    latest  -> first pulls new messages addressed to this agent from BAND, then answers from the local copy,
               so the agents keep working even if BAND is briefly unreachable.
    """

    MARKER = "[openrange:{topic}]"
    MAX_PULL = 50

    def __init__(self, local: LocalBus, cfg: BandSettings, api_key: str, me: str, other: str):
        if not (api_key and cfg.room_id and me and other):
            raise ValueError("BAND needs room_id, both agent ids (config) and this agent's API key (.env)")
        self.local = local
        self.base = cfg.base_url.rstrip("/") + "/api/v1/agent"
        self.room = cfg.room_id
        self.me, self.other = me, other
        self.headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

    def publish(self, topic: Topic, message: BaseModel, ts: datetime) -> None:
        self.local.publish(topic, message, ts)
        content = f"@{self.other} {self.MARKER.format(topic=topic)} {message.model_dump_json()}"
        try:
            r = requests.post(f"{self.base}/chats/{self.room}/messages", headers=self.headers, timeout=20,
                              json={"message": {"content": content, "mentions": [{"id": self.other}]}})
            r.raise_for_status()
        except requests.RequestException as exc:
            log.error("BAND publish failed (%s); message kept locally: %s", topic, exc)

    def latest(self, topic: Topic) -> dict | None:
        self._pull()
        return self.local.latest(topic)

    def _pull(self) -> None:
        """Read every new message for this agent from BAND and store the OpenRange ones locally."""
        for _ in range(self.MAX_PULL):
            try:
                r = requests.get(f"{self.base}/chats/{self.room}/messages/next", headers=self.headers, timeout=20)
            except requests.RequestException as exc:
                log.error("BAND pull failed: %s", exc)
                return
            if r.status_code == 204:
                return
            r.raise_for_status()
            self._store(_find_content(r.json()))

    def _store(self, content: str) -> None:
        for topic in Topic:
            marker = self.MARKER.format(topic=topic)
            if marker in content:
                payload = json.loads(content.split(marker, 1)[1])
                self.local.db.save("events", {"topic": str(topic), "message": payload}, datetime.now(),
                                   symbol=str(topic))
                return


def _find_content(body) -> str:
    """The message text, wherever it sits in the response ({"content"}, {"data": {"content"}}, ...)."""
    if isinstance(body, dict):
        if isinstance(body.get("content"), str):
            return body["content"]
        for value in body.values():
            found = _find_content(value)
            if found:
                return found
    return ""
