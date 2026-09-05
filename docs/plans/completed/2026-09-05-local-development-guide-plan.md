# Local Development Guide Plan

## Goal

Cho người mới một tài liệu chạy được từ đầu đến cuối: dựng môi trường, chạy ba service, demo đủ các nhánh kết quả chấm tái hiện được, và tự chẩn đoán khi hỏng.

## Files

```text
docs/plans/active/2026-09-05-local-development-guide-plan.md
docs/plans/completed/2026-09-05-local-development-guide-plan.md
docs/local-development.md
README.md
AGENTS.md
CLAUDE.md
dev.ps1
```

## Decision Records

### Decision: A New File Owns Running Locally, README Keeps Only The Quickstart

options considered:

- Mở rộng `README.md`, vì nó đang sở hữu chủ đề "cách chạy project".
- Tạo `docs/local-development.md` sở hữu chủ đề rộng hơn, `README.md` rút còn quickstart và trỏ sang.
- Tạo `docs/getting-started.md` song song với `README.md`.

selected option: Tạo `docs/local-development.md` và rút gọn `README.md`.

reason: Nội dung cần thêm gồm kịch bản demo bốn nhánh, cách xác minh từng service, và mục chẩn đoán sự cố. Nhồi hết vào `README.md` biến trang đầu repo thành một tài liệu dài mà phần lớn người đọc không cần ngay. Phương án thứ ba bị loại vì hai file cùng sở hữu một chủ đề chính là thứ Documentation Rules cấm; ở đây quyền sở hữu được chuyển hẳn chứ không nhân đôi, và bảng ownership trong `AGENTS.md` được cập nhật cùng change set.

### Decision: Fix dev.ps1 Rather Than Document Around It

options considered:

- Ghi vào mục chẩn đoán sự cố rằng `infra-up` báo lỗi giả, người dùng cứ bỏ qua.
- Sửa `Invoke-Step` để phán đoán thành công theo exit code thay vì theo stderr.

selected option: Sửa `Invoke-Step`.

reason: Lỗi này lộ ra ngay khi chạy thử `.\dev.ps1 infra-up` để viết tài liệu: Redis lên `healthy` và `docker` trả exit code 0, nhưng script báo thất bại. Nguyên nhân là Windows PowerShell 5.1 bọc stderr của native command thành ErrorRecord, mà `docker compose`, `pip` và `pnpm` đều ghi tiến trình ra stderr; gặp `$ErrorActionPreference = 'Stop'` là abort. Đây là lệnh đầu tiên người mới chạy, nên một tài liệu dạy cách phớt lờ lỗi giả sẽ dạy luôn thói quen phớt lờ lỗi thật. Sửa gọn trong một hàm và exit code vốn đã là thứ hàm đó định dùng.

## Ordered Tasks

- [x] Create this active plan before other repo-tracked changes.
- [x] Run the whole flow end to end and capture the real output every step produces.
- [x] Fix the false failure in `dev.ps1` found while running that flow.
- [x] Write `docs/local-development.md` from what was actually observed.
- [x] Trim `README.md` to a quickstart that links the new guide.
- [x] Add the new file to the ownership table in `AGENTS.md` and update the pointer in `CLAUDE.md`.
- [x] Run validation checks.
- [x] Move this plan to `docs/plans/completed/` after validation passes.

## Validation Checks

- Every command printed in the guide was run in this session and produced the output shown.
- All five grading scenarios in the guide were reproduced against a running system, covering three of the four `ReviewReason` values; `anomaly` stays unreachable until submissions are persisted.
- Run `.\dev.ps1 check` and confirm the repo contract checks still pass, including the line caps.
- Confirm `AGENTS.md` stays at or below 170 lines after the ownership row is added.
- Confirm `.\dev.ps1 infra-down` and `.\dev.ps1 infra-up` both exit 0 after the stderr fix.
- Confirm Markdown files are non-empty and internal links resolve.

## Status

Completed.
