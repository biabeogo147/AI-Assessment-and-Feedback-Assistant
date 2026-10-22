"""Lượt kèm học sinh: trợ lý nói gì tiếp theo, viết ra ngay lúc được đọc.

Hai luật từ các decision record định hình prompt này nhiều hơn bất kỳ lựa chọn câu
chữ nào:

- **Trợ lý giải thích, nó không bao giờ kết luận.** Không điểm, không "em đã hiểu
  rồi", không phán xét xem việc chữa lỗi có nên dừng. Những thứ đó là điểm, và điểm
  thuộc về BE (ADR-16, ADR-20). Một lượt mà đi chấm sẽ đặt cùng một quyết định ở hai
  chỗ.
- **Cái lỗi đã có tên sẵn.** Mỗi distractor mang một error label do người soạn viết
  (ADR-18). Trợ lý dùng đúng cái label ấy chứ không tự chẩn đoán lại từ đầu, nhờ vậy
  học sinh nghe đúng lời giải thích giáo viên đã viết, và hai học sinh mắc cùng một
  lỗi thì nghe cùng một điều.

Graph có hai node vì phần dựng prompt đáng được đọc riêng: những gì trợ lý được cho
biết về học sinh chính là phần một con người sẽ muốn sửa, và nó không nên bị chôn bên
trong lời gọi lo việc stream.
"""

from agent.graphs.explain.graph import speak

__all__ = ["speak"]
