"""SQLite storage.

Every table has the same simple shape, so any schema object can be saved and read back:

    id | run_id | mode | ts | symbol | payload (JSON of the Pydantic model)

`run_id` + `mode` (fake | backtest | live) keep different runs from mixing.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

import pandas as pd
from pydantic import BaseModel

TABLES = (
    "fundamentals", "macro_snapshots", "regimes", "sentiment", "in_play", "watchlists",
    "signals", "gate_decisions", "risk_decisions", "orders", "fills", "trades",
    "equity_curve", "daily_reports", "lessons", "llm_calls", "events",
)


class Database:
    def __init__(self, path: Path | str, run_id: str, mode: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id
        self.mode = mode
        # WAL + a 60 s wait: several runs (e.g. parallel backtests) can write to the same file safely.
        self.conn = sqlite3.connect(self.path, timeout=60)
        try:
            self.conn.execute("PRAGMA journal_mode=WAL")      # stays set on the file once any run sets it
        except sqlite3.OperationalError:
            pass                                               # another run is writing right now: fine
        self._create_tables()

    def _create_tables(self) -> None:
        for table in TABLES:
            self.conn.execute(
                f"""CREATE TABLE IF NOT EXISTS {table} (
                    id      INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id  TEXT NOT NULL,
                    mode    TEXT NOT NULL,
                    ts      TEXT NOT NULL,
                    symbol  TEXT,
                    payload TEXT NOT NULL
                )"""
            )
        self.conn.commit()

    # ------------------------------------------------------------ write

    def save(self, table: str, item: BaseModel | dict, ts: datetime, symbol: str | None = None) -> None:
        self._check(table)
        payload = item.model_dump_json() if isinstance(item, BaseModel) else json.dumps(item, default=str)
        self.conn.execute(
            f"INSERT INTO {table} (run_id, mode, ts, symbol, payload) VALUES (?, ?, ?, ?, ?)",
            (self.run_id, self.mode, ts.isoformat(), symbol, payload),
        )
        self.conn.commit()

    def save_many(self, table: str, items: Iterable[BaseModel], ts: datetime, symbol_field: str = "") -> None:
        for item in items:
            symbol = getattr(item, symbol_field, None) if symbol_field else None
            self.save(table, item, ts, symbol)

    # ------------------------------------------------------------ read

    def load(self, table: str, run_id: str | None = None) -> list[dict]:
        """Payloads of one table for one run (default: this run), oldest first."""
        self._check(table)
        rows = self.conn.execute(
            f"SELECT payload FROM {table} WHERE run_id = ? ORDER BY id", (run_id or self.run_id,)
        ).fetchall()
        return [json.loads(r[0]) for r in rows]

    def load_latest(self, table: str, mode: str | None = None) -> dict | None:
        """Most recent payload of a table across runs (used to pass lessons to the next day)."""
        self._check(table)
        query = f"SELECT payload FROM {table}"
        args: tuple = ()
        if mode:
            query += " WHERE mode = ?"
            args = (mode,)
        row = self.conn.execute(query + " ORDER BY id DESC LIMIT 1", args).fetchone()
        return json.loads(row[0]) if row else None

    def close(self) -> None:
        self.conn.close()

    @staticmethod
    def _check(table: str) -> None:
        if table not in TABLES:
            raise ValueError(f"Unknown table: {table}")


def read_table(path: Path | str, table: str, run_id: str | None = None) -> pd.DataFrame:
    """For the dashboard: one table as a DataFrame with the JSON payload expanded into columns."""
    with sqlite3.connect(path) as conn:
        query = f"SELECT run_id, mode, ts, payload FROM {table}"
        df = pd.read_sql_query(query + (" WHERE run_id = ?" if run_id else ""), conn,
                               params=(run_id,) if run_id else None)
    if df.empty:
        return df
    expanded = pd.json_normalize(df["payload"].map(json.loads).tolist())
    return pd.concat([df.drop(columns="payload"), expanded], axis=1)


def list_runs(path: Path | str) -> pd.DataFrame:
    with sqlite3.connect(path) as conn:
        return pd.read_sql_query(
            "SELECT run_id, mode, MIN(ts) AS started FROM daily_reports GROUP BY run_id ORDER BY started DESC",
            conn,
        )
