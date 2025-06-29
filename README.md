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

## Quick-start

```bash
git clone https://github.com/your-org/socrates.git
cd socrates
python -m venv socrates-venv && source socrates-venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY=sk-…
pytest                        # all unit tests should pass
python socrates_main.py       # generate a draft report for “Citigroup”
