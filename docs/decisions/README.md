# Quyết định nghiệp vụ

Mỗi file ở đây ghi **một** quyết định về cách sản phẩm cư xử: ai được làm gì, cái gì không đảo ngược
được, thông tin nào bắt buộc phải hiện. Quyết định **kỹ thuật hoặc quy trình** thì không nằm ở đây —
chúng sống trong mục `## Decision Records` của plan tương ứng.

Quyết định nghiệp vụ ở riêng vì nó thuộc về sản phẩm chứ không thuộc về một thay đổi: plan chạy xong
sẽ chuyển sang `docs/plans/completed/`, nơi không ai được sửa.

| ADR | Quyết định | Trạng thái |
| --- | --- | --- |
| [01](adr-01-vong-doi-de-kiem-tra.md) | Vòng đời đề kiểm tra có bốn trạng thái | đã mở rộng bởi ADR-02 |
| [02](adr-02-phat-hanh-va-cua-so-thu-hoi.md) | Chỉ giáo viên phát hành; có cửa sổ thu hồi tới giờ mở | đã chốt (cửa sổ thu hồi chưa thi hành) |
| [03](adr-03-ranh-gioi-cua-vao.md) | Giờ đóng chặn việc vào làm, không chặn việc nộp | đã chốt |
| [04](adr-04-hai-nguon-cau-hoi.md) | Câu hỏi chỉ có hai nguồn; tài liệu là phạm vi | đã chốt |
| [05](adr-05-ba-cong-teacher-in-the-loop.md) | Ba cổng teacher-in-the-loop | đã chốt |
| [06](adr-06-agent-phat-bang-chung.md) | Agent phát bằng chứng, không quyết định | đã chốt |
| [07](adr-07-dieu-gi-dua-ket-qua-toi-giao-vien.md) | Ngưỡng, thứ tự ưu tiên lý do, và phép so bao gồm | đã chốt |
| [08](adr-08-bon-loai-nghi-ngo.md) | Bốn loại nghi ngờ; kết quả low-confidence vắng mặt với học sinh | đã chốt |
| [09](adr-09-ket-qua-cham-la-tam-thoi.md) | Kết quả chấm chỉ sống một giờ | đã chốt |
| [10](adr-10-pham-vi-dot-dau.md) | Chỉ giáo viên, chỉ desktop, chat là dòng lệnh | đã chốt |
| [11](adr-11-bo-assessment-type.md) | Bỏ `AssessmentType` khỏi contract | đã chốt |
| [12](adr-12-mau-va-hinh-anh-ma-hoa-luat.md) | Một số màu và hình ảnh mang nghĩa nghiệp vụ cố định | đã chốt |
| [13](adr-13-lop-va-tai-khoan-hoc-sinh.md) | Giáo viên tạo lớp; tài khoản học sinh sinh từ CSV | đã chốt (mật khẩu một lần: chưa thi hành) |

Khuôn cho ADR mới: [adr-00-template.md](adr-00-template.md). Mục cuối — *Nơi luật này đang được thi
hành* — là mục bắt buộc và là thứ mọi decision record cũ trong `docs/plans/completed/` đều thiếu.

## Nguồn thiết kế

Phần lớn luật ở đây hiện chỉ được thi hành trong **file thiết kế Figma**, chưa có ở backend:

<https://www.figma.com/design/mOe2ZmrqOq1Uix45v6PNGD>

Trang `Screen — Chat` chứa mười một artboard: tám artboard theo luồng chat từ lúc mở tới lúc phát
hành xong, và ba màn hình quản lý vật thể (lớp học, chi tiết lớp, kết quả bài kiểm tra). Trang
`Components` chứa các component set, và **mô tả của từng component set là nơi nhiều luật nghiệp vụ
được ghi lần đầu**. Khi một ADR trỏ tới một node id, node đó nằm trong file này.

## Còn thiếu

Bốn luật từng nằm ở mục này — thứ tự ưu tiên lý do review, phép so ngưỡng bao gồm, giá trị `0.7`, và
hạn giữ kết quả một giờ — nay đã có ADR-07 và ADR-09.

Còn lại, và cố ý chưa viết:

- **Luồng học sinh** — chấm bài, feedback, mastery, luyện tập thích ứng. Có tài liệu và có code, nhưng
  chưa có thiết kế; xem ADR-10.
- **Màn hình Bảng theo dõi** — chưa thiết kế, nên chưa có luật nào để ghi.
- **Luồng nhập CSV danh sách lớp** — chỗ duy nhất mật khẩu ban đầu được phép hiện. ADR-13 đã
  chốt luật, nhưng màn hình chưa dựng.
- Quyết định **thiết kế tương tác** (điều hướng rail, hai mật độ, ràng buộc bộ gõ tiếng Việt) không
  thuộc thư mục này. Chúng sống trong mô tả component Figma tương ứng.
