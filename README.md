# Socrates ─ Strategy Copilot (⚗ Incubator)

Welcome! **Socrates** is a *research prototype* that chains a fleet of
LLM “agents” to draft a board-quality strategic review for a given
company (e.g. *Citigroup*).  
The current sprint is refactoring the workflow to use **OpenAI
Agents SDK ≥ 0.4** and typed **Pydantic v2** schemas so that:

1. **Every agent returns strict JSON** that validates against a local
   schema (→ fewer downstream parse hacks).
2. **Builders** cache raw JSON and return **typed models**, not `dict`s.  
3. The **main orchestration** passes those models end-to-end instead of
   ad-hoc nested dicts / stringified payloads.
4. Unit-tests lock the contracts so future changes are safe.

---
> The code is **not production-grade**; it is a playground for schema-driven
> agent orchestration, unit-tested JSON validation, and lightning-fast rebuilds
> via aggressive caching.

---

## Current state

| Area                       | Status | Notes |
|----------------------------|--------|-------|
| **Schemas** (`schemas.py`) | ✅     | `FiveForcesResult`, `PestResult`, `TrendRadarResult`, `InitialCruxResult` fully typed & unit-tested. |
| **Agents** (`local_agents`) | ⚠️     | `forces_agent`, `pest_agent`, `trend_radar_agent`, `initial_crux_agent` migrated to `output_type=`; finance/background still raw → see **PR-4**. |
| **Builders** (`pipeline/builders.py`) | ✅     | All above agents wrapped with `_run()` → JSON validated → cached. |
| **Main Orchestration** (`socrates_main.py`) | ⚠️     | End-to-end run works again **except**: <br>• finance & background still return untyped dicts <br>• downstream report composer untouched. |
| **Tests** (`tests/`) | ✅     | Green on `pytest -q` (3 schema suites). |
| **CI / pre-commit** | ❌     | None yet. |



## Quick-start

```bash
git clone https://github.com/your-org/socrates.git
cd socrates
python -m venv socrates-venv && source socrates-venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY=sk-…
pytest                        # all unit tests should pass
python socrates_main.py       # generate a draft report for “Citigroup”
