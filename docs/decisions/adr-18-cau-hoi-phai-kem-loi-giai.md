# ADR-18 — Mỗi câu hỏi phải kèm lời giải nhiều cách, và mỗi phương án nhiễu gắn một lỗi

- **Trạng thái:** đã chốt (chưa có ở backend)
- **Ngày:** 2026-09-10

## Bối cảnh

Pha 2 ([ADR-14](adr-14-hai-pha-lam-bai.md)) đòi trợ lí **giải thích lỗi sai** cho học sinh rồi **dạy
lại**. Muốn làm được việc đó, nó phải biết hai thứ: học sinh sai vì cái gì, và cách làm đúng là gì.

Hôm nay nó không biết cả hai. `business-workflows.md` Workflow 3 bước 4 nói khi không có lời giải
thích thì hệ thống **dự đoán** lỗi sai dựa trên distractor, lịch sử học tập và ngữ cảnh — mà lịch sử
học tập thì chưa tồn tại. `services/agent/src/agent/handlers.py` phản ánh đúng tình trạng ấy: khi
không có phần giải thích, nó hạ `confidence` xuống 0,55; và với mọi đáp án sai, nó sinh
`misconception_code` suy ra thẳng từ mã phương án đã chọn.

Đoán sai lỗi rồi đi giải thích một lỗi học sinh không mắc thì **tệ hơn im lặng**.

## Quyết định

- Mỗi câu hỏi, ở cả hai nguồn theo [ADR-04](adr-04-hai-nguon-cau-hoi.md), phải mang theo **lời giải**,
  và lời giải đó phải có **nhiều hơn một cách làm**.
- Mỗi **phương án nhiễu** phải mang theo **lỗi mà nó đại diện**. Ánh xạ này được soạn cùng câu hỏi,
  không suy ra lúc chấm.
- **Số phương án không cố định.** Một câu có thể có ba, bốn, năm lựa chọn — bao nhiêu tuỳ câu — nhưng
  **đúng một** trong số đó là đáp án đúng. Mọi phương án còn lại là nhiễu, nên mọi phương án còn lại
  đều phải có lỗi gắn kèm.
- Trợ lí ở pha 2 **đi theo lời giải và ánh xạ đã có**. Nó không tự nghĩ ra cách làm mới và không tự
  đoán lỗi.
- Lời giải và ánh xạ là **một phần của nội dung đề**, nên chúng bị khoá khi giáo viên duyệt, đúng như
  câu hỏi. Xem [ADR-01](adr-01-vong-doi-de-kiem-tra.md).

## Vì sao

Với trắc nghiệm, phần chấm là một phép so và không có gì để mà không chắc. Thứ **thật sự** không chắc
là chẩn đoán: cùng một phương án nhiễu có thể do ba lỗi khác nhau. Soạn sẵn ánh xạ biến chẩn đoán từ
**suy đoán** thành **tra cứu** — và làm điều đó ở chỗ đúng, tức là lúc soạn đề, nơi có người biết môn
học đang ngồi.

Nhiều cách làm, vì một cuộc giải thích chỉ có một cách thì không đi đâu được khi học sinh nói *em vẫn
chưa hiểu*. Nhiều cách cho hội thoại một chỗ để bước tiếp thay vì lặp lại to hơn. Nó cũng tránh việc
dạy lại một em bằng đúng con đường em vừa đi hỏng.

**Đây là chỗ luật này va vào nguyên tắc lõi, và phải nói ra.**
[ADR-06](adr-06-agent-phat-bang-chung.md) viết *cả sản phẩm sống bằng việc thú nhận giới hạn*. Ánh xạ
soạn sẵn là ánh xạ **một-một**: chọn nhiễu B thì hệ thống tuyên bố lỗi B, với giọng chắc nịch, kể cả
khi em chọn B vì một lý do khác hẳn. Đổi lại sự chắc chắn ấy, sản phẩm **mất khả năng nói tôi không
chắc** đúng ở chỗ nó đang nói chuyện với học sinh.

Chấp nhận đánh đổi này vì phương án còn lại tệ hơn theo cách đo được: giữ chẩn đoán bằng suy đoán
nghĩa là ngưỡng tin cậy hiện tại đẩy **mọi câu của mọi em** vào hàng đợi giáo viên, và pha 2 không
khởi động cho ai (xem `docs/plans/backlog.md`). Một chẩn đoán do người soạn đề viết ra sai ít hơn một
chẩn đoán do máy đoán. Nhưng nó **không phải không sai**, và mục *Hệ quả* nói cái giá.

## Hệ quả

- **Cổng duyệt của giáo viên nặng hơn hẳn.** Duyệt một đề nay là duyệt cả lời giải và ánh xạ nhiễu.
  Và **lời giải khó duyệt hơn câu hỏi**: một câu hỏi sai thì đọc là thấy, một lời giải sai tinh vi thì
  phải làm thử mới thấy.
- **Lời giải sai bị khuếch đại.** Một câu hỏi sai làm hỏng một câu; một lời giải sai được **dạy lại**
  cho mọi em sai câu đó, cùng lúc. Sai sót ở nội dung không còn tỉ lệ với số người gặp nó.
- **Câu đúng ở pha 1 không bao giờ kiểm được lời giải của nó**, vì nó không vào pha 2. Lời giải sai chỉ
  lộ ra qua chính những em bị dạy lại bằng nó.
- **Ngân hàng câu hỏi hiện có không đủ tiêu chuẩn.** Mọi câu đã lưu trước luật này đều thiếu lời giải
  và thiếu ánh xạ, nên chưa dùng được ở pha 2.
- **Chi phí soạn đề đi theo số phương án, không theo số câu.** Vì mỗi nhiễu cần một lỗi, một câu năm
  lựa chọn tốn gấp rưỡi một câu ba lựa chọn. Ai định nới số phương án để đề khó hơn thì đang nới cả
  phần việc của người duyệt.
- **Soạn một câu hỏi đắt hơn nhiều.** Trước đây là đề bài, các phương án và đáp án; nay thêm nhiều
  cách giải và một lỗi cho từng nhiễu. Điều này áp cho cả câu Kriky soạn lẫn câu giáo viên tự viết.
- Sản phẩm **không còn bề mặt nào để nói tôi chưa chắc lỗi của em là gì**. Nếu sau này chẩn đoán quay
  lại có độ tin cậy, bề mặt ấy phải được dựng lại từ đầu.

## Nơi luật này đang được thi hành

- Figma `Question card` (`267:30`) — một variant `Lời giải=thu gọn`, với khung `options` **năm ô**;
  mỗi instance ẩn bớt ô thừa, nên artboard 7 có câu ba lựa chọn, câu bốn và câu năm cạnh nhau. Đáp án
  đúng đánh dấu bằng **một dấu ✓**, không kèm chữ. Mười thẻ trên artboard 6 và 7 là instance của
  component này; trước đó là mười frame dựng tay.
- **Bề mặt sửa của giáo viên, từ 06/10/2026**: Figma `Question card — đang sửa` (`468:2050`) có một
  `radio` 14px ở đầu mỗi `option-head`, và `Panel.tsx` dựng nó thành một nhóm `<input type="radio">`
  chung `name` theo `question_id`. Đây là nơi luật *đúng một đáp án đúng* được thi hành ở tầng người
  dùng — trước đó phương án đúng chỉ có một cái nhãn và không control nào, nên một câu model đánh
  dấu sai đáp án là một câu **không ai sửa được**, dù cả ba cổng người của ADR-05 đều mở.
  Nhóm radio **không** tự giữ luật: `checked` đi từ state, nên `onChange` mới là chỗ bỏ cờ cũ, và
  test *"payload có ĐÚNG MỘT đáp án đúng"* trong `teacher.test.tsx` là lưới của nó.
- **Và luật *mọi nhiễu có nhãn lỗi* được nói trước cú bấm**: `Editing` khoá nút *Lưu* kèm một câu
  tiếng Việt khi còn nhiễu nào chưa có nhãn. Không có nó thì đổi đáp án đúng là một đường dẫn thẳng
  tới 422, và lời từ chối về là `distractors ['A'] carry no error label: <cả đề bài>` — tiếng Anh,
  kèm `repr` của một list Python.
- Figma `Solution dialog` (`309:41`) trên artboard `12 · Xem lời giải một câu` — hai cách giải và bảng
  ánh xạ nhiễu→lỗi nằm trong một hộp thoại, **không mở bung trong thẻ**. Mở bung đẩy chín thẻ còn lại
  ra khỏi tầm nhìn của người đang duyệt, mà duyệt là việc so sánh giữa các câu.
- **Học sinh đọc cùng hộp đó**, trên artboard `18 · Xem lời giải đầy đủ`, mở từ từng câu sai ở panel
  màn `17`. Bản học sinh đổi nhãn bảng nhiễu thành *Vì sao các phương án khác sai* — *mỗi phương án
  nhiễu gắn một lỗi* là chữ của người soạn đề.
- **Luật một đáp án đúng vừa bắt được một lỗi trong chính dữ liệu mẫu**: câu mẫu số 4 hỏi hàm đồng
  biến trên khoảng nào, mà cả `(−∞; −1)` lẫn `(1; +∞)` đều đúng. Phương án D đổi thành `(−2; 0)` —
  khoảng chứa cả phần tăng lẫn phần giảm. Một bộ phương án có hai đáp án đúng thì ánh xạ nhiễu→lỗi
  **không viết được**, nên lỗi này lộ ra ở đúng chỗ nó phải lộ.
- **Chưa có gì ghi nhận giáo viên đã đọc lời giải.** Đây là lỗ do chính ADR này tạo ra; xem
  `docs/plans/backlog.md`.
- **Chưa có ở contract**: `packages/contracts` có `question_id` nhưng không có **model** câu hỏi, nên
  chưa có chỗ nào để gắn lời giải vào.
- `docs/overview/business-workflows.md` Workflow 3 đã đổi *dự đoán* thành **tra cứu**, và distractor
  từ *nên* thành **phải**.
- **Đang bị vi phạm ở code**: `services/agent/src/agent/handlers.py` vẫn suy `misconception_code` từ
  mã phương án chứ không tra một ánh xạ đã soạn. Sửa code chưa lên lịch; xem `docs/plans/backlog.md`.
