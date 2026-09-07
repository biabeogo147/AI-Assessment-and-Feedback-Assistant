# ADR-12 — Một số màu và hình ảnh mang nghĩa nghiệp vụ cố định

- **Trạng thái:** đã chốt
- **Ngày:** 2026-09-06

## Bối cảnh

Vài quyết định trông như thẩm mỹ nhưng thực ra là luật nghiệp vụ: chúng ràng buộc thiết kế được phép
làm gì, và phá chúng làm người dùng hiểu sai hệ quả của một hành động.

ADR này **không** ghi chép design token. Nó chỉ ghi những ánh xạ mà nghiệp vụ áp đặt lên thiết kế.

## Quyết định

- **Đỏ nghĩa là có gì đó hỏng** — hoặc đáp án của học sinh sai, hoặc hệ thống không làm được việc.
  Hai nghĩa này dùng chung họ token `answer/incorrect`. Đỏ **không bao giờ** là màu thương hiệu, và
  **không bao giờ** dùng cho một trạng thái chỉ cần người xem lại.
- **Hổ phách nghĩa là cần người.** Không dùng nó cho thứ chỉ đang chạy, và không dùng nó cho lỗi.
- **Không đặt hình ảnh ăn mừng cạnh một hành động không thu hồi được**, và không đặt hình ảnh cười cợt
  cạnh một đáp án sai.
- **Thang độ tin cậy không có màu.** Luật này thuộc
  [ADR-06](adr-06-agent-phat-bang-chung.md) — tô màu theo mức là mã hoá ngưỡng vào giao diện. Nhắc
  lại đây vì nó ràng buộc bảng màu.

## Vì sao

Đỏ và hổ phách đã mang nghĩa trong chính sản phẩm này: đỏ là `answer/incorrect`, hổ phách là
`state/needs-human`. Dùng lại chúng cho việc khác không phải chọn sai màu — nó là **nói sai**. Một
linh vật màu hổ phách sẽ trông như đang báo động suốt ngày, và làm chìm mất thẻ cảnh báo thật.

Đỏ mang hai nghĩa vì **hai nghĩa đó không bao giờ xuất hiện cùng lúc trên một màn hình**: một thẻ kết
quả nói câu này sai, một khối lỗi nói hệ thống không lấy được kết quả nào. Đó là sự trùng lặp có kiểm
soát, không phải sự lẫn lộn. Vạch quan trọng nằm ở chỗ khác: **lỗi và cần-người là hai chuyện khác
nhau**, nên chúng không được dùng chung màu — nếu không, giáo viên sẽ đọc một hàng đợi cần xử lý
thành một danh sách sự cố.

Cấm hình ảnh ăn mừng vì phát hành đề là hành động có hệ quả ra ngoài. Một hình vẽ ăn mừng cạnh biên bản
phát hành biến biên bản thành lời chúc mừng, và người ta thôi đọc nó. Cùng lý do với ảnh cười cợt cạnh
một đáp án sai: nó biến một nhận xét thành lời chế nhạo học sinh.

Thang tin cậy không màu là hệ quả trực tiếp của ADR-06. Nếu FE tô màu theo ngưỡng, đổi ngưỡng trong
`.env` sẽ không còn đổi được cách người dùng đọc kết quả.

## Hệ quả

- Bảng màu thương hiệu **mất hai vùng màu** — đỏ và hổ phách — và phải tìm bản sắc trong phần còn lại.
  Linh vật đã phải hạ bão hoà vì đúng lý do này.
- Vì đỏ mang hai nghĩa, giao diện **không thể** dùng riêng màu để phân biệt "em trả lời sai" với "hệ
  thống hỏng". Chữ phải làm việc đó, ở mọi chỗ hai thứ có thể đứng gần nhau.
- Sản phẩm không có bề mặt nào để khen học sinh hay ăn mừng cho giáo viên. Đó là cái giá đã chọn, và
  người thiết kế sau sẽ thấy nó thiếu vắng.
- Mọi ảnh minh hoạ mới phải qua một câu hỏi trước khi dùng: *nó sẽ đứng cạnh cái gì?* Cùng một hình có
  thể hợp lệ ở màn hình rỗng và bị cấm ở thẻ kết quả.

## Nơi luật này đang được thi hành

- Figma `mOe2ZmrqOq1Uix45v6PNGD`, collection `Color` — `answer/incorrect` và `state/needs-human` là hai
  token riêng, không hoán đổi cho nhau. (Hai token này là **nơi** luật được thi hành, không phải nội
  dung của luật; sắc độ cụ thể là việc của design system.)
- Figma `Error state` (`6:75`) — cả ba variant lỗi hệ thống dùng `answer/incorrect` trên nền
  `answer/incorrect-surface`, và không variant nào chạm vào `state/needs-human`.
- Figma `Confidence meter` (`5:32`) — năm variant, không variant nào có màu theo mức.
- Figma trang `Assets — Dế Mèn`, khối **Cách ly — sai tông · 6** (`46:119`) — sáu asset bị loại, kèm
  ghi chú nói rõ chúng bị loại vì **nội dung**, không phải vì cách vẽ.
- Figma `Assistant avatar` (`28:6`) — thân linh vật tách khỏi hổ phách. Mức bão hoà cụ thể là cách
  design system tuân thủ; luật chỉ đòi *tách ra*.
- **Chưa có lint hay test** nào chặn việc dùng sai hai màu này ở code.
- `services/fe/src/App.tsx:89` dùng đỏ thô `#a11` cho lỗi hệ thống thay vì token. Hợp luật về nghĩa,
  sai về nguồn màu — màn hình demo chưa dùng token nào.
