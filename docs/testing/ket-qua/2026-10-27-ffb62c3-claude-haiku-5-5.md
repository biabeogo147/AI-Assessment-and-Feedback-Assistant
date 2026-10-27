# Lần chạy 27/10/2026 trên Claude Haiku 5.5 — trên ffb62c3 (vòng T27: plan Tier 1)

- **Ngày:** 27/10/2026, 19:48–19:52.
- **Code:** `ffb62c3` cộng thay đổi chưa commit của plan `2026-10-27-tier-1-plan.md`, gồm:
  - `list_documents` có `processing` và `note`;
  - `Unparsed` hỏi lại một lần;
  - bước 6 `soan-de`;
  - dòng bước tạo đề không lặp chữ *Đề*.
  BE, AGENT và mọi worker khởi động lúc 19:40, sau mọi thay đổi trừ `note`. BE tự nạp lại `note`
  lúc 19:49.
- **Model:** `anthropic/claude-haiku-5-5`, `thinking=disabled`, `effort=low`.
- **Database:** dev đang có, không `db-reset`. Tệp scan tải lên bằng `POST /api/teacher/documents`
  với phiên giáo viên seed, cùng đường FE gọi: `scan-mot-trang-T27.pdf`, rồi `scan-mot-trang-T27b.pdf`.
- **Chi phí:** khoảng 67 nghìn token chat (ba đoạn chat, 6 lượt model), cộng 3 job soạn câu, đặt
  tên và OCR một trang. Tổng khoảng 0,07–0,08 USD, hơi vượt mức ước 0,05 USD.
- **Ảnh:** `docs/report/screenshot/27_10/tier-1/` (không commit).

## Kết quả

| Ca | Kết quả | Lý do |
| --- | --- | --- |
| 13 lượt 1, lần 1 (chỉ có key `processing`) | **Không đạt** | Kriky hỏi *"Bạn muốn soạn từ tài liệu nào?"*, kèm nút hai cuốn đã sẵn sàng, không nhắc tệp vừa tải (ảnh `05`). Kết quả tool có đúng `"processing": ["scan-mot-trang-T27.pdf"]`: model bỏ qua nó, theo luật *nhiều tài liệu → hỏi lại* của `BOOK_PROCEDURE` |
| 13 lượt 1, lần 2 (thêm `note`) | **Đạt** | *"Tệp bạn vừa up (trang sách chụp lại) vẫn **còn đang đọc, chưa đọc xong** nên mình chưa mở được để soạn. Bạn chờ một chút rồi nhắn lại nhé…"* (ảnh `06`). Một bước *Xem thư viện tài liệu*, không dàn ý, không thẻ |
| Câu kết sau plan, đề không sách | **Chấp nhận được** | *"Đã xong: đề "**Đề mệnh đề**" có đủ **3 câu** trắc nghiệm. Bạn xem câu hỏi ở panel bên phải…"* (ảnh `07`). Không còn *"không còn câu nào đang soạn"*, không còn *Đề **Đề …***. Còn chữ *đề* thường đứng trước tên, nên vẫn đọc là *đề "Đề mệnh đề"* |

Lượt 2 của case 13 không chạy: plan này không đổi đường ấy.

Lần 1 của case 13 chạy khi worker `document` (OCR) **chưa bật**: tệp đứng ở *đang xử lý* đúng như
case cần. Lần 2 chạy khi worker đã bật; chip đi *Đang dựng mục lục…* rồi sẵn sàng, không F5.

## Ngoài thử tay

Hai thay đổi FE đo bằng trình duyệt, ảnh `01`–`04`:

- **Hộp 25b:** báo cáo `8521482c…` đã xử lý nên tạm đặt `resolved_at = NULL` để mở, chụp xong trả
  về giá trị cũ. Lời Kriky in đậm đúng, không còn `**`.
- **Công thức trang 18:** đoạn chat `e74859ff…` đọc thành *"n thừa số"* dưới `\underbrace`.
- **Dòng bước tạo đề:** `— "Đề Kết nối tri thức Lớp 6 tập 1"`.

Trần proxy (`deploy/lab/Caddyfile`) đo bằng image `aiafa-lab-caddy` cạnh một upstream giả:

| Tệp | Kết quả |
| --- | --- |
| 3 MB | 413 kèm *"Tệp danh sách lớn hơn 1 MB."* |
| 1,5 MB | tới upstream |
| đường khác | đi qua |
