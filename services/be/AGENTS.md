# AGENTS.md — services/be

Adds to the root contract. Constraints only.

- BE owns every business decision. If code decides something rather than reporting it, it belongs
  here and nowhere else.
- BE owns every database. AGENT receives no credentials, so anything AGENT needs travels in the job
  payload.
- The Teacher Review threshold and routing live in `review_policy.py`. `decide_review` is the only
  function allowed to produce `needs_teacher_review` or a `ReviewReason`.
- Apply the review policy when reading a result, not when storing one, so changing
  `REVIEW_CONFIDENCE_THRESHOLD` takes effect without regrading.
- Enqueue with `GRADE_SUBMISSION_TASK` from `contracts`. Never `import agent`.
- BE is the only service the frontend calls. Do not add a second public entry point.
- `main.py` holds one Redis pool for the process lifetime; clients poll once per second, so opening a
  pool per request exhausts connections.
