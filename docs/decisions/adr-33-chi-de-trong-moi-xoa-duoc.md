# ADR-33 — Chỉ đề trống mới xoá được; một đoạn chat dùng lại đề trống của nó

- **Trạng thái:** đã chốt, đang thi hành
- **Ngày:** 2026-10-18

## Bối cảnh

Tới ngày 18/10/2026, một đề kiểm tra không bao giờ bị xoá. Điều ấy đúng với đề có câu: câu mang công
của giáo viên, đã duyệt thì có bản trong ngân hàng ([ADR-28](adr-28-ngan-hang-cau-hoi-ghi-khi-duyet.md)),
đã phát hành thì có bài làm. Nhưng nó để lại một rác không ai dọn: **đề trống**. Mỗi lần Kriky gọi
`create_draft` là một đề `EMPTY` mới, kể cả khi đoạn chat đã có một đề trống từ lượt trước, nên một
đoạn chat thử ba lần là ba đề trống cho một việc, và không đường nào gỡ chúng.

Câu Tier 2 số 7 của artifact *Backlog theo tier* hỏi cách giải. Người dùng chốt ngày 18/10/2026, ở
buổi review Figma: **đề trống xoá được, và xoá cứng**; đoạn chat đã có đề trống thì BE dùng lại đề ấy.

## Quyết định

- **Chỉ đề trống mới xoá được.** Đề trống là đề `EMPTY`, không câu nào, không ô **đang soạn** nào
  (`pending`, `retry`). Ô `failed` không chặn: đề mà mọi job đều hỏng vẫn là đề trống, và ô hỏng bị
  xoá cùng nó. Một phép cho mọi chỗ: `drafting.why_not_erasable`.
- **Xoá là xoá cứng**: `DELETE /teacher/assessments/{id}` xoá brief rồi đề, trong một giao dịch.
  Không có cột `deleted_at`. Chỉ tác giả (người khác thấy 404, [ADR-22](adr-22-de-co-tac-gia.md)).
- **Lượt chat cũ giữ `entity_id` của đề đã xoá.** Đọc lại đoạn chat thì BE gắn `entity_gone`, và thẻ
  *Đã tạo đề* cũ nói *"Đề trống này đã xoá"*, không nút, không mở được.
- **`create_draft` dùng lại đề trống mới nhất của chính đoạn chat đang chạy**, tìm qua các bước
  `create_draft` của đoạn ấy (`TeacherTurn.entity_kind/entity_id`): khoá hàng, ghi tên, môn, khối mới
  lên đề ấy, bỏ dàn ý và ô hỏng cũ, rồi thay brief. Đoạn chat khác thì vẫn mở đề mới.
- **Panel chỉ hiện link *Xoá đề* khi BE nói đề xoá được** (`AssessmentDetail.erasable`). Hộp xác nhận
  chỉ có câu hỏi và hai nút, vì đề trống không có gì để mất.

## Vì sao

**Xoá cứng, không xoá mềm.** Một đề trống không có gì đáng giữ: không câu, không bài làm, không bản
ngân hàng. Xoá mềm thì mọi truy vấn về đề phải lọc thêm một cột, chỉ để giữ một hàng rỗng. Cái giá là
thẻ cũ trỏ vào một đề không còn, và `entity_gone` trả đúng cái giá ấy.

**Ranh giới là *trống*, không là *chưa duyệt*.** Đề có câu mà chưa duyệt vẫn mang công soạn và có thể
mang câu đã vào ngân hàng từ một lần duyệt trước. Xoá từng câu đã có đường riêng (hậu ký ADR-01).

**Dùng lại trong một đoạn chat, không trên toàn giáo viên.** Một đoạn chat là một việc
([ADR-24](adr-24-mot-giao-vien-nhieu-doan-chat.md)). Đề trống của đoạn khác là việc khác mà giáo viên
có thể còn định làm, nên ghi đè nó là lấy mất của việc kia.

## Hệ quả

- Docstring `BankQuestion` thôi nói *"Đề không bao giờ bị xoá"*: đề có câu thì vẫn không, còn đề trống
  thì chưa bao giờ có dòng ngân hàng nào trỏ về.
- Một đề trống đang có ô soạn (`DraftItem`) không xoá được: job đang bay sẽ về ghi vào một đề không còn.
- AGENT không đổi gì: kết quả `create_draft` có thêm `reused: true` khi dùng lại, và model đọc nó như
  một trường thừa.
- Một plan có **hai** bước `create_draft` trong cùng một lượt sẽ ra một đề, không hai: bước thứ hai
  thấy đề trống của bước đầu. Chưa có skill nào nêu plan như thế.
- Lịch sử gửi AGENT không đánh dấu đề đã xoá; model gọi `start_drafting` với id cũ thì nhận lời từ
  chối *không có đề này*, như mọi id lạ.

## Nơi luật này đang được thi hành

- `services/be/src/be/drafting.py`: `why_not_erasable`.
- `services/be/src/be/teacher_routes.py`: `erase_empty_draft`, `AssessmentDetail.erasable`.
- `services/be/src/be/teacher_tools.py`: `_create_draft`, `_empty_draft_of`.
- `services/be/src/be/teacher_chat.py`: `Turn.entity_gone`, `_current_titles`, `_visible`.
- `services/fe/src/screens/teacher/Panel.tsx` (link và hộp xoá), `ActionCard.tsx` (thẻ *đã xoá*).
- Figma: `Consequence dialog — xoá đề nháp trống` `652:3899`, variant `tạo-đề-trống — đã xoá`
  `652:3900`, artboard `18` `653:2846`, `18b` `653:3095`.
- Test: `services/be/tests/test_empty_draft.py`; vitest *đề nháp trống: xoá được*.
