# Contributing

## Dev setup

```bash
python -m venv .venv && .venv\Scripts\activate
pip install -e ".[dev]"
pytest -q && ruff check .
```

## Project rules

- **Clean architecture**: interfaces → orchestrator → agents → services → infrastructure.
  Dependencies point downward only.
- **Every component is replaceable**: new LLM = one class implementing `LLMProvider`;
  new capability = one class implementing `Agent`, registered in `app.py`.
- Type hints everywhere; comments only where the code can't speak for itself.
- Services stay synchronous and framework-free — async belongs at the edges
  (Telegram/FastAPI), via `asyncio.to_thread`.
- Business logic never imports from `telegram/` or `api/`.

## Adding an agent

1. Create `src/sirius/agents/<name>_agent.py` implementing `Agent`
   (`tools()`, `execute()`, optional `system_hint()`).
2. Register it in `app.py::build_app`.
3. Add tests under `tests/`.

Tool design tips: write prescriptive descriptions ("Use this when the user…"),
use `enum` for fixed choices, and return short JSON strings the model can read.

## Testing

- Pass `FakeEmbeddingFunction` (see `tests/conftest.py`) to anything touching
  ChromaDB so tests stay offline.
- Use the `ScriptedProvider` pattern (`tests/test_orchestrator.py`) instead of
  calling real LLMs.
- CI runs `ruff check .` and `pytest` on every push/PR.

## Commit style

Small, focused commits; imperative subject lines ("Add habit tracking service").
