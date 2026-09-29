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
- `advance` in `assessment_state.py` is the only function allowed to change `Assessment.state`, and
  every path that writes a question calls `assert_editable` first.
- A class and an assessment each name their owner. Scope every teacher query by `teacher_id`, and
  answer "not yours" exactly as "does not exist" (ADR-22).
- Enqueue with `GRADE_SUBMISSION_TASK` from `contracts`. Never `import agent`.
- BE is the only service the frontend calls. Do not add a second public entry point.
- `main.py` holds one Redis pool for the process lifetime; clients poll once per second, so opening a
  pool per request exhausts connections.
