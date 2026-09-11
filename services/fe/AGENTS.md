# AGENTS.md — services/fe

Adds to the root contract. Constraints only.

- FE talks only to BE, over relative `/api` paths that `vite.config.ts` proxies. It does not know
  AGENT exists, and must not learn.
- No screen decides a rule. `status`, `actions`, `warn_cut`, `can_start_round` and `mark_reason`
  arrive decided; deriving any of them from dates or scores moves a rule out of BE.
- A countdown is decoration. Reaching zero changes nothing: BE refuses a late answer.
- The types in `api.ts` are a hand-written mirror of BE's response models. TypeScript cannot detect
  drift, so changing either side means changing both in one change set.
- Keep the proxy rather than adding CORS to BE. One origin is why no credentials or preflight logic
  exists anywhere in this project.
- SSE is an accelerant, never a source of truth: reload the stored history after a stream ends.
- `ACTOR` in `api.ts` is the stand-in for sign-in. One constant, one call site to delete.
- Colours come from `tokens.css`, which mirrors the Figma collection. No raw hex in a component.
