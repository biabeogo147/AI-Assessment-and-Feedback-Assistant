# Use Case Specification

## Mục đích tài liệu

Tài liệu này mô tả các use case nghiệp vụ chính của project **AI Assessment and Feedback Assistant** trong giai đoạn đầu.

Nội dung tập trung vào actor nghiệp vụ, mục tiêu, điều kiện trước, luồng chính và ngoại lệ. Tài liệu này chưa mô tả API, database schema, service boundary hoặc AI agent internals.

Diagram liên quan:

- [Use Case Diagram](../diagrams/use-case.drawio)
- [Activity Overview Diagram](../diagrams/activity-overview.drawio)

## Actor nghiệp vụ

| Actor | Vai trò |
| --- | --- |
| Teacher | Tạo yêu cầu, review đề, phát hành đề, xử lý kết quả chấm cần review. |
| Student | Làm bài, nộp bài, xem feedback, luyện tập thích ứng. |

Hệ thống nằm bên trong system boundary nên không được xem là actor trong Use Case Diagram. Các hành vi như sinh đề, chấm bài, kiểm tra confidence hoặc tạo câu luyện tập được mô tả như use case được `<<include>>` hoặc `<<extend>>` từ mục tiêu của Teacher và Student.

## Quy ước quan hệ trong Use Case Diagram

| Quan hệ | Ý nghĩa sử dụng |
| --- | --- |
| Association | Actor trực tiếp tương tác với use case. |
| `<<include>>` | Hành vi bắt buộc xảy ra như một phần của use case chính. |
| `<<extend>>` | Hành vi chỉ xảy ra khi có điều kiện nghiệp vụ cụ thể. |
| Generalization | Use case chuyên biệt kế thừa mục tiêu chung từ use case tổng quát. |

Các giải thích dài không đặt trên connector của diagram để tránh rối hình. Điều kiện chi tiết được ghi trong từng use case bên dưới.

## Quy ước màu trong Use Case Diagram

| Màu | Ý nghĩa sử dụng |
| --- | --- |
| Xanh dương | Use case thể hiện mục tiêu chính của Teacher. |
| Xanh lá | Use case thể hiện mục tiêu chính của Student. |
| Cam | Hành vi hệ thống bắt buộc, thường được dùng trong quan hệ `<<include>>`. |
| Hồng | Hành vi điều kiện, ngoại lệ hoặc review, thường được dùng trong quan hệ `<<extend>>`. |

Các use case có cùng mục đích nghiệp vụ dùng cùng màu để người đọc nhận ra nhóm chức năng mà không cần đọc toàn bộ quan hệ.

## UC-01 — Teacher tạo đề nháp

### Mục tiêu

Teacher tạo được đề nháp từ yêu cầu ban đầu.

### Actor chính

Teacher

### Điều kiện trước

- Teacher biết chủ đề hoặc mục tiêu học tập cần kiểm tra.
- Teacher có thể mô tả yêu cầu tạo đề ở mức đủ hiểu.

### Luồng chính

1. Teacher nhập yêu cầu tạo đề.
2. Teacher cung cấp các ràng buộc như chủ đề, số lượng câu hỏi, độ khó, thời gian làm bài và loại bài kiểm tra.
3. Hệ thống phân tích yêu cầu.
4. Hệ thống sinh nội dung đề nháp gồm câu hỏi, phương án trả lời, đáp án đúng, lời giải và metadata cơ bản.
5. Hệ thống hiển thị đề nháp cho Teacher review.

### Quan hệ diagram

- `Tạo đề nháp` `<<include>>` `Sinh nội dung đề`.
- `Hỏi bổ sung yêu cầu` `<<extend>>` `Tạo đề nháp` khi yêu cầu ban đầu chưa đủ rõ.

### Kết quả

Một đề nháp sẵn sàng để Teacher review.

## UC-02 — Teacher review và phát hành đề

### Mục tiêu

Teacher kiểm soát chất lượng đề trước khi phát hành cho Student.

### Actor chính

Teacher

### Điều kiện trước

- Đã có đề nháp.

### Luồng chính

1. Teacher xem từng câu hỏi trong đề nháp.
2. Teacher xem đáp án đúng, lời giải và phương án sai.
3. Teacher chỉnh sửa câu hỏi, đáp án, lời giải hoặc metadata nếu cần.
4. Teacher duyệt đề.
5. Hệ thống phát hành đề cho Student.

### Quan hệ diagram

- `Tạo lại nội dung đề` `<<extend>>` `Review và phát hành đề` khi Teacher thấy một phần hoặc toàn bộ đề chưa phù hợp.

### Kết quả

Đề đã được Teacher duyệt và phát hành.

## UC-03 — Student làm và nộp bài

### Mục tiêu

Student hoàn thành bài được giao và gửi câu trả lời để hệ thống đánh giá.

### Actor chính

Student

### Điều kiện trước

- Bài đã được Teacher phát hành.
- Student có quyền truy cập bài được giao.

### Luồng chính

1. Student mở bài được giao.
2. Student đọc câu hỏi.
3. Student chọn đáp án.
4. Student nhập giải thích cách làm nếu bài yêu cầu.
5. Student nộp bài.
6. Hệ thống ghi nhận bài nộp để chuyển sang đánh giá.

### Quan hệ diagram

- `Làm bài thường xuyên` generalizes to `Làm và nộp bài`.
- `Làm bài nhiều bước/cuối kỳ` generalizes to `Làm và nộp bài`.
- `Yêu cầu giải thích cách làm` `<<extend>>` `Làm và nộp bài` khi bài khó, bài cuối kỳ hoặc câu hỏi nhiều bước.

Không dùng `<<include>>` từ `Làm và nộp bài` sang `Chấm bài và sinh feedback` vì chấm bài là bước xử lý sau khi có bài nộp, không phải hành vi bắt buộc để Student hoàn thành mục tiêu nộp bài.

### Kết quả

Bài nộp được ghi nhận và có thể được đánh giá.

## UC-04 — Student xem feedback

### Mục tiêu

Student xem kết quả, nhận xét và gợi ý học tập sau khi bài được đánh giá.

### Actor chính

Student

### Điều kiện trước

- Student đã nộp bài.
- Hệ thống đã tạo kết quả chấm hoặc Teacher đã chốt kết quả cần review.

### Luồng chính

1. Student mở kết quả bài làm.
2. Hệ thống hiển thị điểm hoặc trạng thái đánh giá.
3. Hệ thống hiển thị feedback phù hợp với lỗi sai hoặc cách làm của Student.
4. Student đọc feedback và biết bước học tiếp theo.

### Quan hệ diagram

- `Xem feedback` `<<include>>` `Chấm bài và sinh feedback`.
- `Chấm bài và sinh feedback` `<<include>>` `Kiểm tra confidence`.

`Xem feedback` dùng `<<include>>` với `Chấm bài và sinh feedback` vì để Student nhận feedback có căn cứ, hệ thống bắt buộc phải tạo kết quả đánh giá và feedback trước. `Chấm bài và sinh feedback` dùng `<<include>>` với `Kiểm tra confidence` vì mọi kết quả đánh giá đều cần confidence để quyết định có cần Teacher review không.

### Kết quả

Student nhận được feedback có căn cứ để tiếp tục học hoặc luyện tập.

## UC-05 — Teacher xử lý bài cần review

### Mục tiêu

Teacher xem xét và chốt kết quả chấm khi hệ thống không đủ tự tin hoặc phát hiện tình huống bất thường.

### Actor chính

Teacher

### Điều kiện trước

- Hệ thống đã tạo kết quả đánh giá cần Teacher review.

### Luồng chính

1. Teacher mở danh sách bài cần review.
2. Teacher xem câu hỏi, đáp án chuẩn, bài làm, lời giải thích của Student và feedback do hệ thống đề xuất.
3. Teacher xem lý do hệ thống yêu cầu review.
4. Teacher xác nhận hoặc chỉnh sửa điểm.
5. Teacher xác nhận hoặc chỉnh sửa lỗi sai, misconception và feedback.
6. Hệ thống lưu kết quả cuối cùng.

### Quan hệ diagram

- `Xử lý bài cần review` `<<extend>>` `Chấm bài và sinh feedback` khi confidence thấp hoặc có dấu hiệu bất thường.

### Kết quả

Kết quả cuối cùng được Teacher xác nhận và có thể hiển thị cho Student.

## UC-06 — Student luyện tập thích ứng

### Mục tiêu

Student nhận câu hỏi luyện tập phù hợp khi feedback cho thấy Student chưa đạt mastery ở phạm vi đang luyện tập.

### Actor chính

Student

### Điều kiện trước

- Student đã xem feedback.
- Feedback hoặc kết quả đánh giá cho thấy Student chưa đạt mastery ở phạm vi liên quan.

### Luồng chính

1. Student xem feedback sau khi bài được đánh giá.
2. Hệ thống kiểm tra trạng thái mastery ở phạm vi liên quan.
3. Nếu Student đã đạt mastery, hệ thống không tạo câu luyện tập mới.
4. Nếu Student chưa đạt mastery, hệ thống tạo câu hỏi luyện tập tương tự.
5. Student làm câu hỏi luyện tập mới.
6. Hệ thống đánh giá câu trả lời và cập nhật lại mastery.
7. Vòng luyện tập tiếp tục cho đến khi đạt mastery.

### Quan hệ diagram

- `Luyện tập thích ứng` `<<extend>>` `Xem feedback` khi feedback cho thấy Student chưa đạt mastery.
- `Luyện tập thích ứng` `<<include>>` `Tạo câu luyện tập`.

`Luyện tập thích ứng` là `<<extend>>` của `Xem feedback` vì nó không luôn xảy ra sau feedback. Nếu Student đã đạt mastery, workflow kết thúc. Nếu chưa đạt mastery, hệ thống mở rộng luồng bằng việc tạo practice question. `Tạo câu luyện tập` là `<<include>>` vì adaptive practice không thể bắt đầu nếu hệ thống chưa tạo câu luyện tập.

### Kết quả

Student chỉ nhận thêm câu luyện tập khi chưa đạt ngưỡng mastery ở phạm vi đã xác định.

## Ghi chú điều kiện nghiệp vụ

- `Tạo đề nháp` diễn ra trước `Review và phát hành đề`, nhưng đây là thứ tự workflow nên được mô tả trong Activity Diagram và tài liệu workflow, không ghi như một quan hệ riêng trong Use Case Diagram.
- Student nộp bài là điều kiện để hệ thống chấm và sinh feedback, nhưng không biểu diễn bằng `<<include>>` vì đây là thứ tự workflow.
- Kết quả confidence thấp hoặc có mâu thuẫn sẽ mở rộng sang use case Teacher xử lý bài cần review.
- Feedback chỉ mở rộng sang vòng luyện tập thích ứng khi Student chưa đạt mastery.

## Nguyên tắc nghiệp vụ chung

- Hệ thống không tự phát hành đề nếu Teacher chưa duyệt.
- Confidence thấp cần Teacher review.
- Distractor nên có ý nghĩa chẩn đoán lỗi.
- Bài khó hoặc nhiều bước nên yêu cầu Student giải thích cách làm.
- Adaptive practice không sao chép nguyên văn câu cũ mà tạo biến thể cùng mục tiêu học tập.
