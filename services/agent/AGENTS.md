# AGENTS.md — services/agent

Adds to the root contract. Constraints only.

- AGENT decides nothing. It reports evidence: a score, a confidence, a misconception code, and flags
  for whether the answer contradicts the reasoning and whether there was enough to judge by.
- Never add `needs_teacher_review` or `ReviewReason` to what a handler returns. That decision belongs
  to `be/review_policy.py`; putting it here moves the teacher-in-the-loop gate inside the AI service.
- AGENT holds no database credentials. Everything needed to grade must arrive in the job payload,
  which is why `GradingRequested` carries the explanation and the learning objective rather than ids.
  `tools/check_contract.py` fails the build if database access appears here.
- Handlers return `dict`, not a pydantic model, because arq serialises the result into Redis.
- Register tasks under `GRADE_SUBMISSION_TASK` from `contracts`, never under a Python function name.
  Renaming a function must not break BE's enqueue call.
- Never `import be`.
- On Windows, arq cannot install signal handlers, so shutdown is not graceful. Do not rely on cleanup
  running after Ctrl+C.
