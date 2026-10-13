---
name: lop-va-ket-qua
description: The teacher asks about one of their classes or about how a class did on a published test -- class size, which tests a class took, average marks, how many answers still wait for grading -- or answers a question about which class they meant.
---
Quy trình TRA LỚP VÀ KẾT QUẢ. Mọi id lấy từ kết quả tool, không bao giờ tự đoán.

1. Tìm lớp: call_tool list_class — name = tên lớp giáo viên nói (bỏ trống để lấy mọi lớp).
   - Đúng một lớp trong candidates → dùng class_id của nó.
   - Nhiều lớp → ask_clarify: text là câu hỏi, choices chép đúng name của các lớp trong
     candidates. Đừng liệt kê tên lớp trong text, đừng chọn hộ —
     hai lớp trùng tên chỉ giáo viên phân biệt được, bằng sĩ số hệ thống gắn vào nút.
   - more > 0 → gọi lại list_class với name hẹp hơn. Hẹp rồi mà vẫn more > 0 → say rằng danh sách
     chưa đầy đủ, còn bấy nhiêu lớp nữa.
   - Một tool trả found: false, hoặc list_class có name mà không ra lớp nào → gọi list_class không có
     name để lấy danh sách thật, rồi say là không tìm thấy, chỉ nhắc lớp có trong kết quả.
   - list_class không có name mà vẫn rỗng → say rằng giáo viên chưa có lớp nào.

2. Thông tin một lớp (tên, sĩ số): call_tool get_class — class_id.

3. Kết quả một bài kiểm tra:
   1. call_tool list_assessment — class_id → chọn assessment_id của bài giáo viên nói.
   2. call_tool class_assessment_summary — class_id, assessment_id.
   Nói điểm kèm thang: average_total_marks trên average_out_of câu, không phải thang 10.

4. Đủ dữ liệu → say, chỉ dùng con số có trong kết quả tool.
