# ADR-03 — Giờ đóng chặn việc vào làm, không chặn việc nộp

- **Trạng thái:** đã chốt
- **Ngày:** 2026-09-06

## Bối cảnh

Một lần phát hành có ba tham số thời gian độc lập: **thời gian làm bài**, **giờ mở**, **giờ đóng**. Ba
con số này rất dễ bị gộp thành một trong đầu người đọc.

## Quyết định

- **Luật này áp cho pha 1**, tức phần làm bài và nộp. Pha 2 có hai đồng hồ riêng và một luật ngược
  lại ở chỗ cắt giữa chừng; xem [ADR-15](adr-15-thoi-gian-pha-hai.md).
- Giờ đóng là hạn **vào tham gia**, không phải hạn nộp.
- Vào **tới hết** giờ đóng vẫn được — mốc là bao gồm, không loại trừ.
- Học sinh đã vào rồi thì **không bị dừng giữa chừng**, và được đủ thời gian làm bài kể cả khi tràn qua
  giờ đóng.

Ví dụ: đóng 18:00, làm bài 15 phút, thì bài cuối có thể nộp lúc 18:15.

## Vì sao

Đây là chỗ dễ hiểu nhầm nhất trong toàn bộ luồng phát hành. Gần như chắc chắn giáo viên đọc *"đóng
18:00"* thành *"18:00 là xong hết"*.

Hiểu nhầm đó gây hại theo chiều ngược: giáo viên muốn bài nộp xong trước 18:00 sẽ **đặt giờ đóng thành
17:45 để bù**, tức là tự cắt mất mười lăm phút của cả lớp mà không biết.

Mốc chọn bao gồm vì một học sinh bấm vào đúng giây cuối không nên bị từ chối bởi một ranh giới họ không
nhìn thấy.

## Hệ quả

- Câu giải thích phải xuất hiện ở **cả ba nơi**: lúc đang chọn giờ, lúc xác nhận, và trong biên bản sau
  khi phát hành. Và phải **giống hệt nhau từng chữ** — ba cách diễn đạt cho một luật là ba luật. Luật
  một-chuỗi-ba-nơi này áp cho **chuỗi của pha 1**; hai mốc của pha 2 cần chuỗi riêng, cũng phải xuất
  hiện ở đủ ba nơi và cũng phải giống hệt nhau từng chữ.
- Câu phải nói ra **kết quả** trước cơ chế. Người đọc lướt chỉ bắt được cụm đầu và cụm cuối.
- Con số "18:15" là giá trị **dẫn xuất** từ giờ đóng cộng thời gian làm bài. Ghi cứng nó là sai ngay khi
  ai đó đổi thời gian làm bài.

## Nơi luật này đang được thi hành

- Figma `mOe2ZmrqOq1Uix45v6PNGD` — cùng một chuỗi ở ba nơi: `Publish settings` (`67:29`), `Consequence dialog` (`68:15`),
  và thẻ `đã-phát-hành` trong `Action result card`:
  *"Vào tham gia tới hết 18:00 - có thể nộp lúc 18:15, và không dừng người đang làm."*
- Chuỗi của **pha 2** cũng đã có mặt ở đủ ba nơi và giống hệt nhau từng chữ:
  *"Chữa bài tới hết 22:00 - mỗi lượt 5 phút một câu, và hết hạn thì lượt đang làm bị cắt."* Xem
  [ADR-15](adr-15-thoi-gian-pha-hai.md).
- **Chưa có ở backend**: không có trường giờ mở hay giờ đóng nào trong `packages/contracts`.
