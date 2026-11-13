# ADR-38 — Dàn ý là lời Markdown; Kriky tự chia việc

- **Trạng thái:** đã chốt, đang thi hành (thay các luật về mục có cấu trúc của
  [ADR-29](adr-29-dan-y-de-truoc-khi-soan.md) và [ADR-30](adr-30-loi-kriky-do-model-viet.md))
- **Ngày:** 2026-11-13

## Bối cảnh

[ADR-29](adr-29-dan-y-de-truoc-khi-soan.md) đặt một dàn ý trước mọi đề. Từ
[ADR-30](adr-30-loi-kriky-do-model-viet.md), một lượt dàn ý có **hai bản song song**:
- lời Markdown Kriky viết cho giáo viên;
- các mục có cấu trúc (`OutlineItem`: số câu, kiến thức, công thức, cách làm, bài nguồn).

BE kiểm các mục (`be/outline.validate`), rồi chia mục thành ô theo luật cứng (`place_items`): mục phủ
k câu thì k ô liên tiếp, giống hệt nhau, chỉ khác số *"câu thứ mấy của mục"*.

Người dùng thấy BE đang kiểm soát kết quả của agent quá chặt ở chính hai bước ấy. Bench chất lượng ra
đề (`tools/exam_bench`, plan `agent-split-bench`) đã thử hướng ngược lại:
- **Cách thử:** agent đọc lại lời Markdown giáo viên đã thấy, rồi tự viết lời dặn riêng cho từng câu.
- **Q1 so cặp** (tỉ lệ câu dùng được nguyên, so trên cùng một dàn ý): +1,8 điểm, khoảng 95% từ −3,1
  tới +10,8, trên 9 cặp. Chưa thấy hơn, nhưng cũng không kém.
- **Độ trung thành:** 49/50 job đúng với dàn ý.
- Lượt chạy dừng giữa chừng vì hết credit API.

Người dùng chốt đưa hướng này vào hệ thống thật (13/11/2026).

## Quyết định

- **Dàn ý là lời Markdown của Kriky**, in nguyên văn ra chat. Đi kèm lời chỉ có hai thứ:
  - **một con số** số câu (`outline_questions`);
  - **các bài nguồn** khi có sách (`outline_nodes`).
- **BE chỉ kiểm hai thứ ấy:**
  - số câu: tối đa 10 câu mỗi lần, tổng 50 câu mỗi đề, đúng 1 câu khi thay câu;
  - bài nguồn: có thật trong cây của tài liệu.

  BE không đọc lời dàn ý.
- **Giáo viên đồng ý thì Kriky tự chia** chính lời ấy thành câu, mỗi câu một job, và gửi cách chia
  kèm plan soạn (`NextStepCompleted.split`). BE đòi cách chia đúng số câu của dàn ý đã xem; lệch hay
  thiếu thì không câu nào được soạn. **BE không chia gì.**
- **Mỗi job một câu.** Job nhiều câu chưa làm.
- **Lời Kriky kể nó chia việc thế nào** hiện trên chat, **trong khối các bước** của lượt ấy (một
  lượt, một khối *Thinking*):
  - mở sẵn trong lúc soạn;
  - thu gọn khi đề soạn xong;
  - lưu trên lượt `plan`, nên F5 dựng lại đúng lời ấy.
- **Không đổi so với ADR-29:**
  - mọi đề đi qua một dàn ý giáo viên đã xem ở lượt ngay trước;
  - job không nhận chữ tài liệu thô;
  - sau khi đã soạn, đề chỉ đổi khi giáo viên nói;
  - mỗi lần tối đa 10 câu.

## Vì sao

**Một bản, không hai.** Bản cấu trúc và lời Markdown là hai bản của cùng một dàn ý. Từ hậu ký
20/10/2026 của ADR-30, BE không còn đối chiếu hai bản với nhau, nên chúng có thể lệch mà không ai thấy.
Hơn nữa, bắt model viết dàn ý hai lần chỉ để BE có thứ mà kiểm. Đo ở pilot `run-130`: phép kiểm mục
của BE không từ chối dàn ý nào (0/16), nên nó không đổi được gì cho chất lượng.

**Phép chia cứng tạo những câu giống nhau.** Mục phủ k câu cho ra k job nhận cùng một lời dặn. Hai câu
cùng phần chỉ khác nhau ở con số *"câu thứ mấy"*. Agent đọc cả dàn ý nên viết được lời dặn riêng cho
từng câu: câu này khác câu anh em ở đâu, cách làm của riêng câu này. Đó là thứ một người soạn không thấy
dàn ý cần biết.

**Con số ở lại vì nó là ranh giới chi phí, không phải nội dung.** Trần 10 câu mỗi lần và 50 câu mỗi đề
là luật của hệ thống. Kiểm nó ngay ở lượt dàn ý thì giáo viên không duyệt một dàn ý mà sau đó không soạn
đủ.

**Giáo viên thấy cách chia**, vì thứ giáo viên đọc nay không còn đúng là thứ job nhận. Thứ giáo viên
đọc là lời dàn ý; thứ job nhận là lời dặn agent rút từ lời ấy. Lời chia việc trong khối các bước đặt chỗ rút ấy
trước mắt giáo viên, đúng lúc câu đang về.

## Hệ quả

- **Thứ giáo viên duyệt và thứ job nhận không còn là một.** ADR-29 nói *"thứ giáo viên đọc là đúng
  thứ các job nhận"*. Nay giữa hai thứ có một bước agent:
  - lệch thì không có cổng nào chặn;
  - giáo viên thấy chỗ lệch ở lời chia việc và ở panel đề, rồi sửa bằng thay câu.

  Bench đo độ lệch này là S1 (job trung thành với lời dàn ý).
- **Thêm một lời gọi model** sau lời đồng ý, trong cùng lượt.
  - Nếu chia hỏng, kể cả sau một lần trả lại, lượt ra thông báo hệ thống (ADR-30, ngoại lệ 1); giáo
    viên gõ lại lời đồng ý.
  - Nếu thừa câu ở đề mới hay đề soạn thêm, phần đuôi bị cắt. Khi thay câu thì không cắt: job đầu là
    câu 1, không phải câu bị thay.
- **Cơ sở dữ liệu không đổi.** `DraftBrief.outline` và `DraftItem.outline_item` nay giữ job, mỗi phần
  tử một câu. Ba đường vẫn đọc đúng hai cột ấy: thay câu, nút *Thử lại* ô hỏng, và câu làm lại ở pha 2
  (hậu ký 26/10/2026 của ADR-17). Ô của đề soạn trước ADR-38 vẫn mang mục nhiều câu
  (`item_part`, `item_parts`).
- **Job mang nhãn phần dàn ý** (`SplitJob.part`). Câu anh em cùng phần không bị dặn *"đừng hỏi sang"*
  kiến thức của nhau. Nhãn chỉ có tác dụng khi cùng một bản dàn ý có từ hai nhãn trở lên.
- **Bench đo lại theo đường mới.** Nhánh `agent` của `exam_bench` chia việc bằng chính bước của AGENT.
  Chạy bench phải hỏi người dùng trước.

## Nơi luật này đang được thi hành

| Luật | Sống ở | Test canh |
|---|---|---|
| Dàn ý là lời kèm số câu và bài nguồn; kind khác không chở chúng; `split` chỉ đi với `plan` | `contracts/teacher_chat.py` (`NextStepCompleted`, `Split`, `SplitJob`) | `packages/contracts/tests/test_draft_outline.py` |
| BE chỉ kiểm số câu và bài nguồn của dàn ý | `be/outline.validate`, `teacher_chat.outline_turn` | `services/be/tests/test_outline.py`, `test_the_outline_shown_is_kriky_s_own_words_and_its_count_is_stored` |
| AGENT chia dàn ý vừa được đồng ý, đúng số câu, theo cùng luật *ngay trước* với BE | `agent/graphs/propose/split.py` (`split_outline`), gọi ở cuối `propose()` | `services/agent/tests/test_split.py` |
| Plan soạn thiếu cách chia hay lệch số câu thì không câu nào được soạn | `teacher_chat.guard_drafting`; lớp thứ hai ở `drafting.fire`, `drafting.replace` | `test_a_drafting_plan_must_carry_a_split_of_exactly_the_outline_s_count`, `test_a_plan_whose_split_is_missing_drafts_nothing`, `test_a_round_whose_jobs_do_not_match_its_count_drafts_nothing` |
| Câu mới thứ k nhận job thứ k; BE không chia | `drafting.fire` | `test_a_job_receives_exactly_its_outline_item`, `test_each_question_gets_its_own_job_and_siblings_are_not_off_limits` |
| Lời chia việc lưu trên lượt `plan`, không về lại model ở lượt sau | `teacher_chat` (lưu plan, `_shrunk`) | `test_an_agreed_outline_drafts_each_question_on_the_job_agent_split_for_it`, `test_a_plan_s_split_note_does_not_go_back_to_the_model` |
| Lời chia việc nằm trong khối các bước, mở và thu cùng khối; F5 dựng lại | `services/fe/src/screens/teacher/Steps.tsx` (`told`), `Chat.tsx` | `services/fe/src/steps-split.test.tsx`, `đọc lại một lượt soạn theo dàn ý: một khối bước, thu gọn, lời chia việc ở trong` (`teacher.test.tsx`) |
