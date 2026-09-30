# ADR-23 — Không phân định được thì hỏi lại, và lựa chọn phải đến từ dữ liệu

- **Trạng thái:** đã chốt
- **Ngày:** 2026-09-30

## Bối cảnh

Platform giáo viên nhận việc bằng tiếng người: *"lớp 12A làm bài hôm qua thế nào"*. Nhưng mọi tool
đều cần `class_id`, và `classes.name` **không unique** — một giáo viên có thể có hai lớp cùng tên
12A qua hai năm, hai giáo viên có thể mỗi người một lớp 12A. Xem
[ADR-22](adr-22-de-co-tac-gia.md).

Nghĩa là **tên lớp không phải định danh**, và bước dịch từ chữ sang id là nơi cả bề mặt giáo viên
hoặc hỏi lại, hoặc đoán.

Đoán là thất bại tệ nhất trong các thất bại có thể xảy ra ở đây: agent sẽ đọc điểm của **lớp khác**
rồi trả lời hoàn toàn tự tin, và không có gì trên màn hình nói rằng nó vừa nhầm lớp.

[ADR-05](adr-05-ba-cong-teacher-in-the-loop.md) đã chốt cổng thứ ba — *agent hỏi lại khi chưa đủ
thông tin* — nhưng chưa nói cổng đó được thi hành ở đâu. ADR này trả lời.

## Quyết định

Bước giải nghĩa có **đúng ba** kết quả, không có kết quả thứ tư:

- **Phân định được** — đúng một lớp của giáo viên đó khớp.
- **Nhiều khả năng** — vài lớp có thể là nó. Trả về **tất cả** kèm số học sinh, và hỏi lại.
- **Không tìm thấy** — không lớp nào khớp, kèm danh sách lớp giáo viên đó **có**.

Và ba luật đi cùng:

- **Không có đường nào chọn một trong nhiều.** Không lấy hàng đầu, không lấy hàng mới nhất, không
  lấy hàng đông học sinh nhất.
- **Lựa chọn trong câu hỏi do hệ thống dựng, không do model viết.** Model viết câu hỏi; danh sách
  đáp án dựng từ chính các hàng đã đọc, gồm cả sĩ số. `choices` model trả về bị **bỏ qua**.
- **Khớp chính xác thắng khớp một phần.** "12A" phân định được ngay cả khi tồn tại 12A1.

## Vì sao

**Vì sao trả về cả số học sinh.** Một câu hỏi đưa ra hai lựa chọn cùng tên "12A" là câu hỏi không
trả lời được. Sĩ số là chi tiết nhỏ nhất phân biệt được hai lớp mà giáo viên nhận ra ngay.

**Vì sao hệ thống dựng lựa chọn, chứ không lọc chữ model viết.** Một tên lớp do model bịa ra sẽ
hiện trước mặt giáo viên **kèm theo thẩm quyền của hệ thống**. Họ bấm vào nó, và họ bấm vào một thứ
không tồn tại.

Bản đầu tiên đi đường lọc, và nó **rò cả hai chiều** — đo được, không phải đoán. Với lớp thật duy
nhất là `12A`: `12A-1`, `12A.1`, `12A_1`, `12A, 11C` và `12A (45 học sinh)` đều **lọt**, trong khi
`12A 3 học sinh` và `11C hoặc 12A` bị **bỏ oan**. `12A-1` là ca tệ nhất: một tên lớp Việt Nam hoàn
toàn hợp lý, lệch tên thật đúng một dấu gạch, tức là cái tên giáo viên sẽ không bao giờ đặt câu hỏi.
Và **sĩ số không đi qua phép lọc nào cả**, nên `12A (45 học sinh)` qua được trong khi lớp thật có 3
em — làm hỏng đúng thứ mục trên vừa dựa vào để phân biệt hai lớp cùng tên.

Cả lớp lỗi ấy biến mất cùng lúc khi **không còn chữ tự do nào để kiểm**.

**Vì sao khớp chính xác phải thắng.** Khớp một phần là thứ làm cho "12" có nghĩa là *một trong 12A và
12B*, và cũng chính là thứ sẽ làm "12A" thành mơ hồ ngay khi có lớp 12A1. Thử chính xác trước giữ
được cả hai.

**Vì sao danh sách lớp đi kèm lời từ chối.** *"Không có lớp nào tên đó"* để giáo viên không biết mình
gõ sai hay dữ liệu đã mất. Danh sách biến lời từ chối thành câu trả lời cho câu hỏi kế tiếp.

## Hệ quả

- Luật *"mỗi lựa chọn tự nêu cái giá của nó"* của ADR-05 **không áp** ở đây. Luật đó viết cho quyết
  định **sư phạm** — chọn nguồn câu hỏi, chọn độ khó — nơi mỗi phương án có một cái giá. Phân định
  tên lớp không có giá nào để nêu, chỉ có *lớp nào*. Phần **cấm đánh dấu phương án nên chọn** thì áp
  đầy đủ.
- Số lựa chọn phải có trần. Một giáo viên ba mươi lớp cần một câu hỏi trả lời được, không cần một
  danh sách phải đọc.
- Danh sách ứng viên phải có **thứ tự ổn định**. Một câu hỏi mà các phương án đổi chỗ giữa hai lần
  hỏi là câu hỏi không trả lời được hai lần.
- Mọi thứ trả lên phải là **giá trị**, không phải hàng ORM: vòng lặp tool `rollback()` giữa các bước
  để nhả connection, và rollback làm expire mọi object của session.
- Chữ "lớp" trong tên phải bị bóc, và **"ơ" (U+01A1) khác "ớ" (U+1EDB)** — một character class
  `[oơ]` trông như phủ được chữ "lớp" mà lặng lẽ không phủ.
- Bóc chữ "lớp" là chưa đủ: giáo viên viết cả `Lớp: 12A` và `lớp12A`, nên dấu phân cách sau nó phải
  tuỳ chọn. Và tên phải được chuẩn hoá về **NFC** trước khi so — macOS gửi dạng phân rã, nên "lớp"
  có thể tới dưới dạng `l` + `o` + U+031B + `p` và so khác với chính nó.
- Chuẩn hoá xoá hết khoảng trắng, nên hai lớp tên `12A` và `12 A` trở thành cùng một chuỗi và sẽ
  **mơ hồ vĩnh viễn**. Vì thế phải thử **đúng chính tả đã lưu trước**, trước khi chuẩn hoá: đó là
  cửa duy nhất để chọn được một trong hai mà không phá luật không-đoán.
- Trần `_MOST_CANDIDATES = 6` không phải "ba lựa chọn" như bong bóng hỏi lại của ADR-05 mô tả. Con
  số ba viết cho một quyết định sư phạm có ba hướng; phân định tên lớp thì số ứng viên do dữ liệu
  quyết định, và cắt xuống ba sẽ giấu mất lớp giáo viên đang cần. Ai đó dựng UI phải biết là có thể
  nhận tới sáu.

## Nơi luật này đang được thi hành

- `services/be/src/be/resolve.py` — `resolve_class()` trả `Resolved | Ambiguous | NotFound`, không có
  nhánh nào chọn một trong nhiều. `_MOST_CANDIDATES = 6` là trần; `order_by(name, id)` là thứ tự ổn
  định; `normalise()` chuẩn hoá NFC rồi bóc chữ "lớp" — đủ mười bảy biến thể dấu của nguyên âm, kèm
  dấu phân cách tuỳ chọn. Chưa phủ mọi cách gõ tưởng tượng được, nhưng phủ những cách đã thử.
- `services/be/src/be/teacher_tools.py` — `_find_class` chuyển ba kết quả đó thành ba hình dạng dữ
  liệu cho model đọc, gồm `candidates` và `your_classes`.
- `services/be/src/be/teacher_chat.py` — `_offered()` dựng danh sách lựa chọn từ `candidates` của
  kết quả tool, kèm sĩ số BE tự đếm; `choices` model trả về bị bỏ qua và chỉ được ghi log. Đây là
  chỗ luật *lựa chọn đến từ dữ liệu* được thi hành, chứ không phải trong prompt.
- `AGENTS.md` bảng Invariants — hàng *"The options in a clarifying question are written by BE from
  rows it read"*, trỏ tới `test_the_options_are_written_by_be_not_by_the_model`.
- `services/agent/src/agent/graphs/propose.py` — `_SYSTEM` bảo model dùng `ask_clarify` khi tool trả
  `ambiguous`, đưa đúng các `candidates`, và không nói lớp nào có vẻ đúng hơn.
- `services/be/tests/test_resolve.py` — chín test, mỗi luật ở trên một test. Trong đó
  `test_another_teachers_class_is_answered_as_if_it_did_not_exist` giữ ADR-22, và
  `test_an_exact_name_wins_over_a_longer_one_containing_it` giữ thứ tự thử.
- `services/be/tests/test_teacher_chat.py::test_the_options_are_written_by_be_not_by_the_model` —
  model trả ba lựa chọn sai theo ba cách khác nhau (sĩ số sai, tên lệch một dấu gạch, lớp không tồn
  tại) và không cái nào tới được giáo viên.
- **Chưa thi hành:** chưa có bề mặt nào hiện các lựa chọn ấy, và endpoint chat **chưa lưu hội thoại**
  nên câu trả lời của giáo viên tới mà không mang theo câu hỏi. Cổng đã dựng, nửa sau của nó nằm ở
  bảng hội thoại bền.
