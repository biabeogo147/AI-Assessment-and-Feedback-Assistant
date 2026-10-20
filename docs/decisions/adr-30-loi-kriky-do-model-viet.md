# ADR-30 — Lời Kriky do model viết, bằng Markdown

- **Trạng thái:** đã chốt, đang thi hành (trừ khung kèm học của học sinh, xem bảng cuối)
- **Ngày:** 2026-10-17
- **Sửa:** 2026-10-20 — BE thôi đối chiếu lời dàn ý với các mục, thôi bắt hình dạng công
  thức. Xem *Hậu ký 20/10/2026*.

## Bối cảnh

Tới ngày 17/10/2026, một phần lời Kriky nói với giáo viên không do model viết mà do code ghép:

- **Dàn ý đề** ([ADR-29](adr-29-dan-y-de-truoc-khi-soan.md)): BE dựng chữ từ các mục theo một khuôn
  cố định — *"Dàn ý — N câu (bản k)"*, *"Công thức Kriky đề xuất:"*, *"Cách làm:"*, *"Theo:"* — rồi
  một câu kết cố định xin đồng ý. Model chỉ viết câu mở.
- **Lời mở khi giáo viên đồng ý dàn ý** là một câu cố định, kể cả khi model đã viết một câu khác.
- **Câu hỏi lại về tài liệu nào** bị đè bằng một câu cố định.
- **Plan bị từ chối** thì BE nói thay model một câu chung (*"Bạn nói lại giúp mình một lần nữa
  nhé"*), hoặc một câu cố định báo tài liệu chưa dùng được.
- **Khi model hỏng**, lượt gãy hay AGENT không trả lời, câu báo lỗi hiện **như lời Kriky**, cùng
  avatar, cùng bong bóng; và khi model hỏng lúc đang bật, AGENT lùi về nội dung soạn sẵn của chế độ
  demo, cũng dưới giọng Kriky.

Thử tay 15–16/10/2026 cho thấy các câu ấy đọc ra máy móc — cùng một khuôn, cùng một câu kết, cho mọi
đề — và lời Kriky không định dạng được: mọi prompt cấm Markdown vì màn hình chưa dựng nó.

## Quyết định

- **Mọi lời Kriky nói do model viết** — trong chat của giáo viên và trong khung kèm học của học sinh.
  Code không đặt câu, không ghép khuôn vào lời Kriky. Khi một việc không làm được, **lý do** tới model
  như một kết quả, và model nói với người dùng.
- **Mọi lời Kriky là Markdown**, và màn hình dựng nó, cùng toán trong `$…$`. Màn hình không chạy HTML
  thô trong lời. Tên đoạn chat vẫn là chữ trơn. Câu hỏi, phương án và lời giải trong đề không phải lời
  Kriky, và vẫn in như trước.
- **Dàn ý là hai trường**: lời Kriky trình bày dàn ý cho giáo viên (Markdown, model viết, kết bằng một
  câu hỏi xin đồng ý do model tự viết) và **các mục có cấu trúc** — vẫn là thứ duy nhất đi vào job soạn
  câu (ADR-29).
- **BE đối chiếu nhẹ lời với các mục** trước khi in: lời nhắc tới **Câu m** — câu đầu của mỗi mục;
  lời không nhắc câu nào ngoài khoảng của dàn ý; mỗi mục có công thức thì lời có ít nhất một công thức
  của nó; lời có một câu hỏi; và lời không in số node — định danh máy, bài nguồn gọi bằng tên (thêm
  sau thử tay 17/10/2026). Lệch thì lý do về model và model viết lại trong cùng lượt; lệch mãi
  thì lượt chạm trần bước, và đó là ngoại lệ 1. Kiến thức, cách làm và tên bài **không** cần giống
  từng chữ.
- **Ngoại lệ 1 — khi model không trả lời được**: model hỏng hai lần liền, lượt chạm trần bước, lượt
  gãy giữa chừng, không với tới AGENT, đoạn chat đang chạy một việc khác, hay model nêu lại một plan
  sau khi đã nghe **cùng một lý do từ chối** hai lần liền — nó đã có lý do mà không sửa được, nên
  hỏi tiếp chỉ tốn lời gọi (thêm sau thử tay 17/10/2026). Lúc ấy hệ thống nói,
  bằng một **thông báo hệ thống** hiện khác lời Kriky — không avatar, không giọng của Kriky. Chế độ
  demo không model (`LLM_ENABLED=false`) nói bằng nội dung soạn sẵn như trước.
- **Ngoại lệ 2 — phần tử giao diện**: tên bước, dòng kết quả của bước, thẻ kết quả, nhãn nút hỏi lại
  do BE dựng từ hàng nó đọc ([ADR-23](adr-23-hoi-lai-khi-khong-phan-dinh-duoc.md)), hộp xác nhận.
  Chúng nói việc đã hay sắp xảy ra, nên giữ tất định. Chữ của panel đề không phải lời Kriky.

## Vì sao

**Trò chuyện thì phải có người nói.** Cùng một câu kết cho mọi dàn ý, cùng
một lời xin lỗi cho mọi plan hỏng, là dấu hiệu của một biểu mẫu, không phải của một trợ lý. Model đã
biết việc đang làm và lý do một việc không làm được; nó nói được câu đúng với lúc ấy.

**Dàn ý vẫn giữ được điều ADR-29 bảo vệ.** ADR-29 cho BE dựng chữ để *thứ giáo viên duyệt và thứ job
nhận là một*. Tách hai trường giữ phần quan trọng của luật ấy: job vẫn chỉ nhận các mục có cấu trúc,
không nhận lời. Cái mất đi là phép chứng minh *từng chữ* — lời có thể diễn đạt một mục khác cách mục
được ghi. Phép đối chiếu nhẹ bắt các lệch thô làm giáo viên duyệt nhầm một đề khác (sai số câu, sai
đánh số, mất công thức). Phần còn lại lộ ra ở câu đã soạn, và giáo viên sửa bằng thay câu hay xoá
câu; cổng duyệt đề ([ADR-05](adr-05-ba-cong-teacher-in-the-loop.md)) vẫn đứng trước học sinh.

**Hai ngoại lệ là chỗ model không có mặt, hay không được phép có mặt.** Khi model hỏng, không có model
để viết lời; một câu của hệ thống, nói rõ là của hệ thống, trung thực hơn một câu giả giọng Kriky.
Tên bước, thẻ, nhãn nút thì phải nói đúng việc đã xảy ra — để model viết chúng là mở lại đúng lỗi nút
bịa của ADR-23, và lỗi khối bước kể một việc khác việc đã chạy mà ADR-25 đóng bằng plan có trước.

## Hệ quả

- **Lời dàn ý không còn chứng minh được là từng chữ của các mục.** Luật *"BE dựng chữ dàn ý"* của
  ADR-29 thôi áp dụng (hậu ký 17/10/2026 của ADR-29); các luật khác của ADR-29 giữ nguyên.
- **Luật *"công thức là của Kriky, không của sách"* (ADR-29) nay chỉ còn prompt giữ.** Khuôn của BE
  từng in nó; phép đối chiếu nhẹ không canh nó. Đây là chỗ luật bị nới.
- **Khi bật model, model hỏng không còn lùi về nội dung soạn sẵn**: lượt ra thông báo hệ thống (ngoại
  lệ 1). Nội dung soạn sẵn chỉ còn cho `LLM_ENABLED=false`.
- **Có thêm lượt hỏi model lại** khi lời lệch các mục, hay khi plan bị từ chối: tốn token, và chạm
  trần bước sớm hơn. Trần bước vẫn là lưới cuối, và chạm trần là ngoại lệ 1.
- **Prompt cho phép Markdown**; luật thử tay *"không Markdown"* thành *"Markdown được dựng, không ký
  tự Markdown nguyên văn trên màn hình"*.
- **Một loại lượt mới trong hội thoại**: thông báo hệ thống, lưu như một lượt và đọc lại được sau F5.
  Model đọc nó như ghi chú của hệ thống, không như lời mình đã nói.

## Nơi luật này đang được thi hành

Plan thi hành: `docs/plans/completed/2026-10-17-kriky-writes-every-word-plan.md` (đóng 17/10/2026,
sau một lượt thử tay mười ca trên Claude Haiku 5.5 —
`docs/testing/ket-qua/2026-10-17-02ba28a-claude-haiku-5-5.md`).

| Luật | Sống ở | Test canh |
|---|---|---|
| Code không đặt câu cố định vào lời Kriky; câu hệ thống chỉ đi dưới `kind="notice"` | `be/notices.py`; `teacher_chat._go`; `propose`; `handlers.propose_next_step`, `report_plan` | `check_kriky_says_nothing_fixed` (`tools/check_contract.py`), `test_a_fixed_sentence_in_kriky_s_mouth_is_caught` |
| Model hỏng, chạm trần, không kể lại được, plan cứ bị từ chối → thông báo hệ thống | `be/notices.py`; `handlers._MODEL_DOWN`, `propose._UNCLEAR` (`notice=True`); `teacher_chat._go` (`stuck`, `refused`) | `test_a_model_that_breaks_gives_a_system_notice_not_the_mock`, `test_the_ceiling_streams_a_notice_not_kriky_s_words`, `test_a_turn_that_only_hears_refused_plans_says_where_it_is_stuck`, `test_the_turn_survives_a_model_that_cannot_tell_what_happened` |
| Thông báo là một lượt riêng, không avatar; model đọc nó như ghi chú, nó không làm mất lời duyệt dàn ý | contracts `TurnRecord.kind`, `NextStepCompleted.notice`; FE `Chat.blocks`, `Notice`, `voiced`; `propose._compose`, `_approved_plan`; `teacher_chat._shown_outline` | `test_a_notice_from_the_agent_is_stored_as_a_system_notice`, *"thông báo hệ thống là một dòng riêng…"*, *"lượt đang chạy chỉ có thông báo hệ thống…"*, `test_a_system_notice_in_history_reads_as_a_note_not_as_kriky_s_words`, `test_an_agreement_retyped_after_a_system_notice_still_drafts` |
| Lời dàn ý là lời model, lên khung chat nguyên vẹn; BE chỉ trả về lời trống (hậu ký 20/10/2026) | `teacher_chat.outline_turn` | `test_a_message_that_drifts_from_its_outline_is_shown_as_kriky_wrote_it`, `test_an_empty_outline_message_still_goes_back_to_the_model`, `test_the_outline_shown_is_kriky_s_own_words_and_the_items_are_stored` |
| Lời mở plan là lời model, không thì không có | `propose._approved_plan`, `_choose` | `test_an_agreement_keeps_the_words_the_model_wrote_for_its_plan` |
| Câu hỏi sai điều sau danh sách tài liệu: hỏi model lại kèm lý do, không đè chữ | `propose._which_book`, `_asks_which_book`, `_WrongQuestion.hint` | `test_a_question_right_after_the_library_asks_which_document`, `test_a_question_still_off_the_second_time_keeps_the_model_s_words`, `test_a_question_about_which_document_is_told_apart` |
| Mọi lời Kriky dựng Markdown, toán dựng y như `MathText`, không HTML thô | FE `KrikyText` (`inline` → `span.line`) | `kriky-text.test.tsx` |
| Phần tử giao diện tất định: tên bước một nguồn, lúc chạy như sau F5 | FE `ActionCard.STEP_TITLE`, `titleOf`, `stepFor`; BE `TurnEvent.tool_name`, `result` | `test_a_lookup_before_the_plan_shows_while_it_runs`, *"bước tra cứu trước plan hiện lúc đang chạy…"* |
| **Chưa thi hành:** khung kèm học của học sinh — model hỏng thì `explain` vẫn lùi về lời giảng soạn sẵn | `handlers.explain` | — (đổi nó cần sửa hợp đồng và màn học sinh; ghi ở mục *Ngoài phạm vi* của plan) |

## Hậu ký 20/10/2026

Viết sau bốn vòng thử tay đầu-cuối trên Claude Haiku 5.5
(`docs/testing/ket-qua/2026-10-20-48919a3-dau-cuoi-claude-haiku-5-5.md`).

- **BE không đụng vào lời dàn ý nữa.** Phép đối chiếu nhẹ (`outline.check_message`) bị gỡ: lời Kriky
  lên khung chat đúng như model viết, kể cả khi không nhắc câu đầu của một mục, không lặp công thức,
  hay không kết bằng câu hỏi. Chỉ lời **trống** còn bị trả về — đó là một bong bóng rỗng, không phải
  một cách nói.
- **BE cũng thôi bắt hình dạng công thức** (ADR-29: *đúng một cặp `$`*). Công thức chỉ đi vào prompt
  soạn câu, nơi chữ quanh nó vẫn đọc được.
- **Vì sao.** Bốn vòng trả về 59 dàn ý, cả 59 vì hai luật này (50 vì hình dạng công thức, 9 vì đối
  chiếu); 21 lượt dừng ở thông báo *"Kriky chưa nêu được dàn ý…"*, và một vòng không qua được bước
  soạn đề. Giáo viên thấy một câu hệ thống thay cho lời Kriky: đúng thứ ADR này muốn bỏ.
- **Cái mất.** Lời có thể lệch các mục mà không gì bắt: nói *3 câu* trong khi các mục là 4. Job vẫn
  chỉ nhận các mục, và cổng duyệt đề (ADR-05) vẫn đứng trước học sinh, nên lệch lộ ra ở panel, nơi
  giáo viên sửa được. Mục *Quyết định* nói *"BE đối chiếu nhẹ"* và đoạn *Vì sao* về phép đối chiếu
  thôi áp dụng; phần còn lại giữ nguyên.
- **Luật còn sống ở `outline.validate`**: tổng 1–10 câu, mục có kiến thức và cách làm, mỗi phần tối
  đa 600 ký tự, tối đa 6 công thức mỗi mục và 200 ký tự mỗi công thức, `source_nodes` có thật.
