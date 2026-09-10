# ADR-15 — Thời gian ở pha 2: hai đồng hồ, và chỉ một trong hai chạy khi học sinh đang học

- **Trạng thái:** đã chốt
- **Ngày:** 2026-09-10

## Bối cảnh

[ADR-14](adr-14-hai-pha-lam-bai.md) cho bài kiểm tra một pha thứ hai. Pha đó cần thời gian, và thời
gian của nó không giống pha 1 ở bất cứ điểm nào: số câu phải làm **thay đổi theo từng lượt**, phần học
sinh đọc lời giải thì **không nên bị hối**, và cả pha có thể kéo dài tới cuối ngày.

[ADR-03](adr-03-ranh-gioi-cua-vao.md) đã cho thấy ba con số thời gian rất dễ bị gộp thành một trong đầu
người đọc. Pha 2 thêm hai con số nữa, nên nguy cơ đó tăng chứ không giảm.

## Quyết định

- Phát hành đề nhận thêm **hai** tham số cho pha 2: **số phút mỗi câu** và **hạn kết thúc pha 2**.
  Tổng cộng phát hành có sáu tham số; xem [ADR-02](adr-02-phat-hanh-va-cua-so-thu-hoi.md).
- **Số phút mỗi câu là một tỉ lệ, không phải một khoảng.** Thời lượng một lượt bằng số phút mỗi câu
  nhân số câu còn dở trong lượt đó. Sai hai câu với tỉ lệ 5 phút mỗi câu thì lượt đó là 10 phút.
- Thời lượng ấy là một **quỹ chung** cho cả lượt. Học sinh được dồn thời gian sang câu khó hơn.
- **Phần Kriky giải thích và học sinh hỏi lại không tính giờ.** Đồng hồ chỉ bắt đầu khi học sinh **tự
  bấm** nút làm bài mới.
- **Hạn kết thúc pha 2 là một mốc tuyệt đối** do giáo viên đặt, chung cho cả lớp, và dài hơn hẳn hạn
  của pha 1 — có thể là cuối ngày.
- **Hết hạn thì cắt**, kể cả khi học sinh đang làm dở một lượt. Câu chưa xong nhận 0 điểm.
- Một lượt vẫn được mở kể cả khi thời lượng của nó vượt quá phần hạn còn lại.

## Vì sao

Tỉ lệ thay vì khoảng cố định, vì số câu phải chữa **giảm dần qua từng lượt**. Một khoảng cố định sẽ quá
rộng ở lượt cuối và quá chật ở lượt đầu, và giáo viên không có cách nào đoán trước lớp mình sai bao
nhiêu câu để đặt cho đúng.

Phần giải thích không tính giờ vì **đó là lúc học sinh đang học**, không phải lúc em đang chứng minh.
Đặt đồng hồ lên một cuộc giải thích là dạy học sinh gật cho xong rồi bấm tiếp. Đồng hồ chỉ có nghĩa ở
phần đo được, và phần đo được là câu biến thể.

Ranh giới đặt ở nút làm bài mới vì đó là hành động **học sinh tự chọn**. Một cánh cửa một chiều mà
người đi qua tự mở thì công bằng; một cánh cửa tự đóng sau lưng họ thì không.

**Hết hạn thì cắt** là chỗ pha 2 đi ngược pha 1, và điều đó có chủ đích.
[ADR-03](adr-03-ranh-gioi-cua-vao.md) chọn *không dừng người đang làm* vì ở pha 1 thời gian là **thứ
được cấp cho mỗi người**, đo từ lúc họ vào, nên cắt ngang là lấy lại thứ đã hứa. Ở pha 2 thì ngược:
thời lượng lượt do học sinh **tự chọn lúc nào bắt đầu**, và hạn cuối là một mốc họ nhìn thấy suốt cả
ngày. Không cắt nghĩa là hạn cuối không tồn tại — ai cũng có thể mở một lượt dài lúc còn một phút và
kéo bài kiểm tra qua đêm. Ai đọc hai luật này rồi thấy chúng không nhất quán thì phải đọc lại đoạn này
trước khi sửa một trong hai.

## Hệ quả

- **Giao diện phải nói trước rằng lượt này có thể bị dừng**, ngay tại nút làm bài mới, kèm số phút còn
  lại thật. Một học sinh bị dừng giữa chừng mà không được báo trước sẽ tin là hệ thống hỏng. Từ dùng
  với học sinh là **dừng**, và nó được in đậm trong câu luật — *cắt* là từ nội bộ của ADR này.
- **Giáo viên phải đặt một con số mà họ chưa từng phải nghĩ tới.** Không có kinh nghiệm nào giúp đoán
  mấy phút là đủ cho một câu chữa, và đặt sai thì hoặc lớp không kịp, hoặc bài kiểm tra kéo lê.
- Vì số phút mỗi câu là **một con số cho cả đề**, một câu dài và một câu ngắn được cấp thời gian như
  nhau. Muốn phân biệt thì phải là một khái niệm khác, không phải nới tỉ lệ này.
- **Tổng thời gian một học sinh bỏ ra không dự đoán được**, vì phần giải thích không giới hạn. Mọi
  tính năng sau này muốn báo cáo em học bao lâu đều phải đo, không suy ra được từ cài đặt.
- Hai con số mới phải đi qua **cùng cả ba nơi** mà [ADR-03](adr-03-ranh-gioi-cua-vao.md) đòi cho các
  mốc pha 1: lúc đang chọn, lúc xác nhận, và trong biên bản sau khi phát hành.

## Nơi luật này đang được thi hành

- Figma `Publish settings` (`67:41`) — nhóm **PHA 2** với hai trường *PHÚT MỖI CÂU* và
  *HẠN CHỮA XONG*, ở cả hai variant.
- Figma — chuỗi *"Chữa bài tới hết 22:00 - mỗi lượt 5 phút một câu, và hết hạn thì lượt đang làm bị
  **DỪNG**."* xuất hiện **giống hệt nhau ở bốn nơi**: `Publish settings` (`67:41`), `Consequence dialog`
  (`11:41`), `Action result card` variant `đã-phát-hành` (`10:45`), và variant `chưa có lớp`
  (`77:341`) — đúng như [ADR-03](adr-03-ranh-gioi-cua-vao.md) đòi.
- Figma `Publish settings` (`67:41`) — mô tả component ghi định dạng ngày giờ `HH:MM · DD/MM` là
  **ràng buộc**, vì cột pha 1 chỉ rộng 119 và trừ padding còn 94.
- **Chưa có ở backend**: `packages/contracts` không có trường thời gian nào, kể cả của pha 1.
- **Bị chặn**: một đồng hồ chạy xuyên qua nhiều lượt là trạng thái có nhớ, mà
  [ADR-09](adr-09-ket-qua-cham-la-tam-thoi.md) xoá mọi thứ sau một giờ. Xem `docs/plans/backlog.md`.
