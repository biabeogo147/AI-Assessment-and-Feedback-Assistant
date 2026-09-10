# ADR-02 — Chỉ giáo viên phát hành, và phát hành có cửa sổ thu hồi

- **Trạng thái:** đã mở rộng bởi ADR-15
- **Ngày:** 2026-09-06

## Bối cảnh

`docs/overview/business-workflows.md` dòng 57 ghi *"Hệ thống phát hành đề cho Student"*, và diagram vẽ
hành động đó bằng màu cam — theo legend là *hành vi hệ thống bắt buộc*. Thiết kế thực tế thì ngược lại.

Đồng thời, suốt quá trình thiết kế, phát hành được coi là hành động **tuyệt đối** không thu hồi được.
Điều đó không đúng: một đề đã phát hành nhưng **chưa tới giờ mở** thì chưa ai chạm vào được.

## Quyết định

- **Chỉ giáo viên phát hành.** Hệ thống không bao giờ tự phát hành đề cho học sinh.
- Phát hành bắt buộc **sáu** tham số: **lớp** (chỉ chọn được lớp đã tạo trước), **thời gian làm bài**,
  **giờ mở**, **giờ đóng**, **số phút mỗi câu ở pha 2** và **hạn kết thúc pha 2**. Hai tham số cuối do
  [ADR-15](adr-15-thoi-gian-pha-hai.md) thêm vào. Vì cần sáu thứ, phát hành là một **biểu mẫu**, không
  phải câu hỏi có/không.
- **Thu hồi được cho tới hết giờ mở**, bao gồm cả đúng thời điểm đó. Sau giờ mở — khi học sinh đã có
  thể vào làm — phát hành trở thành không đảo ngược được.
- Thu hồi đưa đề về **đã duyệt**, không về nháp. Nội dung vẫn khoá; chỉ cài đặt phát hành bị gỡ.
- **Giờ mở phải ở tương lai** so với lúc bấm phát hành, và phải trước giờ đóng. Không có ràng buộc này
  thì cửa sổ thu hồi dài không giây nào mà chẳng ai vi phạm luật gì.
- Hộp xác nhận **đọc lại đúng giá trị vừa nhập**, không dùng con số ghi cứng.
- Phát hành có thể **thất bại một phần**: một lớp nhận được đề, lớp khác không.

## Vì sao

Đề kiểm tra ảnh hưởng trực tiếp tới đánh giá học sinh, nên quyền phát hành không thể nằm ở hệ thống.

Cửa sổ thu hồi tồn tại vì **một sai lầm bị bắt trước khi có ai vào làm thì không tốn gì cả**. Cấm thu
hồi trong khoảng đó là nghiêm khắc mà không bảo vệ ai.

Ranh giới đặt ở **giờ mở** chứ không phải lúc bấm nút, vì thứ làm cho hành động không đảo ngược được là
**học sinh đã có thể nhìn thấy đề**, không phải thao tác của giáo viên.

Hộp xác nhận đọc lại giá trị thật làm cổng **mạnh lên**: nó nói lại con số giáo viên vừa chọn, thay vì
một con số dựng sẵn.

## Hệ quả

- Câu *"Sau khi phát hành, bạn không sửa và không thu hồi đề được nữa"* trong hộp xác nhận **đang sai**
  và phải viết lại thành một hạn thu hồi cụ thể. Cổng xác nhận vì thế **nhẹ đi**: nó không còn nói
  "vĩnh viễn", nên phải nói cho đúng khoảnh khắc nào mới thành vĩnh viễn.
- Thẻ `đã-phát-hành` cần hành động **Thu hồi** khi chưa tới giờ mở, và mất nó khi đã qua.
- Cần phân biệt hai trạng thái con: *đã phát hành, chưa mở* và *đã mở*. ADR-01 chưa có hai trạng thái
  này và sẽ phải mở rộng.
- Thất bại một phần cần trạng thái riêng và phải nói rõ lớp nào đã nhận bản ghi phát hành — với những
  lớp đó, thu hồi vẫn được nếu chưa qua giờ mở.
- Chiều cao khối chọn lớp **phải bị chặn**: chọn chín lớp mà khối phình ra sẽ đẩy danh sách câu hỏi
  xuống dưới chiều cao một thẻ, tức là làm hỏng chính cổng này. Luật này **khó hơn** kể từ ADR-15:
  biểu mẫu dài thêm hai trường ngay cả khi chưa chọn lớp nào, nên phần dư để co giãn đã hẹp lại.
- Mọi diagram vẽ phát hành nằm trong lane hệ thống đều sai và phải chuyển sang lane Teacher.

## Nơi luật này đang được thi hành

- Figma `mOe2ZmrqOq1Uix45v6PNGD`, `Publish settings` (`67:41`) — **sáu** trường, nhóm theo hai pha,
  cả hai variant; mô tả component ghi luật chặn chiều cao.
- Figma `Consequence dialog` (`11:41`) — khối đọc lại **sáu** giá trị.
- Figma `Action result card` (`10:63`) — variant `đã-phát-hành`, `phát-hành-thất-bại`.
- Figma artboard `1 · Bắt đầu`: *"Kriky sẽ tạo lớp, soạn đề, thêm câu hỏi — nhưng chỉ bạn mới phát hành
  được đề cho học sinh."*
- `docs/diagrams/business-workflows.drawio` — `t-publish` nằm trong **lane Teacher**. Điều khoản
  *mọi diagram vẽ phát hành nằm trong lane hệ thống đều sai* ở mục **Hệ quả** trước đây chưa từng
  được thi hành: node này vốn nằm giữa lane System/AI, và ba node khác bị gắn `parent` sai lane. Nay
  mọi node dùng toạ độ tuyệt đối nên vị trí không lệch khỏi lane được nữa.
- **Cửa sổ thu hồi: mới thi hành một nửa.** Câu *"không sửa và không thu hồi đề được nữa"* — thứ mục
  *Hệ quả* ở trên tuyên là sai — đã bị thay ở **cả ba** chỗ nó xuất hiện: `Consequence dialog`
  (`11:41`), `Action result card` variant `đã-phát-hành` (`10:45`), và variant
  `phát-hành-thất-bại` (`76:23`), nơi nó còn mâu thuẫn thẳng với luật thất bại một phần ở trên.
  Thẻ `đã-phát-hành` nay có hành động **Thu hồi**.
- **Nửa chưa thi hành:** nút Thu hồi phải **mất đi khi đã qua giờ mở**, và `Action result card`
  (`10:63`) không có trục trạng thái *chưa mở* / *đã mở* nên nút luôn hiện. Đừng đọc thẻ đó như bằng
  chứng rằng thu hồi lúc nào cũng được. Xem `docs/plans/backlog.md`.
- **Chưa có ở backend** cho toàn bộ ADR này.
