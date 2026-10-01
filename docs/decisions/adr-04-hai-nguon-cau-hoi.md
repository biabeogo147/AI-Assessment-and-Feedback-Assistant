# ADR-04 — Câu hỏi chỉ có hai nguồn; tài liệu là phạm vi, không phải nguồn

- **Trạng thái:** đã chốt (ngoại lệ về câu luyện tập: chưa thi hành)
- **Ngày:** 2026-09-06

## Bối cảnh

Khi thêm khả năng kèm tài liệu PDF, thiết kế ban đầu coi tài liệu là **nguồn thứ ba** của câu hỏi,
ngang hàng với ngân hàng câu hỏi và câu do Kriky soạn. Đó là hiểu sai bản chất, và nó đã lan vào ba chỗ
trước khi bị bắt.

## Quyết định

- **Luật này áp cho câu hỏi trong đề.** Câu luyện tập sinh ra ở pha 2 là ngoại lệ; xem cuối mục này.
- Câu hỏi chỉ đến từ **hai** nguồn: **ngân hàng câu hỏi**, hoặc **Kriky soạn mới**.
- **Tài liệu PDF không phải một nguồn.** Nó cung cấp kiến thức và **giới hạn phạm vi** ra đề. Nó không
  chứa câu hỏi.
- Câu Kriky soạn có hai trạng thái kiểm: **chưa kiểm** và **đã kiểm**. **Giáo viên** là người chuyển,
  bằng một thao tác trên chính câu hỏi đó. Duyệt cả đề **không** tự đánh dấu đã kiểm cho từng câu.
- **Tài liệu thuộc về giáo viên**, không thuộc về từng đề. Một cuốn sách dùng cho nhiều đề suốt học kỳ.
- Ba mức nguồn dùng ba màu đối nhau: ngân hàng **xám trung tính**, đã kiểm **xanh**, chưa kiểm
  **hổ phách**.
- **Ngoại lệ — câu luyện tập ở pha 2.** Câu biến thể sinh ra theo
  [ADR-17](adr-17-ba-vong-moi-cau.md) là câu Kriky soạn, tới thẳng tay học sinh, và **không ai đánh
  dấu đã kiểm cho nó** — nó vĩnh viễn ở trạng thái *chưa kiểm*. Luật hai trạng thái kiểm ở trên vì
  thế không áp cho nó. Ba đường xử lý đang cân nhắc nằm ở `docs/plans/backlog.md`.

## Vì sao

Coi tài liệu là nguồn làm hỏng hai thứ cùng lúc. Nó **giấu mất việc chưa ai kiểm câu hỏi đó** — một câu
sinh từ sách vẫn là câu Kriky viết, chưa người nào đọc qua. Và nó khiến "truy vết được" mất nghĩa: chỉ
về một trang sách không phải là chỉ về nơi câu hỏi đến từ đó.

Trạng thái kiểm phải có **hai** giá trị. Chỉ có "chưa kiểm" thì giáo viên không có cách nào đánh dấu
mình đã xem — và cổng duyệt mất tác dụng vì không lưu lại được việc gì đã làm.

Màu xám cho ngân hàng là có chủ ý: câu lấy từ ngân hàng là **mặc định, không cần chú ý**. Nếu nó cũng
xanh như "đã kiểm" thì hai thứ khác hẳn nhau về trách nhiệm lại trông giống nhau.

Tài liệu thuộc về giáo viên vì đó là quyết định **mô hình dữ liệu**: quan hệ là Document ↔ Teacher, chứ
không phải Document ↔ Assessment. Đề chỉ tham chiếu tới tài liệu.

Câu luyện tập là ngoại lệ vì nó **sinh ra khi học sinh đang ngồi đó**, và không ai chờ được một thao
tác của giáo viên ở giữa. Đó là lý do cơ học, không phải lý do nguyên tắc — và vì thế nó là một lỗ
chứ không phải một thiết kế. Ba đường bịt lỗ đang cân nhắc nằm ở `docs/plans/backlog.md`.

## Hệ quả

- Mỗi câu Kriky soạn cần một thao tác đánh dấu riêng, nên duyệt một đề mười câu có thể tốn mười thao
  tác nữa. Đó là cái giá phải trả để "đã kiểm" có nghĩa.
- Vì có một loại câu **không bao giờ được kiểm**, nhãn *chưa kiểm* mất đi tính tạm thời của nó. Ở đề
  thì nó nghĩa là *chờ giáo viên xem*; ở pha 2 thì nó nghĩa là *sẽ không ai xem*. Cùng một chữ, hai
  nghĩa, và giao diện phải phân biệt được nếu bao giờ bày cả hai.
- Bong bóng hỏi lại **không được** xếp tài liệu ngang hàng với ngân hàng như một lựa chọn nguồn. Nói
  "Kriky soạn, giới hạn trong sách X", không nói "soạn từ sách X".
- Thư viện tài liệu sống ở rail trái, không nằm trong panel đề.
- Phạm vi ra đề chỉ tới cấp chương và khoảng trang, và phải đổi được.
- Bốn khái niệm `Class`, `Question Bank`, `Document`, `Scope` phải giữ đúng nghĩa này ở mọi nơi; chúng
  đã được thêm vào glossary của `docs/overview/project-overview.md`.

## Nơi luật này đang được thi hành

- Figma `mOe2ZmrqOq1Uix45v6PNGD`, `Source citation` (`84:35`) — ba variant `ngân hàng`, `chưa kiểm`, `đã kiểm`, và mô tả
  component ghi thẳng luật về ba màu đối nhau.
- Figma `Document chip` (`84:25`) — mô tả ghi tài liệu thuộc về giáo viên.
- Figma `Clarify request` (`64:23`) — ba lựa chọn dựng theo hai nguồn.
- Figma artboard `2 · Kèm tài liệu, giới hạn phạm vi` — thanh phạm vi, nay chỉ còn **tên file**:
  *"chương 1, trang 30-62"* hứa một phạm vi không có gì thi hành, nên nó đã bị gỡ khỏi thiết kế.
- **Ngoại lệ về câu luyện tập: chưa thi hành ở đâu cả.** `Source citation` (`84:35`) có ba variant và
  không variant nào dành cho một câu **sẽ không bao giờ được kiểm** — nhãn *chưa kiểm* ở đó nghĩa là
  *đang chờ giáo viên xem*, một nghĩa không đúng cho câu biến thể.
- `services/be/src/be/models.py` — bảng `documents` gắn `teacher_id`, **không** gắn `assessment_id`:
  một cuốn sách dùng cho nhiều đề suốt học kỳ. `services/be/src/be/teacher_documents.py` tải lên và
  liệt kê.
- **Frontend hiện *giả vờ* thi hành phần nguồn câu hỏi.** `Question` có năm cột và không cột nào nói
  nguồn hay trạng thái kiểm, nên ba cái chip trên panel là **chữ bịa**, dồn vào
  `services/fe/src/screens/teacher/invented-not-from-be.ts` và canh bằng
  `check_invented_data_lives_in_one_file`. Màn hình đang nói với giáo viên một điều hệ thống không
  biết là đúng; `docs/plans/backlog.md` giữ món nợ ấy.
- **Nội dung tài liệu vẫn chưa đi vào prompt của AGENT.** Tải lên được, liệt kê được, đính được —
  nhưng chưa có gì mở file ra đọc, nên tài liệu chưa thật sự giới hạn phạm vi ra đề. Vì thế chip
  tài liệu in **kích thước** chứ không in số trang.
- **Chưa có ở backend**: không có model QuestionBank nào.
