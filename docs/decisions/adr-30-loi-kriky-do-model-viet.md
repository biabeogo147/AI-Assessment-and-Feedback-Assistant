# ADR-30 — Lời Kriky do model viết, bằng Markdown

- **Trạng thái:** đã chốt, chưa thi hành
- **Ngày:** 2026-10-17

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
  của nó; và lời có một câu hỏi. Lệch thì lý do về model và model viết lại trong cùng lượt; lệch mãi
  thì lượt chạm trần bước, và đó là ngoại lệ 1. Kiến thức, cách làm và tên bài **không** cần giống
  từng chữ.
- **Ngoại lệ 1 — khi model không trả lời được**: model hỏng hai lần liền, lượt chạm trần bước, lượt
  gãy giữa chừng, không với tới AGENT, hay đoạn chat đang chạy một việc khác. Lúc ấy hệ thống nói,
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

Plan thi hành: `docs/plans/active/2026-10-17-kriky-writes-every-word-plan.md`. Bảng điền khi plan đóng.
