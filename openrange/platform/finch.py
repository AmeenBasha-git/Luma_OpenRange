"""Finch skill market (finchtech.ai).

Two uses in OpenRange:
  1. PUBLISH: our 12 modules are packaged as skills in skills/<slug>/ (see platform/skills.py).
     Publishing needs the Finch CLI and a wallet login (done by a person, see docs/SPONSOR_SETUP.md).
  2. DISCOVER: search the public Finch market for skills/agents (no login needed), e.g. to show on the
     dashboard which trading skills exist next to ours.

    python -m openrange.platform.finch "trading"
"""

from __future__ import annotations

import sys

import requests

SEARCH_URL = "https://www.finchtech.ai/api/market/search"


def search(query: str, kind: str = "skill", timeout: int = 20) -> list[dict]:
    """Public market search. Returns a list of result dicts (empty on any error)."""
    try:
        r = requests.get(SEARCH_URL, params={"kind": kind, "q": query}, timeout=timeout)
        r.raise_for_status()
    except requests.RequestException:
        return []
    body = r.json()
    if isinstance(body, list):
        return body
    for key in ("results", "items", "data"):
        if isinstance(body.get(key), list):
            return body[key]
    return []


if __name__ == "__main__":
    results = search(sys.argv[1] if len(sys.argv) > 1 else "trading")
    print(f"{len(results)} results")
    for item in results[:10]:
        print("-", item.get("name") or item.get("title") or item)
