# Plan — kênh tài liệu tự nối lại, và không giữ connection Postgres

## Goal

Tải tệp trên FE phải tự về *sẵn sàng* mà không cần F5, kể cả khi BE vừa Rerun. Lần thử tay ngày
12/10/2026 bắt ra ba lỗi trên kênh `/api/teacher/documents/stream`:

1. BE giữ session của request (đã mở transaction ở `current_teacher`) suốt đời stream, nên mỗi tab
   là một connection *idle in transaction*. Rò theo mỗi lần tải lại tab, chặn `db-reset`
   (`DROP SCHEMA` chờ khoá, mọi request sau xếp hàng sau nó) và sẽ cạn pool.
2. FE đọc kênh bằng `fetch`, kênh đứt là hết; chip đứng ở *đang xử lý* tới khi F5.
3. BE chết thì proxy của Vite không đóng phía trình duyệt, nên FE không biết kênh đã đứt.

## Files

| File | Việc |
|---|---|
| `services/be/src/be/teacher_documents.py` | `watch` đóng session trước khi stream; khung `: mở` ngay khi đã subscribe |
| `services/fe/src/api.ts` | `watchDocuments` nối lại có giãn (3 s → 30 s), chó canh 40 s im lặng, đọc lại danh sách ở byte đầu |
| `services/be/tests/test_documents.py`, `services/fe/src/teacher.test.tsx` | test cho cả ba lỗi |
| `docs/local-development.md` | số dòng breakpoint dịch theo code |

## Ordered Tasks

- [x] BE: đóng session, gửi `: mở`.
- [x] FE: vòng nối lại, chó canh, đọc lại khi kênh nghe được, dừng hẳn khi rời màn hình.
- [x] Test hai phía, thử đột biến để chắc test bắt được lỗi.
- [x] Thử tay trên trình duyệt; subagent review ảnh chụp và diff, sửa theo review.

## Validation Checks

- Trình duyệt: năm tệp `.md` và `report.pdf` (31 trang, 42 nút) tải từ FE đều về *sẵn sàng*.
- Trên một cặp BE 8001 + Vite 5174 dựng riêng: giết BE giữa lúc xử lý rồi bật lại thì chip tự về
  *sẵn sàng*; để BE chết thì FE cắt kênh câm sau 40 s rồi nối lại.
- `pg_stat_activity`: BE mới thêm 0 phiên *idle in transaction* mỗi lần mở kênh, BE cũ thêm 1.
- `.\dev.ps1 check` và `typecheck` xanh; vitest 190/190; pytest 680 qua, 1 hỏng
  (`test_a_turn_that_outlived_its_lock…`, không liên quan -- ghi ở `backlog.md`).

## Status

**Xong 12/10/2026.** Không thử: PDF scan từ FE (đường OCR, đã chạy ở plan 3c); `db-reset` lúc đang
mở tab trên BE mới. Để lại trong `backlog.md`: các lần `GET` danh sách song song có thể về lệch thứ
tự. Kênh đứt thì nối lại **im lặng** -- màn hình không đổi, nên không qua Figma.
