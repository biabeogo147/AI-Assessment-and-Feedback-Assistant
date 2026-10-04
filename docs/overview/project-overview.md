# Project Overview

## Mục đích tài liệu

Tài liệu này cung cấp bức tranh toàn cảnh về project **Kriky** cho cả thành viên tech và non-tech.

Nó tập trung vào nghiệp vụ, actor, mục tiêu sản phẩm và phạm vi phát triển đầu tiên. Tài liệu này không mô tả kiến trúc hệ thống, AI agent internals, API hoặc database schema.

Diagram liên quan:

- [Use Case Diagram](../diagrams/use-case.drawio)
- [Domain Context Diagram](../diagrams/domain-context.drawio)
- [Vòng học khép kín](../diagrams/vong-hoc.drawio) — tám bước ở mục *Tóm tắt project* vẽ thành
  hình. Là **bản rút gọn** của [Activity Overview](../diagrams/activity-overview.drawio): cùng
  một vòng, bỏ nhánh rẽ và ô quyết định, giữ đúng tám bước và đánh số để tham chiếu được.

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
AI giải thích lỗi; học sinh hỏi lại đến khi hiểu
        ↓
AI tạo câu biến thể của chính câu sai
        ↓
Học sinh làm lại, tối đa ba vòng mỗi câu
        ↓
Mỗi câu chốt 1 / 0,5 / 0. Bài kết thúc
```

Trong vòng này, giáo viên giữ quyền kiểm soát ở ba điểm: duyệt đề trước khi phát hành, xử lý kết quả chấm có độ tin cậy thấp, và trả lời khi agent chưa đủ thông tin để làm.

Cổng thứ nhất có **một ngoại lệ đã biết**: câu biến thể ở pha 2 do trợ lí sinh ra giữa lúc học sinh đang làm bài, nên không đi qua duyệt. Xem ADR-05 và `docs/plans/backlog.md`.

## Vấn đề cần giải quyết

Giáo viên thường mất nhiều thời gian để:

- Soạn đề phù hợp với mục tiêu học tập.
- Tạo phương án sai có ý nghĩa, không chỉ là đáp án nhiễu ngẫu nhiên.
- Chấm bài và viết nhận xét cho từng học sinh.
- Xác định học sinh sai vì kiến thức, suy luận, tính toán hay hiểu nhầm khái niệm.
- Tạo câu biến thể của chính câu học sinh làm sai, để kiểm đúng lỗi vừa mắc.

Học sinh thường cần phản hồi nhanh và bài luyện tập đúng với điểm yếu của mình, nhưng giáo viên khó cá nhân hóa sâu cho từng học sinh nếu làm thủ công hoàn toàn.

## Mục tiêu sản phẩm

Hệ thống hướng đến bốn mục tiêu nghiệp vụ chính:

1. Hỗ trợ giáo viên tạo đề từ yêu cầu hoặc prompt.
2. Hỗ trợ chấm bài và sinh nhận xét có căn cứ.
3. Phân tích lỗi sai hoặc misconception của học sinh.
4. Bắt buộc học sinh chữa lại những câu đã sai, ngay trong cùng bài kiểm tra.

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
- Chọn đáp án và nộp bài (pha 1).
- Nghe giải thích lỗi và hỏi lại đến khi hiểu (pha 2).
- Làm câu biến thể của những câu đã sai, tối đa ba vòng mỗi câu (pha 2, bắt buộc).
- Báo cáo chỗ trợ lí giải thích chưa rõ.

## Hành vi hệ thống bên trong boundary

Hệ thống hỗ trợ các tác vụ thông minh trong workflow, nhưng không được xem là actor nghiệp vụ trong Use Case Diagram.

Hệ thống có thể:

- Sinh đề, đáp án, lời giải nhiều cách, và ánh xạ mỗi distractor sang một lỗi.
- Đánh giá câu trả lời ở pha 1, và lời học sinh nói trong hội thoại pha 2.
- **Tra** lỗi sai từ distractor đã chọn — mỗi distractor được soạn kèm một lỗi, nên đây là tra cứu chứ không phải suy đoán. Xem ADR-18.
- Sinh nhận xét.
- Tính confidence.
- Sinh câu biến thể của **chính câu học sinh làm sai**, giữ cấu trúc và lỗi cần kiểm. Xem ADR-17.

Hệ thống không tự thay thế vai trò kiểm soát của giáo viên ở các điểm cần review.

## Phạm vi giai đoạn đầu

Giai đoạn đầu tập trung vào bức tranh nghiệp vụ:

- Teacher tạo, review và phát hành đề. Duyệt bao gồm cả lời giải và ánh xạ nhiễu sang lỗi.
- Student làm bài và nộp bài. **Nộp bài kết thúc pha 1, không kết thúc bài kiểm tra.**
- Hệ thống chấm bài và tra lỗi sai từ phương án nhiễu đã chọn.
- Kết quả confidence thấp đi vào Teacher Review Queue.
- Pha 2: hệ thống giải thích lỗi và sinh câu biến thể; học sinh làm lại cho tới khi chốt điểm.

## Ngoài phạm vi giai đoạn đầu

Các nội dung sau chưa được thiết kế trong giai đoạn này:

- Kiến trúc hệ thống chi tiết.
- Cấu trúc service, module hoặc component.
- API contract.
- Database schema.
- AI prompt chain, tool calling hoặc model routing.
- Công thức confidence chi tiết, và `confidence` đo cái gì khi phần chấm đã xác định.
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
- `Mastery`: mức độ thành thạo của học sinh với một mục tiêu học tập hoặc kỹ năng. **Không còn là điều kiện dừng** của vòng chữa bài — điều kiện dừng là số vòng. Xem ADR-17.
- `Pha 1`: phần làm bài và nộp, có đồng hồ theo giờ mở, giờ đóng và thời gian làm bài.
- `Pha 2`: phần chữa bài, bắt buộc, có đồng hồ riêng. Bài kiểm tra kết thúc ở cuối pha 2. Xem ADR-14.
- `Lượt`: một lần học sinh làm cùng lúc mọi câu còn dở ở pha 2. Thời lượng bằng số phút mỗi câu nhân số câu trong lượt. Xem ADR-15.
- `Câu biến thể`: câu sinh từ **chính câu học sinh làm sai** — giữ cấu trúc và lỗi cần kiểm, chỉ đổi dữ kiện. Xem ADR-17.
- `Lời giải`: cách làm đi kèm mỗi câu hỏi, bắt buộc có nhiều hơn một cách. Là thứ trợ lí đi theo khi giải thích ở pha 2, và là một phần nội dung bị khoá khi giáo viên duyệt. Xem ADR-18.
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
