# Business Workflows

## Mục đích tài liệu

Tài liệu này mô tả các workflow nghiệp vụ tổng quan của project **Kriky**.

Tài liệu dành cho cả product, giáo viên, BA, engineer và QA. Nội dung tập trung vào luồng nghiệp vụ, chưa mô tả kiến trúc triển khai, API hoặc AI agent internals. Trong workflow, `System/AI` là lane xử lý bên trong hệ thống, không phải actor nghiệp vụ trong Use Case Diagram.

Diagram liên quan:

- [Activity Overview Diagram](../diagrams/activity-overview.drawio)
- [Business Workflows Swimlane Diagram](../diagrams/business-workflows.drawio)

## Workflow tổng quan

```text
Teacher tạo yêu cầu
        ↓
Hệ thống sinh đề nháp
        ↓
Teacher review và duyệt đề
        ↓
Student làm bài
        ↓
Hệ thống chấm và phân tích lỗi
        ↓
Confidence thấp?
        ↓
Teacher review nếu cần
        ↓
Student nhận feedback
        ↓
Hệ thống kiểm tra mastery
        ↓
Chưa đạt mastery?
        ↓
Hệ thống tạo câu luyện tập thích ứng
        ↓
Lặp lại đến khi đạt mastery
```

## Workflow 1 — Teacher tạo và duyệt đề

### Mục tiêu

Giúp giáo viên tạo được đề kiểm tra phù hợp với mục tiêu học tập, nhưng giáo viên vẫn là người duyệt cuối cùng trước khi phát hành.

### Luồng chính

1. Teacher nhập yêu cầu tạo đề.
2. Teacher cung cấp ràng buộc như chủ đề, độ khó, số lượng câu hỏi, loại bài kiểm tra và thời gian làm bài.
3. System/AI phân tích yêu cầu.
4. System/AI tạo đề nháp gồm câu hỏi, phương án trả lời, đáp án đúng, lời giải và metadata cơ bản.
5. Teacher xem đề nháp.
6. Teacher chỉnh sửa thủ công hoặc yêu cầu System/AI tạo lại một phần.
7. Teacher duyệt đề.
8. Teacher phát hành đề cho Student, kèm lớp và ba mốc thời gian. Xem ADR-02.

### Điểm kiểm soát của Teacher

Teacher phải duyệt đề trước khi đề được phát hành.

Lý do: đề kiểm tra ảnh hưởng trực tiếp đến đánh giá học sinh, nên AI không được tự phát hành đề mà không có kiểm soát nghiệp vụ.

## Workflow 2 — Student làm bài

### Mục tiêu

Cho phép học sinh làm bài kiểm tra và cung cấp đủ thông tin để hệ thống đánh giá phù hợp với loại bài.

### Luồng chính

1. Student nhận assessment đã được Teacher phát hành.
2. Student trả lời câu hỏi trắc nghiệm.
3. Với bài thường xuyên hoặc bài ít bước, Student có thể chỉ cần chọn đáp án.
4. Với bài khó, bài cuối kỳ hoặc bài nhiều bước, Student cần giải thích cách làm.
5. Student nộp bài.
6. Hệ thống ghi nhận submission để đánh giá.

### Khác biệt theo loại bài

Bài thường xuyên:

- Tập trung phản hồi nhanh.
- Có thể dự đoán lỗi sai từ distractor đã chọn.
- Không bắt buộc Student giải thích cách làm.

Bài khó hoặc cuối kỳ:

- Cần phân tích cả đáp án và cách làm.
- Student nên cung cấp lời giải thích.
- Hệ thống không nên chỉ so sánh đáp án cuối cùng.

## Workflow 3 — System/AI chấm bài và sinh feedback

### Mục tiêu

Đánh giá bài làm, xác định lỗi sai hoặc misconception và tạo feedback phù hợp cho Student.

### Luồng chính

1. System/AI nhận submission.
2. System/AI so sánh với đáp án chuẩn và lời giải chuẩn.
3. Nếu có lời giải thích của Student, System/AI phân tích cách làm.
4. Nếu không có lời giải thích, System/AI dự đoán lỗi sai dựa trên distractor, lịch sử học tập và ngữ cảnh câu hỏi.
5. System/AI tạo kết quả gồm điểm số, nhận xét, lỗi sai, misconception và confidence.
6. System quyết định kết quả có cần Teacher review không.

### Nguyên tắc đánh giá

- Đáp án đúng nhưng cách làm sai không nên mặc định là đã mastery.
- Đáp án sai nhưng một phần cách làm đúng cần được ghi nhận.
- Distractor nên đại diện cho lỗi có ý nghĩa.
- Feedback nên giúp Student hiểu lỗi và biết bước tiếp theo.

## Workflow 4 — Teacher Review Queue

### Mục tiêu

Đưa các kết quả có confidence thấp hoặc dấu hiệu bất thường cho Teacher xem xét.

### Luồng chính

1. System/AI hoàn thành đánh giá.
2. System/AI tính confidence ở mức nghiệp vụ.
3. Nếu confidence đủ cao, kết quả có thể được công bố cho Student.
4. Nếu confidence thấp, kết quả đi vào Teacher Review Queue.
5. Teacher xem câu hỏi, đáp án chuẩn, bài làm, lời giải thích của Student, nhận xét AI và lý do cần review.
6. Teacher xác nhận hoặc chỉnh sửa điểm, lỗi sai, misconception và feedback.
7. Hệ thống lưu kết quả cuối cùng.

### Điểm kiểm soát của Teacher

Teacher bắt buộc review khi:

- Confidence thấp.
- Bài làm có mâu thuẫn, ví dụ đáp án đúng nhưng cách làm sai.
- Hệ thống không đủ căn cứ để xác định lỗi.
- Có trường hợp bất thường cần người có chuyên môn xem lại.

## Workflow 5 — Adaptive Practice

### Mục tiêu

Tạo vòng luyện tập giúp Student sửa đúng lỗi sai hoặc misconception vừa được phát hiện.

### Luồng chính

1. System/AI xác định lỗi sai hoặc misconception.
2. System/AI xác định learning objective hoặc kỹ năng liên quan.
3. Hệ thống cập nhật hoặc kiểm tra trạng thái mastery.
4. Nếu đã đạt mastery, hệ thống không tạo câu luyện tập mới.
5. Nếu chưa đạt mastery, System/AI tạo câu hỏi luyện tập tương tự.
6. Câu hỏi mới giữ cùng mục tiêu kiến thức nhưng thay đổi dữ kiện, ngữ cảnh hoặc độ khó.
7. Student làm câu hỏi luyện tập.
8. System/AI đánh giá lại và cập nhật mastery.
9. Vòng luyện tập lặp lại cho đến khi đạt mastery.

### Nguyên tắc tạo câu tương tự

Câu hỏi mới nên giữ:

- Cùng mục tiêu kiến thức.
- Cùng loại kỹ năng.
- Cùng misconception cần kiểm tra, nếu phù hợp.

Câu hỏi mới có thể thay đổi:

- Dữ kiện.
- Ngữ cảnh.
- Giá trị số.
- Cách diễn đạt.
- Độ khó.
- Số bước suy luận.

## Những điểm chưa chốt

Các điểm sau được ghi nhận nhưng chưa thiết kế chi tiết trong Phase 1:

- Công thức tính confidence.
- Công thức cập nhật mastery.
- Rubric chi tiết cho từng môn học hoặc từng loại bài.
- Cách hệ thống quyết định khi nào giảm độ khó hoặc cung cấp gợi ý.

Những điểm này cần được làm rõ ở các phase sau khi team bắt đầu thiết kế nghiệp vụ chi tiết hơn hoặc technical design.
