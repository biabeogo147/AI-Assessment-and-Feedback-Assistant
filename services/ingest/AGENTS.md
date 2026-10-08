# AGENTS.md — services/ingest

Adds to the root contract. Constraints only.

- Writes down what another service reported. It owns no decision: no threshold, no routing, no
  model call, no Vietnamese sentence of its own. If code here decides something rather than
  recording it, it belongs in `services/be`.
- It holds a database credential, and that is deliberate. What makes AGENT and DOCUMENT
  report-only services is that they write no row, not that they run their own process.
- `UPDATE` only, never `INSERT`. The row exists from the moment of upload; a job that creates one
  is a second way for a document to appear in a teacher's library.
- Never `prepare_schema`. The API process owns building the schema; this one calls `check_schema`
  at startup and dies on drift. `tools/check_contract.py` enforces it.
- A job must not fail for anything already written. Publish errors are logged, never raised: arq
  retries a failed job, and that retry would overwrite what is already correct.
- Never `import be`, and never reach for a business rule by copying one. `lint-imports` enforces
  the first; only review catches the second.
- Config has four fields. Adding a fifth needs a reason in the plan — this file's shortness is
  the measurement that the boundary is real.
