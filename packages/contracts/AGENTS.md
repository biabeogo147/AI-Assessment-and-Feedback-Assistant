# AGENTS.md — packages/contracts

Adds to the root contract. Constraints only.

- Data only. No thresholds, no scoring, no routing, no I/O. Both services import this package, so
  anything with behaviour placed here becomes shared behaviour that neither service owns.
- Never import `be` or `agent`, not even inside a type-checking block.
- Changing or removing a field is a breaking change for both sides at once, since they deploy from
  one repository but read the queue independently.
- `SCHEMA_VERSION` is the default on both messages and nothing validates it today. Adding a field
  with a default needs no bump; changing a field's meaning or removing one does, and the plan must
  say which reader enforces it.
- `GRADE_SUBMISSION_TASK` is the queue task name. It lives here so BE can enqueue by string instead
  of importing AGENT — that constant is the boundary, not a convenience.
- Models are frozen. Treat a message as a record of what was sent, not a mutable object.
