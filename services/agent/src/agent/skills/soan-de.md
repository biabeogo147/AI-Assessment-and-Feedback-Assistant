---
name: soan-de
description: The teacher wants a test, quiz or exam drafted, or more questions written for a draft, possibly from an attached document -- including replies that supply a missing subject, grade, topic, number of questions, or the chapter or lesson of the document for such a draft.
---
Quy trình SOẠN ĐỀ. Chỉ dùng khi giáo viên nhờ soạn. Hỏi một lớp đã làm bài thế nào là hỏi kết quả,
không phải nhờ soạn.

1. Có tài liệu thì làm bước này TRƯỚC — dòng "Tài liệu giáo viên đính kèm", hoặc giáo viên nhắc tới
   sách mà không đính (call_tool list_documents, nhiều tài liệu thì hỏi lại tài liệu nào):
   1. call_tool list_chapters — document_id. Cần bài hay mục bên trong một chương thì
      call_tool get_chapter — document_id, node.
   2. Khớp phạm vi giáo viên nói với các node vừa đọc. Không khớp, hay khớp nhiều cách →
      ask_clarify, chỉ viết câu hỏi; hệ thống tự dựng lựa chọn là tên chương, bài. Giáo viên muốn
      cả cuốn thì chọn mọi chương.
   3. Có phạm vi: nodes là các số node đã chọn, topic_scope là tên các mục ấy.
   Không có tài liệu thì bỏ qua bước này.

2. Gom bốn mục từ lời giáo viên, kể cả các lượt trước trong đoạn chat:
   - subject (môn): nói thẳng, hoặc suy từ phạm vi hay tên tài liệu — "Hàm số", "tích phân" là Toán.
   - grade (khối): nói thẳng, hoặc đọc từ tên lớp hay tên tài liệu — "lớp 12A" là 12.
   - topic_scope (phạm vi): đúng lời giáo viên, hoặc tên các mục ở bước 1 — "chương Hàm số".
   - question_count (số câu): 1 đến 50.
   Ngoài bốn mục này không cần gì nữa: độ khó, tên đề, thời lượng, lớp áp dụng đều tự lo.
   Đề không thuộc lớp nào: tên lớp chỉ để đọc ra khối, không cần tra lớp hay hỏi gì về lớp.

3. Mục nào suy được là đã có — dùng luôn, không hỏi để xác nhận.
   Thiếu mục nào → ask_clarify một lần, hỏi đúng những mục còn thiếu.
   ĐỦ BỐN MỤC (và có tài liệu thì đã có nodes) → NÊU PLAN NGAY.

4. Plan mở đề mới, hai bước:
   1. create_draft — subject, grade, topic_scope (có tài liệu thì thêm document_id, nodes)
   2. start_drafting — assessment_id = {1.assessment_id}, question_count
   Có tài liệu thì lời nêu plan nói rõ số câu được rải đều theo độ dài các mục, mỗi câu một
   mục khác nhau.

5. Soạn THÊM câu cho đề đã mở trong đoạn chat này → plan một bước:
   1. start_drafting — assessment_id lấy từ kết quả create_draft phía trên, question_count
   Tổng số câu của một đề không quá 50.

Câu hỏi hiện dần ở panel bên phải, nên đừng nói là đã soạn xong.
