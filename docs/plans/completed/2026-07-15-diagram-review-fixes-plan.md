# Diagram Review Fixes Plan

## Goal

Sửa lại bộ diagram và tài liệu overview để đúng quy ước mô hình nghiệp vụ giai đoạn đầu: Use Case Diagram chỉ có actor nghiệp vụ là `Teacher` và `Student`; `domain-context.drawio` thể hiện system/domain context thay vì các object nội bộ; mọi diagram có chú thích, ít crossing line và không overlay text.

## Scope

Trong phạm vi:

- Sửa `docs/diagrams/use-case.drawio`.
- Sửa `docs/diagrams/domain-context.drawio`.
- Rà soát và chỉnh `activity-overview.drawio`, `business-workflows.drawio` để có khung chú thích và layout rõ hơn.
- Cập nhật `docs/overview/use-case-specification.md`.
- Cập nhật `project-overview.md`, `business-workflows.md`, `doc-structure.md` nếu nội dung cũ gây hiểu nhầm.
- Chuyển plan đã hoàn thành sang `docs/plans/completed/` sau khi validation pass.

Ngoài phạm vi:

- Không thiết kế API, schema, runtime code hoặc kiến trúc triển khai.
- Không thêm actor ngoài `Teacher` và `Student` trong Use Case Diagram.
- Không khôi phục hoặc xử lý các diagram cũ đã bị delete trước đó.

## Files

```text
docs/plans/active/2026-07-15-diagram-review-fixes-plan.md
docs/plans/completed/2026-07-15-diagram-review-fixes-plan.md
docs/plans/completed/2026-07-14-docs-foundation-plan.md
docs/diagrams/use-case.drawio
docs/diagrams/domain-context.drawio
docs/diagrams/activity-overview.drawio
docs/diagrams/business-workflows.drawio
docs/overview/use-case-specification.md
docs/overview/project-overview.md
docs/overview/business-workflows.md
docs/raw-idea/doc-structure.md
```

## Ordered Tasks

1. Create this active plan.
2. Rewrite Use Case Diagram with only `Teacher` and `Student` as actors and only association, `<<include>>`, `<<extend>>`, and generalization relationships.
3. Rewrite `domain-context.drawio` as a true system/domain context diagram with system boundary, central system, Teacher, Student and main interactions only.
4. Add or clean legend boxes and layout in all four `.drawio` diagrams.
5. Update overview Markdown docs to match the corrected diagrams.
6. Validate XML, required text exclusions, legend presence, Markdown placeholders, empty Markdown files and diagram links.
7. If validation passes, move completed plans to `docs/plans/completed/`.

## Completion Criteria

- `use-case.drawio` contains no `AI/LLM Provider`.
- `use-case.drawio` contains no custom relation labels such as `precedes`, `triggers`, `feeds misconceptions`, or `extends when confidence low`.
- Use Case Diagram uses only association, `<<include>>`, `<<extend>>`, and generalization.
- `domain-context.drawio` contains no internal object nodes: `Assessment`, `Question`, `Submission`, `Grading Result`, `Misconception`, `Mastery`, `Teacher Review Queue`.
- Every `.drawio` file has a legend/chú thích box.
- All `.drawio` files parse as XML.
- Markdown has no empty files and no placeholder markers.
- Markdown diagram links still resolve to existing `.drawio` files.

## Status

- [x] Create active plan.
- [x] Rewrite Use Case Diagram.
- [x] Rewrite Domain Context Diagram.
- [x] Clean legends and layout across diagrams.
- [x] Update overview Markdown docs.
- [x] Run validation checks.
- [x] Move completed plans to `docs/plans/completed/`.
