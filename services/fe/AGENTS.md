# AGENTS.md — services/fe

Adds to the root contract. Constraints only.

- FE talks only to BE, over relative `/api` paths that `vite.config.ts` proxies. It does not know
  AGENT exists, and must not learn.
- FE displays `confidence` but never compares it. Any threshold in `App.tsx` or `api.ts` leaks the
  teacher-in-the-loop gate into the browser; render `needs_teacher_review` as BE returned it.
- The types in `api.ts` are a hand-written mirror of BE's response models and the `contracts` enums.
  TypeScript cannot detect drift, so changing either side means changing both in one change set.
- Keep the proxy rather than adding CORS to BE. One origin is why no credentials or preflight logic
  exists anywhere in this project.
- Grading is asynchronous: submit, then poll. Never assume a result is available on the response to
  the submission itself.
