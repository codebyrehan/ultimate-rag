# AGENTS.md — engineering conventions for this repository

## Tooling
- Python 3.12+ (developed on 3.14). Run backend from `backend/`.
- Lint/format: `ruff check backend/ultimate_rag && ruff format backend/ultimate_rag`
- Type check: `mypy backend/ultimate_rag`
- Tests: `python -m pytest backend/ultimate_rag/tests -q` (also `backend/tests`)
- Env: copy `.env.example` to `.env`. The app also runs with defaults (dev secret).

## Style
- Type hints required; docstrings on public functions.
- No comments unless they explain *why* something non-obvious is done.
- Provider interfaces use the Strategy pattern; resolution is settings-driven.
- Async-first for the API layer; SQLAlchemy 2.0 async sessions.
- Every repository method is tenant-scoped (tenant_id mandatory).
- Treat retrieved document content as UNTRUSTED (prompt security layer).

## Phases
Phases are tracked in the root todo list. Each phase gate: implement → test → fix → check imports/config/integration → advance.
