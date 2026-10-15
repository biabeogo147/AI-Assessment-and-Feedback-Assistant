# ADR-29 — Dàn ý đề trước khi soạn

- **Trạng thái:** đã chốt, chưa thi hành
- **Ngày:** 2026-10-15

## Bối cảnh

Tới ngày 15/10/2026, soạn đề theo tài liệu ([ADR-27](adr-27-tai-lieu-di-vao-ngu-canh-ra-de.md), hậu
ký 12/10/2026) chạy như sau: hệ thống tự chia số câu lên các mục của sách theo độ dài nội dung, rồi gửi
**chữ OCR thô** của mục vào từng job soạn câu. Giáo viên không thấy câu nào sẽ hỏi gì cho tới khi câu
đã ra.

Đo trên SGK Lớp 6 tập 1: 7–12% chữ của sách là rác hay công thức đọc lệch, hình và bảng mất không dấu,
một phần bảy số mục chỉ có bài tập, và mục dài bị cắt đuôi. Job đọc đúng thứ ấy và không ai kiểm thứ nó
đọc. Phép chia theo độ dài, như chính ADR-27 tự nhận, là một **lựa chọn sư phạm ngầm**.

## Quyết định

- **Mọi đề đi qua một dàn ý giáo viên đã được xem**, có tài liệu hay không. Kriky đề xuất; mỗi mục của
  dàn ý nói **kiến thức** câu ấy kiểm, **công thức** sẽ dùng, **phương án làm bài**, và bài nguồn khi có
  tài liệu. Một mục có thể phủ nhiều câu.
- **Chữ dàn ý trên màn hình do BE dựng từ dàn ý đã lưu**, không do model viết tự do. Thứ giáo viên đọc
  là đúng thứ các job nhận.
- **Giáo viên duyệt hay sửa dàn ý bằng chat.** Soạn chỉ bắt đầu sau khi dàn ý đã hiện ở một lượt
  trước; sửa thì Kriky đưa bản mới đủ mục.
- **Job soạn câu chỉ nhận mục dàn ý của nó**, cộng kiến thức của các mục khác để tránh hỏi trùng. **Chữ tài liệu
  thô không tới job nào**; nó chỉ tới Kriky, lúc Kriky đọc để viết dàn ý.
- **Công thức trong dàn ý là công thức Kriky đề xuất, và dàn ý nói rõ điều đó.** Bản đọc của sách
  hiện chỉ có chữ, nên không công thức nào chép được từ sách; chữ dàn ý BE in gọi chúng là công thức
  Kriky đề xuất, không bao giờ là công thức của sách.
- **Sau khi đã soạn, đề chỉ đổi khi giáo viên nói.** Thay một câu thì đúng câu ấy được soạn lại theo
  một mục dàn ý mới, và câu cũ ở lại cho tới khi câu mới qua được phép kiểm ADR-18. Soạn thêm thì có
  dàn ý bổ sung, duyệt rồi mới soạn; câu đã có không đổi.
- **Mỗi lần xin tối đa 10 câu.** Một đề vẫn tới 50 câu qua nhiều lần soạn thêm.
- Pha 2 không đổi: câu luyện tập không nhận tài liệu, không qua dàn ý.

## Vì sao

**Một đề xuất hiện rõ, sửa được, không phải gợi ý ngầm.** ADR-05 cấm Kriky đánh dấu một lựa chọn sư
phạm là nên chọn, vì *"gợi ý ngầm còn tệ hơn gợi ý công khai"*. Phép chia theo độ dài là đúng loại gợi
ý ngầm ấy: không ai thấy nó, nên không ai sửa được nó. Dàn ý thì nằm cả trên màn hình, từng câu một,
trước khi có câu nào được soạn, và giáo viên đổi được bất kỳ mục nào bằng một câu nói. Quyết định sư
phạm vẫn là của giáo viên; Kriky chỉ làm phần việc tốn công là đọc sách và viết ra một bản để sửa.

**BE dựng chữ, không để model viết lại**, vì một dàn ý model kể lại bằng lời của nó có thể lệch với
dữ liệu gửi đi mà không ai nhận ra -- giáo viên duyệt một thứ, job nhận thứ khác. Đây là cùng lý do
lựa chọn của câu hỏi lại do BE viết từ hàng nó đọc (ADR-23).

**Chữ thô không tới job**, vì rác OCR làm câu sinh ra kém đi, và không ai kiểm được thứ job đọc. Kriky
đọc chữ thô một lần, viết lại sạch, và giáo viên kiểm bản viết lại. Rác được xử lý ở đúng một chỗ, trước
mắt người.

**Công thức và cách làm, không chỉ chủ đề.** *"Câu 1 về hàm hằng"* không cho giáo viên duyệt được gì:
mười câu cùng chủ đề vẫn có thể cùng một cách giải. Công thức và phương án làm bài là thứ phân biệt hai
câu, và là thứ giáo viên có ý kiến.

**Câu cũ ở lại khi thay**, vì job soạn có thể hỏng; xoá trước thì giáo viên mất một câu tốt để đổi lấy
một ô trống.

**Mười câu mỗi lần**, vì Kriky phải đọc phạm vi trong một lượt chat: mỗi câu được một phần đọc, và
mười phần đọc cộng các bước khác là trần một lượt chịu được. Một dàn ý mười mục cũng là thứ giáo viên
còn đọc hết được.

## Hệ quả

- **Thêm một lượt chat trước mỗi lần soạn.** Giáo viên phải đọc và trả lời dàn ý; đó là cái giá của
  việc thấy trước câu nào hỏi gì.
- **BE chỉ chứng minh được dàn ý đã hiện, không chứng minh được giáo viên đồng ý.** *"oke"* được đọc
  bằng model. Đọc nhầm thì sửa được bằng thay câu hay xoá câu, và cổng duyệt đề (ADR-05) vẫn đứng
  trước học sinh.
- **Bài tập trong sách có thể vào dàn ý** dưới dạng phương án làm bài, vì Kriky đọc cả bài tập. Giáo
  viên thấy nó trong dàn ý; đó là lưới, như hậu ký ADR-27 đã chọn cho đề giáo viên soạn.
- **Luật *mỗi câu một mục* và phép rải theo độ dài của ADR-27 thôi áp dụng**; dàn ý thay chúng.
- **Đề trên 10 câu cần nhiều lần soạn thêm**, mỗi lần một dàn ý.
- **Không phải cổng thứ tư của ADR-05.** Dàn ý nằm ở cổng thứ ba -- đầu vào, trước một việc còn đảo
  ngược được -- nhưng không đi qua `ask_clarify`: nó không hỏi thông tin còn thiếu, nó cho xem việc
  sắp làm. Luật lựa chọn của ADR-23 vì thế không áp cho nó; luật *không đánh dấu nên chọn* của ADR-05
  được giữ bằng cách khác -- một đề xuất duy nhất, hiện trọn, sửa được từng mục (xem *Vì sao*). Ba cổng
  vẫn là ba.
- **Thay câu theo luật xoá câu của ADR-28**: câu bị thay thôi nằm trong đề, bản của nó trong ngân hàng
  (nếu có) ở lại.

## Nơi luật này đang được thi hành

**Chưa nơi nào.** Plan thi hành: `docs/plans/active/2026-10-15-draft-outline-plan.md`. Nơi nó sẽ sống:

| Luật | Sẽ sống ở |
|---|---|
| Mọi đề qua dàn ý đã hiện | cổng `_shown_outline` trong `services/be/src/be/teacher_chat.py` |
| BE dựng chữ dàn ý, gọi công thức là của Kriky | `services/be/src/be/outline.py` (`render`) |
| Job chỉ nhận mục của nó, không chữ thô | `drafting.fire`; check `check_drafting_reads_no_document_text` |
| Thay câu giữ câu cũ | `replace_question` và `harvest` trong `drafting.py` |
| Mười câu mỗi lần | `be/outline.validate`, `start_drafting` |
| Pha 2 không đổi | **đã có**: `packages/contracts/tests/test_draft_outline.py` (`test_phase_two_has_no_room_for_an_outline_item`) |
