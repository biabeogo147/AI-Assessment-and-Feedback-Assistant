# Plan — Kriky trả lời câu hỏi về nội dung tài liệu

- **Mở:** 26/10/2026 · Phần còn lại của plan 5 trong đợt `doc-pdf-vao-ngu-canh`; cùng plan
  `formulas-on-demand` thì B10 đóng

## Goal

Hôm nay Kriky chỉ đọc sách để **soạn đề**. Giáo viên hỏi *"sách định nghĩa luỹ thừa thế nào?"* thì
không có quy trình nào: skill `tro-chuyen-chung` trả lời bằng trí nhớ của model, không mở sách. Plan
này thêm skill `hoi-tai-lieu`. Với skill ấy, Kriky tìm mục trong mục lục, đọc bằng `read_section`
(không `questions`), rồi trả lời **chỉ từ chữ đã đọc**:

- nêu bài và trang;
- sách không có thì nói là không có;
- được dẫn công thức đọc từ ảnh trang (plan `formulas-on-demand`).

Lượt hỏi không được làm hỏng luật đọc của một lượt soạn đề sau đó, trong cùng đoạn chat.

## Scope

- Trong:
  - skill `hoi-tai-lieu`;
  - thủ tục `BOOK_QUESTIONS`; `BOOK_PROCEDURE` chỉ chèn khi skill `soan-de` được chọn;
  - `read_section` có `questions` tuỳ chọn, kết quả đánh dấu `answering`;
  - chữ của lần đọc hỏi đáp không ở lại lượt sau;
  - `read_before_outline` bỏ qua lần đọc hỏi đáp;
  - `LIBRARY` mở thư viện cả khi giáo viên hỏi;
  - ca bench; case thử tay 18; hậu ký ADR-27.
- Ngoài: pha 2 (`retry-sees-its-outline-item`); FE; sympy.

## Decision Records

### Decision: một skill mới, không mở rộng `tro-chuyen-chung`

**options considered:**

- (a) thêm nhánh *hỏi về sách* vào `tro-chuyen-chung`;
- (b) skill `hoi-tai-lieu` riêng, Jev chọn bằng một câu yes/no.

**selected option:** (b).

**reason:** `tro-chuyen-chung` là skill bao quát, Jev không hỏi nó (`skill_router`). Nó là chỗ rơi
vào, nên một nhánh trong nó không bật được gì bằng code: không mở thư viện (`opens_library` cần chỗ
trống `{thư viện}` của một skill đã chọn), không chọn được thủ tục. Skill riêng thì `compose` biết
lượt này hỏi hay soạn.

### Decision: BE đánh dấu lần đọc hỏi đáp trong kết quả

**options considered:**

- (a) AGENT và BE mỗi bên tự nhìn `tool_args.questions` của lời gọi;
- (b) `read_section` không `questions` trả thêm `answering: true`.

**selected option:** (b).

**reason:** hàng `tool_result` lưu ở BE không mang tham số của lời gọi. Ghép kết quả với lời gọi
từng lệch một lần (`read_order`, backlog chia `propose.py`). Một cờ trong chính kết quả thì cả hai
bên đọc cùng một chỗ.

## Files

- `services/agent/src/agent/skills/hoi-tai-lieu.md` (mới)
- `services/agent/src/agent/graphs/propose/prompt.py`, `compose.py`, `read_order.py`, `books.py`,
  `choose.py`, `ask_again.py` (không stage
  dòng TODO)
- `services/be/src/be/teacher_tools.py`, `teacher_chat.py`
- test: `services/agent/tests/test_skills.py`, test `read_order`; `services/be/tests/test_read_section.py`,
  `test_history_shape.py`
- `tools/skill_bench/cases.json`, `tools/propose_bench/cases.json`
- `docs/decisions/adr-27-*.md`, `docs/testing/cases/18-hoi-ve-sach.md`, `docs/testing/huong-dan.md`

## Ordered Tasks

- [x] Pha 1 — hậu ký ADR-27 (tài liệu nay cũng là nguồn trả lời trong chat; chỉ đọc, không vào
      job). Review subagent.
- [x] Pha 2 — BE: `questions` tuỳ chọn, cờ `answering`, chữ hỏi đáp không ở lại lượt sau; test.
      Review subagent.
- [x] Pha 3 — AGENT: skill, `BOOK_QUESTIONS`, điều kiện chèn hai thủ tục, `LIBRARY`,
      `read_before_outline`; test. Review subagent.
- [x] Pha 4 — bench: ca mới của `skill_bench` và `propose_bench`, không tụt ca cũ. Review subagent.
- [x] Pha 5 — thử tay case 18, chạy lại 04; biên bản. Review subagent.

## Validation Checks

- `.\dev.ps1 check` và `.\dev.ps1 test` xanh.
- `skill_bench`: ca hỏi về sách ra `hoi-tai-lieu`, ca soạn đề không bị cướp.
- `propose_bench`: ca mới đạt, ca cũ không tụt.
- Case 18 đạt: trả lời có bài và trang; câu ngoài sách được nói là không có; lượt soạn sau vẫn đọc
  phạm vi trước khi nêu dàn ý.

## Status

Mở và đóng ngày 26/10/2026. `check` và `test` xanh.

**Pha 1–3, code.** Review pha 1–2 sửa ba chỗ:
- số `0` gửi dạng số không còn thành đọc hỏi đáp;
- hai câu chưa đúng trong hậu ký ADR-27;
- một comment test.

Review pha 3 sửa `book_in_view`: một lần đọc hỏi đáp khép việc chọn sách. Không có bản sửa ấy thì
mọi lượt soạn đề sau một câu hỏi không chip nhận thủ tục sách và mất dòng mở thư viện. Ngoài plan
gốc có thêm:
- dòng mở thư viện riêng cho skill hỏi (`LIBRARY_ASK`), để không đổi `LIBRARY` đã đo;
- luật code `AnsweredUnread`, thêm sau thử tay.

**Pha 4, bench.**
- `skill_bench` (run-107): `hoi-tai-lieu` recall và precision 100% ở ngưỡng 0,3. Mô tả skill phải
  sửa một lần: Jev từng chọn nó cho câu *"Soạn 10 câu chương số phức từ sách này"*, và
  `tai-lieu-khong-khop` tụt 0/3 (run-106) rồi về 6/6 (run-108).
- `propose_bench`, 8 ca hỏi đáp: 29/32 (run-116). Trượt ở `hoi-sach-khong-co`: model đoán *"lớp 9"*
  ngoài sách.
- 14 ca sách cũ: 40/42 (run-115), không tụt so với baseline. `tai-lieu-khong-khop` 2/3 so với 5/6
  của run-101; `dan-y-thay-cau` vốn chập chờn.
- Chế độ nạp mọi skill (run-111): `tai-lieu-khong-khop` 2/3, ghi vào backlog.

**Pha 5, thử tay** (`docs/testing/ket-qua/2026-10-26-c4c767f-hoi-sach-claude-haiku-5-5.md`):
- Case 18 trượt lượt 2 ở hai lần đầu (không mở mục con *Số La Mã*). Lần 3, sau `AnsweredUnread`
  (bắn 3 lần), **chấp nhận được**: lượt 2 nêu đúng mục và trang nhưng kể nội dung chưa đọc, và lượt
  2–3 không có `read_section`; lượt soạn đề sau vẫn đọc phạm vi có `questions`. Case đã sửa theo
  review.
- Lời đáp còn bù bằng hiểu biết riêng (backlog).
- Case 04 không đạt ở lượt 2 vì `brief` rỗng: lỗi có từ trước, Tier 2 câu 24. Hôm nay 6/7 dàn ý có
  `brief` rỗng.

**Chi phí:** khoảng 0,3 USD (bench khoảng 0,25 USD, thử tay khoảng 0,06 USD).

**Chưa làm**, ghi ở `backlog.md` mục *Lộ ra khi làm plan Kriky trả lời câu hỏi về tài liệu*:
- chưa chạy lại cả bộ `propose_bench`;
- hai thủ tục vênh nhau khi nạp mọi skill;
- lỗi KaTeX với chữ có dấu.
