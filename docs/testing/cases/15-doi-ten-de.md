# 15. Đổi tên đề

Nhóm: Panel đề · Lượt model: ~1 (phần A, B: 0) · Chạy sau: 14 (trên đoạn chat của 04)

## Cho người xem thấy gì

Giáo viên đặt lại tên đề ngay ở tiêu đề panel, và tên mới hiện ở **mọi chỗ** — kể cả các thẻ cũ
trong đoạn chat và trí nhớ của Kriky — chứ không chỉ ở chỗ vừa sửa. Tên có trần 60 ký tự, và đề đã
duyệt thì khoá cả tên (ADR-31).

## Chuẩn bị

- Chạy **sau cùng**, tiếp trên **đoạn chat của case 04, 06, 14**: đề theo sách, chưa duyệt, tên
  `Đề Kết nối tri thức Lớp 6 tập 1 (tr6-28)`. Chạy cuối vì các case trước lọc database theo tên đề.
- Đoạn chat có ít nhất hai thẻ `Đã tạo đề` (case 04 và 06). Bấm thẻ cuối để mở panel; chép `<CID>`
  và `<id>` từ địa chỉ `#/teacher/chat/<CID>/de/<id>`.
- Không đính chip.

## Lời chat

**Phần A — đổi tên, không gõ chat.**

A1. Ở tiêu đề panel, bấm `Đổi tên`. Ô nhập điền sẵn tên hiện tại.
A2. Bấm `Huỷ` (hay Esc): tiêu đề về như cũ, không gì đổi.
A3. Bấm `Đổi tên` lần nữa, xoá hết, dán đúng chuỗi 72 ký tự này:

```
Kiểm tra chương I số tự nhiên lớp 6 tập hợp cách ghi số và thứ tự số nhé
```

A4. Đọc ô và bộ đếm. Xoá hết, gõ tên mới rồi Enter:

```
Kiểm tra 15 phút — Số tự nhiên
```

**Phần B — khoá theo trạng thái.**

B1. Ở chân panel bấm `Duyệt đề`. Panel sang cài đặt phát hành; đọc tiêu đề panel.
B2. Bấm `Hoàn tác`. Panel về nội dung đề; đọc tiêu đề panel.

**Phần C — Kriky biết tên mới.** Gõ vào ô chat chính:

```
đề mình vừa làm giờ tên là gì nhỉ?
```

## Nếu Kriky rẽ

| Kriky làm gì | Trả lời / phán | Vì sao |
| --- | --- | --- |
| Ô nhập ở A3 nhận đủ 72 ký tự | Bấm `Lưu`, ghi câu lỗi. **Không đạt** | `maxLength` 60 chặn ở ô; BE từ chối 422 là lưới thứ hai |
| Thẻ cũ chưa đổi tên ngay sau A4 | F5. Đúng sau F5: **chấp nhận được**. Vẫn tên cũ: **không đạt** | Lưu xong FE đọc lại đoạn chat; thẻ đọc tên hiện tại của đề |
| B1 vẫn còn nút `Đổi tên` | **Không đạt** | Đề đã duyệt khoá tên cùng nội dung (ADR-01, ADR-31) |
| Phần C Kriky tra đề (`list_assessment`) rồi nói tên mới | **Đạt** | Tool đọc tên trong database |
| Phần C Kriky nói tên cũ `Đề Kết nối tri thức…` | **Không đạt** | BE thay tên ở lịch sử gửi AGENT bằng tên hiện tại |
| Phần C Kriky hỏi lại "đề nào?" | Gõ `đề theo sách lớp 6 ấy`. **Chấp nhận được** nếu lượt sau nói tên mới | Thừa một lượt; đoạn chat chỉ có một đề |

## Đạt khi

- **A1:** tiêu đề thành ô nhập viền màu nhấn, bên phải bộ đếm `40/60` (tên tệp 40 ký tự), `Lưu`,
  `Huỷ`. `Đóng` ẩn lúc đang sửa (variant `rename`, `626:2730`).
- **A2:** tiêu đề về nguyên tên cũ; truy vấn bên dưới chưa đổi.
- **A3:** ô chỉ giữ **60** ký tự đầu của chuỗi dán, bộ đếm `60/60`.
- **A4:** tiêu đề panel đọc `Kiểm tra 15 phút — Số tự nhiên`; **mọi** thẻ `Đã tạo đề` của đoạn
  chat (case 04 lẫn 06) và mọi dòng `— đề "…"` dưới bước đều đọc tên mới, không cần F5. F5 vẫn
  vậy. Rê chuột lên tên trên thẻ thấy đủ tên.
- **B1:** tiêu đề panel không có nút `Đổi tên`. **B2:** nút `Đổi tên` hiện lại.
- **C:** Kriky nói đúng tên mới, không nhắc tên cũ như tên hiện tại.
- Database, sau A4:

  ```
  docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select title, length(title), state from assessments where id = '<id>';"
  docker exec aiafa-postgres psql -U aiafa -d aiafa -c "select sequence, tool_result->>'title' from teacher_turns where conversation_id = '<CID>' and tool_result::jsonb ? 'title' order by sequence;"
  ```

  Hàng đề ra tên mới, `state` vẫn như trước A1. Các hàng `teacher_turns` **vẫn giữ tên cũ** — tên
  hiện tại được thay lúc đọc, không ghi đè lịch sử.

## Không đạt khi

- Lưu xong mà panel, một thẻ cũ, hay một dòng bước vẫn tên cũ sau F5.
- Ô nhận quá 60 ký tự, hay lưu được tên trống (nút `Lưu` với ô trống phải không đổi gì).
- Đề đã duyệt vẫn đổi được tên; hay `Hoàn tác` xong không đổi tên được nữa.
- Đổi tên làm đổi `state` của đề, hay xoá dấu duyệt của câu nào.
- Phần C Kriky nói tên cũ, hay bịa một tên thứ ba.

## Ghi lại

- Ảnh: ô đổi tên ở A1; ô sau A3 (60/60); đoạn chat sau A4 với thẻ cũ mang tên mới; tiêu đề panel ở
  B1 và B2.
- Kết quả hai truy vấn database.
- Nguyên văn câu trả lời của Kriky ở phần C, và tool nó gọi (nếu có).
