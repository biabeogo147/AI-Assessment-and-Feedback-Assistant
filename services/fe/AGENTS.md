# AGENTS.md — services/fe

Adds to the root contract. Constraints only.

- FE talks only to BE, over relative `/api` paths that `vite.config.ts` proxies. It does not know
  AGENT exists, and must not learn.
- No screen decides a rule. `status`, `actions`, `warn_cut`, `can_start_round` and `mark_reason`
  arrive decided; deriving any of them from dates or scores moves a rule out of BE.
- A countdown never decides: at zero the screen asks BE, and only BE's answer moves it.
- The types in `api.ts` are a hand-written mirror of BE's response models. TypeScript cannot detect
  drift, so changing either side means changing both in one change set.
- Keep the proxy rather than adding CORS to BE. One origin is why no credentials or preflight logic
  exists anywhere in this project.
- SSE is an accelerant, never a source of truth: reload the stored history after a stream ends.
- Identity is the session cookie BE sets at sign-in. No request carries `X-Actor`, and no screen keeps who-is-signed-in in storage or the URL.
- Colours come from `tokens.css`, which mirrors the Figma collection. No raw hex in a component.
- Teacher class names must not collide with any top-level class in `tokens.css`. A second rule of
  the same name adds to the first, it does not replace it.
- The design file is the other half of a screen. Changing a screen changes its artboard on `Screen —
  Student` or `Screen — Teacher` of Figma `mOe2ZmrqOq1Uix45v6PNGD` in the same change set, named in the
  commit. What the artboards MEAN is written in `docs/overview/teacher-surface.md`, never re-derived.
- Prove the two agree by a ruler, not a glance: position, size, padding, gap, radius, fill and font of
  the Figma node against the computed style of the same element in a running browser.
- Every FE change, refactors included, ends in the browser: screenshot each state it can reach and have
  one subagent grade the shots against the artboards. Vitest reads the DOM; it never sees the screen.
