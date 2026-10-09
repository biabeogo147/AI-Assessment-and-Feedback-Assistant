# AGENTS.md — services/agent

Adds to the root contract. Constraints only.

- AGENT decides nothing. It submits content: a draft question, a retry question, a tutoring turn,
  a proposed next step, a plan narration, a conversation title -- never a verdict on any of them.
- Never add a field carrying a verdict to what a handler returns, at any depth; the exact pattern of
  banned names lives in `tests/test_no_routing_decision.py`. `tests/test_no_routing_decision.py` calls every registered task and
  fails the build if one appears; putting a verdict here moves the teacher gate inside the AI service.
- AGENT holds no database credentials. Everything a job needs must arrive in its payload, which is
  why `ExplainTurnRequested` carries the prepared solution rather than a question id.
  `tools/check_contract.py` fails the build if database access appears here.
- Handlers return `dict`, not a pydantic model, because arq serialises the result into Redis.
- Register tasks under the constants from `contracts`, never under a Python function name.
  Renaming a function must not break BE's enqueue call.
- Never `import be`.
- On Windows, arq cannot install signal handlers, so shutdown is not graceful. Do not rely on cleanup
  running after Ctrl+C.
