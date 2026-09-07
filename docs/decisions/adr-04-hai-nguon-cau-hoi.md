# ADR-04 — Câu hỏi chỉ có hai nguồn; tài liệu là phạm vi, không phải nguồn

- **Trạng thái:** đã chốt
- **Ngày:** 2026-09-06

## Bối cảnh

Khi thêm khả năng kèm tài liệu PDF, thiết kế ban đầu coi tài liệu là **nguồn thứ ba** của câu hỏi,
ngang hàng với ngân hàng câu hỏi và câu do Kriky soạn. Đó là hiểu sai bản chất, và nó đã lan vào ba chỗ
trước khi bị bắt.

## Quyết định

- Câu hỏi chỉ đến từ **hai** nguồn: **ngân hàng câu hỏi**, hoặc **Kriky soạn mới**.
- **Tài liệu PDF không phải một nguồn.** Nó cung cấp kiến thức và **giới hạn phạm vi** ra đề. Nó không
  chứa câu hỏi.
- Câu Kriky soạn có hai trạng thái kiểm: **chưa kiểm** và **đã kiểm**. **Giáo viên** là người chuyển,
  bằng một thao tác trên chính câu hỏi đó. Duyệt cả đề **không** tự đánh dấu đã kiểm cho từng câu.
- **Tài liệu thuộc về giáo viên**, không thuộc về từng đề. Một cuốn sách dùng cho nhiều đề suốt học kỳ.
- Ba mức nguồn dùng ba màu đối nhau: ngân hàng **xám trung tính**, đã kiểm **xanh**, chưa kiểm
  **hổ phách**.

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

## Hệ quả

- Mỗi câu Kriky soạn cần một thao tác đánh dấu riêng, nên duyệt một đề mười câu có thể tốn mười thao
  tác nữa. Đó là cái giá phải trả để "đã kiểm" có nghĩa.
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
- Figma artboard `2 · Kèm tài liệu, giới hạn phạm vi` — thanh phạm vi *"chương 1, trang 30-62"*.
- **Chưa có ở backend**: không có model Document, Class hay QuestionBank nào.
