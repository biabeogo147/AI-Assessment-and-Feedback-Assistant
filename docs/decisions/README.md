# Quyết định nghiệp vụ

Mỗi file ở đây ghi **một** quyết định về cách sản phẩm cư xử: ai được làm gì, cái gì không đảo ngược
được, thông tin nào bắt buộc phải hiện. Quyết định **kỹ thuật hoặc quy trình** thì không nằm ở đây —
chúng sống trong mục `## Decision Records` của plan tương ứng.

Quyết định nghiệp vụ ở riêng vì nó thuộc về sản phẩm chứ không thuộc về một thay đổi: plan chạy xong
sẽ chuyển sang `docs/plans/completed/`, nơi không ai được sửa.

| ADR | Quyết định | Trạng thái |
| --- | --- | --- |
| [01](adr-01-vong-doi-de-kiem-tra.md) | Vòng đời đề kiểm tra có bốn trạng thái (hậu ký 13/10/2026: xoá câu không đổi trạng thái; 18/10/2026: đề trống xoá được) | đã mở rộng bởi ADR-02, ADR-18 |
| [02](adr-02-phat-hanh-va-cua-so-thu-hoi.md) | Chỉ giáo viên phát hành; phát hành có sáu tham số (hậu ký 18/10/2026: thu hồi chỉ trước giờ mở) | đã mở rộng bởi ADR-15 |
| [03](adr-03-ranh-gioi-cua-vao.md) | Giờ đóng chặn việc vào làm, không chặn việc nộp (hậu ký 18/10/2026: chữ câu luật mới, in ngày khi mốc khác ngày giờ mở) | đã chốt (phạm vi: pha 1) |
| [04](adr-04-hai-nguon-cau-hoi.md) | Câu hỏi chỉ có hai nguồn; tài liệu là phạm vi (hậu ký 13/10/2026: duyệt đề là đã kiểm mọi câu; 18/10/2026: `questions.source`, chip nguồn thật) | đã chốt (trừ câu luyện tập) |
| [05](adr-05-ba-cong-teacher-in-the-loop.md) | Ba cổng teacher-in-the-loop (hậu ký 19/10/2026: cổng 2 đã bỏ, còn hai cổng) | đã chốt; cổng 2 thay bởi ADR-37 (cổng 1 có ngoại lệ) |
| [06](adr-06-agent-phat-bang-chung.md) | Agent phát bằng chứng, không quyết định (hậu ký 19/10/2026: phần chấm bài và ngưỡng hết đối tượng) | đã chốt (phần chấm bài và ngưỡng: hết đối tượng) |
| [07](adr-07-dieu-gi-dua-ket-qua-toi-giao-vien.md) | Ngưỡng, thứ tự ưu tiên lý do, và phép so bao gồm (hậu ký 18/10/2026: ngưỡng tỉ lệ sai của hàng đợi là chuyện khác, ADR-34) | đã thay bởi ADR-37 |
| [08](adr-08-bon-loai-nghi-ngo.md) | Bốn loại nghi ngờ; thứ vắng mặt với học sinh là *chẩn đoán* (hậu ký 18/10/2026: hàng đợi cùng trọng lượng, rỗng là tin tốt; 19/10/2026: bốn loại thay bởi ADR-37, luật vắng mặt đã thi hành) | đã mở rộng bởi ADR-18; bốn loại nghi ngờ thay bởi ADR-37 |
| [09](adr-09-ket-qua-cham-la-tam-thoi.md) | Kết quả chấm chỉ sống một giờ (hậu ký 19/10/2026: chỉ còn hạn của kết quả job AGENT) | đã chốt; thu hẹp bởi ADR-21 (API 404: hết đối tượng) |
| [10](adr-10-pham-vi-dot-dau.md) | Chỉ giáo viên, chỉ desktop, chat là dòng lệnh | đã chốt |
| [11](adr-11-bo-assessment-type.md) | Bỏ `AssessmentType` khỏi contract (hậu ký 19/10/2026: đã gỡ trọn) | đã chốt |
| [12](adr-12-mau-va-hinh-anh-ma-hoa-luat.md) | Một số màu và hình ảnh mang nghĩa nghiệp vụ cố định | đã chốt |
| [13](adr-13-lop-va-tai-khoan-hoc-sinh.md) | Giáo viên tạo lớp; tài khoản học sinh sinh từ CSV (hậu ký 19/10/2026: mật khẩu một lần đã thi hành, không bắt đổi lần đầu, mã do hệ thống cấp) | đã mở rộng bởi ADR-36 (tạo lớp: chưa có đường) |
| [14](adr-14-hai-pha-lam-bai.md) | Bài kiểm tra có hai pha; nộp bài không phải điểm kết thúc (hậu ký 19/10/2026: tra theo tên hàm) | đã chốt, đã thi hành ở backend |
| [15](adr-15-thoi-gian-pha-hai.md) | Hai đồng hồ ở pha 2; phần giải thích không tính giờ | đã chốt, đang thi hành (hậu ký 17/10/2026: backend đã có hai đồng hồ; 18/10/2026: hết giờ lượt chữa thì màn hỏi BE rồi về màn xem điểm) |
| [16](adr-16-thang-diem-ba-muc.md) | Ba mức điểm; 0,5 nghĩa là hiểu sau khi được dạy | đã chốt, đang thi hành (hậu ký 17/10/2026) |
| [17](adr-17-ba-vong-moi-cau.md) | Ba vòng cho mỗi câu; biến thể sinh từ chính câu đó (hậu ký 18/10/2026: `check_schema` soi cả unique; 19/10/2026: tra theo tên hàm) | đã chốt, đã thi hành ở backend (lưới *giữ nguyên dạng đề*: chưa có) |
| [18](adr-18-cau-hoi-phai-kem-loi-giai.md) | Câu hỏi phải kèm lời giải nhiều cách và nhiễu gắn lỗi | đã chốt, đang thi hành (hậu ký 18/10/2026: `validate_question`; gộp phương án trùng, bắt lời giải chọn sai nhãn) |
| [19](adr-19-bao-cao-giai-thich-chua-ro.md) | Học sinh báo cáo chỗ Kriky giải thích chưa rõ | đã chốt, đang thi hành (hậu ký 18/10/2026: giáo viên đọc ở Bảng theo dõi) |
| [20](adr-20-cham-trac-nghiem-thuoc-be.md) | Chấm trắc nghiệm là việc của BE, không của AGENT (hậu ký 19/10/2026: UC-05 nay là hàng đợi Cần bạn xem) | đã chốt, đã thi hành |
| [21](adr-21-trang-thai-bai-lam-la-ben.md) | Trạng thái bài làm là bền; hạn một giờ chỉ áp cho job | đã chốt, đang thi hành (hậu ký 18/10/2026: bài làm ở Postgres) |
| [22](adr-22-de-co-tac-gia.md) | Đề và lớp có tác giả; của người khác đọc ra như không tồn tại (hậu ký 18/10/2026: đường xoá đề trống; chỉ tác giả xuất bảng điểm) | đã chốt, đang thi hành |
| [23](adr-23-hoi-lai-khi-khong-phan-dinh-duoc.md) | Không phân định được thì hỏi lại; lựa chọn đến từ dữ liệu (hậu ký 19/10/2026: test thứ tự thử đã gỡ) | đã mở rộng bởi ADR-25 |
| [24](adr-24-mot-giao-vien-nhieu-doan-chat.md) | Một giáo viên nhiều đoạn chat; biên bản rơi vào đoạn đã tạo ra đề (hậu ký 18/10/2026: đoạn chat dùng lại đề trống của nó) | đã chốt, đang thi hành |
| [25](adr-25-hai-pha-mot-luot-chat.md) | Một lượt chat có hai pha: lên plan, rồi thực hiện plan | đang thi hành (hậu ký 18/10/2026: job kể lại vẫn chạy) |
| [26](adr-26-chu-sai-cu-phap-di-toi-giao-vien.md) | Chữ sai cú pháp đi tới giáo viên, và giáo viên nhìn thấy chỗ sai (hậu ký 19/10/2026: một câu báo ngắn, bỏ bản in lại ký hiệu) | đã chốt |
| [27](adr-27-tai-lieu-di-vao-ngu-canh-ra-de.md) | Tài liệu đi vào ngữ cảnh ra đề để cung cấp kiến thức (hậu ký 12/10/2026: lọc bài tập chỉ còn cho pha 2; hậu ký 15/10/2026: *mỗi câu một mục* nhường cho ADR-29) | đã chốt, đang thi hành (hậu ký 18/10/2026: qua dàn ý của ADR-29) |
| [28](adr-28-ngan-hang-cau-hoi-ghi-khi-duyet.md) | Ngân hàng câu hỏi nhận câu lúc giáo viên duyệt đề; riêng từng giáo viên; xoá trong đề không xoá ngân hàng | đã chốt, đang thi hành (Kriky rút câu từ ngân hàng: chưa có) |
| [29](adr-29-dan-y-de-truoc-khi-soan.md) | Mọi đề qua một dàn ý giáo viên đã xem; job chỉ nhận mục của nó, không chữ tài liệu thô (hậu ký 17/10/2026: lời dàn ý do Kriky viết, ADR-30) | đã chốt, đang thi hành (hậu ký 18/10/2026: lời đồng ý đọc bằng regex; ô câu hỏng soạn lại được) |
| [30](adr-30-loi-kriky-do-model-viet.md) | Mọi lời Kriky do model viết, bằng Markdown; dàn ý gồm lời và các mục, BE đối chiếu nhẹ; ngoại lệ: thông báo khi model không trả lời được, và phần tử giao diện | đã chốt, đang thi hành (trừ khung học sinh) |
| [31](adr-31-ten-de-kiem-tra.md) | Tên đề tối đa 60 ký tự; đề sách mang tên tệp; giáo viên đổi tên khi đề chưa duyệt; mọi chỗ hiện tên hiện tại (hậu ký 18/10/2026: bỏ khoảng trang của tên tệp) | đã chốt, đang thi hành |
| [32](adr-32-hoi-lai-nhieu-cau.md) | Hỏi lại tối đa ba câu một lượt, mỗi câu một bộ nút; không bỏ câu; tóm tắt rồi gửi gộp một tin | đã chốt, đang thi hành |
| [33](adr-33-chi-de-trong-moi-xoa-duoc.md) | Chỉ đề trống mới xoá được, và xoá cứng; một đoạn chat dùng lại đề trống của nó | đã chốt, đang thi hành |
| [34](adr-34-hang-doi-review-va-diem-gop.md) | Hàng đợi *Cần bạn xem* (báo cáo gom theo đề; tỉ lệ sai ≥ 70%, trên 20 bài, sau giai đoạn 2) và điểm gộp theo lớp quy về thang 10 | đã chốt, đang thi hành |
| [35](adr-35-sua-loi-giai-sau-phat-hanh.md) | Câu trong đề đã phát hành không bao giờ sửa; sửa lời giải là sửa bản trong ngân hàng | đã chốt, đang thi hành |
| [36](adr-36-dang-nhap-va-tai-khoan.md) | Đăng nhập bằng phiên cookie, mỗi vai một cookie; giáo viên tự đăng ký; giáo viên phát tài khoản học sinh, dòng trùng tên phải xác nhận | đã chốt, đang thi hành |
| [37](adr-37-bo-cong-do-tin-thap.md) | Bỏ cổng *kết quả độ tin thấp*; còn hai cổng teacher-in-the-loop; hàng đợi giáo viên là *Cần bạn xem* | đã chốt |

Khuôn cho ADR mới: [adr-00-template.md](adr-00-template.md). Mục cuối — *Nơi luật này đang được thi
hành* — là mục bắt buộc và là thứ mọi decision record cũ trong `docs/plans/completed/` đều thiếu.

## Nguồn thiết kế

Phần lớn luật ở đây hiện chỉ được thi hành trong **file thiết kế Figma**, chưa có ở backend:

<https://www.figma.com/design/mOe2ZmrqOq1Uix45v6PNGD>

Hai trang màn hình xếp **mỗi hàng một chặng nghiệp vụ, trái sang phải theo thứ tự luồng**; biến thể
`b`, `c`, `d` của một màn đứng ngay sau màn gốc (sắp lại ngày 19/10/2026). Số artboard là số lúc vẽ,
không phải thứ tự luồng; code và tài liệu gọi artboard bằng số và node id, nên số không đổi.

Trang `Screen — Teacher` (`12:2`, tên cũ `Screen — Chat`):
1. tài khoản giáo viên: 26, 26c, 26b, 27;
2. lớp học: 9, 10, 11, 23 (kết quả một đề trong lớp, bài làm một học sinh), 28, 28d, 28b, 28c, 10b;
3. luồng chat từ lúc mở tới lúc phát hành xong: 1, 2, 3, 3b, 4, 16, 5, 17, 6, 12, 14, 18, 18b, 19b
   (hộp chọn câu, mở từ nút cuối panel màn 6), 19 (đề sau khi thêm), 7, 15 (xoá câu sau khi bỏ duyệt),
   8, rồi 13 (xoá một đoạn chat);
4. theo dõi: 20, 25, 25b, 29;
5. bài kiểm tra và ngân hàng câu hỏi: 21, 22, 22b;
6. các khung *Ghi chú* và *Đã duyệt …*, mỗi khung ghi một quyết định thiết kế kèm ngày.

Trang `Screen — Student` (`278:2`):
1. pha 1: 12, 12b (đăng nhập), 13, 13c (dải trên khi đăng xuất chưa được), 13b, 14, 15, 16, 17;
2. pha 2: 18, 19, 20, 21, 22, 18b (hỏi trợ lý khi đang có lượt chữa mở), 22b, 16b, 23, 24, 25 — màn
   hỏi trợ lý ở hình dạng **bài đã kết thúc** đọc lại được, không nhắn thêm được.

Số `12`–`29` trùng giữa hai trang: gọi một artboard thì gọi kèm tên trang. Hai màn kết quả là **hai artboard riêng** cho hai hình dạng
dữ liệu, không phải hai state của một. Tất cả chạy Density mode `Student` và không có rail.

Trang `Components` chứa các component set, và **mô tả của từng component set là nơi nhiều luật nghiệp
vụ được ghi lần đầu**. Khi một ADR trỏ tới một node id, node đó nằm trong file này.

## Còn thiếu

Bốn luật từng nằm ở mục này — thứ tự ưu tiên lý do review, phép so ngưỡng bao gồm, giá trị `0.7`, và
hạn giữ kết quả một giờ — từng có ADR-07 và ADR-09. Ba luật đầu đã bỏ cùng cổng độ tin thấp (ADR-37).
Bảng theo dõi đã có ADR-34; nhập danh sách lớp và mật khẩu một lần đã có ADR-36.

Còn lại, và cố ý chưa viết:

- **Một luật của mô hình hai pha chưa ai quyết**, nằm ở `docs/plans/backlog.md`: câu luyện tập có
  qua cổng duyệt không. Câu hỏi *`confidence` đo cái gì khi phần chấm đã xác định* thì đã khép: không
  có độ tin nào để đo, và cổng dùng nó đã bỏ (ADR-37). Vòng đếm và đồng hồ khi học sinh mở hai tab thì đã có
  chỗ đứng: trạng thái lượt nằm ở database (ADR-21), và lượt đang mở đọc lại được ở tab mới (plan
  `backlog-tier-1`, pha 2). Mức điểm 0,5 thì đã hết là câu hỏi: ADR-16 chốt nó **không được cấp màu mới**, phân biệt
  bằng hình tròn đầy / nửa / rỗng.
- **Hạn lưu trữ dài hạn của bài làm** — ADR-21 chốt trạng thái bài làm là bền, nhưng *bền tới bao
  giờ* thì chưa ai quyết. Một học kỳ, một năm, hay tới khi giáo viên xoá lớp: ba câu trả lời khác
  nhau kéo theo ba nghĩa vụ pháp lý khác nhau về dữ liệu của trẻ em.
- **Tạo lớp** — ADR-13 nói giáo viên tạo lớp, nhưng chưa có đường nào tạo lớp
  (`docs/plans/backlog.md`).
- Quyết định **thiết kế tương tác** (điều hướng rail, hai mật độ, ràng buộc bộ gõ tiếng Việt) không
  thuộc thư mục này. Chúng sống trong mô tả component Figma tương ứng.
