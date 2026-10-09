# ADR-17 — Ba vòng cho mỗi câu, và biến thể sinh ra từ chính câu đó

- **Trạng thái:** đã chốt, và đã thi hành ở backend (cập nhật 2026-10-10)
- **Ngày:** 2026-09-10

## Bối cảnh

[ADR-14](adr-14-hai-pha-lam-bai.md) bắt học sinh chữa những câu đã sai. Một vòng lặp bắt buộc phải có
lối ra, nếu không nó giam người ta lại.

`business-workflows.md` Workflow 5 khi đó mô tả vòng lặp dừng khi **đạt mastery**, không có trần số
vòng. `Mastery` chưa có công thức, chưa có dữ liệu, và `docs/plans/backlog.md` đã ghi nó bị chặn bởi
việc chưa có cơ sở dữ liệu — nên điều kiện dừng ấy hiện không tính được.

Câu hỏi thứ hai, độc lập: biến thể sinh ra **giống câu gốc tới mức nào**.
Lúc ấy `packages/contracts/src/contracts/messages.py` mang sẵn `learning_objective` cho đúng việc
này, và
docstring của nó nói biến thể giữ *cùng mục tiêu học tập*.

## Quyết định

- Mỗi câu sai sinh biến thể của **chính câu đó**, không phải một câu khác cùng mục tiêu học tập. Sai
  câu 3 thì sinh câu 3 phẩy; sai câu 7 thì sinh câu 7 phẩy.
- **Mỗi câu đếm vòng riêng**, tối đa **ba vòng**. Vòng của câu 3 và vòng của câu 7 không liên quan
  tới nhau.
- Một **lượt** gom mọi câu còn dở lại làm cùng lúc. Số câu trong một lượt giảm dần khi từng câu được
  chốt.
- Hết ba vòng mà vẫn sai thì câu đó **đóng lại ở 0 điểm**, và bài kết thúc bình thường.
- Điều kiện dừng là **số vòng**, không phải mastery.
- Biến thể **không phải bản sao của câu gốc**. Nó giữ nguyên **dạng đề và cách làm**, còn dữ kiện, con
  số và cách hỏi thì trợ lí đổi. Mỗi vòng là một **câu khác**, và học sinh nhìn thấy nó dưới tên
  *lượt làm lại thứ n*, không phải *câu 4* lần thứ hai.

## Vì sao

Biến thể của chính câu đó, chứ không phải câu khác cùng mục tiêu, vì thứ cần chữa là **một lỗi cụ thể
vừa xảy ra**, không phải một chủ đề. Một câu khác cùng learning objective có thể hỏng ở bước khác và
không chạm tới lỗi vừa mắc. Đổi dữ kiện và giữ nguyên cấu trúc là cách duy nhất kiểm được rằng học sinh
đã sửa đúng chỗ mình sai, chứ không phải nhớ được đáp án.

Trần ba vòng có lý do **sư phạm** làm gốc: sai ba lần cùng một dạng nghĩa là lỗ hổng nằm sâu hơn thứ
luyện tập chữa được. Em đó cần **người**, không cần thêm bài. Vòng thứ tư chỉ làm em nản, và làm hệ
thống trông như đang cố thắng một cuộc tranh cãi.

Chi phí sinh câu hỏi cũng đẩy về cùng con số, nhưng nó là **lý do phụ và không được dùng một mình**.
Nới trần lên bốn vì model rẻ đi thì phải trả lời trước câu hỏi sư phạm ở trên; siết xuống hai vì model
đắt lên thì đang lấy tiền đổi lấy cơ hội học của học sinh, và phải nói ra như vậy.

Số vòng thay cho mastery vì mastery **chưa tính được** và một điều kiện dừng không tính được là một
vòng lặp không có lối ra. Số vòng cũng có một tính chất mastery không có: học sinh **đếm được** và biết
mình còn mấy lần.

## Hệ quả

- **`Mastery` mất vai trò điều kiện dừng.** Nó vẫn nằm trong glossary nhưng không quyết định gì nữa —
  một khái niệm còn tên mà hết việc là thứ người đọc sau sẽ tưởng là đang chạy.
- **Trần ba vòng không răn đe.** Vì điểm phẳng ở 0,5 ([ADR-16](adr-16-thang-diem-ba-muc.md)), thử ở
  vòng một hay vòng ba tốn như nhau. Trần chỉ chọn thời điểm dừng, không tạo động cơ làm nghiêm túc.
- **Câu đóng ở 0 điểm là một tín hiệu bị bỏ rơi.** Ba lần sai cùng một lỗi là thứ giáo viên rất cần
  biết, nhưng không có chỗ nào nhận nó --- và hàng đợi review từng được tính tới thì đã bị bỏ hẳn:
  `services/be/src/be/review_policy.py` không còn tồn tại, và `needs_teacher_review` chỉ còn sống
  trong hai tệp test canh để **cấm** nó. Tín hiệu này vì thế vẫn chưa có nơi đi tới.
- **Bộ đếm vòng phải sống lâu hơn một phiên.** Học sinh chữa dở rồi quay lại thì hệ thống phải biết em
  đã dùng mấy vòng. Đây là trạng thái có nhớ, và nó đã có: `rounds_used` nằm trong database, không
  nằm trong kết quả job. Kết quả job vẫn hết hạn sau một giờ
  ([ADR-09](adr-09-ket-qua-cham-la-tam-thoi.md), `services/be/src/be/config.py:84`), nhưng `_harvest`
  (`services/be/src/be/student_routes.py:1458`) coi một câu trả lời đã mất là một cái kết bình thường
  và đẩy lại job khi cần.
- Vì vòng đếm theo **câu** còn đồng hồ đếm theo **lượt** ([ADR-15](adr-15-thoi-gian-pha-hai.md)), hai
  thứ này lệch nhịp. Hai ca từng chưa định nghĩa thì nay đều đã có câu trả lời, ở hai chỗ khác nhau.
  **Mở hai tab**: partial unique index `uq_one_open_round_per_attempt` cho mỗi Attempt nhiều nhất
  một lượt chưa nộp, nên một bên nhận lỗi toàn vẹn và `start_round` đổi nó thành 409. Bảo đảm ấy chỉ
  có trên database dựng từ model này: `create_all` không thêm index vào bảng đã có, và `check_schema`
  chỉ soi cột còn thiếu, không soi index (`packages/schema/src/schema/ddl.py`). **Tải lại trang**:
  `start_attempt` trả lại chính Attempt đang dở, `remediation_panel` trả `open_round_id` nên màn hình
  quay về lượt đang mở, và `ends_at` đã ghim từ lúc `start_round` nên reload không nới đồng hồ.
- Biến thể phải giữ **cùng cấu trúc câu gốc**, nên nó cũng cần lời giải và ánh xạ nhiễu tương ứng
  ([ADR-18](adr-18-cau-hoi-phai-kem-loi-giai.md)) — mà không ai duyệt nó
  ([ADR-05](adr-05-ba-cong-teacher-in-the-loop.md)).
- **Màn kết quả phải in đề của từng lượt, không chỉ đề pha 1.** Vì mỗi lượt là một câu khác, một bảng
  điểm chỉ hiện câu gốc thì không nói được học sinh đã làm đúng *cái gì* để lên 0,5 — con số trở thành
  một tuyên bố không kiểm được. Đây là lý do hàng `Mức=0,5` và `Mức=0` mang theo đề của từng lượt.

## Nơi luật này đang được thi hành

**Ở backend, và ở Figma phần nhìn thấy được.**

- **Ở Figma**: trang `Screen — Student` có `17 · Hỏi trợ lý và làm lại dạng bài sai`,
  `19 · Bắt đầu lượt chữa` và `21 · Làm câu của lượt làm lại`; `Round gate` có hàng *Vòng —
  vòng 1, mỗi câu còn 3 vòng*, đầu màn `21` ghi *Lượt làm lại thứ 1 / tối đa 3*, và `Result row` in
  đề của từng lượt kèm kết quả từng lượt. Chữ trên màn dùng *lượt làm lại thứ n*, không dùng *biến thể* —
  *biến thể* là từ của tài liệu này, không phải từ nói với học sinh.
- **Ở contract, nợ đã trả**: `packages/contracts/src/contracts/messages.py` không còn tồn tại, và
  `GradingRequested` cũng không còn trong code. Docstring nay nói đúng luật này:
  `packages/contracts/src/contracts/authoring.py:64` ghi rằng `learning_objective` được chở theo
  *để báo cáo*, và **không** phải là thứ làm cho một câu hỏi thử lại thành câu hỏi thử lại.
- **Ở backend**: bộ đếm vòng là `rounds_used` (`packages/schema/src/schema/models.py:365`), với trần
  ba vòng ép ở `services/be/src/be/scoring.py:12` và đọc ở `:62`. Khái niệm lượt là `RemediationRound`
  (`models.py:369`, bảng `rounds`), với `start_round` (`services/be/src/be/student_routes.py:1866`),
  `save_round_answer` (`:2052`) và `submit_round` (`:2095`) --- chính `submit_round` là nơi một lượt
  được chấm và câu được đóng. Biến thể được **lưu** ở `RoundItem` và `PregeneratedItem`, cả hai chở
  `origin_question_id`; chỗ **sinh** là `ask_for_retry_question`
  (`services/be/src/be/agent_gateway.py:293`).
- **Phần chưa có lưới**: luật duy nhất được ép trên một biến thể là *stem phải khác* --- `validate_retry`
  (`agent_gateway.py:444-463`) so stem với câu gốc và với các stem đã dùng. Nửa còn lại của quyết định
  trên đây, *giữ nguyên dạng đề và cách làm*, không được kiểm ở đâu cả.
- `docs/overview/business-workflows.md` Workflow 5 và `use-case-specification.md` UC-06 đã viết lại
  theo trần ba vòng, và `Mastery` trong glossary đã được ghi rõ là không còn quyết định gì.
