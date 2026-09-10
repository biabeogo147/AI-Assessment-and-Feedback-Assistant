# Use Case Specification

## Mục đích tài liệu

Tài liệu này mô tả các use case nghiệp vụ chính của project **Kriky** trong giai đoạn đầu.

Nội dung tập trung vào actor nghiệp vụ, mục tiêu, điều kiện trước, luồng chính và ngoại lệ. Tài liệu này chưa mô tả API, database schema, service boundary hoặc AI agent internals.

Diagram liên quan:

- [Use Case Diagram](../diagrams/use-case.drawio)
- [Activity Overview Diagram](../diagrams/activity-overview.drawio)

## Actor nghiệp vụ

| Actor | Vai trò |
| --- | --- |
| Teacher | Tạo yêu cầu, review đề, phát hành đề, xử lý kết quả chấm cần review. |
| Student | Làm bài và nộp bài ở pha 1; chữa bài ở pha 2; báo cáo chỗ trợ lí giải thích chưa rõ. |

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
5. Teacher phát hành đề cho Student. Phát hành cần sáu tham số: lớp, thời gian làm bài, giờ mở, giờ đóng, số phút mỗi câu ở pha 2 và hạn kết thúc pha 2. Xem ADR-02 và ADR-15.

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
4. Student nộp bài.
5. Hệ thống ghi nhận bài nộp, chấm, và tra cứu lỗi sai từ phương án nhiễu đã chọn.

Pha 1 **không** thu lời giải thích bằng ô nhập. Lời giải thích được hỏi ở pha 2, đúng vào câu Student
làm sai và sau khi đồng hồ pha 1 đã dừng. Xem [ADR-11](../decisions/adr-11-bo-assessment-type.md).

### Quan hệ diagram

- `Làm bài thường xuyên` generalizes to `Làm và nộp bài (pha 1)`.
- `Làm bài cuối kỳ` generalizes to `Làm và nộp bài (pha 1)`.

Không dùng `<<include>>` từ `Làm và nộp bài (pha 1)` sang `Chấm bài và tra cứu lỗi sai` vì chấm bài là bước xử lý sau khi có bài nộp, không phải hành vi bắt buộc để Student hoàn thành mục tiêu nộp bài.

### Kết quả

Bài nộp được ghi nhận và được chấm. **Nộp bài không kết thúc bài kiểm tra** — nó kết thúc pha 1. Xem
[ADR-14](../decisions/adr-14-hai-pha-lam-bai.md) và UC-04.

## UC-04 — Student chữa bài sau khi nộp (pha 2)

### Mục tiêu

Student sửa được những lỗi vừa mắc, và bài kiểm tra chỉ kết thúc khi việc đó đã diễn ra.

### Actor chính

Student

### Điều kiện trước

- Student đã nộp bài ở pha 1 và hệ thống đã chấm.
- Chưa quá hạn kết thúc pha 2 do Teacher đặt lúc phát hành.

### Luồng chính

1. Student mở kết quả và thấy từng câu đúng hay sai.
2. Với mỗi câu sai, trợ lí giải thích lỗi theo lời giải đã soạn kèm câu hỏi. Student hỏi lại đến khi hiểu. **Phần này không tính giờ.**
3. Student bấm nút làm bài mới. Đồng hồ của lượt bắt đầu chạy, dài bằng số phút mỗi câu nhân số câu còn dở.
4. Student làm câu biến thể của từng câu còn dở.
5. Câu nào làm đúng thì câu gốc chốt 0,5 điểm; câu nào còn sai thì sang vòng tiếp, tối đa ba vòng.
6. Hết ba vòng mà vẫn sai thì câu đó chốt 0 điểm.
7. Bài kết thúc khi mọi câu đã chốt, hoặc khi hết hạn pha 2.

### Ngoại lệ

- Hết hạn pha 2 giữa một lượt thì lượt bị **dừng** và các câu còn dở nhận 0 điểm. Xem [ADR-15](../decisions/adr-15-thoi-gian-pha-hai.md).
- Student không mở pha 2 lần nào thì mọi câu sai nhận 0 điểm — bằng đúng kết quả của việc vào rồi sai cả ba vòng.

### Quan hệ diagram

- `Chữa bài sau khi nộp (pha 2)` `<<include>>` `Chấm bài và tra cứu lỗi sai`.
- `Chữa bài sau khi nộp (pha 2)` `<<include>>` `Làm câu biến thể, tối đa ba vòng`.
- `Yêu cầu giải thích cách làm` `<<extend>>` `Chữa bài sau khi nộp (pha 2)`.
- `Báo cáo giải thích chưa rõ` `<<extend>>` `Chữa bài sau khi nộp (pha 2)`.

Quan hệ với `Làm câu biến thể` là `<<include>>` chứ không phải `<<extend>>` vì pha 2 **bắt buộc**: nó
không phải một nhánh có thể không xảy ra. Xem [ADR-14](../decisions/adr-14-hai-pha-lam-bai.md).

Màu trên diagram nói **việc đó thuộc về ai**, không nói kiểu quan hệ. `Báo cáo giải thích chưa rõ` là
mục tiêu của Student nên tô xanh lá, kể cả khi nó nối bằng `<<extend>>`.

### Kết quả

Mỗi câu chốt ở một trong ba mức: 1 khi đúng ngay ở pha 1, 0,5 khi sai rồi chữa được, 0 khi không chữa
được. Điểm chỉ đi lên, nên điểm ngay sau khi nộp là sàn chứ không phải kết quả. Xem
[ADR-16](../decisions/adr-16-thang-diem-ba-muc.md).

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

## UC-06 — Hệ thống tạo câu biến thể

### Mục tiêu

Sinh một câu hỏi kiểm được đúng lỗi Student vừa mắc, trên dữ kiện mới.

### Actor chính

Không có actor trực tiếp. Đây là hành vi hệ thống, được `<<include>>` từ UC-04.

### Điều kiện trước

- Một câu ở pha 1 bị làm sai, và câu đó chưa dùng hết ba vòng.

### Luồng chính

1. Hệ thống lấy câu gốc mà Student làm sai.
2. Hệ thống sinh **biến thể của chính câu đó**: giữ nguyên cấu trúc và lỗi cần kiểm, thay dữ kiện.
3. Câu biến thể đi thẳng tới Student.
4. Kết quả câu biến thể quyết định câu gốc chốt 0,5 hay sang vòng tiếp.

### Quan hệ diagram

- `Chữa bài sau khi nộp (pha 2)` `<<include>>` `Làm câu biến thể, tối đa ba vòng`.
- `Làm câu biến thể, tối đa ba vòng` `<<include>>` `Tạo câu biến thể của chính câu sai`.

### Ghi chú

Điều kiện dừng là **số vòng**, không phải `Mastery`. Mastery chưa tính được vì hệ thống chưa lưu lịch
sử làm bài, và một điều kiện dừng không tính được là một vòng lặp không có lối ra. Xem
[ADR-17](../decisions/adr-17-ba-vong-moi-cau.md).

Câu biến thể **không đi qua cổng duyệt của Teacher**, vì nó sinh ra giữa lúc Student đang làm bài.
Đây là ngoại lệ đã biết của cổng thứ nhất trong [ADR-05](../decisions/adr-05-ba-cong-teacher-in-the-loop.md);
xem `docs/plans/backlog.md`.

### Kết quả

Student được kiểm lại đúng lỗi vừa mắc, trên dữ kiện chưa từng thấy.

## UC-07 — Student báo cáo chỗ trợ lí giải thích chưa rõ

### Mục tiêu

Đưa tới Teacher tín hiệu rằng một lời giải hoặc một cách giải thích khó hiểu.

### Actor chính

Student

### Điều kiện trước

- Student đang ở pha 2, hoặc bài của **chính Student đó** đã kết thúc.

### Luồng chính

1. Student đánh dấu một câu hoặc một đoạn hội thoại là *giải thích chưa rõ*.
2. Hệ thống ghi lại kèm câu hỏi và đoạn hội thoại tương ứng.
3. Teacher xem được các báo cáo.

### Quan hệ diagram

- `Báo cáo giải thích chưa rõ` `<<extend>>` `Chữa bài sau khi nộp (pha 2)`.

Đây **không** phải cổng teacher-in-the-loop thứ tư: nó không chặn Student, không chặn lượt, không chặn
điểm và không chặn việc bài kết thúc. Cổng theo ADR-05 là chỗ hệ thống dừng lại chờ người; ở đây không
có gì dừng lại. Xem [ADR-19](../decisions/adr-19-bao-cao-giai-thich-chua-ro.md).

Diagram **không** vẽ association từ Teacher tới use case này. Teacher đọc được báo cáo, nhưng chỗ để
đọc thì chưa tồn tại — nó không thuộc Teacher Review Queue, vốn dành cho việc có tính chặn.

### Kết quả

Teacher có căn cứ để sửa lời giải đã lưu, và ngân hàng câu hỏi tốt lên.

## Ghi chú điều kiện nghiệp vụ

- `Tạo đề nháp` diễn ra trước `Review và phát hành đề`, nhưng đây là thứ tự workflow nên được mô tả trong Activity Diagram và tài liệu workflow, không ghi như một quan hệ riêng trong Use Case Diagram.
- Student nộp bài là điều kiện để hệ thống chấm, nhưng không biểu diễn bằng `<<include>>` vì đây là thứ tự workflow.
- Kết quả confidence thấp hoặc có mâu thuẫn sẽ mở rộng sang use case Teacher xử lý bài cần review. Với luồng Student của mô hình hai pha, điều kiện ngưỡng hiện **tạm không áp**; xem ADR-07 và ADR-08.
- `Làm câu biến thể` là `<<include>>` của UC-04 chứ không phải `<<extend>>`, vì pha 2 bắt buộc. Bắt buộc ở đây nghĩa là bắt buộc **thử**, không phải bắt buộc **đạt**.

## Nguyên tắc nghiệp vụ chung

- Hệ thống không bao giờ tự phát hành đề. Chỉ Teacher phát hành. Xem ADR-02.
- Confidence thấp cần Teacher review. Xem ADR-07 cho phạm vi hiện tại của luật này.
- **Mỗi phương án nhiễu phải gắn một lỗi cụ thể**, soạn cùng câu hỏi. Nhờ đó chẩn đoán là tra cứu chứ không phải suy đoán. Xem ADR-18.
- **Mỗi câu hỏi phải kèm lời giải, và lời giải phải có nhiều hơn một cách làm.** Xem ADR-18.
- Bài khó hoặc nhiều bước vẫn cần Student giải thích cách làm, nhưng chỗ hỏi là **hội thoại ở pha 2**, không phải ô nhập ở pha 1. Xem ADR-11.
- Câu biến thể không sao chép nguyên văn câu cũ. Nó giữ **chính câu gốc** — cùng cấu trúc, cùng lỗi cần kiểm — và chỉ đổi dữ kiện. Chặt hơn *cùng mục tiêu học tập*. Xem ADR-17.
