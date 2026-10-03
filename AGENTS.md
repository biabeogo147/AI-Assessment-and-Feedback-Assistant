# AGENTS.md

## Purpose

Repository-wide operating contract. It holds the rules; `README.md` holds how to run the project and
`docs/overview/architecture.md` holds why the system is shaped this way. Read this before changing
anything tracked by git. A subdirectory `AGENTS.md` adds to this file and never contradicts it.

## Repository Layout And Ownership

Each topic has exactly one owning file. Update the owner instead of adding a parallel document.

| Path | Owns |
| --- | --- |
| `services/be` | Enforces business rules at runtime, all databases, the only service FE calls |
| `services/agent` | AI grading. Emits evidence, decides nothing |
| `services/fe` | User interface. Talks only to BE |
| `packages/contracts` | Messages crossing the queue. Data only |
| `tools/` | Repo-level checks no single service can make about itself |
| `docs/local-development.md` | Running, demoing and troubleshooting locally |
| `docs/overview/project-overview.md` | Problem, actors, scope, glossary |
| `docs/overview/business-workflows.md` | The five business workflows |
| `docs/overview/use-case-specification.md` | UC-01 to UC-06 |
| `docs/overview/architecture.md` | Services, communication, boundaries, service naming |
| `docs/overview/data-model.md` | The database schema and why it is shaped that way |
| `docs/diagrams/*.drawio` | Every diagram, as source of truth |
| `docs/decisions/` | Records business rules. They outlive every plan |
| `docs/plans/` | Plans, their technical decision records, and `backlog.md` for deferred work |
| `docs/raw-idea/` | Historical input only. Never cite as current truth |

Reserved: `docs/overview/grading-design.md` for prompts, model choice, evaluation. Not written yet.

## Invariants That Must Not Break

This is an enforcement index, not an explanation. The reasoning lives in `architecture.md`.

| Invariant | Caught by |
| --- | --- |
| BE and AGENT never import each other | automatic: `lint-imports`, also a pre-commit hook |
| `contracts` never imports a service | automatic: `lint-imports` |
| AGENT emits no routing decision | automatic: `test_agent_emits_no_routing_decision` |
| Low confidence is flagged for Teacher review | automatic: `test_low_confidence_routes_to_teacher` |
| A correct answer does not exempt a submission from review | automatic: `test_correct_answer_does_not_exempt_a_submission_from_review` |
| `ReviewReason` covers all four Workflow 4 conditions | automatic: `test_review_reason_covers_all_four_workflow_4_conditions` |
| AGENT holds no database credentials | automatic: `tools/check_contract.py` |
| Every `.env.example` variable is read by a service | automatic: `tools/check_contract.py` |
| A whole AGENT job times out before the job waiting on it does | automatic: `tools/check_contract.py` |
| Teacher approves an assessment before release | automatic: `test_an_unapproved_assessment_cannot_be_published_over_http` |
| The options in a clarifying question are written by BE from rows it read | automatic: `test_the_options_are_written_by_be_not_by_the_model` |
| No agent tool changes an assessment's state | automatic: `tools/check_contract.py` |
| Invented screen data stays in its one self-accusing module | automatic: `tools/check_contract.py` |
| An empty assessment is never approved | automatic: `test_an_empty_assessment_cannot_be_approved` |
| A deleted conversation reads as absent, takes no new turn, and keeps the turns it holds | automatic: `test_a_deleted_conversation_is_not_the_running_one`, `test_a_deleted_conversation_keeps_its_turns` |
| Only a question back carries buttons | automatic: `test_a_plain_answer_carries_no_buttons_even_with_candidates_in_hand` |
| `contracts` holds no business logic | review: read the diff of `packages/contracts` |
| FE never applies its own confidence threshold | review: `confidence` may be displayed, never compared |
| No package named `common`, `utils` or `shared` | review: look at `packages/` |
| A low-confidence result is not shown to the Student before a Teacher handles it | not yet enforced; needs a test when UC-05 is built |
| A retry question is a variant of the same question, not merely the same objective | not yet enforced; needs a test when UC-06 is built (ADR-17) |

Never let the unenforced group grow past three rows. When you implement one of those use cases, the
plan for it must convert its row to an automatic check.

## Core Workflow

1. Read the request and inspect the relevant files.
2. Create a plan in `docs/plans/active/` unless the change is exempt.
3. Implement it, updating the plan as tasks complete.
4. Run the validation checks that match the change.
5. Move the plan to `docs/plans/completed/` only after validation passes.

If interrupted or validation fails, leave the plan in `active/` with honest checkboxes and a note.

## Planning Requirements

**A plan is required** when the change touches any of these: more than one directory under
`services/` or `packages/`; any field or enum in `packages/contracts`; a new dependency, a new
`.env.example` variable, or new infrastructure; `AGENTS.md`, `CLAUDE.md`, `dev.ps1`, or the
`import-linter` and pre-commit configuration; an endpoint or a queue task name; behaviour in
`be/review_policy.py` or any business threshold. A change that produces a decision record always
needs a plan.

**Exempt**, with a clear commit message instead: typo and wording fixes in docs; ticking plan
checkboxes; moving a plan to `completed/`; `ruff format` and autofix output; adding tests for
behaviour that already exists; a bug fix contained in one file that changes no contract or endpoint.

One plan may span several commits. Each commit belonging to a plan carries a trailer
`Plan: <plan-filename>.md` — the bare filename, not a path, because the plan moves from `active/` to
`completed/` and a path would rot. This is what makes the rule greppable rather than a promise.

Name plans `docs/plans/active/YYYY-MM-DD-<english-kebab-slug>-plan.md`. Every plan has `Goal`,
`Files`, `Ordered Tasks` as checkboxes, `Validation Checks` and `Status`. Add `Scope` and
`Completion Criteria` when the work is large enough to need them. A minimal plan is five sections and
about twenty lines; the ceremony scales with the change, the plan file never disappears.

### Decision Records

Two kinds, two homes. A **technical or process** decision stays in its plan under
`## Decision Records`, as `### Decision: Name` with lowercase `options considered:`,
`selected option:` and `reason:`. A **business** decision — how the product behaves, who may do
what, what cannot be undone — goes to `docs/decisions/adr-NN-topic.md`, because it outlives the
change that produced it while a plan ends up in `completed/`, which nobody may edit. Follow
`adr-00-template.md` and fill its last section: a rule with no named place of enforcement is an
idea, not a decision. "The user decided it" is not a reason — it says who chose, not why. Skip
records for mechanical edits: a typo, a moved plan, a ticked checkbox.

## Documentation Rules

Search before creating: never add a Markdown file when an existing one already owns the topic.
Changing source code means updating the document that owns the affected topic in the same change set.
Never create empty files, files containing only headings, or architecture, API, schema and operations
documents before there is real content for them.

`.drawio` files are the source of truth for diagrams; Markdown links to them and explains them, and
never becomes a second diagram source. Every overview document links the diagrams it discusses, every
`.drawio` is referenced by at least one Markdown file, and changing a diagram means changing the
prose that describes it in the same change set.

Documentation under `docs/`, plus every comment and docstring, is Vietnamese with English technical
and domain terms (`Assessment`, `Distractor`, `Confidence`, `Teacher Review Queue`). Identifiers,
logs and check-matched strings stay English, as does every `AGENTS.md`, `CLAUDE.md` and `README.md`.

## Source Code Rules

Keep changes scoped to the requested behaviour and the files that own it. Follow existing patterns
before introducing new abstractions, libraries, folders or naming conventions. Do not perform
unrelated refactors or formatting churn during a focused request, and preserve changes already in the
worktree. Every service keeps its own `pyproject.toml` declaring its own dependencies even while
services share an environment; naming rules for a new service live in `architecture.md`.

## Function Comment Standard

Add a function comment for any new public, non-trivial, business-logic, side-effecting or async
function, and for complex helpers; skip it for obvious private helpers and one-line transformations.
Cover the relevant parts of purpose, inputs and their constraints, outputs, side effects and errors,
in the language's native style — Python docstrings, JSDoc for TypeScript. `decide_review` in
`services/be/src/be/review_policy.py` is the reference example.

## Validation Before Completion

| Change | Run |
| --- | --- |
| Any Python file | `.\dev.ps1 test` and `.\dev.ps1 check` |
| Any frontend file | `.\dev.ps1 test` and `.\dev.ps1 typecheck` |
| `packages/contracts` | Both of the above; it affects BE and AGENT alike |
| `import-linter`, pre-commit, or a build backend | The boundary probe below, in addition |
| A `.drawio` file | Confirm it still parses as XML |
| A Markdown file | Confirm it is non-empty and its internal links resolve |

Record any check you could not run, and why. Never claim work is complete on an unrun check.

**The boundary probe.** Add `import be` to `services/agent/src/agent/worker.py`, run `.\dev.ps1 check`,
confirm it fails, then revert. Do this whenever the import-linter configuration, the pre-commit hooks
or a build backend changes. The boundary has two known ways of dying silently: `python -m
importlinter.cli` exits 0 without checking anything, and a PEP 660 editable install using a
MetaPathFinder can leave `grimp` reporting zero violations. A check that cannot fail is not a check.

## Amending This Contract

Changing this file always needs a plan and a decision record; it is never exempt. Changing a rule
here means sweeping the four child `AGENTS.md` files and `CLAUDE.md` in the same change set, because
a contradiction between them is worse than either version alone.

Child files carry constraints only, never current state: "this module is currently a placeholder" is
false within a week and turns a rules document into a liar. Each line must name a file, symbol or
constraint existing only in that directory. `tools/check_contract.py` enforces the length caps that
keep this honest.

## Repo-Specific Traps

- Do not create `docs/adr/`; business decisions live in `docs/decisions/`, technical ones in a plan.
- Do not name a package `common`, `utils` or `shared`. A meaningless name absorbs everything.
- Do not edit plans in `docs/plans/completed/`. They are closed records.
- Do not invoke `python -m importlinter.cli`. Use the `lint-imports` console script.
- A `.ps1` needs a UTF-8 BOM; without one PowerShell 5.1 reads cp1252 and `Get-Help` garbles.
- Do not use backslashes in a pre-commit `entry`; it splits with shlex and eats them.
- Do not point `REDIS_URL` at `localhost`; it resolves to `::1` first here and the connection hangs.
- Do not hide unresolved work. Keep the active plan honest.
