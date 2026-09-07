# Project Overview

## Mục đích tài liệu

Tài liệu này cung cấp bức tranh toàn cảnh về project **Kriky** cho cả thành viên tech và non-tech.

Nó tập trung vào nghiệp vụ, actor, mục tiêu sản phẩm và phạm vi phát triển đầu tiên. Tài liệu này không mô tả kiến trúc hệ thống, AI agent internals, API hoặc database schema.

Diagram liên quan:

- [Use Case Diagram](../diagrams/use-case.drawio)
- [Domain Context Diagram](../diagrams/domain-context.drawio)

## Tóm tắt project

Project là một hệ thống hỗ trợ giáo viên tạo đề, duyệt đề, chấm bài, phân tích lỗi sai và tạo vòng luyện tập thích ứng cho học sinh.

Điểm quan trọng của project không chỉ là dùng AI để sinh câu hỏi hoặc chấm trắc nghiệm. Mục tiêu lớn hơn là tạo một vòng học tập khép kín:

```text
Giáo viên tạo và duyệt đề
        ↓
Học sinh làm bài
        ↓
AI đánh giá đáp án và cách tư duy
        ↓
AI xác định lỗi sai hoặc misconception
        ↓
AI tạo câu hỏi luyện tập tương tự
        ↓
Học sinh luyện tập tiếp
        ↓
Dừng khi đạt ngưỡng thành thạo
```

Trong vòng này, giáo viên giữ quyền kiểm soát ở ba điểm: duyệt đề trước khi phát hành, xử lý kết quả chấm có độ tin cậy thấp, và trả lời khi agent chưa đủ thông tin để làm.

## Vấn đề cần giải quyết

Giáo viên thường mất nhiều thời gian để:

- Soạn đề phù hợp với mục tiêu học tập.
- Tạo phương án sai có ý nghĩa, không chỉ là đáp án nhiễu ngẫu nhiên.
- Chấm bài và viết nhận xét cho từng học sinh.
- Xác định học sinh sai vì kiến thức, suy luận, tính toán hay hiểu nhầm khái niệm.
- Tạo bài luyện tập tiếp theo phù hợp với lỗi sai cụ thể.

Học sinh thường cần phản hồi nhanh và bài luyện tập đúng với điểm yếu của mình, nhưng giáo viên khó cá nhân hóa sâu cho từng học sinh nếu làm thủ công hoàn toàn.

## Mục tiêu sản phẩm

Hệ thống hướng đến bốn mục tiêu nghiệp vụ chính:

1. Hỗ trợ giáo viên tạo đề từ yêu cầu hoặc prompt.
2. Hỗ trợ chấm bài và sinh nhận xét có căn cứ.
3. Phân tích lỗi sai hoặc misconception của học sinh.
4. Tạo vòng luyện tập thích ứng để giúp học sinh đạt mastery.

## Actor nghiệp vụ chính

### Teacher

Teacher là người kiểm soát nghiệp vụ quan trọng nhất.

Teacher có thể:

- Nhập yêu cầu tạo đề.
- Xem và chỉnh sửa đề do AI tạo.
- Duyệt đề trước khi phát hành.
- Phát hành đề cho một hoặc nhiều lớp. Đây là thẩm quyền riêng của Teacher; hệ thống không làm thay.
- Xem kết quả làm bài của học sinh.
- Xử lý bài chấm có confidence thấp.
- Xác nhận hoặc chỉnh sửa điểm, lỗi sai và nhận xét.

### Student

Student là người nhận đề, làm bài và luyện tập.

Student có thể:

- Xem bài kiểm tra được giao.
- Chọn đáp án.
- Giải thích cách làm khi bài yêu cầu.
- Nộp bài.
- Xem kết quả và nhận xét.
- Làm các câu luyện tập thích ứng.

## Hành vi hệ thống bên trong boundary

Hệ thống hỗ trợ các tác vụ thông minh trong workflow, nhưng không được xem là actor nghiệp vụ trong Use Case Diagram.

Hệ thống có thể:

- Sinh đề, đáp án, lời giải và metadata câu hỏi.
- Đánh giá câu trả lời và phần giải thích của học sinh.
- Dự đoán lỗi sai dựa trên distractor, lịch sử học tập hoặc lời giải thích.
- Sinh nhận xét.
- Tính confidence.
- Đề xuất câu hỏi luyện tập tiếp theo.

Hệ thống không tự thay thế vai trò kiểm soát của giáo viên ở các điểm cần review.

## Phạm vi giai đoạn đầu

Giai đoạn đầu tập trung vào bức tranh nghiệp vụ:

- Teacher tạo, review và phát hành đề.
- Student làm bài và nộp bài.
- Hệ thống chấm bài và sinh nhận xét.
- Kết quả confidence thấp đi vào Teacher Review Queue.
- Hệ thống tạo câu hỏi luyện tập thích ứng dựa trên lỗi sai.

## Ngoài phạm vi giai đoạn đầu

Các nội dung sau chưa được thiết kế trong giai đoạn này:

- Kiến trúc hệ thống chi tiết.
- Cấu trúc service, module hoặc component.
- API contract.
- Database schema.
- AI prompt chain, tool calling hoặc model routing.
- Công thức confidence và mastery chi tiết.
- Deployment, monitoring và runbook.

## Khái niệm nghiệp vụ chính

- `Assessment`: bài kiểm tra hoặc bộ câu hỏi được giao cho học sinh.
- `Question`: câu hỏi trong assessment.
- `Distractor`: phương án sai có chủ đích, đại diện cho một lỗi hoặc misconception.
- `Submission`: bài làm hoặc câu trả lời của học sinh.
- `Feedback`: nhận xét hệ thống gửi lại cho học sinh hoặc giáo viên.
- `Misconception`: hiểu nhầm khái niệm hoặc lỗi sai có tính lặp lại.
- `Confidence`: mức độ hệ thống tin vào kết quả đánh giá.
- `Teacher Review Queue`: nơi đưa các kết quả cần giáo viên xem xét.
- `Mastery`: mức độ thành thạo của học sinh với một mục tiêu học tập hoặc kỹ năng.
- `Class`: lớp học có sẵn danh sách học sinh. Giáo viên tạo lớp; tài khoản học sinh được sinh
  hàng loạt từ file CSV danh sách lớp, khoá theo mã học sinh. Phát hành đề phải chọn lớp đã tạo
  từ trước. Xem ADR-13.
- `Question Bank`: kho câu hỏi đã dùng qua, một trong hai nguồn câu hỏi của một đề.
- `Document`: tài liệu PDF của giáo viên, nằm trong kho lưu trữ riêng của từng tài khoản. Nhiều
  đoạn chat cùng tham chiếu được một tài liệu. Cung cấp kiến thức và giới hạn phạm vi ra đề,
  không chứa câu hỏi.
- `Scope`: phạm vi ra đề, tới cấp chương và khoảng trang trong một `Document`.

## Nguyên tắc teacher-in-the-loop

Teacher-in-the-loop không có nghĩa là giáo viên phải duyệt mọi hành động của AI.

Trong giai đoạn đầu, giáo viên bắt buộc tham gia ở ba điểm — hai ở đầu ra, một ở đầu vào:

- Duyệt đề trước khi phát hành cho học sinh.
- Xử lý kết quả chấm có confidence thấp hoặc có dấu hiệu bất thường.
- Trả lời khi agent chưa đủ thông tin để làm, thay vì để agent tự đoán.

Chi tiết và ranh giới của từng cổng: [ADR-05](../decisions/adr-05-ba-cong-teacher-in-the-loop.md).

Các bước còn lại có thể được hệ thống hỗ trợ tự động, nhưng vẫn cần minh bạch để giáo viên hiểu lý do hệ thống đưa ra đề xuất.
