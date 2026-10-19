# ADR-37 — Bỏ cổng *kết quả độ tin thấp*; hàng đợi giáo viên là *Cần bạn xem*

- **Trạng thái:** đã chốt
- **Ngày:** 2026-10-19

## Bối cảnh

[ADR-05](adr-05-ba-cong-teacher-in-the-loop.md) đặt ba cổng teacher-in-the-loop. Cổng thứ hai: một kết
quả chấm có độ tin cậy thấp phải chờ giáo viên xử lý rồi mới tới học sinh.
[ADR-07](adr-07-dieu-gi-dua-ket-qua-toi-giao-vien.md) định khi nào một kết quả rơi vào hàng đợi ấy
(ngưỡng 0.7, ba điều kiện), [ADR-08](adr-08-bon-loai-nghi-ngo.md) định bốn loại nghi ngờ `ReviewReason`.

Tới 19/10/2026 cổng ấy không còn gì để chặn:

- Trắc nghiệm do BE chấm bằng một phép so đáp án
  ([ADR-20](adr-20-cham-trac-nghiem-thuoc-be.md)). Không có độ tin cậy nào để so ngưỡng.
- Chẩn đoán ở pha 2 là **tra cứu** lỗi gắn sẵn trên phương án nhiễu
  ([ADR-18](adr-18-cau-hoi-phai-kem-loi-giai.md)), không phải suy đoán.
- Đường chấm cũ (`POST /api/submissions` → `grade_submission` → `decide_review`) đã xoá ngày
  09/10/2026, cùng `ReviewReason`, `GradingRequested`, `GradingCompleted` và
  `REVIEW_CONFIDENCE_THRESHOLD`.

Nhưng ba ADR kia vẫn mô tả cổng như một luật đang đứng. Một dev mới đọc chúng sẽ đi tìm hoặc dựng
lại một hàng đợi độ tin thấp mà sản phẩm đã không cần.

## Quyết định

- **Không có cổng kết quả độ tin thấp.** Không kết quả chấm nào bị giữ lại chờ giáo viên. Học sinh
  thấy điểm pha 1 ngay khi nộp, và điểm ấy là sàn
  ([ADR-16](adr-16-thang-diem-ba-muc.md)).
- **Còn hai cổng teacher-in-the-loop**, giữ nguyên số thứ tự của ADR-05 để các ADR cũ còn đọc đúng:
  - **cổng thứ nhất**: giáo viên duyệt đề trước khi phát hành, với ngoại lệ câu luyện tập ở pha 2;
  - **cổng thứ ba**: Kriky hỏi lại khi chưa đủ thông tin.

  Không có cổng thứ hai. Ranh giới của cổng hỏi lại giữ nguyên như ADR-05.
- **Hàng đợi giáo viên (Teacher Review Queue) là hàng đợi *Cần bạn xem*** của
  [ADR-34](adr-34-hang-doi-review-va-diem-gop.md). Nó nhận báo cáo *giải thích chưa rõ* của học sinh
  ([ADR-19](adr-19-bao-cao-giai-thich-chua-ro.md)) và câu có tỉ lệ sai cao. Nó **không chặn** học sinh
  nào, nên nó không phải một cổng.
- **Hai luật của ADR-08 vẫn đứng.**
  - Chẩn đoán không bao giờ tới học sinh dưới dạng con số hay mã: không `confidence`, không
    `misconception_code`, không lý do duyệt trong dữ liệu gửi xuống.
  - Các loại dòng trong hàng đợi cùng trọng lượng, và hàng đợi rỗng là tin tốt.
- Một luồng sau này cần giáo viên chặn kết quả trước học sinh thì phải mở **ADR mới**, kèm thứ nó đo.
  Ví dụ: chấm tự luận. Ngưỡng 0.7 của ADR-07 không tự sống lại. Câu luyện tập chưa qua cổng nào là lỗ
  của cổng thứ nhất, không phải của cổng này.

## Vì sao

Một cổng không có gì để chặn là một lời hứa rỗng. Nó buộc mỗi tài liệu nhắc *ba cổng* phải giải
thích vì sao cổng thứ hai không chạy. Nó còn mời người sau dựng lại đường chấm qua AGENT, thứ ADR-20
đã gỡ vì lý do thật: điểm sàn không được phụ thuộc vào một dịch vụ bên ngoài.

Giáo viên vẫn cần một chỗ để nhìn thấy việc. Nhưng việc thật là học sinh báo một lời giải khó hiểu,
hay một câu nhiều em sai. Cả hai đều nhìn qua nhiều bài, sau khi bài đã trả về, và không lý do nào
đáng để bắt học sinh chờ.

## Hệ quả

- Câu *"ba cổng"* ở mọi tài liệu đổi thành hai cổng. ADR-05, 06, 07, 08 có hậu ký 19/10/2026 trỏ về
  đây; ADR-10, 14, 18, 19, 26, 27, 29 nhắc *ba cổng* hay *cổng thứ tư* nên cũng có một hậu ký ngắn.
  Một kênh mới không chặn ai thì vẫn phải tự nói nó không phải một cổng, như ADR-19 đã làm.
- ADR-07 **đã thay bởi ADR-37** toàn bộ: nó chỉ nói về cổng này.
- ADR-08 giữ hai luật ở trên. Bốn `ReviewReason` và `ANOMALY` chỉ còn là lịch sử.
- Lỗ đã biết của cổng duyệt đề thì vẫn mở: câu luyện tập ở pha 2 chưa qua cổng nào. Xem
  `docs/plans/backlog.md`, mục *Câu luyện tập chưa qua cổng duyệt nào*.
- Figma còn các component của cổng cũ: `Review reason` (`5:53`), `Student result — chờ giáo viên`
  (`6:50`), `Confidence meter` (`5:32`), mô tả của `Clarify request` (`64:23`) ghi ba cổng. Không màn
  nào dùng ba component đầu. Mô tả `64:23` phải đổi khi Figma được sửa lần tới.

## Nơi luật này đang được thi hành

- **Không có đường giữ kết quả**: BE chấm ngay trong request nộp bài (ADR-20); không còn
  `review_policy.py`, `ReviewReason` hay `REVIEW_CONFIDENCE_THRESHOLD` trong code.
- `services/be/tests/test_core_flow.py` — `test_student_payloads_carry_no_diagnosis_numbers`. Test quét
  response của học sinh; không có `confidence`, `misconception`, `review_reason`.
- `services/be/src/be/student_routes.py` — docstring đầu tệp nêu cùng luật ấy.
- `services/agent/tests/test_no_routing_decision.py` — AGENT không trả về trường phán xử nào
  (invariant *AGENT emits no routing decision* của `AGENTS.md`).
- `services/be/src/be/teacher_board.py` — `ReviewItem.kind` chỉ có `reports` và `wrong_rate`;
  `services/be/tests/test_teacher_board.py` canh hàng đợi.
