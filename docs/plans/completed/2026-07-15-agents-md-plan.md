# AGENTS.md Governance Plan

## Goal

Create a root-level `AGENTS.md` that defines the shared operating contract for human developers and coding agents working in this repository.

## Scope

- Create one root governance file: `AGENTS.md`.
- Update the existing docs structure guide only to clarify the boundary between `AGENTS.md` and project/product documentation.
- Do not change source code.
- Do not create additional docs files.

## Files

- `AGENTS.md`
- `docs/raw-idea/doc-structure.md`
- `docs/plans/active/2026-07-15-agents-md-plan.md`
- `docs/plans/completed/2026-07-15-agents-md-plan.md`

## Decision Records

### Decision: Governance File Location

options considered:

- Put the governance rules in root `AGENTS.md`.
- Put the governance rules under `docs/`.

selected option: root `AGENTS.md`.

reason: Coding agents and dev tooling conventionally discover repository instructions from the root, while `docs/` should remain focused on project/product documentation.

### Decision: Function Comment Requirement

options considered:

- Require comments for every new function.
- Require comments for public/exported or non-trivial functions.
- Leave comments fully contextual.

selected option: require comments for public/exported or non-trivial functions.

reason: This keeps important behavior explicit without creating noisy comments for obvious private helpers.

### Decision: Decision Notes Granularity

options considered:

- Record options for every small step.
- Record options for important design, documentation, code-boundary, or test decisions.
- Record options only when a reviewer asks.

selected option: record options for important decisions.

reason: This keeps plans auditable without making them too noisy to follow.

## Ordered Tasks

- [x] Create this active plan before other repo-tracked changes.
- [x] Draft root `AGENTS.md` with the required governance sections.
- [x] Update `docs/raw-idea/doc-structure.md` only to clarify governance versus project docs.
- [x] Update this active plan as tasks complete.
- [x] Validate markdown files, required terms, active/completed plan state, and placeholder markers.
- [x] Move this plan to `docs/plans/completed/` after validation passes.

## Completion Criteria

- `AGENTS.md` exists at repo root and is non-empty.
- `AGENTS.md` contains the required workflow, documentation, source code, function comment, decision record, and validation rules.
- `docs/raw-idea/doc-structure.md` references root `AGENTS.md` without creating a duplicate governance document.
- Markdown files are non-empty and contain no placeholder markers.
- The completed plan is moved to `docs/plans/completed/`.

## Status

Completed.
