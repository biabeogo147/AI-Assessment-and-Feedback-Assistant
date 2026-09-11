# ADR-19 — Học sinh báo cáo chỗ Kriky giải thích chưa rõ, và vì sao đó không phải cổng thứ tư

- **Trạng thái:** đã chốt (nửa học sinh đã có ở Figma; phía giáo viên và backend chưa)
- **Ngày:** 2026-09-10

## Bối cảnh

[ADR-18](adr-18-cau-hoi-phai-kem-loi-giai.md) để trợ lí giải thích lỗi sai theo lời giải đã soạn. Nếu
lời giải khó hiểu, hoặc ánh xạ nhiễu chỉ sai lỗi, học sinh là **người duy nhất biết** — và hiện không
có đường nào để em nói điều đó.

`docs/diagrams/activity-overview.drawio` đã có sẵn một nhánh tên *Feedback khó hiểu*, và nhánh ấy dẫn
thẳng tới *Teacher xem lại feedback của System/AI*, tức là một chỗ dừng lại chờ người **ở giữa luồng**.
Nếu để nguyên, sản phẩm có cổng teacher-in-the-loop thứ tư, trong khi
[ADR-05](adr-05-ba-cong-teacher-in-the-loop.md) chốt là có đúng ba.

## Quyết định

- Học sinh **đánh dấu** một câu hoặc một đoạn hội thoại là *giải thích chưa rõ*. Giáo viên xem được.
- Có **hai thời điểm** báo cáo: ngay trước khi bấm nút làm bài mới, tức lúc còn đang khó hiểu; và sau
  khi bài của **chính em đó** kết thúc.
- **Kết thúc tính theo từng học sinh**, không chờ cả lớp. Em xong lúc mười giờ sáng báo cáo được ngay,
  dù hạn của lớp là cuối ngày.
- Việc báo cáo **không chặn gì cả**: không chặn học sinh, không chặn lượt, không chặn điểm, không chặn
  bài kết thúc.
- Vì không chặn, **đây không phải cổng teacher-in-the-loop thứ tư.** ADR-05 vẫn có ba cổng.

## Vì sao

Thời điểm thứ nhất — trước khi làm bài mới — tồn tại vì đó là lúc **tín hiệu đúng nhất**. Học sinh vừa
đọc lời giải và biết mình chưa hiểu; hỏi lại điều đó sau ba vòng và một buổi chiều thì em chỉ còn nhớ
là mình sai. Nó cũng đặt nút báo cáo đúng chỗ nó có ích: ngay cạnh thứ đang khó hiểu.

Thời điểm thứ hai tồn tại vì có những chuyện chỉ nhìn ra khi đã xong: ba vòng đều sai, và em nhận ra
mình vẫn không hiểu vì sao.

Không chặn ai, vì báo cáo này nói về **chất lượng của trợ lí**, không phải về kết quả của một học
sinh. Nếu nó chặn, giáo viên phải xử lý bốn mươi báo cáo trước khi lớp đóng bài, và mọi em báo cáo đều
bị treo lại vì một việc không phải của em.

Đó cũng chính là lý do nó không phải cổng. Một cổng theo ADR-05 là chỗ hệ thống **dừng lại chờ người**
trước khi đi tiếp. Ở đây không có gì dừng lại: bài đã kết thúc hoặc đang chạy tiếp, và báo cáo đi
đường riêng. Ranh giới này phải được ghi ra, nếu không người sau đếm bốn cổng và sẽ hoặc dựng một cổng
không cần thiết, hoặc kết luận rằng ADR-05 đã sai.

Và nó đóng một vòng sản phẩm chưa từng có: học sinh nói lời giải khó hiểu, giáo viên xem, giáo viên
sửa lời giải đã lưu, ngân hàng câu hỏi tốt lên. Đây là bề mặt **duy nhất** nơi học sinh đánh giá trợ
lí.

## Hệ quả

- **Giáo viên nhận được một loại việc mới không có hạn xử lý.** Nó không nằm trong hàng đợi review —
  hàng đợi ấy dành cho việc chặn — nên nó cần một chỗ khác, và chỗ đó chưa tồn tại.
- **Giáo viên có thể đọc báo cáo về một lời giải sai trong lúc ba mươi em khác đang được dạy bằng
  chính nó**, mà không có nút nào để dừng lại. Đó là cái giá trực tiếp của việc không chặn, và nó đã
  được chọn có chủ đích.
- **Báo cáo không có nghĩa là lời giải sai.** Nó có thể chỉ nghĩa là một em chưa hiểu. Mọi thiết kế
  đọc dữ liệu này phải chống được việc đếm số báo cáo rồi kết luận về chất lượng câu hỏi.
- Vì kết thúc tính theo từng em, **giáo viên không có một thời điểm nào để biết mình đã nhận đủ báo
  cáo**. Chúng nhỏ giọt suốt cả ngày.
- Hội thoại phải được **lưu lại đủ để trích dẫn**. Một báo cáo trỏ vào một đoạn chat đã biến mất thì
  vô dụng, và [ADR-09](adr-09-ket-qua-cham-la-tam-thoi.md) hiện xoá mọi thứ sau một giờ.

## Nơi luật này đang được thi hành

**Nửa phía học sinh đã có ở Figma. Phía giáo viên chưa.**

- **Ở Figma**: `Report control` (`281:25`), nhãn *"Báo cáo Trợ lý giải thích khó hiểu"*. **Một nút mỗi
  màn, đặt ở chân màn cạnh nút *Làm bài mới*** — artboard `19`, `20` và `24`. Bản trước gắn nó vào
  từng lượt trả lời của Kriky; một đoạn chat năm lượt khi đó có ba nút giống hệt nhau, và cái lặp ấy
  đọc ra như lỗi dựng chứ không như một quyền.
- **Cái được báo cáo là cả đoạn chat của bài này**, không phải một câu trả lời lẻ. Trợ lí bao quát cả
  bài — mọi câu sai nằm cùng một màn — nên gắn báo cáo vào một lượt là hứa một phạm vi hẹp hơn thực
  tế. Ngữ cảnh giáo viên cần vẫn còn: đoạn chat đi kèm bài và những câu em đó làm sai.
- **Màn `17` không có nút này.** Ở đó Kriky mới chỉ chào, chưa giải thích gì; một báo cáo không có
  nội dung để trỏ tới thì giáo viên đọc được gì.
- **Thời điểm thứ hai đã có bề mặt riêng**: từ màn kết quả `22`, nút **ở đầu màn**
  *"Xem lại phần chữa các câu sai"* mở artboard `24` — màn hỏi trợ lý ở hình dạng **bài đã kết
  thúc**: lịch sử chat còn nguyên, ô nhập bị khoá, nút *Làm bài mới* biến mất, còn nút báo cáo thì
  **không**. Báo cáo không chặn ai nên nó sống lâu hơn cả bài kiểm tra.
- Bản trước đặt một link trên từng hàng điểm; link ấy đã bỏ vì nó hứa một đoạn chat riêng cho mỗi
  câu, mà trợ lí không làm việc theo câu.
- **Chưa có ở Figma phía giáo viên**: chưa có màn nào để đọc báo cáo; xem `docs/plans/backlog.md`.
- **Chưa có ở backend**: không endpoint, không model.
- `docs/diagrams/activity-overview.drawio` đã bỏ nhánh chặn giữa luồng và vẽ kênh này bằng cạnh nét
  đứt xuất phát **sau** node kết thúc, nhãn *không chặn luồng*. `use-case.drawio` có
  `Báo cáo giải thích chưa rõ` `<<extend>>` `Chữa bài sau khi nộp (pha 2)`, không có association từ
  Teacher — vì chỗ Teacher đọc báo cáo chưa tồn tại.
- **Bị chặn**: xem `docs/plans/backlog.md`.
