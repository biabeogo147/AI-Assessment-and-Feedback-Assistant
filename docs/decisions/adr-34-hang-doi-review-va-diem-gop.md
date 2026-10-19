# ADR-34 — Hàng đợi *Cần bạn xem* và điểm gộp theo lớp trên Bảng theo dõi

- **Trạng thái:** đã chốt, đang thi hành
- **Ngày:** 2026-10-18

## Bối cảnh

Tới ngày 18/10/2026, đích *Bảng theo dõi* trên rail chỉ có một đầu trang. Hai loại tín hiệu cần chỗ
đứng ở đó:

- báo cáo *giải thích chưa rõ* của học sinh ([ADR-19](adr-19-bao-cao-giai-thich-chua-ro.md)), chưa có
  màn nào để giáo viên đọc;
- câu nhiều em làm sai, thứ chỉ thấy được khi nhìn qua nhiều bài.

Cộng thêm một lớp nhìn thứ ba: điểm gộp của từng lớp qua các đề. ADR-19 dặn rằng báo cáo **không** phải
một kết luận về chất lượng câu hỏi. [ADR-08](adr-08-bon-loai-nghi-ngo.md) dặn rằng các loại nghi ngờ
cùng trọng lượng, và hàng đợi rỗng là tin tốt.

## Quyết định

- **Hàng đợi *Cần bạn xem* có hai loại dòng, cùng trọng lượng**: không tô màu loại, không xếp nặng nhẹ
  (ADR-08). Báo cáo mới nhất đứng trước, rồi tới các câu theo tên đề và số câu.
- **Giải thích chưa rõ: một dòng mỗi đề.** Báo cáo gắn với cả lượt làm bài (ADR-19), nên gom theo đề.
  Dòng ghi số học sinh đã báo cáo, **không ghi lớp**. Màn của đề liệt kê các báo cáo, cùng các câu em
  ấy làm sai ở lần đầu.
- **Đánh dấu đã xem theo đề**, cột `reports.resolved_at`. Chỉ những báo cáo màn hình đã hiện được đánh
  dấu: một báo cáo đến trong lúc giáo viên đang đọc thì ở lại, và đưa đề vào lại hàng đợi.
- **Tỉ lệ sai cao: một dòng mỗi câu.** Câu vào hàng đợi khi:
  - **≥ 70%** bài sai ở lần làm đầu;
  - **trên 20 bài**;
  - đề đã **hết giai đoạn 2 ở mọi lớp còn giữ đề**.

  Câu **ở lại cho tới khi giáo viên đánh dấu đã xem** (cột `questions.wrong_rate_seen_at`), rồi rời
  hàng đợi mãi.
- **Điểm gộp theo lớp chỉ tính đề đã hết hạn chữa ở lớp ấy.** Mỗi bài được **quy về thang 10** rồi mới
  gộp. Mỗi lớp có số đề, trung bình, cao nhất, thấp nhất, và mục kiến thức sai nhiều nhất ở lần đầu.
  Kèm theo là năm mục kiến thức sai nhiều nhất trên mọi lớp ấy. Tỉ lệ của một mục đếm trên **lượt trả
  lời** (câu × bài).
- **Cả ba màn chỉ đọc.** Sửa lời giải là việc của [ADR-35](adr-35-sua-loi-giai-sau-phat-hanh.md).

## Vì sao

Gom báo cáo theo đề vì đó là đơn vị dữ liệu thật có: em ấy báo cáo cả đoạn chat của bài, không chỉ
vào một câu. Gán báo cáo vào từng câu là bịa ra một độ chính xác không có.

Tính tỉ lệ sai **lúc bài đã kết thúc**, không lúc bài đang chạy. Lý do do người dùng chỉ ra: 70% của 20
bài đầu có thể không còn là 70% khi đủ 50 bài, và một câu nhảy vào rồi nhảy ra khỏi hàng đợi trong
một buổi là một tín hiệu không ai tin được. Ngưỡng *trên 20 bài* có vì cùng lẽ ấy: một bài sai trên
một bài nộp đã là 100%.

Quy về thang 10 vì điểm của một đề là tổng trên số câu
([ADR-16](adr-16-thang-diem-ba-muc.md)): đề 6 câu và đề 10 câu không cộng được với nhau. Màn kết quả của
một đề (11) vẫn in thang riêng của đề ấy; chỉ màn gộp quy đổi, và phụ đề nói rõ điều đó.

*Đã xem* theo những gì đã hiện, không theo *mọi báo cáo chưa xem*: báo cáo nhỏ giọt suốt ngày (ADR-19),
và một cú bấm không được nuốt một báo cáo giáo viên chưa từng thấy.

## Hệ quả

- Một câu đã đánh dấu đã xem không vào lại hàng đợi, kể cả khi đề được phát hành thêm cho một lớp
  mới và tỉ lệ đổi.
- Hàng đợi không chặn ai và không có hạn xử lý (ADR-19). Nó không phải cổng teacher-in-the-loop thứ tư
  ([ADR-05](adr-05-ba-cong-teacher-in-the-loop.md)).
- Đếm *x lượt báo cáo* không phải thước đo chất lượng câu (ADR-19). Màn của đề vì thế cho đọc từng lời
  ghi và từng đoạn chat, không xếp hạng câu theo số báo cáo.

## Nơi luật này đang được thi hành

- `services/be/src/be/teacher_board.py`:
  - `GET /api/teacher/board`, `…/reports/{assessment_id}`, `…/questions/{question_id}`,
    `…/chat/{report_id}`;
  - hai route `…/seen`.
  - Sổ điểm đọc bằng join tới lần phát hành chưa thu hồi, và gộp bằng `GROUP BY`.

  Test ở `services/be/tests/test_teacher_board.py`.
- Schema: `reports.resolved_at`, `questions.wrong_rate_seen_at` (`packages/schema/src/schema/models.py`).
- FE: `services/fe/src/screens/teacher/Dashboard.tsx`; vitest *"Bảng theo dõi"* trong
  `services/fe/src/teacher.test.tsx`.
- Figma `mOe2ZmrqOq1Uix45v6PNGD`:
  - artboard `20 · Bảng theo dõi` (`657:3889`);
  - `25 · Báo cáo giải thích chưa rõ — một đề` (`657:4265`);
  - `25b · Đọc đoạn chat hỏi trợ lý` (`699:5826`);
  - `29 · Câu có tỉ lệ sai cao` (`699:5667`).
- Plan `docs/plans/completed/2026-10-18-dashboard-review-queue-plan.md`.
