# Sponsor tools: how OpenRange uses each one, and how to switch it on

Every tool is a switch in `config/settings.yaml` (section `platform:`) plus keys in `.env`.
If a key is missing, OpenRange falls back to the local version and keeps running (check the log for a warning).

| Tool | Role in OpenRange | Code | Switch |
|---|---|---|---|
| **BAND** | The two agents talk through a BAND room: watchlist at 09:35, lessons at 16:15 | `openrange/platform/bus.py` (`BandBus`) | `platform.bus: band` |
| **Lyzr** | The Analyst's LLM calls go through Lyzr agents (guardrails + audit log) | `openrange/platform/lyzr.py` | `platform.analyst_llm: lyzr` |
| **AdaL** | Harness for the Trader's daily review (T6): personality, 12 skills, memory | `openrange/platform/adal.py`, `agents_harness/`, `.adal/skills/`, `AGENTS.md` | `platform.trader_llm: adal` |
| **Finch** | All 12 modules packaged as skills to publish; live market search | `openrange/platform/skills.py`, `openrange/platform/finch.py`, `skills/` | (publish by CLI) |
| **Agent37** | Each agent runs in its own cloud sandbox, 24/7 | `Dockerfile`, `openrange/platform/agent37.py` | `python -m openrange.platform.agent37 deploy` |

---

## 1. BAND (agent-to-agent messages)
1. Sign up at **band.ai** (Free plan is enough).
2. **Agents → Connect remote agent** → create `OpenRange Analyst`. Copy the agent ID and API key (shown once).
3. Do the same for `OpenRange Trader`.
4. Create a **room (chat)**, add both agents (and yourself, to watch in BAND Desktop). Copy the room ID.
5. `config/settings.yaml`:
   ```yaml
   platform:
     bus: band
     band: {room_id: "<room>", analyst_agent_id: "<analyst id>", trader_agent_id: "<trader id>"}
   ```
6. `.env`: `BAND_ANALYST_API_KEY=...` and `BAND_TRADER_API_KEY=...`
7. Run `python scripts/run_fake_day.py` and watch the messages appear in the room.

> Not verified yet (no account): the exact JSON shape returned by `GET .../messages/next`. The code searches the
> reply for the `content` field wherever it is. If the room shows our messages but the Trader doesn't receive them,
> send me the raw reply and I'll adjust `_find_content`.

## 2. Lyzr (LLM gateway with guardrails)
1. Sign up at **studio.lyzr.ai** → **Account → API Keys** → copy the key into `.env` as `LYZR_API_KEY=...`
2. Create two agents in Agent Studio:
   - `openrange-fast`: a cheap model (e.g. a "mini"/"flash" model)
   - `openrange-smart`: a strong model
   - Role for both: *"Financial analyst. Answer only with the JSON requested. Never invent numbers."*
3. Turn on **Responsible AI** (guardrails: PII, toxicity, prompt injection) for both agents.
4. `config/settings.yaml`: `platform.analyst_llm: lyzr` and `platform.lyzr.fast_agent_id / smart_agent_id`.
5. Every Analyst LLM call now shows in Lyzr's logs (Governance → Audit Log).

## 3. AdaL (Trader's review harness)
1. Install: Windows PowerShell `irm https://adal.sylph.ai/install/windows | iex` (Mac/Linux: `curl -fsSL https://adal.sylph.ai/install.sh | bash`).
2. Run `adal` once in this folder and log in in the browser.
3. `config/settings.yaml`: `platform.trader_llm: adal`
4. What AdaL gets:
   - **Personality:** `agents_harness/trader/SYSTEM.md`
   - **Skills:** `.adal/skills/openrange-*/SKILL.md` (regenerate with `python -m openrange.platform.skills`)
   - **Project context:** `AGENTS.md`
   - **Memory:** the same AdaL session is resumed each day (`data/adal_session.txt`), so it remembers past reviews.

## 4. Finch (skills)
- **Already done:** 12 skill packages in `skills/<name>/` (`SKILL.md` + `skill.json`).
- **Search works now:** `python -m openrange.platform.finch trading`
- **To publish** (needs a crypto wallet login, done by a person):
  1. `npm i -g @finchtech/cli`, then `finch login --chain-id <id>` and `finch status`.
  2. In the Finch app: **Create Skill → Bind Token → Validate → Publish**, uploading one `skills/<name>/` folder each.
  > Finch's exact package format isn't public yet. If Validate rejects our folder, send me the error.

## 5. Agent37 (hosting)
1. Sign up at **agent37.com** → **Cloud → API keys** → `.env`: `AGENT37_API_KEY=...` (prepaid credit needed).
2. Build the image as a template (needs Docker + Node): `npx agent37 templates build . --name openrange`
3. Deploy both agents: `python -m openrange.platform.agent37 deploy` → two sandboxes:
   `analyst` runs `--role analyst`, `trader` runs `--role trader`. They talk through BAND (set up step 1 first).
4. Copy your `.env` into each sandbox (Agent37 file upload) so they have the keys.
5. Check / stop: `python -m openrange.platform.agent37 status` / `stop`
> Agent37 puts idle sandboxes to sleep. Turn auto-sleep off for both, or the trading loop will pause.
