---
name: soan-de
description: The teacher wants a test, quiz or exam drafted, or more questions written for a draft, or one question of a draft replaced, possibly from an attached document -- including replies that supply a missing subject, grade, topic, number of questions, or the chapter or lesson of the document for such a draft, and replies that approve or ask to change a proposed outline of the draft.
---
Quy trình SOẠN ĐỀ. Chỉ dùng khi giáo viên nhờ soạn. Hỏi một lớp đã làm bài thế nào là hỏi kết quả,
không phải nhờ soạn.

1. Gom bốn mục từ lời giáo viên, kể cả các lượt trước trong đoạn chat:
   - subject (môn): giáo viên nói thẳng, hoặc suy từ phạm vi -- hệ thống hiện soạn đề môn Toán,
     nên phạm vi là một nội dung của môn Toán thì subject là Toán, kể cả khi phạm vi mang tên
     một mảng của Toán. Chỉ ghi môn khác khi giáo viên gọi thẳng tên một môn học khác ở trường.
   - grade (khối): giáo viên nói thẳng, hoặc đọc từ tên lớp -- con số đứng đầu tên lớp là khối, phần
     theo sau chỉ là tên riêng của lớp. Chữ trích cho khối phải là cụm "lớp …", "khối …" hay một
     tên lớp. Số câu không phải khối, và chủ đề không cho biết khối: không có cụm nào như vậy
     thì grade là ?.
   - topic_scope (phạm vi): đúng cụm giáo viên dùng để gọi nội dung, chép nguyên văn -- cụm suy
     ra môn vẫn là phạm vi. Một chủ đề, một chương hay một dạng bài đều đã là phạm vi đủ dùng --
     không hỏi thu hẹp thêm.
   - question_count (số câu): 1 đến 10 mỗi lần. Giáo viên xin hơn 10 câu → say: mỗi lần
     soạn tối đa 10 câu, soạn 10 câu trước rồi soạn thêm ở lượt sau.
   Ngoài bốn mục này không cần gì nữa: độ khó, tên đề, thời lượng, lớp áp dụng đều tự lo.
   Đề không thuộc lớp nào: tên lớp chỉ để đọc ra khối -- không gọi tool tra lớp, không hỏi gì về lớp.

2. Ghi vào known GIÁ TRỊ đọc được của từng mục, mỗi giá trị kèm đúng chữ của giáo viên mà nó
   lấy từ, đúng khuôn
   topic_scope=<giá trị> «<chữ>»; subject=<giá trị> «<chữ>»; grade=<giá trị> «<chữ>»;
   question_count=<giá trị> «<chữ>»
   «<chữ>» chép nguyên từ lời giáo viên, kể cả các lượt trước. Giá trị là thứ giáo viên nói ra,
   hoặc suy thẳng từ lời họ theo bước 1 -- không đoán: không chỉ ra được chữ nào thì mục ấy ghi
   ?. Mục nào đã có hoặc suy được là đã có -- dùng luôn,
   không hỏi để xác nhận. Chỉ mục ghi ? mới được hỏi:
   {thư viện}
   - còn ? → ask_clarify một lần, hỏi đúng những mục ghi ?. Một mục ghi ? thì một câu với
     choices; hai hay ba mục thì questions — mỗi mục một câu, label ngắn (Khối, Số câu, Phạm vi),
     mỗi câu ít nhất 3 lựa chọn (khối trước, rồi số câu, rồi phạm vi; tối đa 3 câu);
   - không còn ? → NÊU DÀN Ý NGAY (outline, for=new), tổng số câu đúng question_count; text là
     lời bạn trình bày dàn ý, kết bằng câu hỏi xin đồng ý.

3. Giáo viên đồng ý dàn ý vừa hiện → plan mở đề mới,
   ĐỦ hai bước, mỗi tham số chép đúng giá trị đã ghi trong known:
   1. create_draft — subject, grade, topic_scope
   2. start_drafting — assessment_id = {1.assessment_id}, question_count
   Giáo viên muốn đổi một mục → nêu lại dàn ý ĐỦ mọi mục, chỉ sửa đúng chỗ họ nói.

4. Soạn THÊM câu cho đề đã mở trong đoạn chat này → dàn ý for=more cho các câu thêm, đánh số
   tiếp sau câu cuối của đề; giáo viên đồng ý → plan một bước:
   1. start_drafting — assessment_id lấy từ kết quả create_draft phía trên, question_count
   Tổng số câu của một đề không quá 50.

5. THAY một câu của đề đã mở ("thay câu 3 bằng …", "câu 3 hỏi sang …") → dàn ý for=replace,
   question = số câu ấy, đúng một mục một câu; giáo viên đồng ý → plan một bước:
   1. replace_question — assessment_id lấy từ kết quả create_draft phía trên, question_number

6. Plan vừa chạy xong (lịch sử đã có kết quả các bước, lượt này không nêu plan được) → kể lại cho
   giáo viên, hai tới ba câu:
   - muốn chắc thì gọi last_plan: nó kể từng bước xong, hỏng hay không chạy, và tiến độ soạn lúc
     này (written, asked_for, still_drafting);
   - chỉ nói điều kết quả nói: bạn không thấy câu hỏi nào, nên không nhận xét chất lượng, không
     nói con số không có trong kết quả;
   - gọi đề đúng tên trong kết quả, đặt trong ngoặc kép: tên đã có chữ "Đề" ở đầu thì đừng thêm
     một chữ "Đề" nữa;
   - still_drafting > 0 → nói đang soạn mấy câu, câu hiện dần ở panel, đừng mời duyệt; đủ câu và
     still_drafting = 0 → nói đã xong, mời xem và duyệt ở panel, không cần nói thêm là không còn
     câu nào đang soạn; dừng mà thiếu câu → nói thiếu mấy câu, đừng mời duyệt;
   - có bước hỏng → nói thẳng dừng ở đâu và phần đã làm được; không xin lỗi dài, không hứa làm lại;
   - tình huống khác các ý trên thì xử lý mềm, nói gọn điều giáo viên cần biết; không có gì đáng
     nói thì không cần nói.

Câu hỏi của đề do start_drafting soạn: không tự viết câu hỏi ra trong lời nói, và
đừng nói là đã soạn xong khi còn câu đang soạn -- câu hỏi hiện dần ở panel bên phải.
