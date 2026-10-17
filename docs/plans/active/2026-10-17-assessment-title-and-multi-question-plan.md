# Tên đề gọn, giáo viên đổi tên đề; Kriky hỏi tối đa ba câu một lượt

## Goal

Người dùng nêu ngày 17/10/2026, sau thử tay plan `kriky-writes-every-word`:

1. **Tên đề có lúc quá dài.** Thẻ *Đã tạo đề "Đề chương ABC …… XYZ"* vỡ dòng và đẩy chip an toàn
   đi. Gốc: `teacher_tools._create_draft` đặt `"Đề " + topic_scope`, chỉ cắt ở 160 ký tự; đề theo
   sách thì `topic_scope` là cả chuỗi nhãn bài kèm số trang. Giáo viên không đổi được tên đề.
2. **Thẻ hỏi lại chỉ trả lời được một ý.** `ask_clarify` chở một `text` và một dãy `choices`; `_go`
   gặp nó là `return`; FE có một `asked`. Case 01: hỏi khối, phạm vi, số câu mà nút chỉ có khối.

Người dùng chốt:

- Tên đề **tối đa 60 ký tự**. Đề soạn từ sách lấy **tên tệp sách**. Giáo viên **đổi được tên** khi
  đề **chưa duyệt**. Thẻ có **lưới CSS** (một dòng, cắt `…`). Đổi tên rồi thì **mọi chỗ** hiện tên
  hiện tại, kể cả thẻ cũ trong đoạn chat.
- `ask_clarify` hỏi **tối đa ba câu** một lượt, mỗi câu một bộ nút; thẻ hiện **x/y**, nút **câu sau
  / câu trước**; **không bỏ câu**; có **màn tóm tắt** các lựa chọn; gửi **gộp một tin** dạng
  *"Khối: Khối 7 · Số câu: 5 câu · Phạm vi: tỉ lệ thức"*.
- Làm xong: **một subagent review code**; thử tay case 01, 02, 04 và case mới 15 trên Claude Haiku
  5.5, chụp màn hình; **một subagent review ảnh chụp**. Cho phép trước: `db-reset`, khởi động lại
  BE/AGENT/worker, gọi model thật (ước 0,05–0,10 USD).

## Scope

- Trong phạm vi: tên đề mặc định và trần 60 (BE); route đổi tên; tên hiện tại trong lượt đọc lại và
  lịch sử gửi AGENT; panel đổi tên và lưới CSS của thẻ (FE, Figma); `ask_clarify` nhiều câu (contracts,
  AGENT prompt/skill/lưới, BE lưu và đọc lại, FE thẻ nhiều câu và tóm tắt, Figma); ADR-31, ADR-32;
  tài liệu, case thử tay.
- Ngoài phạm vi: lỗi sản phẩm mới lộ ra lúc thử tay (ghi `backlog.md`); đổi tên đề qua chat.
- Mỗi pha: làm → `.\dev.ps1 check` + test → commit. Review subagent ở pha 6 (một cho code, một cho
  ảnh chụp).

## Files

| Đường dẫn | Việc |
| --- | --- |
| `services/be/src/be/titles.py` (mới), `teacher_tools.py`, `teacher_routes.py`, `teacher_chat.py` | Tên mặc định, trần 60, route đổi tên, tên hiện tại khi đọc lại; nhiều câu hỏi |
| `services/fe/src/screens/teacher/Panel.tsx`, `ActionCard.tsx`, `Chat.tsx`, `api.ts`, `teacher.css` | Đổi tên ở panel, lưới CSS thẻ, thẻ hỏi nhiều câu và tóm tắt |
| `packages/contracts/src/contracts/teacher_chat.py` | `ClarifyQuestion`, `NextStepCompleted.questions` |
| `services/agent/src/agent/graphs/propose.py`, `skills/soan-de.md` | Đề nghị nhiều câu, lưới từng câu, lịch sử |
| `docs/decisions/adr-31-…`, `adr-32-…`, `README.md`; `docs/overview/teacher-surface.md`; `docs/testing/…` | Quyết định, tài liệu, case |

## Ordered Tasks

### Pha 1 — Quyết định
- [x] 1. Plan vào `docs/plans/active/`.
- [x] 2. ADR-31 tên đề; ADR-32 hỏi lại nhiều câu; index `docs/decisions/README.md`. Commit.

### Pha 2 — Tên đề ở BE
- [x] 3. `be/titles.py`: tên mặc định (tên tệp bỏ đuôi khi có sách; không thì phạm vi bỏ `(tr. …)`),
  cắt ở ranh giới từ kèm `…`, trần 60. `_create_draft` dùng nó.
- [x] 4. `PATCH /teacher/assessments/{id}`: 404 (ADR-22), 409 đề đã duyệt, 400 trống, 422 quá 60.
- [x] 5. Tên hiện tại thay `title` của mọi `tool_result` có `assessment_id` khi đọc lại đoạn chat và
  khi dựng lịch sử gửi AGENT.
- [x] 6. Test. Commit.

### Pha 3 — Tên đề ở FE
- [x] 7. Figma: panel *đang đổi tên*; `Action result card` tên một dòng cắt `…`. Đo bằng nhau.
  Component `Panel title` (`626:2736`, hai variant `xem` / `đang đổi tên`); `Action result card`
  ba variant có tên đề cắt một dòng, thêm `đã-tạo-đề — tên dài` (`626:2737`). Đo ở mode Teacher: hàng
  sửa 431×37 (ô 330/330,5), hàng xem tên 345/346,1, thẻ 660×57/56,5, tên 428 — lệch dưới 1px do làm
  tròn dòng.
- [x] 8. `teacher.renameAssessment`; ô đổi tên ở panel (Enter lưu, Esc huỷ, tối đa 60, ẩn khi đã
  duyệt); lưu xong đọc lại đoạn chat. Lưới CSS ở thẻ, `title` = tên đủ.
- [x] 9. Vitest. Commit.

### Pha 4 — Nhiều câu hỏi: hợp đồng, AGENT, BE
- [x] 10. Contracts `ClarifyQuestion{label, text, choices}`, `NextStepCompleted.questions` (0 hoặc 2–3,
  chỉ `ask_clarify`).
- [x] 11. AGENT: `_Proposal.questions`, prompt và skill `soan-de`, lưới từng câu, `_compose`.
- [x] 12. BE `_go`: nút từng câu; câu về một dòng (ADR-23) chỉ một câu; lưu `tool_result.questions`;
  sự kiện `clarify` và `Answered` chở `questions`.
- [x] 13. Test. Commit.

### Pha 5 — Nhiều câu hỏi: FE
- [ ] 14. Figma `Clarify request`: *nhiều câu — câu k/n*, *nhiều câu — tóm tắt*. Đo bằng nhau.
- [ ] 15. Thẻ nhiều câu: `Câu k/n`, câu trước/câu sau, không bỏ câu, `Khác…` từng câu, tóm tắt, gửi
  gộp một lần. Một câu duy nhất vẫn là thẻ cũ.
- [ ] 16. Vitest. Commit.

### Pha 6 — Tài liệu, review, thử tay, đóng
- [ ] 17. `teacher-surface.md`, `huong-dan.md`, case 01, 02, 04; case mới `15-doi-ten-de.md`.
- [ ] 18. Một subagent review code của cả plan. Sửa theo.
- [ ] 19. Thử tay 01, 02, 04, 15 trên Haiku 5.5; ảnh chụp; biên bản.
- [ ] 20. Một subagent review ảnh chụp và biên bản. Sửa theo; đóng plan; bảng *Nơi thi hành* của
  ADR-31, ADR-32. Commit.

## Validation Checks

- `.\dev.ps1 check`, `.\dev.ps1 test`, `.\dev.ps1 typecheck` xanh; không test nào gọi mạng.
- `PATCH` đổi tên ra 200/400/404/409/422 đúng ca; đọc lại đoạn chat thấy tên mới ở thẻ cũ.
- Trình duyệt: case 01 ra một thẻ ba câu, `Câu 1/3`, câu sau khoá tới khi chọn, tóm tắt, bong bóng
  gửi gộp; đề sách tên `Đề Kết nối tri thức Lớp 6 tập 1 (tr6-28)`; tên dài cắt `…` một dòng; đổi tên
  ở panel → thẻ cũ đổi theo.
- Figma: mỗi variant mới đo bằng nhau với computed style trình duyệt.

## Status

Đang làm pha 5.
