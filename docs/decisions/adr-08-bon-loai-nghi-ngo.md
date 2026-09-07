# ADR-08 — Bốn loại nghi ngờ, và điều học sinh không được thấy

- **Trạng thái:** đã chốt (luật *vắng mặt về cấu trúc*: đã chốt, chưa thi hành)
- **Ngày:** 2026-09-06

## Bối cảnh

`ReviewReason` có bốn giá trị. Rất dễ đọc chúng thành bốn **mức** nghiêm trọng và xếp hạng chúng trên
giao diện, trong khi chúng là bốn **loại** nghi ngờ khác nhau về bản chất.

Đồng thời có một luật chưa được thi hành ở đâu: kết quả độ tin cậy thấp **không được hiện cho học sinh**
trước khi giáo viên xử lý.

## Quyết định

- Bốn `ReviewReason` là bốn **loại** nghi ngờ, không phải bốn mức nghiêm trọng. Giao diện hiển thị
  chúng **cùng trọng lượng**. Việc *chọn* lý do nào để báo khi nhiều điều kiện cùng đúng thì có thứ
  tự, và thứ tự đó sống ở backend — xem [ADR-07](adr-07-dieu-gi-dua-ket-qua-toi-giao-vien.md).
- `ANOMALY` **chưa sinh ra được** vì nó cần lịch sử làm bài, mà hệ thống chưa lưu gì. Nó vẫn ở trong
  enum để lúc thi hành không phải đổi contract.
- Kết quả độ tin cậy thấp phải **vắng mặt về mặt cấu trúc** với học sinh — không có điểm, không có nhận
  xét, không có mã lỗi sai trong dữ liệu gửi xuống, chứ không phải ẩn bằng một cờ hiển thị.
- **Hàng đợi rỗng là kết quả tốt**, không được trình bày như lỗi tải dữ liệu.

## Vì sao

Bốn loại cùng trọng lượng vì chúng đòi giáo viên làm bốn việc khác nhau, không phải cùng một việc ở bốn
mức gấp. Xếp hạng chúng sẽ khiến ba loại dưới bị bỏ qua.

`ANOMALY` ở lại enum vì thêm một giá trị vào contract sau này là thay đổi contract, mà contract đi qua
hàng đợi giữa hai service — đắt hơn hẳn việc để sẵn một giá trị chưa dùng. Nhưng phải ghi rõ nó chưa
sinh ra được, nếu không người đọc sẽ tưởng bốn control point đều đang chạy.

**Vắng mặt về cấu trúc** chứ không phải ẩn, vì một cờ hiển thị có thể bị bật nhầm, còn dữ liệu không tồn
tại thì không lộ được. Luật này bảo vệ học sinh khỏi một kết luận mà chính hệ thống chưa dám tin.

Hàng đợi rỗng nghĩa là mọi kết quả gần đây đều đủ tin cậy — đó là tin tốt. Vẽ nó giống màn hình lỗi sẽ
dạy giáo viên lo lắng nhầm chỗ.

## Hệ quả

- Không được thêm trường sắp hạng hay mức độ vào `ReviewReason`. Muốn phân loại nặng nhẹ thì phải là
  một khái niệm khác, không phải mở rộng enum này.
- Màn hình kết quả của học sinh cần **hai hình dạng dữ liệu khác nhau** cho hai trạng thái, không phải
  một hình dạng với vài trường rỗng. Đắt hơn khi dựng, nhưng là cách duy nhất luật trên không bị phá
  bằng một dòng cấu hình.
- Chừng nào chưa lưu lịch sử làm bài, một trong bốn control point của Workflow 4 vẫn nằm chết trong
  enum. Bất kỳ báo cáo nào đếm "đã phủ mấy control point" đều phải trừ nó ra.

## Nơi luật này đang được thi hành

- `packages/contracts/src/contracts/enums.py` — `ReviewReason` với bốn giá trị và docstring giải thích
  vì sao một cờ boolean là không đủ.
- `services/be/src/be/review_policy.py:31-34` — docstring nói rõ `ANOMALY` chưa reachable.
- `AGENTS.md` bảng Invariants — dòng *"A low-confidence result is not shown to the Student before a
  Teacher handles it"*, hiện nằm ở nhóm **chưa enforce**.
- Figma `mOe2ZmrqOq1Uix45v6PNGD` — `Review reason` (`5:53`) bốn variant cùng trọng lượng;
  `Student result — chờ giáo viên` (`6:50`) không có điểm/nhận xét/lỗi sai trong cấu trúc;
  `Empty state` (`6:65`) variant `queue-rong` dùng họ màu settled.
- **Chưa có test** nào canh luật vắng mặt về cấu trúc.
- **Đang bị vi phạm ở code.** `services/be/src/be/routes.py:125-136` trả đúng **một** hình dạng
  `GradedResult`, luôn kèm `score`, `confidence`, `misconception_code` và `feedback_text`, bất kể
  `needs_teacher_review`. `services/fe/src/App.tsx:94-113` — màn hình nộp bài thử — hiện Điểm, Độ tin
  cậy và Nhận xét trước, rồi mới hiện băng *"Cần giáo viên xem lại"*. Đó là màn hình demo, không phải
  trải nghiệm học sinh thật, nhưng nó là nợ phải trả trước khi dựng màn hình học sinh.
