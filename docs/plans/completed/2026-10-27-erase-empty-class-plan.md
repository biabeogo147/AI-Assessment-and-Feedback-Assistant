# Xoá lớp rỗng, và tên đề trên thẻ bỏ chữ *Đề* ở đầu

## Goal

Hai việc người dùng giao ngày 27/10/2026, sau plan `tao-lop`:

1. **Tier 2 câu 38.** Thẻ ghi *Đã tạo đề "Mệnh đề"*, không còn *Đã tạo đề "Đề mệnh đề"*.
2. **Xoá lớp.** Người dùng trả lời câu *"có cho xoá lớp rỗng không"* bằng *"Làm thêm Xoá lớp"*.

## Scope

- **Câu 38.**
  - Tên đề mở bằng chữ *Đề* thì mọi câu dạng *đề "…"* bỏ chữ ấy và viết hoa chữ đầu phần còn lại:
    đầu thẻ *Đã tạo đề* / *Đã duyệt đề*, dòng bước `create_draft`, và `plan_outcomes.said_about`, chỗ
    `last_plan` đọc.
  - Panel, màn 21 và mọi chỗ khác in tên đề vẫn in nguyên tên.
  - Ngoại lệ *Đề cương …*: chữ *cương* đi liền thì không bỏ, vì *"Cương ôn tập"* là sai nghĩa.
  - Bước 6 của skill `soan-de` gọi đề theo đúng cụm *đề "…"* của `last_plan`.
- **Xoá lớp.**
  - Chỉ lớp **rỗng** xoá được: không học sinh, chưa từng nhận đề (kể cả đã thu hồi), không lượt làm
    bài nào mang lớp ấy. Một phép duy nhất cho mọi chỗ: `be.classes.why_not_erasable`.
  - Xoá cứng: `DELETE /api/teacher/classes/{id}`, trả 204. Lớp của người khác trả 404. Lớp không rỗng
    trả 409 kèm câu nói vì sao.
  - `ClassDetail.erasable`. Màn 10 chỉ hiện nút *Xoá lớp* khi cờ đúng. Hộp xác nhận theo mẫu
    *Xoá đề nháp* (`652:3899`). Xoá xong thì về màn 9.
  - **Không có tool chat**, cùng luật với xoá đề trống (ADR-33): xoá là việc của màn vật thể. Kriky
    tạo được lớp, nhưng không xoá được lớp.
  - Hậu ký ADR-13. Figma vẽ biến thể màn 10 có nút và hộp xoá lớp.

## Tasks

- [x] Câu 38: BE `titles.spoken_title`, `plan_outcomes.said_about`; FE `ActionCard`; skill bước 6;
  test.
- [x] BE xoá lớp: `why_not_erasable`, route, `ClassDetail.erasable`; test.
- [x] FE xoá lớp: `api.eraseClass`, màn 10 có nút, hộp, lời từ chối; vitest.
- [x] Figma: màn 10 có nút *Xoá lớp*, hộp xoá lớp; ảnh trình duyệt để subagent chấm.
- [x] Hậu ký ADR-13, `teacher-surface.md`, backlog (md và artifact), roadmap nếu cần.
- [x] `.\dev.ps1 check`, `.\dev.ps1 test`, review subagent, commit.

## Completion Criteria

- Thẻ của đề *"Đề mệnh đề"* ghi *Đã tạo đề "Mệnh đề"*, có test.
- Lớp rỗng xoá được ở màn 10; lớp có học sinh hay đã nhận đề thì không có nút, và BE từ chối 409.
- Ảnh ở `docs/report/screenshot/27_10/xoa-lop/` đã được subagent chấm so với Figma.

## Status

Xong 27/10/2026.
- Figma: 10e `802:5401`, 10f `802:5652`, 10g `806:5529`. Thẻ `66:*` không đổi, vì chữ mẫu không mở
  bằng *Đề*.
- Review subagent: sửa skill bước 6 (vẫn dặn bỏ chữ *Đề* khi không gọi `last_plan`), ngoại lệ bỏ dấu
  câu và thêm *Đề án/tài/xuất/nghị/mục*, hộp bị từ chối thay lời dẫn bằng câu của BE và cho bấm lại.
- Ảnh `docs/report/screenshot/27_10/xoa-lop/01–06`, subagent chấm đạt.
- Không chạy LLM thật: câu kết của Kriky với cụm mới chưa đo (Tier 4).

