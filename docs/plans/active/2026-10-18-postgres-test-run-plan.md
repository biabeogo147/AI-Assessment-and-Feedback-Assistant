# Đợt 4, cụm 1 — bộ test BE chạy trên Postgres (việc 23)

## Goal

Làm việc 23 của `2026-10-18-deterministic-batch-master-plan.md`: bộ test BE chạy được trên Postgres
theo yêu cầu, và mọi lỗi chỉ Postgres thấy được sửa. Đứng trước việc 22 (đăng nhập), để phần đăng nhập
được test trên Postgres.

## Scope

- **Trong phạm vi:**
  - `services/be/tests/conftest.py`: tuỳ chọn `--postgres-url`; không có thì không làm gì;
  - database riêng `aiafa_test` trên Postgres của docker; không bao giờ `aiafa`;
  - sửa code BE (hay test) theo những gì Postgres làm lộ ra;
  - `docs/local-development.md` nói cách chạy.
- **Ngoài phạm vi:**
  - test của `packages/schema` (chạy câu sqlite thuần để giả database lệch), `services/agent`,
    `services/document`, `services/ingest`;
  - đưa lần chạy Postgres vào `.\dev.ps1 test` hay pre-commit: nó chậm và cần docker.
- Không thêm biến `.env`.

## Files

| Đường dẫn | Việc |
| --- | --- |
| `services/be/tests/conftest.py` (mới) | harness |
| `services/be/tests/test_delete_question.py`, `test_failed_slots.py` | `PRAGMA foreign_keys` chỉ cho sqlite |
| code BE và test theo kết quả lần chạy | sửa |
| `docs/local-development.md` | cách chạy |

## Ordered Tasks

### Pha 1 — harness
- [x] 1. `conftest.py`: `--postgres-url`; đổi mọi `create_async_engine("sqlite+aiosqlite://")` sang URL
  ấy; lần nối đầu của mỗi engine xoá rồi dựng lại `public`; từ chối database tên `aiafa`.
- [x] 2. `CREATE DATABASE aiafa_test` trên Postgres của docker (DB mới, trống).
- [x] 3. Chạy cả `services/be/tests` trên `aiafa_test`; ghi danh sách test đỏ vào mục *Status*.

### Pha 2 — sửa những gì Postgres lộ ra
- [x] 4. `test_teacher_memory.test_two_steps_cannot_claim_the_same_position`: đoạn chat thử trỏ
  `teacher_id="whoever"`, một giáo viên không có; Postgres chặn bằng khoá ngoại trước khi tới ràng
  buộc unique test muốn kiểm. Dùng giáo viên seed `GV-001`. Lỗi của test, không của code.

### Pha 3 — đóng
- [ ] 5. `docs/local-development.md` có mục chạy test trên Postgres. Roadmap việc 23 *Xong*; backlog;
  tick plan tổng; plan sang `completed/`.

## Decision Records

### Decision: đổi engine trong `conftest`, không sửa 22 file test
options considered: một fixture engine chung rồi sửa từng file test; biến môi trường đổi URL trong
`be.db`; `conftest` thay `create_async_engine` khi có tuỳ chọn dòng lệnh.
selected option: `conftest` thay `create_async_engine`, chỉ khi có `--postgres-url`.
reason: 22 file test có DB tự dựng engine theo cùng một khuôn; sửa từng file là một diff lớn không đổi
hành vi nào. Biến môi trường thì lỡ tay bật được, và `.env` của người dùng không được đụng. Tuỳ chọn
dòng lệnh chỉ bật khi gõ ra, và URL trỏ `aiafa` bị từ chối.

## Validation Checks

| Kiểm | Lệnh |
| --- | --- |
| sqlite như cũ | `.\dev.ps1 test`, `.\dev.ps1 check` |
| Postgres | `pytest services/be/tests --postgres-url=postgresql+asyncpg://aiafa:aiafa@127.0.0.1:5432/aiafa_test` |

## Status

- 18/10/2026: plan mở; harness chạy được (`test_failed_slots.py` 10/10 trên `aiafa_test`).
- 18/10/2026, lần chạy đủ: 634 test BE trên `aiafa_test`, 633 qua, 1 đỏ (task 4). Không lỗi nào của
  code: khoá hàng, khoá ngoại, `String(n)` và các truy vấn mới của đợt 3 (`_empty_draft_of`, DISTINCT
  + ORDER BY) đều qua trên Postgres. 22 file test có DB đều dựng engine theo khuôn conftest đổi được.
