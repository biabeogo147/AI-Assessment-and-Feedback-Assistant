# Quyết định nghiệp vụ

Mỗi file ở đây ghi **một** quyết định về cách sản phẩm cư xử: ai được làm gì, cái gì không đảo ngược
được, thông tin nào bắt buộc phải hiện. Quyết định **kỹ thuật hoặc quy trình** thì không nằm ở đây —
chúng sống trong mục `## Decision Records` của plan tương ứng.

Quyết định nghiệp vụ ở riêng vì nó thuộc về sản phẩm chứ không thuộc về một thay đổi: plan chạy xong
sẽ chuyển sang `docs/plans/completed/`, nơi không ai được sửa.

| ADR | Quyết định | Trạng thái |
| --- | --- | --- |
| [01](adr-01-vong-doi-de-kiem-tra.md) | Vòng đời đề kiểm tra có bốn trạng thái | đã mở rộng bởi ADR-02, ADR-18 |
| [02](adr-02-phat-hanh-va-cua-so-thu-hoi.md) | Chỉ giáo viên phát hành; phát hành có sáu tham số | đã mở rộng bởi ADR-15 |
| [03](adr-03-ranh-gioi-cua-vao.md) | Giờ đóng chặn việc vào làm, không chặn việc nộp | đã chốt (phạm vi: pha 1) |
| [04](adr-04-hai-nguon-cau-hoi.md) | Câu hỏi chỉ có hai nguồn; tài liệu là phạm vi | đã chốt (trừ câu luyện tập) |
| [05](adr-05-ba-cong-teacher-in-the-loop.md) | Ba cổng teacher-in-the-loop | đã chốt (cổng 1 có ngoại lệ) |
| [06](adr-06-agent-phat-bang-chung.md) | Agent phát bằng chứng, không quyết định | đã chốt |
| [07](adr-07-dieu-gi-dua-ket-qua-toi-giao-vien.md) | Ngưỡng, thứ tự ưu tiên lý do, và phép so bao gồm | đã chốt (ngưỡng tạm gỡ khỏi luồng học sinh) |
| [08](adr-08-bon-loai-nghi-ngo.md) | Bốn loại nghi ngờ; thứ vắng mặt với học sinh là *chẩn đoán* | đã mở rộng bởi ADR-18 |
| [09](adr-09-ket-qua-cham-la-tam-thoi.md) | Kết quả chấm chỉ sống một giờ | đã chốt |
| [10](adr-10-pham-vi-dot-dau.md) | Chỉ giáo viên, chỉ desktop, chat là dòng lệnh | đã chốt |
| [11](adr-11-bo-assessment-type.md) | Bỏ `AssessmentType` khỏi contract | đã chốt |
| [12](adr-12-mau-va-hinh-anh-ma-hoa-luat.md) | Một số màu và hình ảnh mang nghĩa nghiệp vụ cố định | đã chốt |
| [13](adr-13-lop-va-tai-khoan-hoc-sinh.md) | Giáo viên tạo lớp; tài khoản học sinh sinh từ CSV | đã chốt (mật khẩu một lần: chưa thi hành) |
| [14](adr-14-hai-pha-lam-bai.md) | Bài kiểm tra có hai pha; nộp bài không phải điểm kết thúc | đã chốt (Figma xong, backend chưa) |
| [15](adr-15-thoi-gian-pha-hai.md) | Hai đồng hồ ở pha 2; phần giải thích không tính giờ | đã chốt (Figma xong, backend chưa) |
| [16](adr-16-thang-diem-ba-muc.md) | Ba mức điểm; 0,5 nghĩa là hiểu sau khi được dạy | đã chốt (Figma xong, backend chưa) |
| [17](adr-17-ba-vong-moi-cau.md) | Ba vòng cho mỗi câu; biến thể sinh từ chính câu đó | đã chốt (Figma xong, backend chưa) |
| [18](adr-18-cau-hoi-phai-kem-loi-giai.md) | Câu hỏi phải kèm lời giải nhiều cách và nhiễu gắn lỗi | đã chốt (Figma xong, contract chưa) |
| [19](adr-19-bao-cao-giai-thich-chua-ro.md) | Học sinh báo cáo chỗ Kriky giải thích chưa rõ | đã chốt (nửa học sinh xong; giáo viên chưa) |
| [20](adr-20-cham-trac-nghiem-thuoc-be.md) | Chấm trắc nghiệm là việc của BE, không của AGENT | đã chốt, chưa thi hành |
| [21](adr-21-trang-thai-bai-lam-la-ben.md) | Trạng thái bài làm là bền; hạn một giờ chỉ áp cho job | đã chốt, chưa thi hành |
| [22](adr-22-de-co-tac-gia.md) | Đề và lớp có tác giả; của người khác đọc ra như không tồn tại | đã chốt, đang thi hành |
| [23](adr-23-hoi-lai-khi-khong-phan-dinh-duoc.md) | Không phân định được thì hỏi lại; lựa chọn đến từ dữ liệu | đã mở rộng bởi ADR-25 |
| [24](adr-24-mot-giao-vien-nhieu-doan-chat.md) | Một giáo viên nhiều đoạn chat; biên bản rơi vào đoạn đã tạo ra đề | đã chốt, đang thi hành |
| [25](adr-25-hai-pha-mot-luot-chat.md) | Một lượt chat có hai pha: lên plan, rồi thực hiện plan | đã chốt, chưa thi hành |

Khuôn cho ADR mới: [adr-00-template.md](adr-00-template.md). Mục cuối — *Nơi luật này đang được thi
hành* — là mục bắt buộc và là thứ mọi decision record cũ trong `docs/plans/completed/` đều thiếu.

## Nguồn thiết kế

Phần lớn luật ở đây hiện chỉ được thi hành trong **file thiết kế Figma**, chưa có ở backend:

<https://www.figma.com/design/mOe2ZmrqOq1Uix45v6PNGD>

Trang `Screen — Chat` chứa mười hai artboard: tám artboard theo luồng chat từ lúc mở tới lúc phát
hành xong, ba màn hình quản lý vật thể (lớp học, chi tiết lớp, kết quả bài kiểm tra), và một màn cho
hộp thoại lời giải của một câu.

Trang `Screen — Student` chứa mười hai artboard của bề mặt học sinh, **đánh số 13…24 theo đúng thứ
tự luồng nghiệp vụ**: danh sách bài, làm bài, kết quả *đã nộp cần chữa*, hover trên điểm 0, màn hỏi
trợ lý và làm lại dạng bài sai, hộp lời giải đầy đủ, cổng bắt đầu lượt ở hai ca (thường và **sắp hết
hạn**), làm câu của một lượt, kết quả *đã hoàn thành*, hover trên điểm 0,5, và màn hỏi trợ lý ở hình
dạng **bài đã kết thúc** — đọc lại được, không nhắn thêm được. Hai màn kết quả là **hai artboard riêng** cho hai hình dạng
dữ liệu, không phải hai state của một. Tất cả chạy Density mode `Student` và không có rail.

Trang `Components` chứa các component set, và **mô tả của từng component set là nơi nhiều luật nghiệp
vụ được ghi lần đầu**. Khi một ADR trỏ tới một node id, node đó nằm trong file này.

## Còn thiếu

Bốn luật từng nằm ở mục này — thứ tự ưu tiên lý do review, phép so ngưỡng bao gồm, giá trị `0.7`, và
hạn giữ kết quả một giờ — nay đã có ADR-07 và ADR-09.

Còn lại, và cố ý chưa viết:

- **Ba luật của mô hình hai pha chưa ai quyết**, cả ba nằm ở `docs/plans/backlog.md`: câu luyện tập
  có qua cổng duyệt không; `confidence` đo cái gì khi phần chấm đã xác định — chẩn đoán có độ tin cậy
  đã **bỏ khỏi đợt này**, ghi nợ để làm sau; và vòng đếm cùng đồng hồ ứng xử ra sao khi học sinh mở
  hai tab. Mức điểm 0,5 thì đã hết là câu hỏi: ADR-16 chốt nó **không được cấp màu mới**, phân biệt
  bằng hình tròn đầy / nửa / rỗng.
- **Hạn lưu trữ dài hạn của bài làm** — ADR-21 chốt trạng thái bài làm là bền, nhưng *bền tới bao
  giờ* thì chưa ai quyết. Một học kỳ, một năm, hay tới khi giáo viên xoá lớp: ba câu trả lời khác
  nhau kéo theo ba nghĩa vụ pháp lý khác nhau về dữ liệu của trẻ em.
- **Màn hình Bảng theo dõi** — chưa thiết kế, nên chưa có luật nào để ghi.
- **Luồng nhập CSV danh sách lớp** — chỗ duy nhất mật khẩu ban đầu được phép hiện. ADR-13 đã
  chốt luật, nhưng màn hình chưa dựng.
- Quyết định **thiết kế tương tác** (điều hướng rail, hai mật độ, ràng buộc bộ gõ tiếng Việt) không
  thuộc thư mục này. Chúng sống trong mô tả component Figma tương ứng.
