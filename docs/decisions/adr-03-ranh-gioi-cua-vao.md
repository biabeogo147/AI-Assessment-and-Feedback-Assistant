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
  *"Chữa bài tới hết 22:00 - mỗi lượt 5 phút một câu, và hết hạn thì lượt đang làm bị **DỪNG**."*
  Chữ *DỪNG* in đậm ngay trên màn, vì đó là phần duy nhất của câu nói về một thứ học sinh sắp mất. Xem
  [ADR-15](adr-15-thoi-gian-pha-hai.md).
- `services/be/src/be/publication_wording.py` — hai câu ấy nay sống trong code, **sao đúng từng
  chữ** từ Figma. Chúng là **hàm** chứ không phải hằng số, vì con số thứ hai trong câu pha 1 (18:15)
  là một *phép tính* — giờ đóng cộng thời gian làm bài — tức chính con số diễn đạt ra cái luật. BE
  tính nó một lần; một câu có số do FE tự tính là bản cài đặt thứ hai của phép tính ấy.
- `services/be/src/be/teacher_routes.py` — cùng hai câu đó đi kèm **cả ba** payload: biểu mẫu (dạng
  chưa có số, vì chưa ai gõ giờ nào), bản `preview` mà hộp xác nhận đọc, và biên bản sau khi phát
  hành. `preview` đi qua **đúng** đoạn code mà lần ghi thật đi qua, nên "ba nơi giống hệt nhau" đúng
  cả với phần số, không chỉ với phần chữ.
- `services/be/src/be/teacher_routes.py` — câu luật in theo **múi giờ giáo viên vừa gõ**, không theo
  UTC, trong khi cột vẫn lưu UTC. Tìm ra bằng một lượt chạy thật: gửi `08:45+07:00` thì câu luật in
  *"tới hết 01:45"* — đúng về vật lý, vô nghĩa với người đọc, và là chính hiểu nhầm mà ADR này ngăn
  chỉ theo một chiều khác. Offset đi kèm request **là** múi giờ người gửi đang đọc.
- `services/be/tests/test_publishing.py` — `test_the_note_is_written_in_the_timezone_the_teacher_typed`
  pin lỗi đó. Nó là test duy nhất trong file gửi một offset khác `+00:00`, và đó là lý do không test
  nào trước nó thấy được lỗi.
- `services/be/tests/test_publishing.py` — `test_the_filled_in_notes_match_the_sentence_adr_03_pinned_on_figma`
  dựng lại câu từ sáu tham số đã gửi rồi so với thứ BE trả về, chứ **không** so ba response với
  nhau: ba bản sao của cùng một lỗi vẫn bằng nhau. Kiểm được rằng nó đỏ bằng cách bỏ phép cộng
  `phase1_minutes`.
- **Chưa có ở backend**: không có trường giờ mở hay giờ đóng nào trong `packages/contracts` — và sẽ
  không có, vì phát hành không đi qua hàng đợi.
