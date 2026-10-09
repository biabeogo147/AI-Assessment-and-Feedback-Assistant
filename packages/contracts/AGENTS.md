# AGENTS.md — packages/contracts

Adds to the root contract. Constraints only.

- Data only. No thresholds, no scoring, no routing, no I/O. Every service imports this package, so
  anything with behaviour placed here becomes shared behaviour that neither service owns.
- Never import `be` or `agent`, not even inside a type-checking block.
- Changing or removing a field is a breaking change for every reader at once, since they deploy
  from one repository but read the queue independently.
- Each message family declares its own `SCHEMA_VERSION`, and nothing validates it today. Adding a
  field with a default needs no bump; changing a field's meaning or removing one does, and the plan
  must say which reader enforces it.
- Task names and `documents_channel` live here so neither side has to import the other. Whichever
  string crosses that gap, that constant is the boundary, not a convenience.
- Models are frozen. Treat a message as a record of what was sent, not a mutable object.
