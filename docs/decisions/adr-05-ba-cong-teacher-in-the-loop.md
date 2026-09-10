# ADR-05 — Có ba cổng teacher-in-the-loop, và cổng đầu vào có ranh giới cứng

- **Trạng thái:** đã chốt (ngoại lệ ở cổng thứ nhất: chưa thi hành)
- **Ngày:** 2026-09-06

## Bối cảnh

`docs/overview/project-overview.md` trước đây ghi giáo viên bắt buộc tham gia ở **hai điểm**: duyệt đề
trước khi phát hành, và xử lý kết quả chấm có confidence thấp.

Cả hai đều nằm ở **đầu ra** — sau khi agent đã làm xong việc. Thiết kế bổ sung một cổng thứ ba ở
**đầu vào**, và tài liệu đã được cập nhật theo ADR này.

## Quyết định

Ba cổng, hai ở đầu ra và một ở đầu vào:

1. **Duyệt đề trước khi phát hành** — đầu ra. Có **một ngoại lệ**; xem cuối mục này.
2. **Xử lý kết quả độ tin cậy thấp** — đầu ra.
3. **Agent hỏi lại khi chưa đủ thông tin** — đầu vào.

Cổng thứ ba có ranh giới cứng:

- Chỉ dùng để hỏi thông tin **trước khi làm việc đảo ngược được**.
- **Không bao giờ** dùng để xin phép một việc không thu hồi được. "Phát hành cho lớp nào?" phải đi qua
  biểu mẫu phát hành và hộp xác nhận.
- Agent **không đánh dấu lựa chọn nào là nên chọn** khi đó là quyết định sư phạm. Mỗi lựa chọn tự nói ra
  cái giá của nó.
- Luôn giữ lối thoát trả lời tự do. Ba lựa chọn không bao giờ phủ hết.

Và một luật đi kèm: **nút Phát hành chỉ xuất hiện trong panel phải và trong hộp xác nhận**, không bao
giờ trong luồng chat.

**Ngoại lệ của cổng thứ nhất.** Câu luyện tập ở pha 2
([ADR-17](adr-17-ba-vong-moi-cau.md)) do trợ lí sinh ra khi học sinh đang ngồi đó, và **không đi qua
cổng nào**. Câu *giáo viên duyệt đề trước khi tới tay học sinh* vì thế không còn đúng nguyên văn.
Đây là một lỗ đã biết, không phải một chi tiết bị bỏ quên: nó được ghi ra ở đây thay vì để ADR âm
thầm sai. Ba đường xử lý nằm ở `docs/plans/backlog.md`.

## Vì sao

Cổng đầu vào tồn tại vì cùng một lý do với hai cổng kia: agent không đoán khi chưa chắc. Đặt ở đầu vào
thì rẻ hơn — sửa một hiểu nhầm trước khi làm rẻ hơn sửa sau khi đã làm.

Ranh giới cứng là phần quan trọng hơn. Nếu bong bóng ba lựa chọn được phép xin phép một việc bất khả
hồi, thì **cổng duyệt bị đi vòng bằng một cú click** — và nó sẽ bị đi vòng, vì ba nút bấm nhẹ hơn một
biểu mẫu bốn trường.

Không đánh dấu "nên chọn" là vì chọn nguồn câu hỏi hay mức độ là quyết định **sư phạm**. Agent có
thông tin (ngân hàng còn bao nhiêu câu ở mức nào), giáo viên có thẩm quyền. Đưa thông tin là đủ; lái
thì vượt quyền.

**Vì sao ngoại lệ ở cổng thứ nhất được phép tồn tại.** Câu luyện tập sinh ra giữa lúc học sinh đang
làm bài, nên không có khoảng trống nào để chờ một thao tác của giáo viên. Đó là lý do **cơ học**,
không phải lý do nguyên tắc — cổng này vẫn đúng, chỉ là chưa ai tìm được cách giữ nó mà không bắt cả
lớp dừng lại. Ghi ra như một lỗ đã biết thay vì như một thiết kế, vì nó là lỗ.

Cảnh báo từ kinh nghiệm: **gợi ý ngầm còn tệ hơn gợi ý công khai.** Bộ ba lựa chọn đầu tiên có một
phương án duy nhất không kèm mệnh đề nhượng bộ, nên nó được ưu ái mà người đọc không nhận ra mình đang
bị đẩy. Mọi lựa chọn phải nêu cái giá bằng cùng một ngữ pháp.

## Hệ quả

- Cổng đầu vào làm chậm agent lại: nó phải nhận ra mình chưa đủ thông tin thay vì chọn mặc định hợp
  lý. Đổi lại, mọi lần nó đoán sai đều tốn một vòng sửa ở đầu ra, nơi đắt hơn.
- Bong bóng hỏi lại phải phụ thuộc ngữ cảnh: có tài liệu trong thư viện thì một lựa chọn phải nhắc tới
  phạm vi tài liệu, nếu không đây là chỗ duy nhất giáo viên chọn nguồn mà lại không biết nhánh đó tồn tại.
- Viết ba lựa chọn khó hơn hẳn viết một khuyến nghị: mỗi cái phải nêu cái giá bằng cùng một ngữ pháp,
  nếu không thì cái duy nhất thiếu mệnh đề nhượng bộ sẽ được ưu ái mà không ai nhận ra.
- Ngoại lệ ở cổng thứ nhất khiến câu **"ba cổng"** không còn đọc được như một lời hứa tuyệt đối. Mọi
  tài liệu nhắc tới ba cổng từ nay phải chịu được câu hỏi *thế câu luyện tập thì sao*, và mọi lần trả
  lời đều tốn một đoạn giải thích.

## Nơi luật này đang được thi hành

- Figma `mOe2ZmrqOq1Uix45v6PNGD`, `Clarify request` (`64:23`) — mô tả component ghi cả ba cổng và ranh giới của cổng thứ ba.
- Figma artboard `3 · Kriky hỏi lại trước khi làm` — ba lựa chọn, mỗi cái một mệnh đề nêu cái giá, cộng
  dòng lối thoát.
- `AGENTS.md` bảng Invariants — hai cổng đầu ra nằm ở nhóm **chưa enforce**.
- **Ngoại lệ ở cổng thứ nhất: chưa thi hành ở đâu cả.** Mô tả component `Clarify request` (`64:23`)
  vẫn ghi ba cổng không kèm ngoại lệ, và đúng như vậy — chưa câu luyện tập nào tồn tại để mà đi vòng
  qua cổng.
- [ADR-19](adr-19-bao-cao-giai-thich-chua-ro.md) thêm một kênh đưa việc tới giáo viên nhưng **không**
  thêm cổng thứ tư, vì nó không chặn ai. Ranh giới đó được giải thích trong chính ADR-19.
- **Chưa có ở backend**: không có cổng nào trong ba cổng được thi hành bằng code.
