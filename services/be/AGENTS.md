# AGENTS.md — services/be

Adds to the root contract. Constraints only.

- BE owns every business decision. If code decides something rather than reporting it, it belongs
  here and nowhere else.
- BE owns the databases it reads, and the API is the only process it has. Writing down what
  DOCUMENT reports belongs to `services/ingest`: it holds a credential and decides nothing.
- Document bytes live in MinIO, not in a column. `documents.storage_key` is the key, and the bytes
  are written before the row so a failure leaves collectable garbage, never a row pointing at
  nothing.
- `storage.py` is the only module allowed to import `minio`. The SDK is synchronous; every call goes
  through `run_in_threadpool` there, and one forgotten wrapper blocks the event loop silently.
- BE grades. `student_routes.py` compares the chosen option against the approved question's own
  correct one and `scoring.py` turns that into a mark, both inside the submit request -- never over
  a queue and never by a model.
- Only `advance` and `withdraw` (`assessment_state.py`) change `Assessment.state`; every path
  that writes a question first checks `assert_editable` (HTTP refusal) or `editable()` (quiet skip).
- A class and an assessment each name their owner. Scope every teacher query by `teacher_id`, and
  answer "not yours" exactly as "does not exist" (ADR-22).
- A turn locks its conversation: `_hold_the_thread` before any write, released in `finally`.
- Enqueue by the task-name constants from `contracts`. Never `import agent`.
- BE is the only service the frontend calls. Do not add a second public entry point.
- `main.py` holds one Redis pool for the process lifetime; every request that enqueues a job or
  listens on a channel borrows it, so opening a pool per request exhausts connections.
