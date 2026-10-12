---
name: soan-de
description: The teacher wants a test, quiz or exam drafted, or more questions written for a draft, possibly from an attached document -- including replies that supply a missing subject, grade, topic, number of questions, or the chapter or lesson of the document for such a draft.
---
Quy trình SOẠN ĐỀ. Chỉ dùng khi giáo viên nhờ soạn. Hỏi một lớp đã làm bài thế nào là hỏi kết quả,
không phải nhờ soạn.

1. Gom bốn mục từ lời giáo viên, kể cả các lượt trước trong đoạn chat:
   - subject (môn): giáo viên nói thẳng, hoặc suy từ phạm vi -- hệ thống hiện soạn đề môn Toán,
     nên phạm vi là một nội dung của môn Toán thì subject là Toán.
   - grade (khối): giáo viên nói thẳng, hoặc đọc từ tên lớp -- con số đứng đầu tên lớp là khối, phần
     theo sau chỉ là tên riêng của lớp.
   - topic_scope (phạm vi): đúng cụm giáo viên dùng để gọi nội dung, chép nguyên văn. Một chủ đề,
     một chương hay một dạng bài đều đã là phạm vi đủ dùng -- không hỏi thu hẹp thêm.
   - question_count (số câu): 1 đến 50.
   Ngoài bốn mục này không cần gì nữa: độ khó, tên đề, thời lượng, lớp áp dụng đều tự lo.
   Đề không thuộc lớp nào: tên lớp chỉ để đọc ra khối -- không gọi tool tra lớp, không hỏi gì về lớp.

2. Mục nào đã có hoặc suy được là đã có -- dùng luôn, không hỏi để xác nhận.
   Thiếu mục nào → ask_clarify một lần, hỏi đúng những mục còn thiếu.
   ĐỦ BỐN MỤC → NÊU PLAN NGAY.
   Giáo viên tự nhắc tới một cuốn sách hay tệp đã tải lên để soạn theo → call_tool list_documents.

3. Plan mở đề mới, hai bước:
   1. create_draft — subject, grade, topic_scope
   2. start_drafting — assessment_id = {1.assessment_id}, question_count

4. Soạn THÊM câu cho đề đã mở trong đoạn chat này → plan một bước:
   1. start_drafting — assessment_id lấy từ kết quả create_draft phía trên, question_count
   Tổng số câu của một đề không quá 50.

Câu hỏi của đề do start_drafting soạn: không tự viết câu hỏi ra trong lời nói, và
đừng nói là đã soạn xong -- câu hỏi hiện dần ở panel bên phải.
