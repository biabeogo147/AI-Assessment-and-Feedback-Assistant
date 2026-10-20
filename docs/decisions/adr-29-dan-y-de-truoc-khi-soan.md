# ADR-29 — Dàn ý đề trước khi soạn

- **Trạng thái:** đã chốt, đang thi hành
- **Ngày:** 2026-10-15
- **Sửa:** 2026-10-17 — chữ dàn ý trên màn hình do Kriky viết, BE đối chiếu nhẹ với các mục
  ([ADR-30](adr-30-loi-kriky-do-model-viet.md)). Xem *Hậu ký 17/10/2026*.
- **Sửa:** 2026-10-20 — BE thôi đối chiếu lời với các mục và thôi bắt hình dạng công thức. Xem
  *Hậu ký 20/10/2026*.

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

Plan thi hành: `docs/plans/completed/2026-10-15-draft-outline-plan.md` (đóng 15/10/2026, sau bốn lượt
thử trên trình duyệt).

| Luật | Sống ở | Test canh |
|---|---|---|
| Mọi đề qua một dàn ý đã hiện ở lượt ngay trước, chưa dùng, đúng việc, đúng sách, đúng đề | `teacher_chat._shown_outline`, `guard_drafting`; `teacher_tools._start_drafting` từ chối khi không có dàn ý | `test_no_question_is_drafted_before_the_teacher_has_seen_an_outline`, `test_an_outline_seen_last_turn_becomes_the_draft_once_and_only_once`, `test_an_outline_from_before_the_last_teacher_message_is_not_an_approval`, `test_drafting_without_an_outline_seen_is_refused` |
| ~~BE dựng chữ dàn ý, gọi công thức là của Kriky~~ — thôi áp dụng 17/10/2026: lời dàn ý là lời model; từ 20/10/2026 BE không kiểm lời ấy (ADR-30) | `teacher_chat.outline_turn` (`render`, `check_message` đã gỡ) | xem bảng của ADR-30 |
| Job chỉ nhận mục của nó, không chữ tài liệu thô | `drafting.fire`, `drafting.item_fields`; agent `authoring.draft_brief` | `test_a_job_receives_exactly_its_outline_item`, `check_drafting_reads_no_document_text` |
| Thay câu giữ câu cũ tới khi câu mới đạt; thay câu theo luật xoá ADR-28 | `drafting.replace`, `harvest`, `drop_question`; `teacher_tools._replace_question` | `test_a_replaced_question_stays_until_its_successor_lands`, `test_a_replacement_whose_job_breaks_leaves_the_old_question`, `test_a_replacement_step_says_whether_the_question_changed` |
| Mười câu mỗi lần | `be/outline.validate`, `teacher_tools.MOST_QUESTIONS_ASKED` | `test_more_than_ten_questions_in_one_go_is_refused` |
| Công thức không bị bắt hình dạng (hậu ký 20/10/2026) | `be/outline.validate` | `test_a_formula_with_words_around_it_is_not_refused` |
| Pha 2 không đổi | contracts | `test_phase_two_has_no_room_for_an_outline_item` |

## Hậu ký 17/10/2026

Viết khi mở plan `kriky-writes-every-word`. Một luật đổi, các luật khác giữ nguyên.

- **Khi ADR-30 thi hành, chữ dàn ý trên màn hình thôi do BE dựng.** Kriky viết lời trình bày dàn ý
  bằng Markdown, kết bằng câu hỏi xin đồng ý của chính nó
  ([ADR-30](adr-30-loi-kriky-do-model-viet.md)); khuôn *"Công thức Kriky đề xuất / Cách làm / Theo"*
  và câu kết cố định bị bỏ. Lời và các mục là hai trường của cùng một lượt dàn ý; **job vẫn chỉ nhận
  các mục**, nên *"job chỉ nhận mục của nó, không chữ tài liệu thô"* đứng nguyên. Thi hành từ
  17/10/2026 (plan `kriky-writes-every-word`).
- **Thứ thay cho phép chứng minh từng chữ là phép đối chiếu nhẹ của ADR-30.**
- **Công thức vẫn là của Kriky**, nhưng luật ấy nay nằm trong prompt dàn ý, không trong khuôn của BE.

## Hậu ký 18/10/2026

Mục *Hệ quả* nói *"oke"* được đọc **bằng model**. Thực ra lời đồng ý dàn ý được đọc bằng regex ở
AGENT (`services/agent/src/agent/graphs/propose.py`): `_AGREES` nhận lời đồng ý (`_approved_plan`),
còn `_REVISES` và `_NO_CHANGE` nhận lời xin sửa để chặn việc soạn. Bốn vòng
review của plan `backlog-tier-1` đều ra một ca biên mới của hai regex ấy; nút *Soạn theo dàn ý này*
(Tier 2 câu 5) là đường thay, đã hoãn cùng đợt khoá AGENT. Hệ quả mục ấy nêu vẫn đúng: đọc nhầm thì
sửa được, và cổng duyệt đề vẫn đứng trước học sinh. Ghi lại theo plan `wave-1-small-fixes`.

**Ô câu soạn hỏng** (plan `wave-3-draft-panel`, việc 12). Một mục dàn ý mà job hỏng hết ba lượt
từng để lại một lỗ trên đề: panel hiện *Câu 1, 2, 3, 5*, và không có đường nào soạn lại mục ấy.
Nay:

- `AssessmentDetail.failed_slots` mang ô hỏng đúng vị trí, nên panel vẽ nó **giữa** các câu và số
  câu là số theo vị trí;
- nút *Thử lại* (`POST …/slots/{order}/redraft`) soạn lại đúng mục dàn ý của ô, với đủ ba lượt
  mới. Nút đi thẳng từ panel, không qua model: mục dàn ý đã được giáo viên xem;
- duyệt thì ô hỏng bị bỏ và số câu dồn lên, nên đề đã khoá không mang lỗ số.

## Hậu ký 19/10/2026

ADR-05 nay còn **hai** cổng: cổng thứ hai (kết quả chấm độ tin thấp) đã bỏ
([ADR-37](adr-37-bo-cong-do-tin-thap.md)). Số thứ tự giữ nguyên: cổng thứ nhất là duyệt đề, cổng thứ
ba là hỏi lại. Câu *"Ba cổng vẫn là ba"* ở trên đọc là hai cổng. Dàn ý vẫn nằm ở cổng thứ ba (đầu vào).

## Hậu ký 20/10/2026

- **BE thôi bắt hình dạng công thức.** Luật *mỗi phần tử `formulas` là đúng một cặp `$`* bị gỡ khỏi
  `outline.validate`: ở bốn vòng thử tay đầu-cuối 20/10/2026 nó trả về 50 trong 59 dàn ý, gần hết là
  mệnh đề có chữ ngoài cặp `$` (*"$f'(x)>0 \Rightarrow f$ đồng biến"*). Công thức chỉ đi vào prompt
  soạn câu, nơi chữ ấy vẫn đọc được. Trần 6 công thức mỗi mục và 200 ký tự mỗi công thức giữ nguyên.
- **Phép đối chiếu nhẹ của ADR-30 bị gỡ** (hậu ký 20/10/2026 của ADR-30), nên dòng *"Thứ thay cho
  phép chứng minh từng chữ là phép đối chiếu nhẹ"* của hậu ký 17/10 thôi áp dụng: không còn gì thay.
  Job vẫn chỉ nhận các mục; giáo viên thấy lệch ở panel và sửa ở đó.

## Hậu ký 20/10/2026 (đường dẫn)

Plan `split-propose-package` chia `services/agent/src/agent/graphs/propose.py` thành package
`graphs/propose/`: `_AGREES` và `_approved_plan` nay ở `propose/outline.py`. Tên hàm và luật không
đổi.
