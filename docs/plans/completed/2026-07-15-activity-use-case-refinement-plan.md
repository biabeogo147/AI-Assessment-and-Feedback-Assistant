# Activity And Use Case Diagram Refinement Plan

## Goal

Refine `activity-overview.drawio` and `use-case.drawio` after visual/structural review:

- Activity Diagram must generate adaptive practice only when the student has not reached mastery.
- Use Case Diagram must visibly render UML `<<include>>` and `<<extend>>` labels and use only relationships that match the business meaning.

## Scope

In scope:

- Render preview images for the current diagrams using `D:\Anaconda\envs\AI-Assessment-and-Feedback-Assistant\python.exe`.
- Install the smallest needed render dependency if the env is missing it.
- Edit `docs/diagrams/activity-overview.drawio`.
- Edit `docs/diagrams/use-case.drawio`.
- Update `docs/overview/use-case-specification.md`.
- Update `docs/overview/business-workflows.md` if its adaptive-practice wording conflicts with the corrected flow.
- Move this plan to `docs/plans/completed/` only after validation passes.

Out of scope:

- No runtime code, API, schema, database or architecture changes.
- No new committed preview images.
- No changes to old deleted diagram files unless requested separately.

## Files

```text
docs/plans/active/2026-07-15-activity-use-case-refinement-plan.md
docs/plans/completed/2026-07-15-activity-use-case-refinement-plan.md
docs/diagrams/activity-overview.drawio
docs/diagrams/use-case.drawio
docs/overview/use-case-specification.md
docs/overview/business-workflows.md
```

Temporary preview artifacts may be written under the Codex visualization workspace, not under `docs`.

## Ordered Tasks

1. Create this active plan.
2. Verify or install preview render support in the specified conda env.
3. Render before-edit previews for use-case and activity diagrams.
4. Fix Activity Diagram flow so adaptive practice is generated only from the `Chưa đạt mastery` branch.
5. Fix Use Case Diagram labels and relationship choices.
6. Update Markdown explanations for activity/mastery and use-case relationships.
7. Render after-edit previews.
8. Run validation checks.
9. Move this plan to `docs/plans/completed/` when validation passes.

## Completion Criteria

- Activity flow is `feedback -> update/check mastery -> mastery?`.
- `Đạt mastery` leads to the end state.
- `Chưa đạt mastery` leads to adaptive-practice generation, then back to student answering.
- Use Case Diagram has visible `<<include>>` and `<<extend>>` labels in rendered preview.
- Use Case Diagram has no custom relation labels.
- Use Case Specification explains why each include/extend relation is used.
- All `.drawio` files parse as XML.
- Markdown files are non-empty, have no placeholder markers and all diagram links resolve.

## Status

- [x] Create active plan.
- [x] Verify or install preview render support.
- [x] Render before-edit previews.
- [x] Fix Activity Diagram flow.
- [x] Fix Use Case Diagram labels and relationships.
- [x] Update Markdown explanations.
- [x] Render after-edit previews.
- [x] Run validation checks.
- [x] Move completed plan to `docs/plans/completed/`.
