# Lời Kriky do model viết, bằng Markdown; dàn ý tách lời và mục; khối bước đọc sách có tên

## Goal

Thử tay 16/10/2026 và khảo sát 17/10/2026 (đoạn chat `83d709ad…` của case 04) cho thấy ba chỗ người
dùng muốn đổi. Người dùng chốt ngày 17/10/2026:

1. **Khối bước của lượt đọc sách** hiện `Đã làm 4 bước` mà mở ra là bốn dòng `Một bước nữa`: bốn
   tool đọc tài liệu không có tên trong `STEP_TITLE`, không có dòng kết quả, và pha 1 không phát
   sự kiện bước nào nên lúc Kriky đọc màn hình đứng im. **Làm đầu tiên.**
2. **Dàn ý cứng:** BE ghép khuôn cố định ("Công thức Kriky đề xuất", "Cách làm", "Theo", câu kết
   cố định). Kriky trả hai trường: lời cho giáo viên (Markdown, model viết) và các mục có cấu trúc
   (đi vào job như nay). BE đối chiếu hai thứ bằng **vài tiêu chí nhẹ**, không so từng chữ.
3. **Mọi lời Kriky do model viết, và mọi lời đều Markdown.** Hai ngoại lệ được đồng ý: thông báo khi
   model không trả lời được (hiện như thông báo hệ thống), và phần tử giao diện (tên bước, dòng kết
   quả, thẻ, nhãn nút BE dựng theo ADR-23, hộp xác nhận). Chế độ demo không model giữ nguyên.

Cuối plan: thử tay các ca bị đổi (01–08, 13, 14) trên `.env` hiện tại (Claude Haiku 5.5), chụp màn
hình, subagent review. Người dùng cho phép trước: `db-reset`, khởi động lại BE/AGENT/index worker,
gọi model thật (ước 0,05–0,08 USD).

## Scope

- Trong phạm vi: FE khối bước, bộ dựng Markdown cho lời Kriky (giáo viên) và trợ lý (học sinh),
  kiểu thông báo hệ thống; BE sự kiện bước pha 1, dàn ý, plan hỏng, thông báo; AGENT prompt, dàn ý,
  `_approved_plan`, `_which_book`; contracts; check mới; ADR-30 và hậu ký ADR-29; tài liệu, case thử
  tay; Figma của mọi màn đổi.
- Ngoài phạm vi: chữ câu hỏi, phương án, lời giải (vẫn `MathText`); tên đoạn chat (chữ trơn); lỗi
  sản phẩm mới lộ ra lúc thử tay (ghi `backlog.md`).
- Mỗi pha: làm → `.\dev.ps1 check` + test → một subagent review → sửa → commit.

## Files

| Đường dẫn | Việc |
| --- | --- |
| `services/fe/src/screens/teacher/ActionCard.tsx`, `Chat.tsx`, `Steps.tsx` | Tên và dòng kết quả bước đọc sách; vẽ mọi bước qua `stepFor`; lời Kriky Markdown; notice |
| `services/fe/src/KrikyText.tsx` (mới), `screens/student/Tutor.tsx`, `api.ts`, `teacher.css`, `package.json` | Bộ dựng Markdown + toán; kiểu chữ |
| `services/be/src/be/teacher_chat.py`, `outline.py`, `notices.py` (mới) | Sự kiện bước pha 1; lời dàn ý của model + đối chiếu; plan hỏng về model; notice |
| `services/agent/src/agent/graphs/propose.py`, `reporting.py`, `explain.py`, `skills/soan-de.md` | Prompt Markdown; dàn ý; `_approved_plan`; `_which_book`; `_UNCLEAR` notice |
| `packages/contracts/src/contracts/teacher_chat.py` | `kind="notice"`, `notice`, nghĩa của `text` với `outline` |
| `tools/check_contract.py`, `AGENTS.md` | Check lời Kriky không là chữ cố định |
| `docs/decisions/adr-30-…`, `adr-29-…`, `README.md`; `docs/overview/teacher-surface.md`; `docs/testing/…` | Quyết định, tài liệu, case |

## Ordered Tasks

### Pha 1 — Khối bước đọc sách
- [x] 1. Plan vào `docs/plans/active/`.
- [x] 2. `STEP_TITLE` cho `list_documents`, `list_chapters`, `get_chapter`, `read_section`; dòng kết
  quả từ chính `tool_result` (`read_section` nêu hai mục đầu rồi đếm phần còn lại).
- [x] 3. BE phát `step_*` cho mỗi `call_tool` pha 1, mang `tool_name` và `result` đã bỏ chữ sách;
  bước của plan mang `tool_name` và `result=None`, dòng của nó vẫn đi trong `detail`. FE đặt tên mọi
  bước bằng `STEP_TITLE` (`titleOf`) và dựng bước tra cứu bằng `stepFor` — đang chạy và sau F5 như
  nhau. Bước tra cứu không vào `bước k/n` và không làm khối thành `Dừng ở bước k`.
- [x] 4. Figma: variant `Trạng thái=đang tra cứu` (`613:20`) của `Thinking` (`83:76`); chữ gắn biến
  `type/label`, `type/caption`, mode `Teacher` 13/11px khớp trình duyệt, màu và khoảng đệm khớp.
- [x] 5. Test vitest + pytest. Review: một lỗi chặn (bước plan đi nhầm nhánh vì `result: {}`), hai
  lỗi header `Dừng ở` — đã sửa. Commit.

### Pha 2 — Quyết định
- [x] 6. ADR-30; hậu ký ADR-29; index decisions. Review → sửa (câu chữ; ngoại lệ 1 gồm cả lùi về
  nội dung soạn sẵn và đoạn chat đang chạy; hệ quả nới luật công thức) → commit.

### Pha 3 — Markdown
- [x] 7. `KrikyText` (react-markdown 9.0.1 + remark-gfm 4.0.0): tách toán bằng `MathText.pieces`
  trước khi parse Markdown; không HTML thô, ảnh chỉ in `alt`, link mở tab mới; `inline` cho tiêu đề
  thẻ hỏi lại. Dùng cho lời Kriky (`Chat.tsx`, cả lúc chạy lẫn sau F5) và bong bóng trợ lý
  (`Tutor.tsx`). Khối `$$…$$` của `MathText` nhận xuống dòng làm phần đệm.
- [x] 8. Figma: component `Kriky text — Markdown` (`616:23`). Đo ở mode `Teacher` bằng một lượt mẫu
  trong DB dev: chữ 14/21px, màu, khoảng 8px, mục 4px, bảng 193px, ô 6×10 khớp; chiều cao bảng lệch
  1px (cách tính viền). Bong bóng học sinh (mode `Student`) chưa đo.
- [x] 9. Prompt `propose`, `reporting`, `explain` cho phép Markdown gọn; luật 5 `huong-dan.md`.
- [x] 10. Test. Review: ba lỗi gần chặn (dòng trống trong mục danh sách, ảnh tự tải, `$$` riêng dòng)
  và các điểm nhỏ — đã sửa. Commit.

### Pha 4 — Dàn ý
- [x] 11. Contract: `text` của `kind=outline` là cả lời Kriky; `outline` vẫn là thứ duy nhất vào job.
- [x] 12. Prompt `_CORE`, `soan-de` (soạn thêm đánh số tiếp sau câu cuối), `_Proposal.text`; lời
  rỗng thì AGENT hỏi lại (`_NothingToSay`); các mục của dàn ý trong lịch sử đi thành một ghi chú
  riêng, không nối vào lời model.
- [x] 13. `outline.check_message`: lời nhắc `Câu m` đầu mỗi mục (cả "Câu hỏi m", "câu số m"); không
  câu nào **sau** câu cuối (câu trước câu đầu là câu đã có của đề); mục có công thức thì một công thức
  có mặt (so bỏ `$`, khoảng trắng, `{}`, `\left`, `\right`, `\cdot`, `\dfrac`→`\frac`); có một `?`.
  Bỏ `render`, `CLOSING`. Lời mock dàn ý (chế độ demo) qua được phép đối chiếu.
- [x] 14. Test; dữ liệu bench (không chạy bench). Review: không lỗi chặn; phép so công thức và khoảng
  câu quá chặt, regex bỏ sót cách viết phổ biến, comment cũ — đã sửa. Commit.

### Pha 5 — Loại A còn lại, notice, check
- [ ] 15. `_approved_plan` dùng lời model hoặc không lời mở.
- [ ] 16. `_which_book` hỏi model lại thay vì đè chữ.
- [ ] 17. Plan hỏng: lý do về model như kết quả tool.
- [ ] 18. `kind="notice"` cho thông báo hệ thống (`be/notices.py`, `_UNCLEAR`); FE vẽ khác, Figma.
- [ ] 19. Check trong `check_contract.py` + hàng `AGENTS.md`. Review → commit.

### Pha 6 — Tài liệu, thử tay, đóng
- [ ] 20. `teacher-surface.md`, `huong-dan.md`, case 01–07, 13, 14.
- [ ] 21. Thử tay 01–08, 13, 14 trên Haiku 5.5; ảnh chụp; biên bản cạnh 16/10.
- [ ] 22. Subagent review biên bản, ảnh, code; sửa; đóng plan.

## Validation Checks

- `.\dev.ps1 check` xanh, gồm check mới; pytest AGENT, BE, contracts, document, tools; vitest FE.
  Không test nào gọi mạng.
- Không còn `CLOSING`, `Bạn đồng ý với dàn ý này chứ`, `Công thức Kriky đề xuất` ngoài plan và biên
  bản đã đóng.
- Trình duyệt: bước đọc sách có tên **lúc đang chạy** và y hệt sau F5; Markdown dựng hình, toán dựng
  hình; dàn ý job nhận đúng mục.
- Figma: mỗi artboard đổi đo bằng nhau với computed style trình duyệt.

## Ngoài phạm vi (từ review)

- Bước tra cứu hỏng in nguyên `reason`/`error` viết cho model (vd *"nodes phải là số node lấy từ
  list_chapters/get_chapter"*) — lỗi đã có trong `backlog.md` (luật 7), nay hiện cả lúc lượt đang
  chạy. Chờ người dùng quyết.
- `test_a_turn_that_outlived_its_lock_does_not_wipe_the_next_ones` chập chờn (hai lần `now()` trùng
  nhau trên đồng hồ Windows); chạy lại thì xanh.

## Status

Đang làm pha 1.
