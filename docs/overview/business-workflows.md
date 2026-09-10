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
Hệ thống sinh đề nháp, kèm lời giải nhiều cách và mỗi distractor gắn một lỗi
        ↓
Teacher review và duyệt đề
        ↓
Teacher phát hành: sáu tham số cho hai pha
        ↓
=== PHA 1 ===
Student làm bài và nộp
        ↓
Hệ thống chấm; lỗi sai tra từ distractor đã chọn
        ↓
=== PHA 2, bắt buộc ===
Với mỗi câu sai: hệ thống giải thích lỗi, Student hỏi lại đến khi hiểu
        ↓
Student bấm Làm bài mới; đồng hồ lượt bắt đầu chạy
        ↓
Student làm câu biến thể của chính câu đó
        ↓
Đúng thì câu gốc chốt 0,5đ; sai thì sang vòng tiếp, tối đa ba vòng
        ↓
Hết ba vòng, hoặc hết hạn pha 2, thì câu gốc chốt 0đ
        ↓
Bài kết thúc. Mỗi câu chốt ở một trong ba mức: 1 / 0,5 / 0
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
8. Teacher phát hành đề cho Student. Phát hành cần sáu tham số: lớp, thời gian làm bài, giờ mở, giờ đóng, số phút mỗi câu ở pha 2, và hạn kết thúc pha 2. Xem ADR-02 và ADR-15.

### Điểm kiểm soát của Teacher

Teacher phải duyệt đề trước khi đề được phát hành.

Lý do: đề kiểm tra ảnh hưởng trực tiếp đến đánh giá học sinh, nên AI không được tự phát hành đề mà không có kiểm soát nghiệp vụ.

## Workflow 2 — Student làm bài (pha 1)

### Mục tiêu

Cho phép học sinh làm bài kiểm tra và ghi nhận bài nộp để hệ thống đánh giá.

### Luồng chính

1. Student nhận assessment đã được Teacher phát hành.
2. Student vào làm, tới hết giờ đóng. Xem ADR-03.
3. Student trả lời câu hỏi trắc nghiệm.
4. Student nộp bài.
5. Hệ thống ghi nhận submission để đánh giá.

### Nộp bài không kết thúc bài kiểm tra

Đây là điểm dễ hiểu nhầm nhất trong toàn bộ vòng. Nộp bài kết thúc **pha 1**; bài kiểm tra kết thúc ở
cuối **pha 2** (Workflow 5), khi mọi câu đã chốt điểm hoặc khi hết hạn pha 2. Một lớp có thể nộp đủ
bốn mươi bài mà chưa em nào hoàn thành. Xem ADR-14.

### Pha 1 không thu lời giải thích

Luật *bài khó hoặc nhiều bước nên yêu cầu Student giải thích cách làm* vẫn còn hiệu lực, nhưng chỗ
hỏi là **hội thoại ở pha 2** — đúng vào câu Student làm sai, và sau khi đồng hồ pha 1 đã dừng. Hỏi ở
pha 1 bằng một ô nhập tuỳ chọn tạo ra một cái bẫy: bỏ trống thì hệ thống coi là không đủ căn cứ và
đẩy kết quả vào hàng đợi review, nên em lười gõ lại là em không nhận được gì. Xem ADR-11.

### Khác biệt theo loại bài

Bài thường xuyên tập trung phản hồi nhanh; bài khó hoặc cuối kỳ cần phân tích cả cách làm. Sự phân
biệt này còn hiệu lực nhưng chưa có chỗ nào trong hệ thống diễn đạt được nó — xem ADR-11.

## Workflow 3 — System/AI chấm bài và sinh feedback

### Mục tiêu

Đánh giá bài làm, xác định lỗi sai hoặc misconception và tạo feedback phù hợp cho Student.

### Luồng chính

1. System/AI nhận submission.
2. System/AI so sánh với đáp án chuẩn và lời giải chuẩn.
3. Pha 1 không thu lời giải thích, nên bước này chỉ chạy với lời Student nói trong hội thoại pha 2.
4. Hệ thống **tra** lỗi sai từ phương án nhiễu Student đã chọn. Mỗi nhiễu được soạn kèm một lỗi cụ thể, nên đây là tra cứu chứ không phải suy đoán. Xem ADR-18.
5. System/AI tạo kết quả gồm điểm số, nhận xét, lỗi sai, misconception và confidence.
6. System quyết định kết quả có cần Teacher review không.

### Nguyên tắc đánh giá

- Đáp án đúng nhưng cách làm sai không nên mặc định là đã hiểu.
- Đáp án sai nhưng một phần cách làm đúng cần được ghi nhận.
- Distractor **phải** đại diện cho một lỗi cụ thể, và lỗi đó được soạn cùng câu hỏi. Đây là điều kiện để pha 2 giải thích được. Xem ADR-18.
- Feedback nên giúp Student hiểu lỗi và biết bước tiếp theo.
- Mỗi câu hỏi phải kèm **lời giải nhiều cách**, để cuộc giải thích ở pha 2 có chỗ đi tiếp khi Student nói vẫn chưa hiểu. Xem ADR-18.

## Workflow 4 — Teacher Review Queue

### Mục tiêu

Đưa các kết quả có confidence thấp hoặc dấu hiệu bất thường cho Teacher xem xét.

### Luồng chính

1. System/AI hoàn thành đánh giá.
2. System/AI tính confidence ở mức nghiệp vụ.
3. Nếu confidence đủ cao, kết quả đi thẳng sang pha 2.
4. Nếu confidence thấp, kết quả đi vào Teacher Review Queue. **Nhánh này không chặn pha 2**: Teacher chốt xong thì luồng hợp lại và học sinh vẫn chữa bài. Với luồng Student của mô hình hai pha, điều kiện ngưỡng hiện **tạm không áp** — xem ADR-07 và ADR-08.
5. Teacher xem câu hỏi, đáp án chuẩn, bài làm, nhận xét AI và lý do cần review.
6. Teacher xác nhận hoặc chỉnh sửa điểm, lỗi sai, misconception và feedback.
7. Hệ thống lưu kết quả cuối cùng.

### Điểm kiểm soát của Teacher

Teacher bắt buộc review khi:

- Confidence thấp.
- Bài làm có mâu thuẫn, ví dụ đáp án đúng nhưng cách làm sai.
- Hệ thống không đủ căn cứ để xác định lỗi.
- Có trường hợp bất thường cần người có chuyên môn xem lại.

## Workflow 5 — Chữa bài (pha 2)

### Mục tiêu

Học sinh sửa được lỗi vừa mắc, và bài kiểm tra chỉ kết thúc khi việc đó đã diễn ra.

### Luồng chính

1. Hệ thống liệt kê những câu Student làm sai ở pha 1.
2. Với mỗi câu sai, hệ thống giải thích lỗi **theo lời giải đã soạn kèm câu hỏi**. Student hỏi lại đến khi hiểu. Phần này **không tính giờ**.
3. Student bấm nút làm bài mới. Đồng hồ của lượt bắt đầu chạy, dài bằng số phút mỗi câu nhân số câu còn dở.
4. Hệ thống sinh **câu biến thể của chính câu sai**: giữ nguyên cấu trúc và lỗi cần kiểm, chỉ đổi dữ kiện.
5. Student làm các câu biến thể trong lượt.
6. Câu nào làm đúng thì câu gốc chốt **0,5 điểm**; câu nào còn sai thì sang vòng tiếp.
7. Mỗi câu có **tối đa ba vòng**, đếm riêng. Hết ba vòng mà vẫn sai thì câu gốc chốt **0 điểm**.
8. Bài kết thúc khi mọi câu đã chốt, hoặc khi hết hạn pha 2. Hết hạn giữa một lượt thì lượt bị cắt và các câu còn dở chốt 0 điểm.

### Điều kiện dừng là số vòng, không phải mastery

`Mastery` vẫn là một khái niệm trong glossary nhưng **không còn quyết định gì**. Nó cần lịch sử làm
bài, mà hệ thống chưa lưu gì — một điều kiện dừng không tính được là một vòng lặp không có lối ra. Số
vòng thì học sinh **đếm được** và biết mình còn mấy lần. Xem ADR-17.

### Bắt buộc nghĩa là bắt buộc thử, không phải bắt buộc đạt

Hệ thống không giam học sinh lại. Em không mở pha 2 lần nào thì tới hạn, mọi câu sai chốt 0 điểm —
đúng bằng kết quả của em vào rồi sai cả ba vòng. Luật được thi hành **bằng điểm, không bằng khoá**.
Xem ADR-14.

### Nguyên tắc tạo câu biến thể

Câu biến thể giữ **chính câu gốc**: cùng cấu trúc, cùng lỗi cần kiểm, chỉ đổi dữ kiện, ngữ cảnh, giá
trị số hoặc cách diễn đạt. Chặt hơn hẳn *cùng mục tiêu học tập* — một câu khác cùng learning objective
có thể hỏng ở bước khác và không chạm tới lỗi vừa mắc.

Câu biến thể do trợ lí sinh ra khi Student đang làm bài, nên nó **không đi qua cổng duyệt của
Teacher**. Đây là ngoại lệ đã biết của cổng thứ nhất trong ADR-05; xem `docs/plans/backlog.md`.

### Báo cáo chỗ giải thích chưa rõ

Student đánh dấu một câu hoặc một đoạn hội thoại là *giải thích chưa rõ*, ở hai thời điểm: ngay trước
khi bấm nút làm bài mới, và sau khi bài của **chính em đó** kết thúc. Teacher xem được. Việc này
**không chặn** ai — không chặn Student, không chặn lượt, không chặn điểm — nên nó không phải cổng
teacher-in-the-loop thứ tư. Xem ADR-19.

## Những điểm chưa chốt

Các điểm sau được ghi nhận nhưng chưa thiết kế chi tiết trong Phase 1:

- Công thức tính confidence, và `confidence` đo cái gì khi phần chấm đã xác định.
- Câu biến thể có nên đi qua một cổng duyệt nào không.
- Mức điểm 0,5 hiện bằng màu nào — ADR-12 mới khoá hai trạng thái đáp án.
- Rubric chi tiết cho từng môn học hoặc từng loại bài.
- Cách hệ thống quyết định khi nào giảm độ khó hoặc cung cấp gợi ý.

Những điểm này cần được làm rõ ở các phase sau khi team bắt đầu thiết kế nghiệp vụ chi tiết hơn hoặc technical design.
