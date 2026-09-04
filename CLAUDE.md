# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository state

This repository currently contains **no source code** — it is a documentation-only repo for the
"AI Assessment and Feedback Assistant" project, still in Phase 1 (business overview). There is no
build, lint, or test tooling, and no package manifest. Do not add one unless the task explicitly
starts Phase 2.

Validation for a change here means: changed Markdown files are non-empty, links resolve to existing
files, and changed `.drawio` files still parse.

## Operating contract

`AGENTS.md` at the repo root is the authoritative workflow contract and applies in full. Read it
before making any repo-tracked change. Key points that are easy to miss:

- Every repo-tracked change needs a plan in `docs/plans/active/` **before** implementation, named
  `YYYY-MM-DD-<slug>-plan.md`, with goal, scope, expected files, checkboxed ordered tasks,
  completion criteria, validation checks, and status.
- Move the plan to `docs/plans/completed/` only after validation passes; leave it in `active/` with
  honest checkbox status otherwise.
- Non-mechanical design/documentation/testing decisions get a Decision Record inside the plan
  (options considered → selected option → reason).
- New public, non-trivial, business-logic, side-effecting, or async functions need a function
  comment covering purpose, inputs, outputs, side effects, and errors — in the language's native
  doc-comment style.

## Documentation layout and ownership

Each topic has exactly one owning file; update the owner rather than adding a parallel doc.

- `docs/raw-idea/` — historical input (`raw-idea.md`, `raw-idea.png`) plus `doc-structure.md`, which
  owns the docs-organization plan and the Phase 0/1/2 roadmap. Check it before creating any new doc
  or diagram: it lists which files each phase is allowed to create and why others are deferred.
- `docs/overview/` — `project-overview.md` (problem, actors, scope), `business-workflows.md`,
  `use-case-specification.md`.
- `docs/diagrams/` — `.drawio` files are the **source of truth** for diagrams. Markdown links to and
  explains them; it never becomes a second diagram source. Every diagram must be referenced by at
  least one Markdown file, and diagram edits require updating the prose that describes them in the
  same change set.

Project documentation is written in **Vietnamese** with English technical/domain terms
(`Assessment`, `Distractor`, `Confidence`, `Teacher Review Queue`, `Mastery`). Match that style when
editing `docs/`. `AGENTS.md` and this file are in English.

## Domain model

The product is a closed learning loop: teacher authors and approves an assessment → student submits →
AI grades the answer and the student's explanation → AI identifies the misconception → AI generates
adaptive practice → loop ends at mastery.

Two teacher-in-the-loop gates are mandatory and must be preserved in any design: teacher approval
before an assessment is released, and teacher handling of low-confidence grading results via the
Teacher Review Queue. The system is not an actor in the use-case diagram — its intelligent behaviors
sit inside the system boundary.

Explicitly out of scope until Phase 2: architecture, service/module structure, API contracts,
database schema, prompt chains / model routing, confidence and mastery formulas, deployment and ops.
Do not introduce docs or code for these ahead of the phase.
