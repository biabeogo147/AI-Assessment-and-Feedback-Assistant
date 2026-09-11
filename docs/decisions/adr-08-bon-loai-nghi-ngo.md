# ADR-08 — Bốn loại nghi ngờ, và điều học sinh không được thấy

- **Trạng thái:** đã mở rộng bởi ADR-18 (luật *vắng mặt về cấu trúc*: chưa thi hành)
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
- **Thu hẹp (2026-09-10): thứ cần giữ lại là *chẩn đoán*, không phải *kết quả*.** Với trắc nghiệm,
  đáp án đúng chỉ có một, nên đúng/sai là một phép so và không có gì để mà không chắc. Cái thật sự
  không chắc là *em sai vì cái gì*: cùng một phương án nhiễu có thể do nhiều lỗi khác nhau. Luật vắng
  mặt vì thế phủ `misconception_code` và `feedback_text`, không phủ việc học sinh biết mình đúng hay
  sai.
- **Và ở đợt hai pha, chẩn đoán không còn độ tin cậy nào.**
  [ADR-18](adr-18-cau-hoi-phai-kem-loi-giai.md) bắt mỗi phương án nhiễu mang sẵn lỗi mà nó đại diện,
  nên chẩn đoán là **tra cứu** chứ không phải suy đoán. Luồng học sinh vì thế **không có trạng thái
  chờ giáo viên**. Đây là việc gỡ một luật đang chạy khỏi một luồng, không phải một chú thích: xem
  `docs/plans/backlog.md` để biết cái gì phải đúng trước khi bật lại.
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
- Sau khi thu hẹp, **sản phẩm không còn chỗ nào nói với học sinh rằng nó chưa chắc**. Đó là cái giá
  của [ADR-18](adr-18-cau-hoi-phai-kem-loi-giai.md), và ADR đó phải tự tranh luận với nó.
- Component `Student result — chờ giáo viên` (`6:50`) trong Figma vì thế **sẽ không có instance nào**.
  Nó ở lại vì luật ở lại; chỉ luồng hiện tại không đi qua nó.
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
- Figma trang `Screen — Student` — **mười hai artboard, không màn nào** hiện `confidence`,
  `misconception_code`, lý do review, hay trạng thái *chờ giáo viên*. Chẩn đoán chỉ xuất hiện dưới
  dạng lời nói thường trong đoạn chat của pha 2 (*"Đó là khoảng hàm số NGHỊCH biến"*) và dưới dạng
  một dòng lỗi trong hộp lời giải — không chỗ nào là con số. Đây là luật **vắng mặt**, nên bằng
  chứng của nó cũng là một phép quét: quét cả trang không ra token nào trong ba token đó.
- **Chưa có test** nào canh luật vắng mặt về cấu trúc.
- **Đang bị vi phạm ở code.** `services/be/src/be/routes.py:125-136` trả đúng **một** hình dạng
  `GradedResult`, luôn kèm `score`, `confidence`, `misconception_code` và `feedback_text`, bất kể
  `needs_teacher_review`. **Phía FE thì hết vi phạm**: màn demo từng hiện Điểm, Độ tin cậy và Nhận
  xét đã bị thay bằng luồng học sinh thật, và `services/be/tests/test_core_flow.py` có test quét mọi
  response của học sinh để chắc ba trường ấy không lọt ra. Đường `/api/submissions` vẫn trả hình
  dạng cũ, nhưng không màn hình nào gọi nó nữa.
