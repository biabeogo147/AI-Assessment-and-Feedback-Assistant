# Plan — Tạo lớp (roadmap C5, Tier 2 câu 28)

- **Mở:** 27/10/2026 · Plan 3 của đợt người dùng giao ngày 27/10/2026

## Goal

Giáo viên chưa tạo được lớp; lớp chỉ đến từ seed (hậu ký ADR-13 ngày 19/10/2026). Plan này cho giáo
viên tạo lớp ở **cả hai** bề mặt ADR-13 nêu: nút *Tạo lớp* của màn 9, và chat với Kriky. Người dùng
chốt ngày 27/10/2026:

- làm *"Màn lớp + Kriky"*;
- trùng tên với lớp của chính mình thì từ chối.

## Scope

- Trong:
  - hậu ký ADR-13;
  - BE: hàm chung `be.classes.create_class`, `POST /api/teacher/classes`, tool ghi `create_class`,
    dòng bước;
  - AGENT: skill `lop-va-ket-qua` và skill của lượt kể lại;
  - FE màn 9: nút, hộp tạo lớp, empty state;
  - Figma;
  - bench nhỏ và thử tay.
- Ngoài: đổi tên lớp, xoá lớp (xoá đụng tài khoản người thật, ADR-13).

## Decision Records

### Decision: một hàm cho hai cửa

**reason:** luật tên (chuẩn hoá, trần 64, trùng) chỉ sống ở `create_class`; route và tool cùng gọi.

### Decision: trùng tên so bằng `resolve.normalise`

**reason:** đúng phép so `list_class` dùng để tìm lớp. Hai lớp đã qua cổng này không bao giờ làm
Kriky hỏi lại *"lớp nào"* chỉ vì tên.

### Decision: không thẻ kết quả cho tạo lớp

**reason:** thẻ là máy trạng thái của một đề (luật người dùng chốt 06/10/2026, check 12). Lớp vừa
tạo hiện ở dòng bước và câu kết.

### Decision: `create_class` vào catalog dù chưa đảo ngược được

**reason:** lớp mới rỗng, không chạm học sinh nào. Ranh giới ADR-05 là việc không lấy lại được với
học sinh.

## Files

- `docs/decisions/adr-13-lop-va-tai-khoan-hoc-sinh.md`
- `services/be/src/be/classes.py` (mới), `resolve.py` (`tidy_name`), `main.py`, `teacher_tools.py`,
  `plan_outcomes.py`
- `services/be/tests/test_classes.py` (mới), `test_write_tools.py`
- `services/agent/src/agent/skills/lop-va-ket-qua.md`, `graphs/propose/graph.py`,
  `graphs/propose/history.py`, `tests/test_telling_after_plan.py`
- `services/fe/src/screens/teacher/Classes.tsx`, `ActionCard.tsx` (dòng bước), `api.ts`, `teacher.css`
- `tools/skill_bench/cases.json`, `tools/propose_bench/cases.json`

## Ordered Tasks

- [x] Pha 1: hậu ký ADR-13
- [x] Pha 2: BE + test; review subagent
- [x] Pha 3: AGENT skill + lượt kể lại + test; bench nhỏ (Haiku); review subagent
- [x] Pha 4: FE + Figma; ảnh vào `docs/report/screenshot/27_10/tao-lop/`, subagent chấm; review
      subagent
- [x] Thử tay (Haiku), biên bản
- [x] Status, chuyển `completed/`, roadmap (C5 *Xong*), backlog file và artifact, commit

## Validation Checks

- `.\dev.ps1 check`, `.\dev.ps1 test` xanh; check 12 vẫn bốn nấc.
- Lớp mới hiện ở màn 9, ở `list_class`, ở hộp phát hành.
- Trùng tên: 409 ở màn, lời từ chối ở chat.

## Status

Xong 27/10/2026.

- **BE:** `be.classes.create_class` (một hàm cho route và tool), `POST /api/teacher/classes`, tool ghi
  `create_class`, dòng bước. Review BE bắt một lỗi trước khi commit: tool chỉ `flush`, mà vòng pha 2
  rollback sau mỗi bước, nên lớp tạo qua Kriky không bao giờ được lưu. Nay tool tự commit, và test
  rollback như đường thật (bỏ commit thì đỏ). Cũng theo review:
  - `tidy_name` chỉ bỏ *"lớp"* trước chữ số;
  - khoá hàng giáo viên khi kiểm trùng (Postgres);
  - thiếu `name` vẫn là một câu 422.
- **AGENT:**
  - skill `lop-va-ket-qua` thêm bước 5–6;
  - lượt kể lại nạp skill của **mọi** tool trong plan (`history.telling_skills`; review: plan vừa
    tạo lớp vừa soạn đề cần cả hai).
- **Bench:**
  - `skill_bench` `run-118`: recall 100%; precision `lop-va-ket-qua` 89% (trước 93%), thêm ca
    `chung-phat-hanh` ở 0,32;
  - `propose_bench` `run-119` 9/9 và `run-120` 6/6. Sau `run-119` bỏ tên lớp ví dụ khỏi skill và
    mô tả tool, vì Kriky chép chúng.
- **FE:**
  - nút *Tạo lớp*, hộp tạo lớp, hàng empty state, dòng bước;
  - review: hộp không đóng khi đang gửi; Enter theo luật của nút; còn nút khi danh sách đọc lỗi;
  - chấm ảnh: nút đứng thấp 26px vì `margin-top: 34px` của màn có link quay về, đã sửa; nút khoá
    bị mờ hai lần, đã sửa.
- **Figma:**
  - artboard 9 đã có nút;
  - thêm 9b `799:5123` (hộp `799:5216`) và 9c `799:6269` (câu từ chối `799:6510`, 11/17);
  - nút chính của 9b vẽ ở trạng thái khoá, bỏ bóng đổ.
- **Ảnh:** `docs/report/screenshot/27_10/tao-lop/` 01–08.
- **Thử tay:** biên bản `docs/testing/ket-qua/2026-10-27-6050d6f-tao-lop-claude-haiku-5-5.md`, mọi
  lượt đạt. Chi phí thử tay khoảng 0,03 USD; bench khoảng 0,07 USD, vượt mức ước.
- **Còn lại:** `backlog.md`, mục *Lộ ra khi làm plan tạo lớp (27/10/2026)*.
