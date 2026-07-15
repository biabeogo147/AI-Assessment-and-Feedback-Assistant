# AGENTS.md

## Purpose

This file is the repository-wide operating contract for human developers and coding agents.

It defines how work is planned, documented, implemented, validated, and completed so the repository stays understandable and does not accumulate duplicate documentation or noisy source code.

These rules apply to the whole repository unless a more specific `AGENTS.md` exists in a subdirectory.

## Core Workflow

Before making any repo-tracked change:

1. Read the user request and inspect the relevant files.
2. Create an active plan in `docs/plans/active/`.
3. Implement the plan step by step.
4. Update the active plan as each meaningful task is completed.
5. Run the relevant validation checks.
6. Move the plan to `docs/plans/completed/` only after validation passes.

If the work is interrupted or validation does not pass, leave the plan in `docs/plans/active/` with accurate checkbox status and a short note describing what remains.

## Planning Requirements

Every implementation plan must include:

- Goal.
- Scope.
- Files expected to be created or modified.
- Ordered tasks with checkbox status.
- Completion criteria.
- Validation checks.
- Current status.

Plans must be created before implementation changes. Reading files, searching the repository, and running non-mutating inspection commands may happen before plan creation when they are needed to understand the task.

Use `docs/plans/completed/` as the canonical completed-plan folder.

## Decision Records Inside Plans

For important design, documentation, code-boundary, testing, or workflow decisions, the plan must record:

- options considered.
- selected option.
- reason for selecting it.

Do not write decision records for purely mechanical edits such as fixing a typo, moving a completed plan, or updating a checkbox.

Recommended format:

```markdown
### Decision: Short Decision Name

options considered:

- Option A: impact or tradeoff.
- Option B: impact or tradeoff.

selected option: Option A.

reason: Explain why this option fits the repository better than the alternatives.
```

## Documentation Rules

Do not create a new Markdown file when an existing file already owns the same topic or boundary. Search the existing docs first.

When changing source code, create or update the matching documentation in the same change set. Prefer updating the existing document that owns the topic instead of adding a parallel document.

Use `docs/` for project and product documentation. Use root `AGENTS.md` for repository workflow and collaboration rules.

Draw.io `.drawio` files are the source of truth for diagrams. Markdown files should link to diagrams and explain their meaning; they should not become separate diagram sources.

Do not create empty Markdown files or files that only contain headings.

## Source Code Rules

Keep changes scoped to the requested behavior and the files that own it.

Follow existing project patterns before introducing new abstractions, libraries, folders, or naming conventions.

Do not perform unrelated refactors, formatting churn, or broad cleanup while implementing a focused request.

When adding or changing source code, keep the corresponding docs, diagrams, and tests aligned with the new behavior.

Preserve user or teammate changes already present in the worktree. Do not revert unrelated changes unless explicitly asked.

## Function Comment Standard

Add a function comment for any new public/exported function, non-trivial function, business-logic function, side-effecting function, async workflow, or complex helper.

Do not add noisy comments for obvious private helpers, simple callbacks, or self-explanatory one-line transformations.

Function comments must cover the relevant parts of this contract:

- Purpose: what the function does and why it exists.
- Inputs: parameters, expected shape, and important constraints.
- Outputs: return value, emitted value, or state change.
- Side effects: file, network, database, UI, process, cache, or external-system changes.
- Errors: expected failures, thrown exceptions, rejected promises, or recoverable error states.

Use the native comment style of the language being edited, such as Python docstrings, TypeScript or JavaScript JSDoc, or Java/Kotlin documentation comments.

Example:

```python
def build_feedback_summary(
    submission_id: str,
    feedback_items: list["FeedbackItem"],
) -> str:
    """
    Build a normalized feedback summary for a submitted answer.

    Args:
        submission_id: Identifier of the submission.
        feedback_items: Scored feedback fragments.

    Returns:
        A summary string suitable for student-facing feedback.

    Raises:
        ValueError: If submission_id is empty or feedback_items is missing.

    Side effects:
        None.
    """
    pass
```

## Validation Before Completion

Before claiming work is complete:

- Run the checks that match the change.
- Verify every changed Markdown file is non-empty.
- Verify new or changed links point to existing files.
- Verify diagrams remain parseable when `.drawio` files are changed.
- Verify required docs were updated when source code changed.
- Record any check that could not be run and explain why.

Only move a plan from `docs/plans/active/` to `docs/plans/completed/` after the completion criteria and validation checks pass.

## What Not To Do

- Do not edit source code without checking whether documentation also needs an update.
- Do not create duplicate docs for a topic already owned by an existing Markdown file.
- Do not leave completed plans in `docs/plans/active/`.
- Do not move incomplete plans to `docs/plans/completed/`.
- Do not add comments that restate obvious code.
- Do not introduce broad architecture, API, schema, deployment, or operations docs before the project phase requires them.
- Do not hide unresolved work; keep the active plan honest.
