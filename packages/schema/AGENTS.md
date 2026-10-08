# AGENTS.md — packages/schema

Adds to the root contract. Constraints only.

- Declarations and DDL only. No threshold, no routing, no business rule, no I/O beyond the three
  schema statements. Two services import this package, so anything with a decision in it becomes a
  decision neither service owns.
- Never import `be`, `ingest`, `agent` or `document`, not even inside a type-checking block.
  `contracts` is the one import allowed, for the vocabulary `models.py` already speaks.
- `prepare_schema` is called in exactly one place in the repository: `be/main.py`. Every other
  process calls `check_schema` and dies on drift. `tools/check_contract.py` enforces it.
- Changing a column is a breaking change for both writers at once. That is the price paid for one
  shared definition instead of two that drift; name both readers in the plan that changes it.
- `docs/overview/data-model.md` explains this schema. When the two disagree, this package wins and
  the document is the thing that is wrong.
