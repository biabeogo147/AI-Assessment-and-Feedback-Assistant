# Changelog

Lịch sử các bản đã đưa lên lab, viết cho tester: bản ấy có gì mới, sửa lỗi nào. Tên bản hiện ở chân
rail của giáo viên và góc dưới trái mọi màn học sinh, kể cả màn đăng nhập; bấm vào thì chép được tên
để dán vào ticket.

Tên dạng `lab-<năm>.<z>.<x>`. `lab` là tên môi trường. Mỗi bản mới tăng `x`; `z` chỉ tăng khi người
phụ trách yêu cầu, và khi ấy `x` về `0`. Sang năm mới thì về `<năm>.0.1`. Tên chỉ đặt bằng
`.\dev.ps1 release`, sau khi mục của bản ấy đã có ở đầu file này.

## lab-2026.0.3 — 29/10/2026

- **Đổi:** tiêu đề tab trình duyệt ghi *Kriky*, ở cả trang giáo viên lẫn học sinh.

## lab-2026.0.2 — 28/10/2026

- **Đổi:** tên bản dời xuống góc trái dưới màn: ở màn giáo viên nằm dưới avatar, ở màn học sinh cách
  mép trái 24.
- **Mới:** tab trình duyệt có biểu tượng mặt Kriky, ở cả trang giáo viên lẫn học sinh.

## lab-2026.0.1 — 28/10/2026

Bản đầu tiên có tên. Mọi lỗi báo trước bản này không mang tên bản nào.

- **Mới:** tên bản ở chân rail giáo viên và góc dưới phải màn học sinh; bấm để chép.
- **Mới:** giáo viên tạo lớp ở màn *Danh sách lớp*, hay nhờ Kriky tạo. Lớp còn trống (chưa có học
  sinh, chưa nhận đề nào) thì xoá được ở màn lớp.
- **Mới:** Kriky trả lời câu hỏi về nội dung một tài liệu đã tải lên; công thức trong sách đọc đúng
  hơn.
- **Mới:** câu làm lại ở pha 2 bám đúng mục dàn ý của câu gốc.
- **Sửa:** phát hành hỏng hiện thẻ báo trong đoạn chat; phân số trong chữ thường hiện ngang; nút báo
  cáo câu hỏi ghi *Đã báo cho giáo viên*.
- **Sửa:** tệp danh sách lớp quá 2 MB bị từ chối ngay, có lời tiếng Việt.
- **Sửa:** Kriky không còn gọi đề là *đề "Đề …"*.
