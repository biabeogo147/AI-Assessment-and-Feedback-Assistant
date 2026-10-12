---
name: soan-de
description: The teacher wants a test, quiz or exam drafted, or more questions written for a draft -- including replies that supply a missing subject, grade, topic or number of questions for such a draft.
---
Quy trình SOẠN ĐỀ. Chỉ dùng khi giáo viên nhờ soạn. Hỏi một lớp đã làm bài thế nào là hỏi kết quả,
không phải nhờ soạn.

1. Gom bốn mục từ lời giáo viên, kể cả các lượt trước trong đoạn chat:
   - subject (môn): nói thẳng, hoặc suy từ phạm vi — "Hàm số", "tích phân" là Toán.
   - grade (khối): nói thẳng, hoặc đọc từ tên lớp — "lớp 12A" là 12.
   - topic_scope (phạm vi): đúng lời giáo viên — "chương Hàm số".
   - question_count (số câu): 1 đến 50.
   Ngoài bốn mục này không cần gì nữa: độ khó, tên đề, thời lượng, lớp áp dụng đều tự lo.
   Đề không thuộc lớp nào: tên lớp chỉ để đọc ra khối, không cần tra lớp hay hỏi gì về lớp.

2. Mục nào suy được ở bước 1 là đã có — dùng luôn, không hỏi để xác nhận.
   Thiếu mục nào → ask_clarify một lần, hỏi đúng những mục còn thiếu.
   ĐỦ BỐN MỤC → NÊU PLAN NGAY.

3. Plan mở đề mới, hai bước:
   1. create_draft — subject, grade, topic_scope
   2. start_drafting — assessment_id = {1.assessment_id}, question_count

4. Soạn THÊM câu cho đề đã mở trong đoạn chat này → plan một bước:
   1. start_drafting — assessment_id lấy từ kết quả create_draft phía trên, question_count
   Tổng số câu của một đề không quá 50.

Câu hỏi hiện dần ở panel bên phải, nên đừng nói là đã soạn xong.
