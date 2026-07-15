# Cấu trúc tài liệu giai đoạn đầu

## Mục đích

Tài liệu này mô tả cách tổ chức folder `docs` cho giai đoạn đầu của project **AI Assessment and Feedback Assistant**.

Mục tiêu hiện tại là xây dựng một bộ tài liệu đủ để tech và non-tech hiểu chung về:

- Project đang giải quyết vấn đề gì.
- Actor chính là ai.
- Workflow nghiệp vụ tổng quan diễn ra như thế nào.
- Những use case chính cần hỗ trợ.
- Diagram nào là source of truth cho từng góc nhìn.

Giai đoạn này **chưa** đi sâu vào kiến trúc hệ thống, AI agent internals, API, database schema, deployment hoặc vận hành.

## Nguyên tắc tổ chức

- Chỉ tạo file khi có nội dung thật để viết.
- Không tạo file Markdown rỗng hoặc chỉ có heading.
- Giữ số lượng file ít để team dễ đọc và dễ maintain.
- Markdown dùng để giải thích, mô tả specification và dẫn đường.
- Draw.io `.drawio` là source of truth cho diagram.
- `raw-idea.md` và `raw-idea.png` là input lịch sử, không phải source of truth lâu dài.
- [`AGENTS.md`](../../AGENTS.md) ở root là tài liệu quy định workflow cộng tác giữa dev và coding agent; `docs/` chỉ giữ tài liệu project/product.

## Cấu trúc đề xuất

```text
docs/
  plans/
    active/
      2026-07-14-docs-foundation-plan.md
    completed/

  raw-idea/
    raw-idea.md
    raw-idea.png
    doc-structure.md

  overview/
    project-overview.md
    business-workflows.md
    use-case-specification.md

  diagrams/
    use-case.drawio
    activity-overview.drawio
    business-workflows.drawio
    domain-context.drawio
```

## File Markdown

| File | Giai đoạn tạo | Mục đích |
| --- | --- | --- |
| `docs/plans/active/YYYY-MM-DD-docs-foundation-plan.md` | Trước khi thực hiện plan | Theo dõi mục tiêu, phạm vi, thứ tự thực hiện, tiêu chí hoàn thành và trạng thái của plan đang active. |
| `docs/raw-idea/doc-structure.md` | Phase 0 | Mô tả cấu trúc tài liệu, mục đích từng file, giai đoạn tạo và quy ước diagram. |
| `docs/overview/project-overview.md` | Phase 1 | Tóm tắt project ở mức bức tranh toàn cảnh: vấn đề, mục tiêu, actor, phạm vi đầu tiên và những phần chưa làm. |
| `docs/overview/business-workflows.md` | Phase 1 | Mô tả workflow nghiệp vụ tổng quan từ tạo đề, làm bài, chấm bài, teacher review đến luyện tập thích ứng. |
| `docs/overview/use-case-specification.md` | Phase 1 | Mô tả Use Case Specification cho các use case chính ở mức nghiệp vụ, chưa đi vào API hay thiết kế hệ thống. |

## Diagram Draw.io

| Diagram | Giai đoạn tạo | Mục đích | Có bắt buộc không? |
| --- | --- | --- | --- |
| `docs/diagrams/use-case.drawio` | Phase 1 | Thể hiện actors và các use case chính của hệ thống. | Bắt buộc |
| `docs/diagrams/activity-overview.drawio` | Phase 1 | Thể hiện activity flow end-to-end từ giáo viên tạo đề đến học sinh luyện tập thích ứng. | Bắt buộc |
| `docs/diagrams/business-workflows.drawio` | Phase 1 | Thể hiện workflow theo swimlane giữa Teacher, Student và System/AI. | Nên có |
| `docs/diagrams/domain-context.drawio` | Phase 1 | Thể hiện system/domain boundary, hệ thống trung tâm, Teacher, Student và các nhóm tương tác chính. | Nên có |

## Vì sao chưa dùng các diagram khác?

### Sequence Diagram

Chưa dùng trong Phase 1 vì sequence diagram phù hợp hơn khi đã biết rõ các service, component hoặc API message. Hiện tại project đang ở giai đoạn thống nhất nghiệp vụ, nên Activity Diagram và swimlane workflow dễ hiểu hơn cho cả tech và non-tech.

### Class Diagram

Chưa dùng trong Phase 1 vì class diagram dễ khiến team hiểu nhầm rằng data model hoặc code model đã được chốt. `domain-context.drawio` chỉ mô tả boundary, hệ thống trung tâm và tương tác với Teacher/Student; nó không mô tả object nội bộ hay schema.

### System Architecture Diagram

Chưa dùng trong Phase 1 vì plan hiện tại chưa thiết kế system components, deployment boundary hoặc infrastructure. Khi bắt đầu giai đoạn technical design, có thể bổ sung architecture diagram sau.

## Phase đề xuất

### Phase 0 — Documentation Planning

Mục tiêu: thống nhất cấu trúc docs và active plan.

Tạo:

- `docs/plans/active/YYYY-MM-DD-docs-foundation-plan.md`
- `docs/raw-idea/doc-structure.md`

### Phase 1 — Business Overview

Mục tiêu: tạo bức tranh nghiệp vụ tổng quan để team cùng hiểu.

Tạo:

- `docs/overview/project-overview.md`
- `docs/overview/business-workflows.md`
- `docs/overview/use-case-specification.md`
- `docs/diagrams/use-case.drawio`
- `docs/diagrams/activity-overview.drawio`
- `docs/diagrams/business-workflows.drawio`
- `docs/diagrams/domain-context.drawio`

### Phase 2 — Technical Foundation

Chỉ bắt đầu sau khi Phase 1 đủ rõ.

Có thể tạo sau:

- Architecture overview.
- Data model hoặc schema.
- API contract.
- AI agent workflow chi tiết.
- Evaluation strategy.

Những file này chưa tạo trong Phase 1 để tránh tài liệu rỗng hoặc quyết định kỹ thuật quá sớm.

## Quy ước liên kết

- Mỗi file overview phải link tới diagram liên quan.
- Mỗi diagram `.drawio` phải được nhắc tới trong ít nhất một file Markdown.
- Khi diagram thay đổi, phần mô tả trong Markdown tương ứng phải được cập nhật cùng lúc.

## Tiêu chí hoàn thành Phase 1

Phase 1 được xem là đủ khi:

- Một người non-tech đọc `project-overview.md` hiểu project làm gì và phục vụ ai.
- Một thành viên product hoặc BA đọc `business-workflows.md` hiểu các workflow chính.
- Một engineer đọc `use-case-specification.md` hiểu các use case đầu tiên cần hỗ trợ.
- Draw.io có đủ Use Case Diagram, Activity Diagram, swimlane workflow và system/domain context.
- Không có file Markdown rỗng hoặc diagram không được tài liệu nào nhắc tới.
