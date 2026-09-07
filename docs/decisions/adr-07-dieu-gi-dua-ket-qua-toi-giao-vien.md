# ADR-07 — Điều gì đưa một kết quả chấm tới giáo viên

- **Trạng thái:** đã chốt
- **Ngày:** 2026-09-06

## Bối cảnh

Luật quyết định kết quả nào rơi vào Teacher Review Queue **đang chạy trong code** và không tài liệu
nghiệp vụ nào ghi lại. Con số ngưỡng quyết định trực tiếp khối lượng việc của giáo viên, và chỗ duy
nhất giải thích nó là một comment trong `.env.example` cùng một trang hướng dẫn chạy máy.

## Quyết định

- **Ba điều kiện độc lập** đưa một kết quả tới giáo viên: mâu thuẫn giữa đáp án và lập luận, không đủ
  căn cứ, hoặc `confidence <= ngưỡng`. **Hai điều kiện đầu áp dụng kể cả khi confidence rất cao** —
  chúng không phải biến thể của ngưỡng.
- Phép so ngưỡng là **bao gồm**.
- Khi nhiều điều kiện cùng đúng, báo lý do **cụ thể nhất**:
  `answer_explanation_conflict` > `insufficient_evidence` > `low_confidence`.
- Thứ tự này chỉ áp cho việc **chọn một lý do để báo**, và chỉ sống trong `review_policy.py`. Nó
  **không** phải thang nghiêm trọng: bốn `ReviewReason` hiển thị cùng trọng lượng — xem
  [ADR-08](adr-08-bon-loai-nghi-ngo.md).
- Ngưỡng hiện tại là **0.7**.
- Ngưỡng được áp **lúc đọc kết quả**, không lưu kèm kết quả.
- **Đáp án sai mà hệ thống tự tin thì không cần giáo viên.** Cổng này dành cho lúc *hệ thống* không
  chắc, không phải lúc *học sinh* sai.

## Vì sao

**Bao gồm**, vì nếu loại trừ thì đặt ngưỡng `0.0` sẽ không bắt được cả kết quả mà model không tin chút
nào — một cấu hình hợp lệ lại tạo ra lỗ hổng im lặng.

**Cụ thể nhất trước**, vì `low_confidence` chỉ nói *hệ thống không chắc*, còn `answer_explanation_conflict`
nói *chắc chắn có gì đó lệch, và lệch ở đâu*. Báo cái mơ hồ khi cái cụ thể cũng đúng là vứt đi thông
tin đã có. Đây là tiêu chí **độ cụ thể**, không phải mức nghiêm trọng — bốn lý do không xếp hạng
nặng nhẹ với nhau.

**Áp lúc đọc**, vì ngưỡng là chính sách chứ không phải dữ liệu. Lưu quyết định kèm kết quả nghĩa là đổi
chính sách thì phải chấm lại toàn bộ.

**Đáp án sai không tự động cần review**, vì cổng tồn tại để bắt lúc *máy* không chắc. Nếu mọi câu sai
đều vào hàng đợi thì hàng đợi trở thành danh sách bài kém, và giáo viên sẽ bỏ đọc nó.

## Hệ quả

- Đổi `REVIEW_CONFIDENCE_THRESHOLD` trong `.env` làm **kết luận của kết quả cũ đổi theo ngay**, không
  cần chấm lại. Tiện khi hiệu chỉnh, nhưng nghĩa là một kết quả giáo viên đã xem hôm qua có thể quay
  lại hàng đợi hôm nay mà không ai thao tác gì.
- Giáo viên không có cách nào biết một kết quả *suýt* qua ngưỡng. Ranh giới `0.7` là vách đứng, không
  có vùng xám.
- Thứ tự ưu tiên nghĩa là một kết quả chỉ mang **một** lý do, kể cả khi nó dính ba điều kiện. Muốn
  thấy đủ ba thì phải đổi cả kiểu trả về, không chỉ đổi thứ tự `if`.
- Ngưỡng `0.7` là quyết định nghiệp vụ **còn hiệu lực** sau khi phần chấm placeholder được thay bằng
  lời gọi LLM thật. Năm mốc confidence trong `services/agent/src/agent/handlers.py` thì **không** —
  chúng là dữ liệu giả để demo, không phải luật.

## Nơi luật này đang được thi hành

- `services/be/src/be/review_policy.py:53-69` — ba nhánh `if`, đúng thứ tự ưu tiên.
- `services/be/src/be/review_policy.py:65` — `<=`, phép so bao gồm; docstring dòng 42-44 nêu lý do.
- `services/be/src/be/routes.py:123` — gọi `decide_review` lúc đọc; docstring dòng 98-99 nêu lý do.
- `.env.example:25` — `REVIEW_CONFIDENCE_THRESHOLD=0.7`.
- `services/be/tests/test_review_policy.py:37` — `test_threshold_comparison_is_inclusive`.
- `services/be/tests/test_review_policy.py:48` — `test_answer_explanation_conflict_wins_over_low_confidence`.
- `services/be/tests/test_review_policy.py:43` — `test_missing_evidence_routes_to_teacher_even_when_confident`,
  canh việc điều kiện thứ hai độc lập với ngưỡng.
- `services/be/tests/test_review_policy.py:57` — `test_correct_answer_does_not_exempt_a_submission_from_review`.
  Lưu ý test này canh chiều **ngược lại**: điểm cao không miễn review.
- `services/be/src/be/review_policy.py:53-71` — không nhánh nào đọc `result.score`. Đó là tất cả những
  gì đang giữ luật *đáp án sai mà tự tin thì không cần giáo viên*; **chưa có test** nào canh chiều này.
- `docs/local-development.md` — bảng năm trường hợp demo, có dòng đáp án sai mà không cần review.
