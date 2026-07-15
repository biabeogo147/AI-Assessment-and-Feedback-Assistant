# Use Case Color Legend Plan

## Goal

Bổ sung chú thích màu trong `docs/diagrams/use-case.drawio` để người đọc hiểu ý nghĩa của từng nhóm use case, đồng thời rà soát để các use case có cùng mục đích dùng cùng một màu.

## Scope

- Chỉ chỉnh Use Case Diagram và tài liệu mô tả use case liên quan.
- Không thay đổi actor, quan hệ UML, workflow nghiệp vụ hoặc architecture.
- Không tạo thêm diagram mới.

## Files

- `docs/plans/active/2026-07-15-use-case-color-legend-plan.md`
- `docs/diagrams/use-case.drawio`
- `docs/overview/use-case-specification.md`

## Ordered Tasks

- [x] Tạo active plan để team theo dõi thay đổi.
- [x] Rà soát màu hiện tại của các use case theo nhóm mục đích.
- [x] Cập nhật legend trong `use-case.drawio` để giải thích màu và quan hệ.
- [x] Bổ sung quy ước màu vào `use-case-specification.md`.
- [x] Validate XML, quy ước màu, markdown placeholder và diagram links.
- [x] Nếu validation pass, chuyển plan sang `docs/plans/completed/`.

## Completion Criteria

- `use-case.drawio` có legend giải thích màu của từng nhóm use case.
- Các use case cùng mục đích dùng cùng `fillColor` và `strokeColor`.
- `use-case-specification.md` mô tả cùng quy ước màu với diagram.
- Không có markdown rỗng hoặc placeholder marker.
- Tất cả link tới `.drawio` từ markdown resolve được tới file thật.

## Status

Completed.
