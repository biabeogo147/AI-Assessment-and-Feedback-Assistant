# ADR-22 — Đề có tác giả, và không tìm thấy nói giống hệt không được phép

- **Trạng thái:** đã chốt
- **Ngày:** 2026-09-30

## Bối cảnh

[ADR-13](adr-13-lop-va-tai-khoan-hoc-sinh.md) chốt *"lớp thuộc về giáo viên"*. Nhưng luật đó chưa từng
có chỗ để sống: bảng `classes` có đúng `id` và `name`, còn bảng `assessments` **không có trường tác
giả nào**. Không có cột thì không câu truy vấn nào áp được luật, và không test nào hỏi được là luật có
đúng hay không.

Chuyện này chưa gây hại vì bề mặt duy nhất đã dựng là bề mặt học sinh, nơi phạm vi được cắt bởi
`attempt_id`. Platform giáo viên phá vỡ điều đó: mọi thứ xuất phát từ khung chat, nên agent phải tự
chọn dữ liệu để đọc. Câu *"agent chỉ đọc được dữ liệu của giáo viên đang đăng nhập"* phải thành một
mệnh đề `WHERE`, không phải một dòng trong prompt.

Và có một câu hỏi thứ hai đi kèm, phải quyết cùng lúc: khi giáo viên hỏi về một lớp **của người khác**,
hệ thống trả lời thế nào.

## Quyết định

- Mỗi lớp và mỗi đề có **đúng một** tác giả. `classes.teacher_id` và `assessments.teacher_id` đều
  `NOT NULL`.
- Giáo viên chỉ đọc và chỉ sửa được lớp và đề của mình.
- **Lớp không tồn tại và lớp của giáo viên khác nhận cùng một câu trả lời.** Không có mã lỗi riêng,
  không có câu từ chối riêng, không có chênh lệch nào để so.
- Tên lớp **không** là định danh. `classes.name` không unique, nên một tên có thể trỏ tới nhiều lớp và
  việc phân định thuộc về [ADR-23](adr-23-hoi-lai-khi-khong-phan-dinh-duoc.md).

## Vì sao

Một tác giả chứ không phải nhiều, vì đồng sở hữu là một tính năng chưa ai yêu cầu và nó làm mọi câu
truy vấn phân quyền thành một phép `JOIN`. Thêm sau được; bỏ đi thì không.

Phần đáng bàn là câu trả lời giống hệt nhau. Nếu "không tìm thấy" và "không phải của bạn" khác nhau,
thì hai câu trả lời đó **là một kênh dò**: gõ tên lớp cho tới khi thông báo đổi giọng là biết lớp nào
tồn tại ở trường. Với một agent chat-first thì chuyện này rẻ hơn ở đâu hết, vì giáo viên không phải
đọc mã lỗi — họ chỉ cần đọc hai câu tiếng Việt khác nhau, và chính agent sẽ diễn đạt sự khác nhau ấy
ra thành lời một cách nhiệt tình.

Đây cũng là lý do luật này là luật **nghiệp vụ** chứ không phải chi tiết kỹ thuật: nó nói hệ thống
được phép để lộ điều gì về những người không phải người đang hỏi.

## Hệ quả

- `teacher_id` không nullable nên seed phải `flush()` giáo viên **trước** khi tạo lớp. Thứ tự trong
  `seed_if_empty` từ nay có ý nghĩa.
- Mọi tool đọc của platform giáo viên phải nhận giáo viên như một tham số, không phải đọc nó từ ngữ
  cảnh hội thoại. Danh tính đến từ header, không đến từ câu chữ model sinh ra.
- Câu từ chối **không được** nói "đề này không phải của bạn", vì chính câu đó tiết lộ rằng đề tồn tại.
- Luật này chưa áp cho học sinh: `students` thuộc về lớp, và lớp đã thuộc về giáo viên, nên không cần
  cột thứ hai.
- Chưa có màn hình nào của giáo viên, nên luật hiện được thi hành ở tầng dữ liệu và tầng truy vấn. Khi
  dựng bề mặt, câu từ chối phải giữ đúng tính chất không-phân-biệt ở cả ba nơi: endpoint, tool, và chữ
  hiện trên màn.

## Nơi luật này đang được thi hành

- `services/be/src/be/models.py` — `SchoolClass.teacher_id` và `Assessment.teacher_id`, cả hai là
  `ForeignKey("teachers.id")` không nullable, cộng `Teacher.classes` và `Teacher.assessments`.
- `services/be/src/be/seed.py` — `seed_if_empty` gán cả lớp và đề cho `GV-001`.
- `services/be/tests/test_assessment_lifecycle.py::test_every_class_and_assessment_has_an_owner` —
  mọi hàng seed đều có chủ.
- `services/be/tests/test_assessment_lifecycle.py::test_another_teachers_rows_are_not_in_this_teachers_query`
  — lọc theo chủ là đủ để không thấy gì của người khác.
- **Chưa thi hành:** luật *không tìm thấy nói giống hệt không được phép* chưa có chỗ nào chạy, vì chưa
  có endpoint hay tool nào của giáo viên để từ chối. Nó sẽ được thi hành cùng `resolve_class` ở
  ADR-23 và cùng executor của tool.
