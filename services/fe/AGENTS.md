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
- Teacher class names must not collide with any top-level class in `tokens.css`. A second rule of
  the same name adds to the first, it does not replace it.
- The design file is the other half of a screen, not a sketch that came before it. Adding or changing
  a screen means changing its artboard on page `Screen — Student` or `Screen — Teacher` of Figma
  `mOe2ZmrqOq1Uix45v6PNGD` in the same change set, and saying in the commit which artboards moved.
- Then prove the two agree, by measurement rather than by eye: read position, size, padding, gap,
  radius, fill and font from the Figma node, read the computed style of the same element in a
  running browser, and compare the numbers. Every style defect this project has shipped was
  invisible to a glance and obvious to a measurement.
